"""假路况：几辆车在我前面开，雷达每 0.1 秒给一组框中心（A6 第 3 步多车跟踪的实验台）。

坐标和 A5 一样：x 前、y 左，原点在我的车上；位置都是相对我的（我也在动，所以只看相对运动）。
三车道，车道中心 y = +3.5（左）、0（本车道）、−3.5（右）。

雷达给的只是一堆框中心 (x, y)：没有名字，每帧顺序打乱，还带 0.2 米的误差；
有时少一个（被挡住 / 漏检），有时多一个（误检，比如路边护栏）。
A5 的“只看到车尾、框中心偏 2.3 米”这里先不加：框中心 = 真中心 + 噪声。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DT_S = 0.1


@dataclass
class Car:
    """一辆车的真值：t 秒时在 (x0 + vx·t, y)。vx 是相对我的速度，负数 = 在靠近。"""
    name: str
    x0_m: float
    y_m: float
    vx_mps: float
    hidden_frames: tuple[int, ...] = ()  # 这几帧雷达看不到它

    def pos(self, t_s: float) -> tuple[float, float]:
        return self.x0_m + self.vx_mps * t_s, self.y_m


def default_cars() -> list[Car]:
    """本车道前车（就是第 1、2 步那辆）、左车道慢慢拉开的车、右车道靠近的车（2.0–2.4 秒被挡住）。"""
    return [
        Car("lead", 20.0, 0.0, -2.0),
        Car("left", 12.0, 3.5, 1.0),
        Car("right", 30.0, -3.5, -3.0, hidden_frames=tuple(range(20, 25))),
    ]


@dataclass
class Scene:
    t_s: np.ndarray                      # 形状 (N,)：每帧的时间
    truth: dict[str, np.ndarray]         # 车名 → 形状 (N, 2)：每帧真中心
    detections: list[np.ndarray]         # 第 k 帧：形状 (M_k, 2)，雷达给的框中心（顺序乱）
    det_labels: list[list[str]] = field(default_factory=list)  # 第 k 帧每个框其实是谁（"false" = 误检）；算法不许偷看


def make_scene(cars: list[Car] | None = None, duration_s: float = 5.0, noise_m: float = 0.2,
               false_alarms: dict[int, tuple[float, float]] | None = None, seed: int = 12) -> Scene:
    """造一段路况。false_alarms：{帧号: (x, y)}，那一帧多出一个误检框（默认 3.5 秒在路边护栏 (8, −6)）。"""
    cars = default_cars() if cars is None else cars
    false_alarms = {35: (8.0, -6.0)} if false_alarms is None else false_alarms
    rng = np.random.default_rng(seed)
    n = int(round(duration_s / DT_S)) + 1
    t = np.arange(n) * DT_S
    truth = {c.name: np.array([c.pos(tk) for tk in t]) for c in cars}
    detections, labels = [], []
    for k in range(n):
        pts, who = [], []
        for c in cars:
            if k in c.hidden_frames:
                continue
            pts.append(np.array(c.pos(t[k])) + rng.normal(0.0, noise_m, 2))
            who.append(c.name)
        if k in false_alarms:
            pts.append(np.array(false_alarms[k], dtype=float))
            who.append("false")
        order = rng.permutation(len(pts))
        detections.append(np.array([pts[i] for i in order]).reshape(-1, 2))
        labels.append([who[i] for i in order])
    return Scene(t, truth, detections, labels)
