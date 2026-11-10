"""B1 第 2 步：邻车加塞。同一个考生（IDM），考几道“旁边车道的车切到我前面”，出一张成绩表。

题目分三类：陪跑（它不切进来，考会不会白刹车）、切入（考会不会漏刹）、靠线（它往我这边靠、不进来，考预测会不会误判）。
考生分四档：预测 0 秒（不预测，只认已经在我车道上的车）、0.5、1.0、1.5 秒。

运行（在项目根目录）：
    python -m examples.b_eval.b1_cut_in                跑全部题 × 四档预测，打印成绩表
    python -m examples.b_eval.b1_cut_in --show 3 1.0   开窗口看第 3 题，预测 1.0 秒
"""

from __future__ import annotations

import math
import sys
from collections import deque
import numpy as np

from examples.b_eval.b1_highway_brake import CAR_WIDTH_M, DT_S, MAX_BRAKE_MPS2, SIM_TIME_S, follow, idm_driver, pick_lead, score, to_action
from examples.b_eval.b1_scenarios import judge
from scenarios.cut_in import CAR_LENGTH_M, LANE_WIDTH_M, CutIn, build, cutter_lateral

PREDICT_S = [0.0, 0.5, 1.0, 1.5]    # 考生预测几秒（0 = 不预测）

# ---------- 题库 ----------
BANK = [
    CutIn(gap_m=10, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=0),                    # 1 陪跑：它不切进来
    CutIn(gap_m=10, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=2),                    # 2 2 秒切进来
    CutIn(gap_m=5, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=2),                     # 3 更近
    CutIn(gap_m=10, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=2, cut_depth_m=1.8),   # 4 压线：中心只挪 1.8 米，车身压进我车道 0.8 米（该刹）
    CutIn(gap_m=10, ego_speed_mps=15, cut_speed_mps=10, cut_time_s=2, cut_depth_m=0.8),   # 5 靠线：中心挪 0.8 米，车身离线还差 0.2 米（不该刹）
]


def gap_ahead(ego_xy, other_xy) -> float:
    """考官的尺子：量“我车头到它车尾”的前后距离。只量两种都满足的车，否则 inf（= 不算）：
      ① 它在我前面（它的中心在我的中心前面）；
      ② 它的车身压进了我的车道（横向差 < 半个车道 + 半个车宽 = 3 米，和考生认前车的规矩一样）。
    B4 修之前：按中心点判车道（车身压线 0.8 米的车量不到），也不管前后（被我超过、切到我后面的车算出 −140 米）。"""
    dx = other_xy[0] - ego_xy[0]
    dy = abs(other_xy[1] - ego_xy[1])
    if dx <= 0 or dy >= LANE_WIDTH_M / 2 + CAR_WIDTH_M / 2:
        return math.inf
    return dx - CAR_LENGTH_M


def run(sc: CutIn, predict_s: float = 0.0, show: bool = False, delay_s: float = 0.0, noise_y_m: float = 0.0, seed: int = 0, confirm_frames: int = 1, accel: bool = False,
        frames: list | None = None) -> dict:
    """考一道题：每 0.1 秒 看 → 想 → 动 → 世界走一步；它第 0 秒起按题目往我这边挪（带真的横向速度）。
    frames 给了一个空列表的话，每一帧往里录一条：考生看到了什么、真实世界怎样、考生做了什么（B3 录像 / 回灌用）。"""
    env, cutter = build(sc, DT_S, SIM_TIME_S, MAX_BRAKE_MPS2, show)
    world = env.unwrapped
    ego = world.vehicle
    y_side = cutter.position[1]
    rng = np.random.default_rng(seed)

    def sensor(o):
        """故障注入：给考生看到的别的车的横向位置 y 加噪声（标准差 noise_y_m 米），模拟传感器不准。"""
        o = np.array(o, dtype=float)
        o[1:, 2] += rng.normal(0.0, noise_y_m, size=len(o) - 1) * (o[1:, 0] == 1)
        return o

    obs = sensor(world.observation_type.observe())
    late = deque([obs] * (round(delay_s / DT_S) + 1), maxlen=round(delay_s / DT_S) + 1)   # 排队：队头是几帧以前的路况
    log = {"t": [], "gap": [], "ego_v": [], "lead_v": [], "accel": []}
    crashed = False
    streak = 0                                                        # 连着几帧挑出了前车
    prev = None                                                       # 上一帧（算横向加速度用）
    try:
        for k in range(round(SIM_TIME_S / DT_S)):
            t_s = k * DT_S
            lead = pick_lead(late[0], predict_s, prev if accel else None)    # ① 挑前车（看队头那帧）
            prev = late[0]
            streak = streak + 1 if lead is not None else 0                     # 挑出来了就 +1，没挑出来就清零
            if streak < confirm_frames:                                        # 防噪声：没连续够几帧，就当没看见
                lead = None
            action = to_action(follow(late[0], lead), ego.speed)               # ② 算刹车
            d, vd = cutter_lateral(sc, t_s)                                  # 剧本：它往我这边挪 d 米，横向速度 vd
            cutter.position[1] = y_side + d
            cutter.heading = math.atan2(vd, sc.cut_speed_mps)                # 车头朝挪的方向，obs 里才有 vy
            cutter.speed = math.hypot(sc.cut_speed_mps, vd)                  # 往前的速度不变
            cutter.action = {"steering": 0.0, "acceleration": 0.0}
            log["t"].append(t_s)
            log["gap"].append(gap_ahead(ego.position, cutter.position))     # 考官的尺子（B4 修过）
            log["ego_v"].append(ego.speed)
            log["lead_v"].append(sc.cut_speed_mps)
            log["accel"].append(action[0] * MAX_BRAKE_MPS2)
            if frames is not None:                                          # 录像：这一帧
                frames.append({
                    "k": k, "t_s": round(t_s, 1),
                    "seen": late[0].tolist(),                               # 考生看到的（已经过噪声和延迟）
                    "ego_x": float(ego.position[0]), "ego_y": float(ego.position[1]), "ego_v": float(ego.speed),
                    "cutter_x": float(cutter.position[0]), "cutter_y": float(cutter.position[1]),   # 真实世界
                    "lead_seen": lead is not None,                          # 考生的决定：认没认出前车
                    "accel_cmd": float(action[0] * MAX_BRAKE_MPS2),         # 考生的决定：踩多大（负 = 刹车）
                })
            obs, reward, terminated, truncated, info = env.step(action)     # 考场
            late.append(sensor(obs))                                         # 新路况先过“传感器”，再排到队尾
            if info["crashed"]:
                crashed = True
                break
    finally:
        env.close()
    return score(log, crashed)


def main():
    if "--show" in sys.argv:
        i = sys.argv.index("--show")
        n, p = int(sys.argv[i + 1]), float(sys.argv[i + 2]) if len(sys.argv) > i + 2 else 0.0
        print(BANK[n - 1], f"预测 {p} 秒", run(BANK[n - 1], p, show=True))
        return
    print("题  车距  我   它  几秒切  挪多远  |  " + "  ".join(f"预测 {p:.1f} 秒            " for p in PREDICT_S))
    for n, sc in enumerate(BANK, start=1):
        cells = []
        for p in PREDICT_S:
            s = run(sc, p)
            gap = "  -  " if math.isinf(s["min_gap_m"]) else f"{s['min_gap_m']:5.2f}"
            ttc = "  撞 " if s["crashed"] else ("  -  " if math.isinf(s["min_ttc_s"]) else f"{s['min_ttc_s']:5.2f}")
            cells.append(f"{judge(s):<3} {gap} {ttc} {s['hardest_brake_mps2']:6.2f}")
        print(f"{n:<3} {sc.gap_m:>4.0f} {sc.ego_speed_mps:>4.0f} {sc.cut_speed_mps:>4.0f} {sc.cut_time_s:>6.0f} {sc.cut_depth_m:>7.1f}  |  "
              + "  ".join(cells))
    print("每格：判定  最小车距（- = 它一直没在我前面压进我的车道）  最小 TTC 秒（- = 没在接近它；撞 = 撞了）  最猛刹车")


if __name__ == "__main__":
    main()
