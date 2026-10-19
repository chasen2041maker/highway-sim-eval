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

from dataclasses import dataclass


@dataclass
class StopHold:
    """停车保持（ACC 的 stop & go）：跟着前车停下后就踩住刹车不动，等前车起步再走。

    进入（三个条件都满足）：我的车速 < enter_speed_mps，前车车速 < enter_lead_mps，车距 < enter_gap_m。
    退出（满足一个就行）：前车车速 > exit_lead_mps（前车起步了），或车距 > exit_gap_m（前车走远了）。
    进入和退出用不同的门槛（迟滞），防止在门槛附近一会儿进、一会儿出。
    """
    enter_speed_mps: float = 1.0
    enter_lead_mps: float = 0.5
    enter_gap_m: float = 8.0
    exit_lead_mps: float = 1.0
    exit_gap_m: float = 11.0
    holding: bool = False      # 现在是不是在停车保持（自己记着）

    def update(self, speed_mps: float, lead_speed_mps: float, gap_m: float) -> bool:
        """每帧调用一次：更新状态，返回这一帧要不要停车保持。"""
        if self.holding:
            if lead_speed_mps > self.exit_lead_mps or gap_m > self.exit_gap_m:
                self.holding = False
        elif speed_mps < self.enter_speed_mps and lead_speed_mps < self.enter_lead_mps and gap_m < self.enter_gap_m:
            self.holding = True
        return self.holding
