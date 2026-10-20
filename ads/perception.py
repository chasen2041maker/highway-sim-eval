"""感知：从激光雷达的一帧点云里找出障碍物（A5）。

点云坐标：雷达坐标系，x 前、y 左、z 上，原点在雷达上（车顶，离地 1.8 米），单位米。
回家换 CARLA 的 sensor.lidar.ray_cast 时，先把点转到这个坐标系（y 变号），这里的函数不用改。
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import DBSCAN


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


def cluster_points(points: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    """把挨得近的点归成一堆（DBSCAN；从天上往下看，只用 x、y 两列）。

    points：形状 (M, 3)，去完地面后留下的点。
    eps：两个点相距不超过 eps 米，就算“挨着”。
    min_samples：一个点的 eps 圈里（算上它自己）至少有这么多个点，它才算“核心点”，能把圈里的点拉进同一堆。
    返回 labels：形状 (M,) 的整数，第 i 个点属于第几堆（0, 1, 2, …），−1 = 噪声（哪堆都不算）。
    """
    # 本人敲（3 行）：取出 x、y 两列 → 用参数 eps、min_samples 调 DBSCAN → return 每个点的堆号
    xy = points[:, :2]
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(xy)   # 返回每一行的堆号，−1 = 噪声
    return labels


def cluster_to_box(points: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """给每一堆点画一个框（从天上往下看，框的四条边和 x、y 轴平行）。

    points：形状 (M, 3)，去完地面后留下的点（和传给 cluster_points 的是同一批）。
    labels：形状 (M,)，cluster_points 的输出，第 i 个点属于第几堆，−1 = 噪声。
    返回 boxes：形状 (K, 4) 的小数数组，K = 堆数（噪声不算一堆）；第 k 行是第 k 堆的框：
        (中心 x, 中心 y, 沿 x 方向的长, 沿 y 方向的宽)，单位米。
    """
    boxes = []
    for k in range(labels.max() + 1):
        xy = points[labels == k, :2]
        lo = xy.min(axis=0)
        hi = xy.max(axis=0)
        center = (lo + hi) / 2
        size = hi- lo
        boxes.append([center[0], center[1], size[0], size[1]])
    return np.array(boxes)
