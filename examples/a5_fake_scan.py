"""A5 第 1 步：先看一眼点云长什么样（假激光雷达，纯 Python）。

雷达装在我的车顶，离地 1.8 米；坐标原点就在雷达上，x 前、y 左、z 上。
周围有 5 个东西：同车道前车（15 米）、左车道一辆、右边停一辆、一个行人、后面一辆。

会打印：一圈打回来多少个点、地面点的 z、每个东西被打中几个点、前车背后有几个地面点；
会画图：outputs/a5_scan.png（左：从天上往下看；右：只看我这条车道，从侧面看）。

运行（在项目根目录）：python -m examples.a5_fake_scan
"""

from pathlib import Path

import numpy as np

from sim.fake_lidar import DEFAULT_SCENE, scan

LANE_HALF_M = 0.9          # "我这条车道"取 |y| < 0.9 米这一窄条
OBJ_COLORS = ["#d23b3b", "#2a78d6", "#1baf7a", "#a347c9", "#e07400"]


def main():
    points, labels = scan()
    total = 32 * 900
    print(f"一圈 32 线 × 900 个方向 = {total} 根激光，打回来 {len(points)} 个点（其余打向天空或超过 50 米）")

    ground = points[labels == -1]
    print(f"地面点 {len(ground)} 个，z 最小 {ground[:, 2].min():.2f}、平均 {ground[:, 2].mean():.2f}、最大 {ground[:, 2].max():.2f} 米")

    for k, box in enumerate(DEFAULT_SCENE):
        n = int((labels == k).sum())
        dist = float(np.hypot(box.cx_m, box.cy_m))
        print(f"  {box.name:14s} 离雷达 {dist:5.1f} 米，被打中 {n:4d} 个点")

    lead = DEFAULT_SCENE[0]
    behind_x = lead.cx_m + lead.length_m / 2
    in_lane = np.abs(ground[:, 1]) < LANE_HALF_M
    before = in_lane & (ground[:, 0] > 3) & (ground[:, 0] < lead.cx_m - lead.length_m / 2)
    after = in_lane & (ground[:, 0] > behind_x) & (ground[:, 0] < 35)
    print(f"我这条车道里：前车前面（3～{lead.cx_m - lead.length_m / 2:.1f} 米）地面点 {int(before.sum())} 个，"
          f"前车背后（{behind_x:.1f}～35 米）地面点 {int(after.sum())} 个")

    plot(points, labels)


def box_outline(box):
    c, s = np.cos(box.yaw_rad), np.sin(box.yaw_rad)
    hx, hy = box.length_m / 2, box.width_m / 2
    corners = [(hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy), (hx, hy)]
    return ([box.cx_m + c * x - s * y for x, y in corners], [box.cy_m + s * x + c * y for x, y in corners])


def plot(points, labels):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。需要的话运行：python -m pip install matplotlib")
        return
    fig, (ax_top, ax_side) = plt.subplots(1, 2, figsize=(15, 6.5), gridspec_kw={"width_ratios": [1.15, 1]})
    g = labels == -1
    ax_top.scatter(points[g, 0], points[g, 1], s=0.4, color="#9a9a94", label="ground points")
    for k, box in enumerate(DEFAULT_SCENE):
        m = labels == k
        ax_top.scatter(points[m, 0], points[m, 1], s=4, color=OBJ_COLORS[k], label=f"{box.name} ({int(m.sum())} pts)")
        ax_top.plot(*box_outline(box), color=OBJ_COLORS[k], linewidth=1, linestyle=":")
    ax_top.plot(0, 0, marker="^", color="black", markersize=9, linestyle="none", label="lidar (origin)")
    ax_top.axhline(LANE_HALF_M, color="#2a78d6", linewidth=0.8, linestyle="--")
    ax_top.axhline(-LANE_HALF_M, color="#2a78d6", linewidth=0.8, linestyle="--", label="my lane strip |y| < 0.9 m")
    ax_top.set_xlim(-25, 40)
    ax_top.set_ylim(-18, 18)
    ax_top.set_aspect("equal")
    ax_top.set_title("top view: looking down from the sky (x forward, y left)")
    ax_top.set_xlabel("x (m)")
    ax_top.set_ylabel("y (m)")

    lane = np.abs(points[:, 1]) < LANE_HALF_M
    lg = lane & g
    ax_side.scatter(points[lg, 0], points[lg, 2], s=3, color="#9a9a94", label="ground points in my lane")
    for k, box in enumerate(DEFAULT_SCENE):
        m = lane & (labels == k)
        if m.any():
            ax_side.scatter(points[m, 0], points[m, 2], s=6, color=OBJ_COLORS[k], label=box.name)
    ax_side.plot(0, 0, marker="^", color="black", markersize=9, linestyle="none", label="lidar (origin, 1.8 m above ground)")
    ax_side.axhline(0, color="black", linewidth=0.6, linestyle=":")
    ax_side.set_xlim(-25, 40)
    ax_side.set_ylim(-2.4, 1.0)
    ax_side.set_title("side view: only my lane strip (x forward, z up)")
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
    fig.savefig(out_dir / "a5_scan.png", dpi=110)
    print("图已保存：outputs/a5_scan.png")


if __name__ == "__main__":
    main()
