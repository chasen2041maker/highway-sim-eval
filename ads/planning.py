"""规划：跟车（IDM）。以后在这里加 Frenet 变道。"""

from __future__ import annotations
import math


def idm_accel(speed_mps: float, lead_speed_mps: float, gap_m: float, target_speed_mps: float, max_accel_mps2: float = 3.0, min_gap_m: float = 5.0,
              time_gap_s: float = 1.5, delta: float = 4.0, comfort_brake_mps2: float = 5.0) -> float:
    """IDM 跟车：加速度 = 本来想加的 − 怕撞要减的。gap_m：我的车头到前车车尾的距离。"""
    want = max_accel_mps2 * (1 - (speed_mps / target_speed_mps) ** delta)     # 本来想加的
    closing_mps = speed_mps - lead_speed_mps    # 我比前车快多少（追得多快）
    chase_m = speed_mps * closing_mps / (2 * math.sqrt(max_accel_mps2 * comfort_brake_mps2))   # 追得快，多留的那一截
    desired_gap_m = min_gap_m + max(0.0, speed_mps * time_gap_s + chase_m)     # 想保持的距离（最少 5 米）

    
    fear = max_accel_mps2 * (desired_gap_m / gap_m) ** 2
    return want - fear