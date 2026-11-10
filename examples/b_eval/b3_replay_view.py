"""B3 回放页的数据：把录像 + 两种回灌（往前看 0.5、1.0 秒）整理成一个 JSON，嵌进 docs/b3_replay.html。

每道题：自车 / 加塞车每帧的位置和车速、老考生每帧认没认出前车、三位考生每帧踩多大、各自第一次踩刹车是第几秒。
运行（在项目根目录，先 conda activate py310；先跑过 b3_record）：
    python -m examples.b_eval.b3_replay_view
"""

from __future__ import annotations

import json

from examples.b_eval.b1_cut_in import BANK
from examples.b_eval.b3_mcap import REC_DIR, load_frames
from examples.b_eval.b3_replay import first_brake, replay

OUT = REC_DIR / "b3_replay_view.json"


def build() -> list[dict]:
    out = []
    for q, fr in sorted(load_frames(REC_DIR / "b1_bank_p0.parquet").items()):
        t = [round(f["t_s"], 1) for f in fr]
        rec = [f["accel_cmd"] for f in fr]
        r05, r10 = replay(fr, 0.5), replay(fr, 1.0)
        sc = BANK[q - 1]
        out.append({
            "q": q, "crashed": bool(fr[0]["crashed"]),
            "sc": {"gap_m": sc.gap_m, "ego_speed_mps": sc.ego_speed_mps, "cut_speed_mps": sc.cut_speed_mps,
                   "cut_time_s": sc.cut_time_s, "cut_depth_m": sc.cut_depth_m},
            "t": t,
            "ex": [round(f["ego_x"], 2) for f in fr], "ey": [round(f["ego_y"], 3) for f in fr],
            "ev": [round(f["ego_v"], 2) for f in fr],
            "cx": [round(f["cutter_x"], 2) for f in fr], "cy": [round(f["cutter_y"], 3) for f in fr],
            "lead": [bool(f["lead_seen"]) for f in fr],
            "a0": [round(a, 2) for a in rec], "a05": [round(a, 2) for a in r05], "a10": [round(a, 2) for a in r10],
            "fb": {"0": first_brake(t, rec), "0.5": first_brake(t, r05), "1.0": first_brake(t, r10)},
        })
    return out


def main():
    data = build()
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    for d in data:
        print(f"第 {d['q']} 题：{len(d['t'])} 帧，第一次踩刹车 {d['fb']}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
