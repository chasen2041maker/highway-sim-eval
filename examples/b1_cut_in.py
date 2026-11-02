"""B1 第 2 步：邻车加塞。同一个考生（IDM），考几道“旁边车道的车切到我前面”，出一张成绩表。

运行（在项目根目录）：
    python -m examples.b1_cut_in           跑全部题，打印成绩表
    python -m examples.b1_cut_in --show 2  开窗口看第 2 题
"""

from __future__ import annotations

import sys

from examples.b1_highway_brake import DT_S, MAX_BRAKE_MPS2, SIM_TIME_S, idm_driver, score, to_action
from examples.b1_scenarios import judge
from scenarios.cut_in import CAR_LENGTH_M, LANE_WIDTH_M, CutIn, build, cutter_y

# ---------- 题库 ----------
BANK = [
    CutIn(gap_m=10, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=0),   # 1 陪跑：它不切进来
    CutIn(gap_m=10, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=2),   # 2 2 秒切进来
    CutIn(gap_m=5, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=2),    # 3 更近
]


def run(sc: CutIn, show: bool = False) -> dict:
    """考一道题：每 0.1 秒 看 → 想 → 动 → 世界走一步；它第 0 秒起按题目往我的车道挪。"""
    env, cutter = build(sc, DT_S, SIM_TIME_S, MAX_BRAKE_MPS2, show)
    world = env.unwrapped
    ego = world.vehicle
    y_side, y_mine = cutter.position[1], ego.position[1]
    obs = world.observation_type.observe()
    log = {"t": [], "gap": [], "ego_v": [], "lead_v": [], "accel": []}
    crashed = False
    try:
        for k in range(round(SIM_TIME_S / DT_S)):
            t_s = k * DT_S
            action = to_action(idm_driver(obs), ego.speed)                 # 考生
            cutter.position[1] = cutter_y(sc, t_s, y_side, y_mine)         # 剧本：它往我的车道挪
            cutter.action = {"steering": 0.0, "acceleration": 0.0}         # 剧本：它车速不变
            log["t"].append(t_s)                                           # 考官：只有它进了我的车道才算车距
            in_my_lane = abs(cutter.position[1] - y_mine) < LANE_WIDTH_M / 2
            log["gap"].append(cutter.position[0] - ego.position[0] - CAR_LENGTH_M if in_my_lane else float("inf"))
            log["ego_v"].append(ego.speed)
            log["lead_v"].append(cutter.speed)
            log["accel"].append(action[0] * MAX_BRAKE_MPS2)
            obs, reward, terminated, truncated, info = env.step(action)    # 考场
            if info["crashed"]:
                crashed = True
                break
    finally:
        env.close()
    return score(log, crashed)


def main():
    if "--show" in sys.argv:
        n = int(sys.argv[sys.argv.index("--show") + 1])
        print(BANK[n - 1], run(BANK[n - 1], show=True))
        return
    print("题  车距  我   它   几秒切  |  撞了  最小车距  最猛刹车（第几秒）  判定")
    for n, sc in enumerate(BANK, start=1):
        s = run(sc)
        print(f"{n:<3} {sc.gap_m:>4.0f} {sc.ego_speed_mps:>4.0f} {sc.cut_speed_mps:>4.0f} {sc.cut_time_s:>6.0f}  |  "
              f"{'是' if s['crashed'] else '否':<4} {s['min_gap_m']:>7.2f}   {s['hardest_brake_mps2']:>6.2f}（{s['brake_at_s']:.1f}）  {judge(s)}")


if __name__ == "__main__":
    main()
