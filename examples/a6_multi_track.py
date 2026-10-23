"""A6 第 3 步：多车跟踪器跑一整段假路况（5 秒、51 帧），看编号是不是一直跟着同一辆车。

场景（sim/fake_traffic.py）：本车道前车 20 米、左车道 12 米、右车道 30 米（2.0–2.4 秒被挡住）；
3.5 秒路边护栏 (8, −6) 误检一次；框中心带 0.2 米误差，每帧顺序打乱。跟踪器在 ads/tracking.py（本人写）。

只改第 20 行做实验：MAX_MISSES = 10（被挡住 1 秒内还认得）或 3（只等 0.3 秒）。
运行（在项目根目录）：python -m examples.a6_multi_track
"""

from collections import Counter
from pathlib import Path

import numpy as np

from ads.tracking import MultiTracker
from sim.fake_traffic import DT_S, make_scene

GATE_M = 2.0         # 配对门槛（米）
LANE = {"lead": "本车道", "left": "左车道", "right": "右车道"}
MAX_MISSES = 10      # 纸条连着没配上超过这么多帧就扔掉


def main():
    scene = make_scene()
    mt = MultiTracker(gate_m=GATE_M, max_misses=MAX_MISSES)
    first, last, alive = {}, {}, Counter()
    follows = {}   # 编号 → 每帧离它最近的真车（2 米以内才算，否则记 none）
    paths = {}     # 编号 → 每帧估计的位置
    for k, t in enumerate(scene.t_s):
        for tr in mt.step(scene.detections[k], DT_S):
            first.setdefault(tr.id, t)
            last[tr.id] = t
            alive[tr.id] += 1
            paths.setdefault(tr.id, []).append(tr.xy.copy())
            name, d = min(((n, float(np.hypot(*(tr.xy - xy[k])))) for n, xy in scene.truth.items()),
                          key=lambda p: p[1])
            follows.setdefault(tr.id, Counter())[name if d < GATE_M else "none"] += 1

    print(f"MAX_MISSES = {MAX_MISSES}：一共发了 {len(first)} 个编号，最后手里 {len(mt.tracks)} 张纸条")
    print("编号   出现     最后一次   活了几帧   大多数时候跟的是")
    for i in sorted(first):
        who = follows[i].most_common(1)[0][0]
        who = "没有真车（误检的鬼影）" if who == "none" else f"{who}（{LANE[who]}）"
        print(f"{i:>3}    {first[i]:.1f} 秒   {last[i]:.1f} 秒    {alive[i]:>3}       {who}")
    plot(scene, paths)


def plot(scene, paths):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。")
        return
    colors = ["#1e66d6", "#e8890c", "#0f8f5c", "#d23b3b", "#8a4fd8", "#6b6b6b"]
    fig, ax = plt.subplots(figsize=(11, 5))
    for y in (1.75, -1.75, 5.25, -5.25):
        ax.axhline(y, color="#cfcfcf", linewidth=1, linestyle="--", zorder=0)
    for name, xy in scene.truth.items():
        ax.plot(xy[:, 0], xy[:, 1], color="#1b222a", linewidth=6, alpha=0.12, solid_capstyle="round")
    det = np.vstack([d for d in scene.detections if len(d)])
    ax.plot(det[:, 0], det[:, 1], ".", color="#9a9a9a", markersize=4, label="radar boxes (all frames)")
    for n, (i, pts) in enumerate(sorted(paths.items())):
        pts = np.array(pts)
        c = colors[n % len(colors)]
        ax.plot(pts[:, 0], pts[:, 1], "-o", color=c, markersize=3, linewidth=2, label=f"ID {i}")
        ax.annotate(f"ID {i}", pts[-1], textcoords="offset points", xytext=(6, 6), color=c, fontsize=11,
                    weight="bold")
    ax.set_xlabel("x: ahead of me (m)", fontsize=12)
    ax.set_ylabel("y: to my left (m)", fontsize=12)
    ax.set_title(f"multi-object tracking, MAX_MISSES = {MAX_MISSES} (thick grey = true path)", fontsize=12)
    ax.set_ylim(-7, 6)
    ax.legend(fontsize=10, loc="upper right", ncol=2)
    ax.grid(color="#eeeeee")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    Path("outputs").mkdir(exist_ok=True)
    fig.savefig("outputs/a6_multi_track.png", dpi=110)
    print("图已保存：outputs/a6_multi_track.png")


if __name__ == "__main__":
    main()
