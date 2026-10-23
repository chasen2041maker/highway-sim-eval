"""跟踪：把每一帧的检测结果串起来，估计位置和速度（A6）。

A4 里 IDM 用的前车车速是向 CARLA 要的真值；真车上没人告诉你前车开多快，
激光雷达每 0.1 秒只给一次前车的位置（还带误差）。这个模块从这些位置里估计速度。
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment  # 匈牙利算法（A6 第 3 步配对用）


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


class KalmanCV:
    """匀速卡尔曼滤波（一维，沿车道方向）：跟踪前车的距离 d 和速度 v（A6 第 2 步）。

    每 0.1 秒一圈：predict(dt) 猜一步 → 雷达这一帧量到了，就 update(z) 合一下；量不到就只猜。

    self.x：形状 (2,)，[d, v]：前车离我多少米、前车相对我的速度（m/s，负数 = 在靠近）。
    self.P：形状 (2, 2)，有多没把握。P[0, 0] = 距离的方差（动画里 ± 那个数的平方），P[1, 1] = 速度的方差。
    q：前车加减速有多猛（越大，每猜一步越没把握）。
    r：雷达量距离的方差：误差 0.2 米 → r = 0.2² = 0.04。
    """

    def __init__(self, d0: float, v0: float = 0.0, p0_d: float = 1.0, p0_v: float = 25.0,
                 q: float = 1.0, r: float = 0.04):
        self.x = np.array([d0, v0], dtype=float)
        self.P = np.diag([p0_d, p0_v]).astype(float)
        self.q = q
        self.r = r

    def predict(self, dt: float) -> None:
        """猜：按现在的速度把前车往前推 dt 秒，速度先当它不变；猜完没把握变大。"""
        F = np.array([[1.0, dt],
                      [0.0, 1.0]])                       # F @ x = [d + v·dt, v]
        Q = self.q * np.array([[dt ** 4 / 4, dt ** 3 / 2],
                               [dt ** 3 / 2, dt ** 2]])  # 这 dt 秒里前车可能加减速，多出来的没把握（给定）
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q


    def update(self, z: float) -> None:
        """合：用这一帧雷达量到的距离 z，修正 self.x 和 self.P。"""
        y = z - self.x[0]
        S = self.P[0, 0] + self.r
        K = self.P[:, 0] / S
        self.x = self.x + K * y
        self.P = self.P - np.outer(K, self.P[0, :])


def match_tracks(pred_xy: np.ndarray, det_xy: np.ndarray, gate_m: float = 2.0) -> list[tuple[int, int]]:
    """配对（A6 第 3 步）：这一帧雷达的框，各归哪条轨迹。

    在系统里：跟踪器每帧先让每条轨迹 predict（猜），再用这个函数把框分给轨迹；
    配上的框交给那条轨迹的卡尔曼 update，配不上的交给编号管理（新车 / 只猜）。

    pred_xy：形状 (T, 2)，T 行 2 列：每条轨迹猜的位置 (x, y)，第 i 行 = 第 i 条轨迹。
    det_xy：形状 (D, 2)，D 行 2 列：雷达这一帧的框中心 (x, y)，顺序是乱的。
    gate_m：门槛（米），距离超过它的不算配上。
    返回：列表 [(i, j), ...]，第 i 条轨迹配第 j 个框（i、j 都是从 0 数的下标）。
          规则：一对一；在所有一对一的配法里挑总距离最小的（匈牙利算法：scipy 的 linear_sum_assignment）；
          挑出来以后，距离超过 gate_m 的那对扔掉。没有轨迹或没有框时返回 []。
    """
    if len(pred_xy) == 0 or len(det_xy) == 0:
        return []
    T = len(pred_xy)
    D = len(det_xy)
    dist = np.zeros((T, D))
    for i in range(T):
        for j in range(D):
            dx = pred_xy[i][0] - det_xy[j][0]
            dy = pred_xy[i][1] - det_xy[j][1]
            dist[i, j] = np.hypot(dx,dy)
    rows, cols = linear_sum_assignment(dist)
    pairs = []
    for i, j in zip(rows, cols):
        if dist[i, j] <= gate_m:
            pairs.append((int(i), int(j)))
    return pairs