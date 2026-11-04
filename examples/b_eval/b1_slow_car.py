"""B1 第 3 种题：慢车挡路。同一个考生（IDM，只会踩油门刹车、不会变道），考几道“前面有辆慢车一直慢慢开”。

成绩表除了判定，还多两列：15 秒里平均开多快、比没有慢车时少走了多少米（通行效率）。

运行（在项目根目录）：
    python -m examples.b_eval.b1_slow_car
    python -m examples.b_eval.b1_slow_car --show 3   开窗口看第 3 题
"""

from __future__ import annotations

import sys

from examples.b_eval.b1_highway_brake import DT_S, MAX_BRAKE_MPS2, SIM_TIME_S, TARGET_SPEED_MPS, idm_driver, score, to_action
from examples.b_eval.b1_scenarios import judge
from scenarios.slow_car import CAR_LENGTH_M, SlowCar, build, is_valid

BANK = [
    SlowCar(gap_m=80, ego_speed_mps=15, slow_speed_mps=8),     # 1 慢车很远
    SlowCar(gap_m=20, ego_speed_mps=15, slow_speed_mps=8),     # 2 慢车近
    SlowCar(gap_m=20, ego_speed_mps=15, slow_speed_mps=3),     # 3 慢车很慢
    SlowCar(gap_m=20, ego_speed_mps=15, slow_speed_mps=15),    # 4 “慢车”其实跟我一样快
]


def run(sc: SlowCar, show: bool = False) -> dict:
    """考一道题；除了阅卷，再算平均车速和比畅通时少走了多少米。"""
    env, slow = build(sc, DT_S, SIM_TIME_S, MAX_BRAKE_MPS2, show)
    world = env.unwrapped
    ego = world.vehicle
    x0 = ego.position[0]
    obs = world.observation_type.observe()
    log = {"t": [], "gap": [], "ego_v": [], "lead_v": [], "accel": []}
    crashed = False
    try:
        for k in range(round(SIM_TIME_S / DT_S)):
            action = to_action(idm_driver(obs), ego.speed)
            slow.action = {"steering": 0.0, "acceleration": 0.0}
            log["t"].append(k * DT_S)
            log["gap"].append(slow.position[0] - ego.position[0] - CAR_LENGTH_M)
            log["ego_v"].append(ego.speed)
            log["lead_v"].append(slow.speed)
            log["accel"].append(action[0] * MAX_BRAKE_MPS2)
            obs, reward, terminated, truncated, info = env.step(action)
            if info["crashed"]:
                crashed = True
                break
    finally:
        env.close()
    s = score(log, crashed)
    s["distance_m"] = ego.position[0] - x0
    s["avg_speed_mps"] = s["distance_m"] / SIM_TIME_S
    s["lost_m"] = TARGET_SPEED_MPS * SIM_TIME_S - s["distance_m"]
    return s


def main():
    if "--show" in sys.argv:
        n = int(sys.argv[sys.argv.index("--show") + 1])
        print(BANK[n - 1], run(BANK[n - 1], show=True))
        return
    print("题  车距  我   慢车  |  判定  最小车距  最猛刹车  |  平均车速  少走了")
    for n, sc in enumerate(BANK, start=1):
        if not is_valid(sc):
            print(f"{n:<3} 无效题：慢车不比我慢")
            continue
        s = run(sc)
        print(f"{n:<3} {sc.gap_m:>4.0f} {sc.ego_speed_mps:>4.0f} {sc.slow_speed_mps:>5.0f}  |  {judge(s):<3} {s['min_gap_m']:>7.2f}  {s['hardest_brake_mps2']:>7.2f}  |  "
              f"{s['avg_speed_mps']:>6.1f}    {s['lost_m']:>5.0f} 米")


if __name__ == "__main__":
    main()
