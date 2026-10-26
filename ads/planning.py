"""规划：跟车（IDM）、停车保持、变道（A7：MOBIL 决定要不要变，Frenet 画变道曲线）。"""

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


# ---------- A7 变道 ----------

def mobil_should_change(me_now: float, me_after: float,
                        new_back_now: float, new_back_after: float,
                        old_back_now: float = 0.0, old_back_after: float = 0.0,
                        politeness: float = 0.0, max_brake_imposed: float = 2.0,
                        min_gain: float = 0.2) -> bool:
    """MOBIL：要不要变道（A7 第 1 步）。开车时“看后视镜”那一下。

    在系统里：每帧对左、右两条车道各问一次；回答 True 就交给第 2 步画变道曲线。
    所有参数都是用 IDM（idm_accel）算出来的加速度，单位 m/s²，负数 = 在刹车：
        me_now / me_after：我现在 / 变过去以后的加速度；
        new_back_now / new_back_after：目标车道后车现在 / 我插到它前面以后的加速度；
        old_back_now / old_back_after：本车道后车现在 / 我走了以后的加速度。
    politeness：礼貌系数，0 = 只管自己，1 = 别人的损失和自己的好处一样重要。
    两道检查（HighwayEnv 的默认值：politeness 0、max_brake_imposed 2、min_gain 0.2）：
        ① 安全：我插进去以后，目标车道后车要刹得比 max_brake_imposed 还狠 → 不变；
        ② 划算：我的好处 + politeness × (两辆后车的好处) > min_gain → 变，否则不变。
    """
    # ① 安全：别逼目标车道后车急刹
    if new_back_after < -max_brake_imposed:
        return False
    # ② 划算：我的好处 + 礼貌 × 两辆后车的好处
    gain = (me_after - me_now) + politeness * ((new_back_after - new_back_now) + (old_back_after - old_back_now))
    return gain > min_gain
