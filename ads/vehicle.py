"""车辆状态与运动学自行车模型。

坐标：x 向前、y 向左，单位米；heading 是车头朝向，弧度，0 = 沿 x 正方向，逆时针为正。
参考点：后轴中心。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

WHEELBASE_M = 2.8   # 轴距：前轴到后轴的距离
MAX_STEER_RAD = math.radians(35)   # 前轮最大转角

@dataclass
class VehicleState:
    x_m: float = 0.0
    y_m: float = 0.0
    heading_rad: float = 0.0  #车头朝那
    speed_mps: float = 0.0 #开多块

def step(state: VehicleState,accel_mps2:float, steer_rad:float, dt_s:float) -> VehicleState:  #dt_S 是时间书，推进的秒数
    """按加速度和前轮转角，把车往前推进 dt_s 秒，返回新状态（原状态不改）。"""
    steer_rad = max(-MAX_STEER_RAD,min(MAX_STEER_RAD, steer_rad)) #转角限幅

    x_m = state.x_m + state.speed_mps * math.cos(state.heading_rad) * dt_s
    y_m = state.y_m + state.speed_mps * math.sin(state.heading_rad) * dt_s
    heading_rad = state.heading_rad + state.speed_mps/ WHEELBASE_M * math.tan(steer_rad) * dt_s
    speed_mps = max(0.0, state.speed_mps + accel_mps2  * dt_s)

    return VehicleState(x_m, y_m, heading_rad, speed_mps)