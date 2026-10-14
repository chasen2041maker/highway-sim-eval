"""控制器：PID（速度控制）。以后在这里加 Pure Pursuit（方向盘控制）。"""

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class PID:
    kp:float       # P：现在差多少
    ki: float = 0.0          # I：一直以来累计差了多少
    kd: float = 0.0          # D：差距变化得多快
    u_max: float | None = None    # 输出上限；None = 不限（A1 里的用法不受影响）
    integral: float = 0.0      # 累计误差（自己记着，不用传）
    pre_error: float | None = None         # 上一帧的误差；None 表示还没有上一帧

    def update(self, error:float, dt_s:float) -> float:
        """输入这一帧的误差（目标 − 当前），返回控制量（这里是加速度）。"""
        #self.integral += error * dt_s
        if self.pre_error is None:
            derivative = 0.0
        else:
            derivative = (error - self.pre_error) / dt_s
        self.pre_error = error

        #防积分饱和：先试算"这帧照常攒"的话，输出是多少
        new_integral = self.integral + error * dt_s
        u_try = self.kp * error + self.ki * new_integral + self.kd *derivative
        windup = self.u_max is not None and u_try > self.u_max and error > 0
        if not windup:
            self.integral = new_integral

        return self.kp * error + self.ki * self.integral + self.kd * derivative

def to_pedals(u: float) -> tuple[float, float]:
    """PID 的输出 → CARLA 的 (油门, 刹车)，都在 0 到 1 之间。
u >= 0 踩油门，u < 0 踩刹车；超过 1 的部分踩不下去，截到 1。"""
    if u >= 0:
        return min(u, 1.0),0.0
    return 0.0, min(-u, 1.0)