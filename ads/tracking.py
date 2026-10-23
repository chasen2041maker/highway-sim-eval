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

class Track:
    """一张纸条：一辆车的编号 + 它的位置和速度 + 连着几帧没配上（A6 第 3 步）。

    在系统里：MultiTracker 每帧先让每张纸条 predict（猜），配上框的纸条 update（用框改准），
    配不上的 misses 加 1，太久没配上就扔掉。

    位置和速度用第 2 步的 KalmanCV：x 方向（往前）一个、y 方向（往左）一个，各管各的
    （KalmanCV 是一维的：它的 x[0] 是位置、x[1] 是速度）。

    track_id：编号（1、2、3……，发出去就不再变）。
    xy：第一次看到它的那个框的中心 (x, y)，米。
    建好以后有 4 个属性：
        self.id：编号；
        self.kx、self.ky：x、y 方向各一个 KalmanCV，初始位置 = 框的 x、y（初始速度用默认的 0）；
        self.misses：连着几帧没配上框，一开始是 0。
    """

    def __init__(self, track_id: int, xy) -> None:
        self.id = track_id
        self.kx = KalmanCV(xy[0])
        self.ky = KalmanCV(xy[1])
        self.misses = 0

    def predict(self, dt: float) -> None:
        """猜：x、y 两个卡尔曼各往前推 dt 秒。"""
        self.kx.predict(dt)
        self.ky.predict(dt)

    def update(self, xy) -> None:
        """改准：x、y 两个卡尔曼各用框中心的 x、y 合一下；配上了，misses 清零。"""
        self.kx.update(xy[0])
        self.ky.update(xy[1])
        self.misses = 0
        

    @property
    def xy(self) -> np.ndarray:
        """现在估计的位置 [x, y]：两个卡尔曼各自的位置 x[0]。用的时候写 t.xy，不加括号。"""
        return np.array([self.kx.x[0], self.ky.x[0]])


class MultiTracker:
    """多车跟踪器：每帧 猜 → 配 → 管编号（A6 第 3 步）。

    gate_m：配对门槛（米），原样交给 match_tracks。
    max_misses：一张纸条连着没配上超过这么多帧就扔掉（10 帧 = 1 秒；动画 ② 比了 10 和 3）。
    self.tracks：现在手里的纸条（Track 列表，按建的先后排）。
    self.next_id：下一个要发的编号，从 1 开始，只增不减（扔掉的编号不回收）。
    """

    def __init__(self, gate_m: float = 2.0, max_misses: int = 10) -> None:
        self.gate_m = gate_m
        self.max_misses = max_misses
        self.tracks: list[Track] = []
        self.next_id = 1

    def step(self, det_xy: np.ndarray, dt: float = 0.1) -> list[Track]:
        """处理一帧雷达框，返回处理完以后手里的纸条（就是 self.tracks）。

        det_xy：形状 (D, 2)，这一帧的框中心，顺序乱（D 可以是 0）。
        按顺序做 5 件事：
          ① 猜：每张纸条 predict(dt)；
          ② 配：把每张纸条猜的位置排成形状 (T, 2) 的表，和 det_xy 一起交给 match_tracks(..., self.gate_m)；
          ③ 改准：配上的纸条，用配给它的那个框 update；
          ④ 没配上的纸条：misses 加 1；misses 超过 max_misses 的扔掉；
          ⑤ 没人认领的框：按框的下标从小到大，每个发一个新编号（self.next_id，发完加 1），建新纸条。
        """
        for t in self.tracks:
            t.predict(dt)

        pre = np.array([t.xy for t in self.tracks])
        pairs = match_tracks(pre, det_xy, self.gate_m)

        matched_t = set()
        matched_d = set()
        for i, j in pairs:
            self.tracks[i].update(det_xy[j])
            matched_t.add(i)
            matched_d.add(j)

        keep = []
        for i, t in enumerate(self.tracks):
            if i not in matched_t:
                t.misses += 1
            if t.misses <= self.max_misses:
                keep.append(t)
        self.tracks = keep

        for j in range(len(det_xy)):
            if j not in matched_d:
                self.tracks.append(Track(self.next_id, det_xy[j]))
                self.next_id += 1
        return self.tracks