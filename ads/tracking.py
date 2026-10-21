"""跟踪：把每一帧的检测结果串起来，估计位置和速度（A6）。

A4 里 IDM 用的前车车速是向 CARLA 要的真值；真车上没人告诉你前车开多快，
激光雷达每 0.1 秒只给一次前车的位置（还带误差）。这个模块从这些位置里估计速度。
"""

from __future__ import annotations

import numpy as np


def diff_speed(dist_m: np.ndarray, dt_s: float) -> np.ndarray:
    """用相邻两帧的距离差算速度（最直接的办法，A6 第 1 步）。

    dist_m：形状 (N,)，一帧一个数：每一帧测到的前车车尾离我多少米。
    dt_s：相邻两帧隔多少秒（激光雷达一秒 10 帧 → 0.1）。
    返回：形状 (N-1,)，第 k 个 = (第 k+1 帧的距离 - 第 k 帧的距离) / dt_s，单位 m/s。
          负数 = 越来越近（前车比我慢）。
    """
    speeds = []
    for k in range(len(dist_m) - 1):
        v = (dist_m[k + 1] - dist_m[k]) / dt_s
        speeds.append(v)
    return np.array(speeds)
