"""感知：从激光雷达的一帧点云里找出障碍物（A5）。

点云坐标：雷达坐标系，x 前、y 左、z 上，原点在雷达上（车顶，离地 1.8 米），单位米。
回家换 CARLA 的 sensor.lidar.ray_cast 时，先把点转到这个坐标系（y 变号），这里的函数不用改。
"""

from __future__ import annotations

import numpy as np


def remove_ground(points: np.ndarray, z_threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """按高度去掉地面点。

    points：形状 (N, 3)，每行一个点 (x, y, z)。
    z_threshold：高度门槛（米）。z 比它高的点留下（当成障碍物），其余当地面扔掉。
                 平地上地面点 z ≈ −1.8，所以门槛取 −1.8 往上一点，比如 −1.6（离地 20 厘米）。
    返回 (kept, keep)：
        kept：留下的点，形状 (M, 3)；
        keep：形状 (N,) 的 True / False，第 i 个点留下就是 True（评测时拿它去对真值 labels）。
    """
    z = points[:,2]     # 取出所有点的第 3 列（z），N 个数
    keep = z > z_threshold      # 每个点和 -1.0 比一比，得到 N 个 True / False
    return points[keep], keep
