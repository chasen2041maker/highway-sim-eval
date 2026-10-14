"""生成 README 里的两张图（纯 Python，不需要 CARLA）。

运行（在项目根目录）：python -m scripts.readme_figures
输出：docs/images/bicycle_circles.png、docs/images/pid_uphill.png
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ads.control import PID  # noqa: E402
from ads.vehicle import WHEELBASE_M, VehicleState, step  # noqa: E402

OUT_DIR = Path("docs/images")

# 配色：数据可视化参考调色板的前两个分类色（已通过色觉缺陷校验）
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834"]

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "text.color": INK,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
})


def circle(speed_mps: float, steer_rad: float, dt_s: float = 0.01):
    """定转角绕一圈，返回 (xs, ys, 实测直径)。"""
    lap_s = 2 * math.pi * (WHEELBASE_M / math.tan(steer_rad)) / speed_mps
    state = VehicleState(speed_mps=speed_mps)
    xs, ys = [0.0], [0.0]
    for _ in range(round(lap_s / dt_s)):
        state = step(state, 0.0, steer_rad, dt_s)
        xs.append(state.x_m)
        ys.append(state.y_m)
    return xs, ys, max(ys) - min(ys)


def uphill(pid: PID, target_mps=10.0, hill_mps2=-0.5, seconds=30.0, dt_s=0.1):
    """上坡跟踪目标车速，返回 (时间, 车速)。"""
    state = VehicleState()
    ts, vs = [0.0], [0.0]
    for k in range(round(seconds / dt_s)):
        accel = pid.update(target_mps - state.speed_mps, dt_s)
        state = step(state, accel + hill_mps2, 0.0, dt_s)
        ts.append((k + 1) * dt_s)
        vs.append(state.speed_mps)
    return ts, vs


def fig_circles() -> None:
    fig, ax = plt.subplots(figsize=(5.2, 4.6), dpi=160)
    for color, steer in zip(SERIES, (0.1, 0.2)):
        xs, ys, d = circle(10.0, steer)
        ax.plot(xs, ys, color=color, linewidth=2, label=f"前轮转角 {steer} rad：直径 {d:.2f} m")
    ax.plot([0], [0], marker="o", markersize=8, color=INK_2, markeredgecolor=SURFACE, markeredgewidth=2)
    ax.annotate("起点", (0, 0), xytext=(6, -14), textcoords="offset points", color=INK_2)
    ax.set_aspect("equal")
    ax.set_xlabel("x（米，向前）")
    ax.set_ylabel("y（米，向左）")
    ax.set_title("运动学自行车模型：10 m/s 定转角绕圈", loc="left", fontsize=11)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "bicycle_circles.png")
    plt.close(fig)


def fig_pid() -> None:
    fig, ax = plt.subplots(figsize=(5.8, 4.6), dpi=160)
    runs = [("只有 P（kp 0.5）", PID(kp=0.5)), ("PI（kp 1.0，ki 0.2）", PID(kp=1.0, ki=0.2))]
    for color, (name, pid) in zip(SERIES, runs):
        ts, vs = uphill(pid)
        ax.plot(ts, vs, color=color, linewidth=2, label=name)
        ax.annotate(f"{vs[-1]:.2f}", (ts[-1], vs[-1]), xytext=(6, 4 if vs[-1] > 9.5 else -4),
                    textcoords="offset points", color=INK, fontsize=9, va="center")
        if max(vs) > 10.0:
            k = vs.index(max(vs))
            ax.plot([ts[k]], [vs[k]], marker="o", markersize=8, color=color,
                    markeredgecolor=SURFACE, markeredgewidth=2)
            ax.annotate(f"最高 {vs[k]:.2f}", (ts[k], vs[k]), xytext=(8, 6),
                        textcoords="offset points", color=INK, fontsize=9)
    ax.axhline(10.0, color=INK_2, linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate("目标 10 m/s", (12.0, 10.0), xytext=(0, -14), textcoords="offset points", color=INK_2, fontsize=9)
    ax.set_xlim(0, 33)
    ax.set_ylim(0, 12)
    ax.set_xlabel("时间（秒）")
    ax.set_ylabel("车速（m/s）")
    ax.set_title("PID 速度控制：上坡（−0.5 m/s²）时的稳态误差", loc="left", fontsize=11)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "pid_uphill.png")
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_circles()
    fig_pid()
    print(f"已生成：{OUT_DIR / 'bicycle_circles.png'}、{OUT_DIR / 'pid_uphill.png'}")


if __name__ == "__main__":
    main()
