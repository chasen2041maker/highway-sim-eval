"""A3：Pure Pursuit 沿“直道 + 左转弯”开，比较三个前视距离 Ld。

车一开始在路线右边 3 米，车速固定 10 m/s，看两件事：
  - 直道上：会不会冲过路线（画龙）
  - 弯道上：会不会往弯里抄近路（切弯）

运行（在项目根目录）：python -m examples.a3_pure_pursuit
动画讲解：docs/a3_pure_pursuit_animation.html（双击用浏览器打开）
"""

import math
from pathlib import Path

from ads.control import find_lookahead_point, pure_pursuit_steer
from ads.vehicle import VehicleState, step

SPEED_MPS = 10.0
DT_S = 0.1
SIM_TIME_S = 10.0                   # 10 秒 × 10 m/s ≈ 100 米，刚好开过弯道
START_Y_M = -3.0                    # 起点：在路线右边 3 米
LOOKAHEADS_M = [2.0, 5.0, 15.0]     # 要比较的前视距离：近 / 中 / 远


def make_path(spacing_m: float = 0.1) -> list[tuple[float, float]]:
    """路线：直道 40 m → 半径 20 m 左转 90° → 直道 40 m，每 spacing_m 米一个点。"""
    path = [(i * spacing_m, 0.0) for i in range(round(40 / spacing_m))]
    n = round(20 * math.pi / 2 / spacing_m)          # 弧长 ÷ 点间距 = 弯道上的点数
    for k in range(n + 1):
        theta = k / n * math.pi / 2                  # 已经转过的角度：0 → 90°
        path.append((40 + 20 * math.sin(theta), 20 - 20 * math.cos(theta)))
    for i in range(1, round(40 / spacing_m)):
        path.append((60.0, 20 + i * spacing_m))
    return path


def lateral_error_m(path: list[tuple[float, float]], state: VehicleState) -> float:
    """横向误差：车离路线上最近的点有多远。"""
    return min(math.hypot(x - state.x_m, y - state.y_m) for x, y in path)


def drive(path: list[tuple[float, float]], lookahead_m: float):
    """用 Pure Pursuit 沿路线开 SIM_TIME_S 秒，返回每一步的 x、y、横向误差。"""
    state = VehicleState(y_m=START_Y_M, speed_mps=SPEED_MPS)
    xs, ys, errs = [state.x_m], [state.y_m], [lateral_error_m(path, state)]

    for _ in range(round(SIM_TIME_S / DT_S)):
        target_x_m, target_y_m = find_lookahead_point(path, state, lookahead_m)
        steer_rad = pure_pursuit_steer(state, target_x_m, target_y_m)
        state = step(state, accel_mps2=0.0, steer_rad=steer_rad, dt_s = DT_S)
        xs.append(state.x_m)
        ys.append(state.y_m)
        errs.append(lateral_error_m(path, state))
    return xs, ys, errs


def main():
    path = make_path()
    results = {}
    for lookahead_m in LOOKAHEADS_M:
        xs, ys, errs = drive(path, lookahead_m)
        results[lookahead_m] = (xs, ys)
        overshoot_m = max([y for x, y in zip(xs, ys) if x < 30] + [0.0])   # 前 30 m 直道：冲到路线左边最多多少
        curve_err_m = max(e for x, y, e in zip(xs, ys, errs) if x > 40 and y < 20)   # 弯道上：最大横向误差
        print(f"Ld = {lookahead_m:4.1f} m：直道冲过头 {overshoot_m:.2f} m，弯道最大误差 {curve_err_m:.2f} m")
    plot(path, results)


# ---------- 以下是画图，助手写好的，不用手敲 ----------
COLORS = {2.0: "#2a78d6", 5.0: "#eb6834", 15.0: "#1baf7a"}


def plot(path, results):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。需要的话运行：python -m pip install matplotlib")
        return
    px, py = zip(*path)
    fig, (ax_all, ax_straight, ax_curve) = plt.subplots(1, 3, figsize=(15, 5))
    panels = [
        (ax_all, "Whole run", None),
        (ax_straight, "Straight: overshoot (zoom)", ((0, 40), (-3.5, 1.5))),
        (ax_curve, "Curve: corner cutting (zoom)", ((38, 62), (-1, 23))),
    ]
    for ax, title, limits in panels:
        ax.plot(px, py, color="#9a9a94", linestyle="--", linewidth=2, label="path")
        for lookahead_m, (xs, ys) in results.items():
            ax.plot(xs, ys, color=COLORS.get(lookahead_m), linewidth=2, label=f"Ld = {lookahead_m:g} m")
        ax.set_title(title)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.grid(color="#e4e3dd", linewidth=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        if limits:
            ax.set_xlim(*limits[0])
            ax.set_ylim(*limits[1])
        else:
            ax.set_aspect("equal")
    ax_all.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / "a3_pure_pursuit.png", dpi=120)
    print("图已保存：outputs/a3_pure_pursuit.png")


if __name__ == "__main__":
    main()
