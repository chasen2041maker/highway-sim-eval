"""A6 第 1 步：只有每帧的位置，用“相邻两帧的距离差 ÷ 0.1 秒”算前车车速，会有多准？

场景（高速跟车）：我 20 m/s，前车 18 m/s，前车车尾一开始在我前面 20 米，所以每秒近 2 米。
激光雷达一秒 10 帧，每帧量一次距离；量的距离有误差，标准差 0.2 米（第 3、4 步框中心的误差大约这么大）。
算速度的函数在 ads/tracking.py 的 diff_speed（本人写）。

只改第 21 行的噪声做实验。
运行（在项目根目录）：python -m examples.a6_diff_speed
"""

from pathlib import Path

import numpy as np

from ads.tracking import diff_speed

DT_S = 0.1                 # 一秒 10 帧
DURATION_S = 5.0
CLOSING_MPS = -2.0         # 真实的接近速度：每秒近 2 米
NOISE_M = 0.2              # 每帧量距离的误差（标准差，米）


def main():
    t = np.arange(0.0, DURATION_S + 1e-9, DT_S)
    true_dist = 20.0 + CLOSING_MPS * t
    rng = np.random.default_rng(0)
    meas = true_dist + rng.normal(0.0, NOISE_M, len(t))

    v = diff_speed(meas, DT_S)
    err = v - CLOSING_MPS
    print(f"{len(t)} 帧，每帧量距离的误差约 {NOISE_M} 米")
    print(f"真实接近速度 {CLOSING_MPS:+.2f} m/s")
    print(f"差分算出来：平均 {v.mean():+.2f} m/s，最小 {v.min():+.2f}，最大 {v.max():+.2f}")
    print(f"和真值差多少：标准差 {err.std():.2f} m/s，最大 {np.abs(err).max():.2f} m/s")
    plot(t, true_dist, meas, v)


def plot(t, true_dist, meas, v):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。")
        return
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    a1.plot(t, true_dist, color="#1b222a", linewidth=2, label="true distance")
    a1.plot(t, meas, "o", color="#1e66d6", markersize=4, label=f"measured each frame (noise {NOISE_M} m)")
    a1.set_ylabel("distance to lead car (m)", fontsize=12)
    a1.legend(fontsize=11)
    a2.axhline(CLOSING_MPS, color="#1b222a", linewidth=2, label="true closing speed -2 m/s")
    a2.plot(t[1:], v, "-o", color="#d23b3b", markersize=3, linewidth=1.2, label="diff_speed: (d[k+1] - d[k]) / 0.1")
    a2.set_ylabel("closing speed (m/s)", fontsize=12)
    a2.set_xlabel("time (s)", fontsize=12)
    a2.legend(fontsize=11)
    for ax in (a1, a2):
        ax.grid(color="#e4e3dd")
        ax.tick_params(labelsize=11)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    Path("outputs").mkdir(exist_ok=True)
    fig.savefig("outputs/a6_diff_speed.png", dpi=110)
    print("图已保存：outputs/a6_diff_speed.png")


if __name__ == "__main__":
    main()
