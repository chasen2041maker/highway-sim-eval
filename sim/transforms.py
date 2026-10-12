"""CARLA 坐标 ↔ 我们的坐标（ads/vehicle.py 用的那套）。

CARLA：左手系，x 前、y 右、z 上，角度用度，往右转角度变大。
我们：右手系，x 前、y 左、z 上，角度用弧度，往左转角度变大。
两套只差 y 轴方向：x 不变，y 变号，角度变号并换单位。
"""

from __future__ import annotations
import math

def carla_to_ours(x_m:float, y_m:float, yaw_deg: float) -> tuple[float, float, float]:
    """CARLA 的 (x, y, yaw 度) → 我们的 (x, y, heading 弧度)。"""
    return x_m, -y_m, -math.radians(yaw_deg)

def ours_to_carla(x_m: float, y_m:float, heading_rad: float) -> tuple[float, float, float]:
    """我们的 (x, y, heading 弧度) → CARLA 的 (x, y, yaw 度)。"""
    return x_m, -y_m, -math.degrees(heading_rad)