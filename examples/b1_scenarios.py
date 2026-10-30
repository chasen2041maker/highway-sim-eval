"""B1 第 1 步：一个小题库。同一个考生（IDM），把题库里每道“前车急刹”都考一遍，出一张成绩表。

题目是数据（scenarios/lead_brake.py 的 LeadBrake），跑题的代码不动：出新题只要往 BANK 里加一行。

运行（在项目根目录）：
    python -m examples.b1_scenarios           跑全部题，打印成绩表
    python -m examples.b1_scenarios --show 3  开窗口看第 3 题
"""

from __future__ import annotations

import sys

from examples.b1_highway_brake import DT_S, MAX_BRAKE_MPS2, SIM_TIME_S, idm_driver, score, to_action
from scenarios.lead_brake import CAR_LENGTH_M, LeadBrake, build

# ---------- 题库 ----------
BANK = [
    LeadBrake(gap_m=25, ego_speed_mps=10, lead_speed_mps=10, lead_decel_mps2=5),   # 1 两车一样快
    LeadBrake(gap_m=12, ego_speed_mps=10, lead_speed_mps=10, lead_decel_mps2=5),   # 2 离得近，但一样快
    LeadBrake(gap_m=12, ego_speed_mps=20, lead_speed_mps=10, lead_decel_mps2=5),   # 3 离得近，我快 10
    LeadBrake(gap_m=12, ego_speed_mps=18, lead_speed_mps=10, lead_decel_mps2=5),   # 4 我快 8
    LeadBrake(gap_m=16, ego_speed_mps=20, lead_speed_mps=10, lead_decel_mps2=5),   # 5 我快 10，远 4 米
]


def run(sc: LeadBrake, show: bool = False) -> dict:
    """考一道题：每 0.1 秒 看 → 想 → 动 → 世界走一步；前车第 0 秒起按题目刹车。"""
    env, lead = build(sc, DT_S, SIM_TIME_S, MAX_BRAKE_MPS2, show)
    world = env.unwrapped
    ego = world.vehicle
    obs = world.observation_type.observe()
    log = {"t": [], "gap": [], "ego_v": [], "lead_v": [], "accel": []}
    crashed = False
    try:
        for k in range(round(SIM_TIME_S / DT_S)):
            t_s = k * DT_S
            action = to_action(idm_driver(obs), ego.speed)
            lead.action = {"steering": 0.0, "acceleration": max(-sc.lead_decel_mps2, -lead.speed / DT_S)}
            log["t"].append(t_s)
            log["gap"].append(lead.position[0] - ego.position[0] - CAR_LENGTH_M)
            log["ego_v"].append(ego.speed)
            log["lead_v"].append(lead.speed)
            log["accel"].append(action[0] * MAX_BRAKE_MPS2)
            obs, reward, terminated, truncated, info = env.step(action)
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
    print("题  车距  我   前车  前车刹  |  撞了  最小车距  最猛刹车（第几秒）")
    for n, sc in enumerate(BANK, start=1):
        s = run(sc)
        print(f"{n:<3} {sc.gap_m:>4.0f} {sc.ego_speed_mps:>4.0f} {sc.lead_speed_mps:>5.0f} {-sc.lead_decel_mps2:>6.0f}  |  "
              f"{'是' if s['crashed'] else '否':<4} {s['min_gap_m']:>7.2f}   {s['hardest_brake_mps2']:>6.2f}（{s['brake_at_s']:.1f}）")


if __name__ == "__main__":
    main()
