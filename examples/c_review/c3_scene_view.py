"""C3 第一课的动画页：nuScenes 一段路况（默认 scene-0061），每个关键帧一张前视照片 + 画上去的 3D 框 + 俯视图，
点一个框，沿着表一路查下去（照片 → 关键帧 → 框 → 这是谁 → 这是什么），再换算成“我的坐标”。

照片缩到 800×450 塞进网页；结果在 outputs/c3/<场景>.html（outputs 不进 git；nuScenes 是 CC BY-NC-SA，只自己看）。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.c_review.c3_scene_view                 scene-0061
    python -m examples.c_review.c3_scene_view scene-1077      换一段（比如夜里那段）
"""

from __future__ import annotations

import base64
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from examples.c_review.nuscenes_tables import ROOT, box_corners, load, project, to_ego, yaw_of

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "c3"
TEMPLATE = Path(__file__).with_name("c3_scene_view_template.html")
SCALE = 0.5                                    # 1600×900 → 800×450
ZH = {
    "vehicle.car": "轿车", "vehicle.truck": "卡车", "vehicle.bus.rigid": "公交车", "vehicle.bus.bendy": "铰接公交",
    "vehicle.construction": "工程车", "vehicle.bicycle": "自行车", "vehicle.motorcycle": "摩托车", "vehicle.trailer": "挂车",
    "vehicle.emergency.police": "警车", "vehicle.emergency.ambulance": "救护车",
    "human.pedestrian.adult": "成年行人", "human.pedestrian.child": "儿童", "human.pedestrian.construction_worker": "施工工人",
    "human.pedestrian.police_officer": "警察", "human.pedestrian.stroller": "婴儿车", "human.pedestrian.wheelchair": "轮椅",
    "human.pedestrian.personal_mobility": "个人代步工具", "movable_object.barrier": "隔离栏", "movable_object.trafficcone": "锥桶",
    "movable_object.pushable_pullable": "手推物", "movable_object.debris": "杂物", "static_object.bicycle_rack": "自行车架",
    "animal": "动物",
}


def group(cat: str) -> str:
    if cat in ("vehicle.bicycle", "vehicle.motorcycle"):
        return "cycle"
    return "vehicle" if cat.startswith("vehicle") else "human" if cat.startswith("human") else "other"


def scene_data(T: dict, scene_name: str) -> dict:
    scene = next(s for s in T["scene"].values() if s["name"] == scene_name)
    log = T["log"][scene["log_token"]]
    by_sample: dict[str, list] = {}
    for a in T["sample_annotation"].values():
        by_sample.setdefault(a["sample_token"], []).append(a)
    front = {d["sample_token"]: d for d in T["sample_data"].values() if d["is_key_frame"] and "/CAM_FRONT/" in d["filename"]}

    frames, tok = [], scene["first_sample_token"]
    t0, prev_xy, prev_t = None, None, None
    while tok:
        s = T["sample"][tok]
        sd = front[tok]
        ego = T["ego_pose"][sd["ego_pose_token"]]
        cal = T["calibrated_sensor"][sd["calibrated_sensor_token"]]
        t = s["timestamp"] / 1e6
        t0 = t if t0 is None else t0
        xy = np.array(ego["translation"][:2])
        speed = 0.0 if prev_xy is None else float(np.linalg.norm(xy - prev_xy) / (t - prev_t))
        prev_xy, prev_t = xy, t

        img = Image.open(ROOT / sd["filename"]).convert("RGB").resize((800, 450))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=68)

        anns = []
        for a in sorted(by_sample.get(tok, []), key=lambda a: a["token"]):
            inst = T["instance"][a["instance_token"]]
            cat = T["category"][inst["category_token"]]["name"]
            corners = to_ego(box_corners(a), ego)
            centre = to_ego(np.array([a["translation"]]), ego)[0]
            uv, depth = project(corners, cal)
            in_img = bool((depth > 0.5).all() and ((uv[:, 0] > 0) & (uv[:, 0] < 1600) & (uv[:, 1] > 0) & (uv[:, 1] < 900)).any())
            anns.append({
                "id": inst["token"][:8], "cat": cat, "zh": ZH.get(cat, cat), "g": group(cat),
                "uv": [[round(float(u) * SCALE, 1), round(float(v) * SCALE, 1)] for u, v in uv] if in_img else None,
                "ex": round(float(centre[0]), 2), "ey": round(float(centre[1]), 2),
                "eyaw": round(math.degrees(yaw_of(a["rotation"]) - yaw_of(ego["rotation"])), 1),
                "w": a["size"][0], "l": a["size"][1],
                "tok": a["token"][:8], "inst": inst["token"][:8], "n_inst": inst["nbr_annotations"],
                "cat_tok": inst["category_token"][:8],
                "xy": [round(a["translation"][0], 1), round(a["translation"][1], 1)],
                "attr": [T["attribute"][x]["name"] for x in a["attribute_tokens"]],
                "vis": T["visibility"][a["visibility_token"]]["level"],
            })
        frames.append({
            "t": round(t - t0, 2), "img": base64.b64encode(buf.getvalue()).decode(), "v": round(speed, 2),
            "sample": tok[:8], "sd": sd["token"][:8], "file": sd["filename"].split("/")[-1],
            "ego": [round(ego["translation"][0], 1), round(ego["translation"][1], 1)],
            "eyaw": round(math.degrees(yaw_of(ego["rotation"])), 1), "anns": anns,
        })
        tok = s["next"]
    return {"scene": scene_name, "desc": scene["description"], "location": log["location"],
            "date": log["date_captured"], "frames": frames}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "scene-0061"
    data = scene_data(load(), name)
    body = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.html"
    out.write_text('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
                   '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                   '<style>body{margin:0}</style>\n</head>\n<body>\n' + body + '\n</body>\n</html>\n', encoding="utf-8")
    n_boxes = sum(len(f["anns"]) for f in data["frames"])
    print(f"{name}：{len(data['frames'])} 个关键帧、{n_boxes} 个框 → {out}（{out.stat().st_size / 1e6:.1f} MB）")


if __name__ == "__main__":
    main()
