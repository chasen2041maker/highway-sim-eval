"""A5 第 3 步：给每一堆点画框，看框的中心离真东西的中心差多少米。

流程：假雷达扫一圈 → 去地面（门槛 −1.6）→ DBSCAN 分堆（eps 1.0、min_samples 5）→ cluster_to_box 画框。
会打印：每个框的中心、长宽，它对上的真东西（这一堆里点最多的那个真东西），真中心、真长宽，中心差多少米。
会画图：outputs/a5_box.png（从天上看：彩色点 = 各堆，实线框 = 算出来的框，虚线框 = 真东西）。

运行（在项目根目录）：python -m examples.a5_box
"""

from pathlib import Path

import numpy as np

from ads.perception import cluster_points, cluster_to_box, remove_ground
from sim.fake_lidar import DEFAULT_SCENE, scan

EPS_M = 1.0
MIN_SAMPLES = 5
Z_THRESHOLD_M = -1.6


def main():
    points, labels_true = scan()
    kept, keep = remove_ground(points, Z_THRESHOLD_M)
    truth = labels_true[keep]                 # 只用来打分
    labels = cluster_points(kept, EPS_M, MIN_SAMPLES)
    boxes = cluster_to_box(kept, labels)

    print(f"{len(kept)} 个点 → {int(labels.max()) + 1} 堆 → {len(boxes)} 个框")
    print("堆  对上的真东西      点数   框中心 (x, y)      框长 × 宽      真中心 (x, y)     真长 × 宽    中心差")
    for k, (cx, cy, lx, wy) in enumerate(boxes):
        mine = truth[labels == k]
        owner = int(np.bincount(mine[mine >= 0]).argmax())
        b = DEFAULT_SCENE[owner]
        err = float(np.hypot(cx - b.cx_m, cy - b.cy_m))
        print(f"{k:2d}  {b.name:14s} {len(mine):5d}   ({cx:6.2f}, {cy:5.2f})   {lx:4.2f} × {wy:4.2f}   "
              f"({b.cx_m:6.2f}, {b.cy_m:5.2f})   {b.length_m:3.1f} × {b.width_m:3.1f}   {err:4.2f} 米")

    plot(kept, labels, boxes)


def box_outline(cx, cy, length, width, yaw=0.0):
    c, s = np.cos(yaw), np.sin(yaw)
    hx, hy = length / 2, width / 2
    corners = [(hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy), (hx, hy)]
    return [cx + c * x - s * y for x, y in corners], [cy + s * x + c * y for x, y in corners]


def plot(kept, labels, boxes):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。")
        return
    fig, ax = plt.subplots(figsize=(13, 6.5))
    palette = ["#2a78d6", "#d23b3b", "#1baf7a", "#a347c9", "#e07400", "#0f8b8d", "#c2185b", "#7a5c00"]
    for k, (cx, cy, lx, wy) in enumerate(boxes):
        m = labels == k
        color = palette[k % len(palette)]
        ax.scatter(kept[m, 0], kept[m, 1], s=6, color=color)
        ax.plot(*box_outline(cx, cy, lx, wy), color=color, linewidth=1.6, label=f"box {k}")
        ax.plot(cx, cy, marker="+", color=color, markersize=12, mew=2)
    for b in DEFAULT_SCENE:
        ax.plot(*box_outline(b.cx_m, b.cy_m, b.length_m, b.width_m, b.yaw_rad), color="#9a9a94", linewidth=1, linestyle=":")
        ax.plot(b.cx_m, b.cy_m, marker="o", color="#9a9a94", markersize=4)
    ax.plot(0, 0, marker="^", color="black", markersize=9, linestyle="none", label="lidar (origin)")
    ax.set_xlim(-18, 30)
    ax.set_ylim(-9, 9)
    ax.set_aspect("equal")
    ax.set_title("top view: solid = boxes from clusters (+ = center), dotted = true objects (o = true center)")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(color="#e4e3dd", linewidth=0.8)
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9, edgecolor="#e4e3dd")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / "a5_box.png", dpi=110)
    print("图已保存：outputs/a5_box.png")


if __name__ == "__main__":
    main()
