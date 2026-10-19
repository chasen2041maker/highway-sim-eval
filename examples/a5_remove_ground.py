"""A5 第 2 步：按高度去掉地面点，看留下了什么（假激光雷达，纯 Python）。

只改第 18 行的门槛 Z_THRESHOLD_M 做实验。
会打印：地面点去掉后还剩几个、5 个东西上的点各留下几个；
会画图：outputs/a5_remove_ground.png（左：留下的点，从天上看；右：只看我这条车道，从侧面看，虚线是门槛）。
真值 labels 只在这里拿来打分和上色，remove_ground 本身看不到它。

运行（在项目根目录）：python -m examples.a5_remove_ground
"""

from pathlib import Path

import numpy as np

from ads.perception import remove_ground
from sim.fake_lidar import DEFAULT_SCENE, LIDAR_HEIGHT_M, scan

Z_THRESHOLD_M = -1.6       # 门槛：z 比它高才算障碍物（−1.6 = 离地 0.20 米）
LANE_HALF_M = 0.9
OBJ_COLORS = ["#d23b3b", "#2a78d6", "#1baf7a", "#a347c9", "#e07400"]


def main():
    points, labels = scan()
    kept, keep = remove_ground(points, Z_THRESHOLD_M)
    print(f"门槛 z > {Z_THRESHOLD_M:.2f} 米（离地 {Z_THRESHOLD_M + LIDAR_HEIGHT_M:.2f} 米以上才算障碍物）")
    print(f"一圈 {len(points)} 个点 → 留下 {len(kept)} 个")

    n_ground = int((labels == -1).sum())
    left_ground = int(((labels == -1) & keep).sum())
    print(f"地面点 {n_ground} 个 → 去完还剩 {left_ground} 个（剩下的会被当成障碍物）")

    n_obj = int((labels >= 0).sum())
    left_obj = int(((labels >= 0) & keep).sum())
    print(f"东西上的点 {n_obj} 个 → 留下 {left_obj} 个（被一起切掉 {n_obj - left_obj} 个）")
    for k, box in enumerate(DEFAULT_SCENE):
        n = int((labels == k).sum())
        m = int(((labels == k) & keep).sum())
        print(f"  {box.name:14s} {n:4d} → {m:4d}")

    plot(points, labels, keep)


def plot(points, labels, keep):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。")
        return
    fig, (ax_top, ax_side) = plt.subplots(1, 2, figsize=(15, 6.5), gridspec_kw={"width_ratios": [1.15, 1]})
    g = labels == -1
    leak = g & keep
    ax_top.scatter(points[leak, 0], points[leak, 1], s=4, color="#555555", label=f"ground points left ({int(leak.sum())})")
    for k, box in enumerate(DEFAULT_SCENE):
        m = (labels == k) & keep
        ax_top.scatter(points[m, 0], points[m, 1], s=5, color=OBJ_COLORS[k], label=f"{box.name} ({int(m.sum())} kept)")
    ax_top.plot(0, 0, marker="^", color="black", markersize=9, linestyle="none", label="lidar (origin)")
    ax_top.set_xlim(-25, 40)
    ax_top.set_ylim(-18, 18)
    ax_top.set_aspect("equal")
    ax_top.set_title(f"top view: points kept by remove_ground (z > {Z_THRESHOLD_M} m)")
    ax_top.set_xlabel("x (m)")
    ax_top.set_ylabel("y (m)")

    lane = np.abs(points[:, 1]) < LANE_HALF_M
    ax_side.scatter(points[lane & ~keep, 0], points[lane & ~keep, 2], s=3, color="#c8c8c2", label="thrown away")
    ax_side.scatter(points[lane & leak, 0], points[lane & leak, 2], s=6, color="#555555", label="ground left (wrong)")
    for k, box in enumerate(DEFAULT_SCENE):
        m = lane & (labels == k) & keep
        if m.any():
            ax_side.scatter(points[m, 0], points[m, 2], s=8, color=OBJ_COLORS[k], label=f"{box.name} kept")
    ax_side.axhline(Z_THRESHOLD_M, color="black", linewidth=1, linestyle="--", label=f"z_threshold = {Z_THRESHOLD_M}")
    ax_side.axhline(-LIDAR_HEIGHT_M, color="#9a9a94", linewidth=0.8, linestyle=":", label="ground z = -1.8")
    ax_side.set_xlim(-25, 40)
    ax_side.set_ylim(-2.0, 0.2)
    ax_side.set_title("side view: only my lane strip |y| < 0.9 m")
    ax_side.set_xlabel("x (m)")
    ax_side.set_ylabel("z (m)")
    for ax in (ax_top, ax_side):
        ax.grid(color="#e4e3dd", linewidth=0.8)
        ax.legend(fontsize=8, loc="upper left", markerscale=2, framealpha=0.9, edgecolor="#e4e3dd")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / "a5_remove_ground.png", dpi=110)
    print("图已保存：outputs/a5_remove_ground.png")


if __name__ == "__main__":
    main()
