"""A6 第 2 步：同一组数据，卡尔曼滤波 vs 相邻两帧相减，谁算的前车速度更准？

场景和第 1 步一样：我 20 m/s、前车 18 m/s，前车车尾一开始在前面 20 米（真实接近速度 -2 m/s）；
激光雷达一秒 10 帧，每帧量距离误差 0.2 米。卡尔曼在 ads/tracking.py 的 KalmanCV（本人写 predict / update）。

只改第 18 行做实验：Q_ACCEL 越大越信雷达（反应快、抖），越小越信自己猜的（稳、慢）。
运行（在项目根目录）：python -m examples.a6_kalman
"""

from pathlib import Path

import numpy as np

from ads.tracking import KalmanCV, diff_speed

DT_S = 0.1
NOISE_M = 0.2
Q_ACCEL = 1.0        # 前车加减速有多猛（KalmanCV 的 q）
R_MEAS = NOISE_M ** 2  # 雷达量距离的方差（KalmanCV 的 r）


def main():
    t = np.arange(0.0, 5.0 + 1e-9, DT_S)
    true_dist = 20.0 - 2.0 * t
    meas = true_dist + np.random.default_rng(0).normal(0.0, NOISE_M, len(t))

    kf = KalmanCV(meas[0], q=Q_ACCEL, r=R_MEAS)
    est_d, est_v, gain = [kf.x[0]], [kf.x[1]], [np.nan]
    for k in range(1, len(t)):
        kf.predict(DT_S)
        p_before = kf.P[0, 0]
        kf.update(meas[k])
        est_d.append(kf.x[0]); est_v.append(kf.x[1]); gain.append(p_before / (p_before + R_MEAS))
    est_v = np.array(est_v)
    dv = diff_speed(meas, DT_S)

    after = t >= 1.0
    e_kf = np.abs(est_v[after] + 2.0)
    e_df = np.abs(dv[after[1:]] + 2.0)
    print("真实接近速度 -2.00 m/s；只看 1 秒以后（卡尔曼前 1 秒在“认识”这辆车）")
    print(f"相邻两帧相减：误差标准差 {e_df.std():.2f}，最大 {e_df.max():.2f} m/s")
    print(f"卡尔曼滤波  ：误差标准差 {e_kf.std():.2f}，最大 {e_kf.max():.2f} m/s")
    print(f"K（这一帧信雷达几成）：第 1 帧 {gain[1]:.2f}，第 5 帧 {gain[5]:.2f}，第 10 帧 {gain[10]:.2f}，最后 {gain[-1]:.2f}")
    print(f"4.0 秒那一帧：相邻两帧算 {dv[39]:+.2f} m/s，卡尔曼 {est_v[40]:+.2f} m/s")
    plot(t, true_dist, meas, np.array(est_d), est_v, dv)


def plot(t, true_dist, meas, est_d, est_v, dv):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。")
        return
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    a1.plot(t, true_dist, color="#1b222a", linewidth=2, label="true distance")
    a1.plot(t, meas, "o", color="#1e66d6", markersize=4, label="measured (noise 0.2 m)")
    a1.plot(t, est_d, color="#0f8f5c", linewidth=2, label="Kalman estimate")
    a1.set_ylabel("distance to lead car (m)", fontsize=12)
    a1.legend(fontsize=11)
    a2.axhline(-2.0, color="#1b222a", linewidth=2, label="true closing speed -2 m/s")
    a2.plot(t[1:], dv, "-o", color="#d23b3b", markersize=3, linewidth=1, alpha=0.8, label="frame differencing")
    a2.plot(t, est_v, color="#0f8f5c", linewidth=2.5, label="Kalman filter")
    a2.set_ylim(-8, 4)
    a2.set_ylabel("closing speed (m/s)", fontsize=12)
    a2.set_xlabel("time (s)", fontsize=12)
    a2.legend(fontsize=11, loc="lower right")
    for ax in (a1, a2):
        ax.grid(color="#e4e3dd")
        ax.tick_params(labelsize=11)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    Path("outputs").mkdir(exist_ok=True)
    fig.savefig("outputs/a6_kalman.png", dpi=110)
    print("图已保存：outputs/a6_kalman.png")


if __name__ == "__main__":
    main()
