"""A5 第 3 步：把去完地面留下的点归成一堆一堆（DBSCAN），看能不能正好找出 5 个东西。

只改第 18、19 行的 EPS_M、MIN_SAMPLES 做实验。
会打印：聚成几堆、几个噪声点、每堆多少个点和中心在哪；
       再拿真值对一下：每个真东西的点被分进了几堆（1 = 正好；>1 = 被切碎；两个东西进了同一堆 = 粘在一起）。
会画图：outputs/a5_cluster.png（从天上看，每堆一个颜色，黑叉 = 噪声，虚线框 = 真东西的位置）。

运行（在项目根目录）：python -m examples.a5_cluster
"""

from pathlib import Path

import numpy as np

from ads.perception import cluster_points, remove_ground
from sim.fake_lidar import DEFAULT_SCENE, scan

EPS_M = 1.0            # 相距不超过几米算“挨着”（窗口：大于车身上最大的缝 0.86、小于两车最近 3.62）
MIN_SAMPLES = 5        # eps 圈里至少几个点才算核心点
Z_THRESHOLD_M = -1.6   # 去地面的门槛（第 2 步定下来的）


def main():
    points, labels_true = scan()
    kept, keep = remove_ground(points, Z_THRESHOLD_M)
    truth = labels_true[keep]                 # 留下的点各自真属于谁（只用来打分）
    labels = cluster_points(kept, EPS_M, MIN_SAMPLES)

    n_clusters = int(labels.max()) + 1 if len(labels) else 0
    n_noise = int((labels == -1).sum())
    print(f"eps = {EPS_M} 米，min_samples = {MIN_SAMPLES}：{len(kept)} 个点 → 聚成 {n_clusters} 堆，噪声 {n_noise} 个")
    for c in range(n_clusters):
        m = labels == c
        cx, cy = kept[m, 0].mean(), kept[m, 1].mean()
        owners = sorted({DEFAULT_SCENE[k].name for k in set(truth[m].tolist()) if k >= 0})
        print(f"  第 {c} 堆：{int(m.sum()):4d} 个点，中心 ({cx:6.1f}, {cy:5.1f})，真值里属于：{', '.join(owners)}")

    print("拿真值对一下（每个东西被分进了几堆）：")
    for k, box in enumerate(DEFAULT_SCENE):
        mine = labels[truth == k]
        parts = sorted(set(mine.tolist()) - {-1})
        print(f"  {box.name:14s} {len(mine):4d} 个点 → 分进 {len(parts)} 堆 {parts}，噪声 {int((mine == -1).sum())} 个")

    plot(kept, labels)


def box_outline(box):
    c, s = np.cos(box.yaw_rad), np.sin(box.yaw_rad)
    hx, hy = box.length_m / 2, box.width_m / 2
    corners = [(hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy), (hx, hy)]
    return ([box.cx_m + c * x - s * y for x, y in corners], [box.cy_m + s * x + c * y for x, y in corners])


def plot(kept, labels):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。")
        return
    fig, ax = plt.subplots(figsize=(13, 6.5))
    palette = ["#2a78d6", "#d23b3b", "#1baf7a", "#a347c9", "#e07400", "#0f8b8d", "#c2185b", "#7a5c00", "#5b6bd6", "#6b8e23"]
    for c in range(int(labels.max()) + 1 if len(labels) else 0):
        m = labels == c
        ax.scatter(kept[m, 0], kept[m, 1], s=7, color=palette[c % len(palette)], label=f"cluster {c} ({int(m.sum())})")
    noise = labels == -1
    if noise.any():
        ax.scatter(kept[noise, 0], kept[noise, 1], s=30, marker="x", color="black", label=f"noise ({int(noise.sum())})")
    for box in DEFAULT_SCENE:
        ax.plot(*box_outline(box), color="#9a9a94", linewidth=1, linestyle=":")
    ax.plot(0, 0, marker="^", color="black", markersize=9, linestyle="none", label="lidar (origin)")
    ax.set_xlim(-18, 30)
    ax.set_ylim(-9, 9)
    ax.set_aspect("equal")
    ax.set_title(f"top view: DBSCAN clusters (eps = {EPS_M} m, min_samples = {MIN_SAMPLES}); dotted = true objects")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(color="#e4e3dd", linewidth=0.8)
    ax.legend(fontsize=8, loc="upper left", markerscale=2, framealpha=0.9, edgecolor="#e4e3dd", ncol=2)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / "a5_cluster.png", dpi=110)
    print("图已保存：outputs/a5_cluster.png")


if __name__ == "__main__":
    main()
