"""C3 第 2 步：从 nuScenes 真实数据里挑“值得再看一眼”的时刻（难例挖掘，原计划的 C0）。

为什么：真实数据绝大部分是平常驾驶，全交给视觉大模型看又贵又没必要。先用便宜的规则挑出“可能危险”的时刻，
后面的大模型和人只看这些。挑出来的是候选名单，不是“确定危险”。

规则（B4 的尺子搬到真实数据上）：
  ① TTC < 3 秒：我的路上、我前面、和我同方向的车和人，前方几米 ÷ 接近速度（只在靠近时算，和 B4 一样 > 0.1 m/s）；
     门槛比 B5 的“险”（1.5 秒）放宽：挖掘阶段漏挑比多挑贵。
     “同方向”看它往哪走（不是车头朝哪）：基本停着（< 1 m/s）照算，我开过去它不会让开；在动的话，
     行驶方向和我的车头差 < 45° 才算。2d 发现：scene-1100 我停在路口，对面的车拐过来从我前面经过，
     被当成 TTC 0.5–2 秒挑了 12 条——TTC 的意思是“我在追前车”，迎面、横穿的车不是前车。
  ② 急刹：我的减速度比 −3 m/s² 还猛。前两帧不算（第 1 帧车速算不出来，第 2 帧会用到它）。

“我的路”：我接下来 5 秒实际开过的轨迹（后面几个关键帧的自车位置连成线），末端再顺着车头直着接 30 米
（快停下或数据到头时路太短，前面的车会量不到）。车身压进路（中心离路 < 半个车道 1.75 + 半个身宽）才算。
这用到了未来，只有录好的数据能这么做（离线挖掘可以“偷看后面”）；车上实时只能用地图车道线和规划出来的路。
对照：直尺版（从车头往正前方伸的直带子）。2a / 2b 在 scene-0061 上发现它在拐弯时会误挑（安全岛上的工人、隔离墩后的挖掘机）。
运行时打印三列：直尺版 → 真实路版 → 再加“同方向”，表里存的是最后一版。

距离是“我的原点到它的中心”，没减车长，所以 TTC 比真实的偏大一点。

运行（项目根目录，conda activate py310）：
    python -m examples.c_review.c3_pick
输出（outputs 不进 git；nuScenes 是 CC BY-NC-SA，只自己看）：
    outputs/c3/picked.parquet      难例表：一行 = 一个时刻 × 一条规则
    outputs/c3/picked/*.jpg         每条一张前视照片，TTC 那条把挑中的框画成橙色
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from examples.c_review.nuscenes_tables import ROOT, box_corners, load, project, to_ego, yaw_of

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "c3"
LANE_HALF_M = 1.75        # 我的车道半宽（当车道宽 3.5 米）
PATH_S = 5.0              # “我的路”往后看几秒
EXTEND_M = 30.0           # 路的末端顺着车头再直着接多远
MIN_CLOSING_MPS = 0.1     # 接近速度大于这个才算 TTC（和 B4 的 score 一样）
SAME_DIR_DEG = 45.0       # 它的行驶方向和我的车头差多少度以内算“同方向”
MOVING_MPS = 1.0          # 它比这快才看方向；更慢 = 基本停着，照算
TTC_MAX_S = 3.0           # 规则①：TTC 门槛
BRAKE_MPS2 = -3.0         # 规则②：急刹门槛


# ---------- 读一段：每个关键帧的自车位置、车速、所有框（地图坐标 + 我的坐标） ----------

def scene_frames(T: dict, scene: dict) -> list[dict]:
    """一段路况 → 关键帧列表。车速用这一帧和上一帧的位置差算，第 1 帧算不出来，记 None。"""
    by_sample: dict[str, list] = {}
    for a in T["sample_annotation"].values():
        by_sample.setdefault(a["sample_token"], []).append(a)
    front = {d["sample_token"]: d for d in T["sample_data"].values()
             if d["is_key_frame"] and "/CAM_FRONT/" in d["filename"]}

    frames, tok, t0 = [], scene["first_sample_token"], None
    while tok:
        s = T["sample"][tok]
        sd = front[tok]
        ego = T["ego_pose"][sd["ego_pose_token"]]
        t = s["timestamp"] / 1e6
        t0 = t if t0 is None else t0
        xy = (ego["translation"][0], ego["translation"][1])
        v = None
        if frames:
            last = frames[-1]
            v = math.dist(xy, last["ego_xy"]) / (t - t0 - last["t"])
        objs = []
        for a in by_sample.get(tok, []):
            inst = T["instance"][a["instance_token"]]
            centre = to_ego(np.array([a["translation"]]), ego)[0]
            objs.append({
                "inst": inst["token"], "ann": a["token"],
                "cat": T["category"][inst["category_token"]]["name"],
                "xy": (a["translation"][0], a["translation"][1]),
                "ex": float(centre[0]), "ey": float(centre[1]),
                "w": a["size"][0], "l": a["size"][1],
            })
        frames.append({"t": t - t0, "v": v, "sample": tok, "cam": sd, "ego_pose": ego,
                       "ego_xy": xy, "ego_yaw": yaw_of(ego["rotation"]), "objs": objs})
        tok = s["next"]
    return frames


# ---------- “我的路”和两种“在不在我车道” ----------

def seg_dist(p, a, b) -> float:
    """点 p 到线段 ab 的距离（A 块的点到线段：先投影，t 夹在 0–1，再量到垂足）。"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0
    if L2 > 0:
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
        t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def path_dist(path, p) -> float:
    """点 p 到一条折线（很多段线段）的最近距离。"""
    best = math.inf
    for i in range(len(path) - 1):
        best = min(best, seg_dist(p, path[i], path[i + 1]))
    return best


def my_path(frames, k, path_s=PATH_S, extend_m=EXTEND_M) -> list:
    """第 k 帧起，我接下来 path_s 秒实际开过的位置（地图坐标），末端顺着车头再直着接 extend_m 米。"""
    path = []
    for m in range(k, len(frames)):
        if frames[m]["t"] - frames[k]["t"] > path_s + 1e-6:
            break
        path.append(frames[m]["ego_xy"])
        last = m
    yaw = frames[last]["ego_yaw"]
    x, y = path[-1]
    path.append((x + extend_m * math.cos(yaw), y + extend_m * math.sin(yaw)))
    return path


def is_road_user(o) -> bool:
    """只看车和人；隔离栏、锥桶这些不算。"""
    return o["cat"].startswith(("vehicle.", "human."))


def in_straight_lane(o) -> bool:
    """直尺版：在我前面，中心离“车头正前方那条线”< 半个车道 + 半个身宽。"""
    return is_road_user(o) and o["ex"] > 0 and abs(o["ey"]) < LANE_HALF_M + o["w"] / 2


def on_my_path(o, path) -> bool:
    """真实路版：在我前面，中心离“我接下来开过的路”< 半个车道 + 半个身宽。"""
    return is_road_user(o) and o["ex"] > 0 and path_dist(path, o["xy"]) < LANE_HALF_M + o["w"] / 2


# ---------- 两把尺子：TTC 和加速度 ----------

def find(frame, inst):
    """在一帧里按编号找这个东西，找不到返回 None。"""
    for o in frame["objs"]:
        if o["inst"] == inst:
            return o
    return None


def neighbours(frames, k, inst):
    """第 k 帧前后各找一帧有 inst 的：上一帧有就用上一帧、下一帧有就用下一帧，都没有返回 None。
    用到了下一帧 = 偷看未来，只能离线用。"""
    a, b = k, k
    if k > 0 and find(frames[k - 1], inst):
        a = k - 1
    if k + 1 < len(frames) and find(frames[k + 1], inst):
        b = k + 1
    if a == b:
        return None
    return a, b


def closing_speed(frames, k, inst):
    """第 k 帧，我在以多快的速度接近 inst（m/s，正数 = 在靠近）。用它在前后两帧的“前方几米”之差。"""
    ab = neighbours(frames, k, inst)
    if ab is None:
        return None
    a, b = ab
    before = find(frames[a], inst)["ex"]
    after = find(frames[b], inst)["ex"]
    return (before - after) / (frames[b]["t"] - frames[a]["t"])


def its_velocity(frames, k, inst):
    """第 k 帧，它自己在地图上怎么动（vx, vy，m/s）：前后两帧的地图位置之差。算不出来返回 None。"""
    ab = neighbours(frames, k, inst)
    if ab is None:
        return None
    a, b = ab
    xa, ya = find(frames[a], inst)["xy"]
    xb, yb = find(frames[b], inst)["xy"]
    dt = frames[b]["t"] - frames[a]["t"]
    return (xb - xa) / dt, (yb - ya) / dt


def same_direction(frames, k, o) -> bool:
    """它往哪走：基本停着（< 1 m/s）照算；在动的话，行驶方向和我的车头差 < 45° 才算（迎面、横穿的不当前车）。"""
    v = its_velocity(frames, k, o["inst"])
    if v is None or math.hypot(v[0], v[1]) < MOVING_MPS:
        return True
    diff = math.atan2(v[1], v[0]) - frames[k]["ego_yaw"]
    diff = (diff + math.pi) % (2 * math.pi) - math.pi        # 换到 −180° 到 180°
    return abs(diff) < math.radians(SAME_DIR_DEG)


def min_ttc(frames, k, keep):
    """第 k 帧，keep(o) 为真的那些车和人里最小的 TTC。返回 (TTC, 那个东西)；一个都没在靠近就 (None, None)。"""
    best, who = None, None
    for o in frames[k]["objs"]:
        if not keep(o):
            continue
        v = closing_speed(frames, k, o["inst"])
        if v is None or v <= MIN_CLOSING_MPS:
            continue
        ttc = o["ex"] / v
        if best is None or ttc < best:
            best, who = ttc, o
    return best, who


def accel(frames, k):
    """第 k 帧我的加速度（m/s²）。前两帧返回 None：第 1 帧车速算不出来，第 2 帧会用到它。"""
    if k < 2:
        return None
    return (frames[k]["v"] - frames[k - 1]["v"]) / (frames[k]["t"] - frames[k - 1]["t"])


# ---------- 挑片段 ----------

def pick_scene(frames, use_path=True, same_dir=True) -> list[dict]:
    """一帧一帧走，符合规则的记一行：第几帧、第几秒、哪条规则、数值、是谁。
    use_path=False 用直尺当车道；same_dir=False 不管它往哪走（对照用）。"""
    picked = []
    for k in range(len(frames)):
        path = my_path(frames, k) if use_path else None

        def keep(o, k=k, path=path):
            if path is None:
                ok = in_straight_lane(o)
            else:
                ok = on_my_path(o, path)
            if ok and same_dir:
                ok = same_direction(frames, k, o)
            return ok

        ttc, who = min_ttc(frames, k, keep)
        if ttc is not None and ttc < TTC_MAX_S:
            picked.append({"k": k, "t_s": frames[k]["t"], "rule": "TTC", "value": ttc, "who": who})
        a = accel(frames, k)
        if a is not None and a < BRAKE_MPS2:
            picked.append({"k": k, "t_s": frames[k]["t"], "rule": "急刹", "value": a, "who": None})
    return picked


# ---------- 输出：难例表 + 照片 ----------

def draw_box(T, frame, who):
    """前视照片（原尺寸）；who 不是 None 就把它的 3D 框画成橙色。返回 PIL 图。"""
    from PIL import Image, ImageDraw
    img = Image.open(ROOT / frame["cam"]["filename"]).convert("RGB")
    if who is not None:
        ann = T["sample_annotation"][who["ann"]]
        cal = T["calibrated_sensor"][frame["cam"]["calibrated_sensor_token"]]
        uv, depth = project(to_ego(box_corners(ann), frame["ego_pose"]), cal)
        if (depth > 0.5).all():
            d = ImageDraw.Draw(img)
            for i, j in [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]:
                d.line([tuple(uv[i]), tuple(uv[j])], fill=(255, 120, 0), width=5)
    return img


def save_photo(T, frame, who, out: Path) -> None:
    """前视照片缩到 800×450；TTC 那条把挑中的框画成橙色。"""
    draw_box(T, frame, who).resize((800, 450)).save(out, quality=85)


def write_parquet(rows: list[dict], out: Path) -> None:
    import duckdb
    con = duckdb.connect()
    con.execute("""CREATE TABLE picked (scene VARCHAR, description VARCHAR, location VARCHAR, frame INTEGER, t_s DOUBLE,
                   rule VARCHAR, value DOUBLE, who VARCHAR, ex DOUBLE, ey DOUBLE, ego_speed DOUBLE,
                   sample_token VARCHAR, photo VARCHAR)""")
    cols = ["scene", "description", "location", "frame", "t_s", "rule", "value", "who", "ex", "ey", "ego_speed",
            "sample_token", "photo"]
    con.executemany(f"INSERT INTO picked VALUES ({', '.join('?' * len(cols))})", [[r[c] for c in cols] for r in rows])
    con.execute(f"COPY picked TO '{out.as_posix()}' (FORMAT parquet)")


def main():
    T = load()
    photo_dir = OUT_DIR / "picked"
    photo_dir.mkdir(parents=True, exist_ok=True)
    for old in photo_dir.glob("*.jpg"):
        old.unlink()                                   # 清掉上一次挑的照片，免得和这次混在一起
    rows = []
    print(f"{'段':<11} {'帧':>3} {'直尺版':>6} {'真实路版':>8} {'+同方向':>7}  描述")
    for scene in sorted(T["scene"].values(), key=lambda s: s["name"]):
        frames = scene_frames(T, scene)
        straight = pick_scene(frames, use_path=False, same_dir=False)
        path_only = pick_scene(frames, use_path=True, same_dir=False)
        real = pick_scene(frames, use_path=True, same_dir=True)
        print(f"{scene['name']:<11} {len(frames):>3} {len(straight):>6} {len(path_only):>8} {len(real):>7}  {scene['description'][:60]}")
        location = T["log"][scene["log_token"]]["location"]
        for p in real:
            f = frames[p["k"]]
            who = p["who"]
            name = f"{scene['name']}_{p['k'] + 1:02d}_{'ttc' if p['rule'] == 'TTC' else 'brake'}.jpg"
            save_photo(T, f, who, photo_dir / name)
            rows.append({
                "scene": scene["name"], "description": scene["description"], "location": location,
                "frame": p["k"] + 1, "t_s": round(p["t_s"], 2), "rule": p["rule"], "value": round(p["value"], 2),
                "who": who["cat"] if who else None,
                "ex": round(who["ex"], 2) if who else None, "ey": round(who["ey"], 2) if who else None,
                "ego_speed": round(f["v"], 2) if f["v"] is not None else None,
                "sample_token": f["sample"], "photo": f"picked/{name}",
            })
    out = OUT_DIR / "picked.parquet"
    write_parquet(rows, out)
    print(f"\n挑出 {len(rows)} 条 → {out}；照片在 {photo_dir}")
    for r in rows:
        who = f"{r['who']}，前方 {r['ex']} 米、左 {r['ey']} 米" if r["who"] else ""
        print(f"  {r['scene']} 第 {r['frame']:>2} 帧 {r['t_s']:>5.2f} 秒  {r['rule']:<3} {r['value']:>6.2f}  车速 {r['ego_speed']}  {who}")


if __name__ == "__main__":
    main()
