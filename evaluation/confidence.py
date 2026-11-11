"""B4 第 4 步：比例的置信区间。

“1000 道撞了 12 道”只是这一批题的结果；换一批题，可能是 9 道、也可能是 16 道。
置信区间回答：真正的比例大概在多少到多少之间（95% 的把握）。题越少，区间越宽。
用 Wilson 区间：次数很少（甚至 0 次）时也靠得住，不会算出负数。
"""

from __future__ import annotations

import math


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """n 道题里出事 k 道 → 真实比例的 95% 区间 (下限, 上限)。z = 1.96 对应 95%。"""
    if n <= 0:
        raise ValueError("n 要大于 0")
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)
