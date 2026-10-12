"""控制器：PID（速度控制）。以后在这里加 Pure Pursuit（方向盘控制）。"""

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class PID:
    kp:float       # P：现在差多少
    ki: float = 0.0          # I：一直以来累计差了多少
    kd: float = 0.0          # D：差距变化得多快
    integral: float = 0.0      # 累计误差（自己记着，不用传）
    pre_error: float | None = None         # 上一帧的误差；None 表示还没有上一帧

    def update(self, error:float, dt_s:float) -> float:
        """输入这一帧的误差（目标 − 当前），返回控制量（这里是加速度）。"""
        self.integral += error * dt_s
        if self.pre_error is None:
            derivative = 0.0
        else:
            derivative = (error - self.pre_error) / dt_s
        self.pre_error = error
        return self.kp * error + self.ki * self.integral + self.kd * derivative