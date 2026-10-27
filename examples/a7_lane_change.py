"""A7 第 3 步：弯道上变道——用 Frenet 画曲线 vs 直接在地图上“往 +y 挪”。

场景：本车道中心线 = 直道 30 m → 半径 50 m 左转 90° → 直道 60 m（每 0.5 米一个点）。
车速 10 m/s；第 4 秒（s = 40 m，已经进弯 10 米）开始往左变道 3.5 米，用 4 秒（s 走到 80 m）。
两条“想走的路线”：
  ① Frenet：每个 s 用 lane_change_d 算 d，再用 frenet_to_xy 换成地图上的 (x, y)；
  ② 直接挪：先找本车道中心线上走了 s 米的那个点，再在地图上把 y 加上 d（不管路朝哪）。
两辆车都用 A1 的自行车模型 + A3 的 Pure Pursuit（前视 6 米）去跟，各开 14 秒。

要回答：开完以后，谁真的在左车道正中间？一路上横向加速度最大多少？
运行（在项目根目录）：python -m examples.a7_lane_change
"""

import math
from pathlib import Path

from ads.control import find_lookahead_point, pure_pursuit_steer
from ads.planning import frenet_to_xy, lane_change_d
from ads.vehicle import MAX_STEER_RAD, WHEELBASE_M, VehicleState, step
from evaluation.metrics import lateral_error_m

SPEED_MPS = 10.0
DT_S = 0.05
LANE_M = 3.5               # 车道宽 = 要往左挪的距离
CHANGE_START_S = 4.0       # 第几秒开始变道
CHANGE_DURATION_S = 4.0    # 变道用几秒
LOOKAHEAD_M = 6.0          # Pure Pursuit 前视距离
SIM_TIME_S = 14.0
RADIUS_M = 50.0            # 弯道半径：10 m/s 过弯本身就要 10² / 50 = 2 m/s² 的横向加速度
SPACING_M = 0.5


def make_reference() -> list[tuple[float, float]]:
    """本车道中心线：直道 30 m → 半径 50 m 左转 90° → 直道 60 m。"""
    pts = [(i * SPACING_M, 0.0) for i in range(round(30 / SPACING_M))]
    n = round(RADIUS_M * math.pi / 2 / SPACING_M)
    for k in range(n + 1):
        th = k / n * math.pi / 2
        pts.append((30 + RADIUS_M * math.sin(th), RADIUS_M - RADIUS_M * math.cos(th)))
    for i in range(1, round(60 / SPACING_M) + 1):
        pts.append((30 + RADIUS_M, RADIUS_M + i * SPACING_M))
    return pts


def length_m(path: list[tuple[float, float]]) -> float:
    return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(path, path[1:]))


def planned_paths(ref):
    """两条想走的路线 + 两条车道中心线（本车道 d = 0、左车道 d = 3.5），每 0.5 米一个点。"""
    frenet, naive, own, left = [], [], [], []
    for k in range(int(length_m(ref) / SPACING_M) + 1):
        s = k * SPACING_M
        d = lane_change_d(s / SPEED_MPS - CHANGE_START_S, CHANGE_DURATION_S, LANE_M)[0]
        frenet.append(frenet_to_xy(ref, s, d))           # ① Frenet
        xr, yr = frenet_to_xy(ref, s, 0.0)
        naive.append((xr, yr + d))                        # ② 直接在地图上把 y 加 d
        own.append((xr, yr))
        left.append(frenet_to_xy(ref, s, LANE_M))
    return frenet, naive, own, left


def drive(path):
    """自行车模型 + Pure Pursuit 沿 path 开 SIM_TIME_S 秒；返回轨迹和每一步的横向加速度。"""
    state = VehicleState(0.0, 0.0, 0.0, SPEED_MPS)
    traj, lat_acc = [(state.x_m, state.y_m)], []
    for _ in range(round(SIM_TIME_S / DT_S)):
        tx, ty = find_lookahead_point(path, state, LOOKAHEAD_M)
        steer = max(-MAX_STEER_RAD, min(MAX_STEER_RAD, pure_pursuit_steer(state, tx, ty)))
        lat_acc.append(SPEED_MPS ** 2 * math.tan(steer) / WHEELBASE_M)   # 横向加速度 = v² × 曲率
        state = step(state, 0.0, steer, DT_S)
        traj.append((state.x_m, state.y_m))
    return traj, lat_acc


def main():
    ref = make_reference()
    frenet, naive, own, left = planned_paths(ref)
    rows = []
    results = {}
    for name, path in [("Frenet", frenet), ("直接挪", naive)]:
        traj, acc = drive(path)
        x, y = traj[-1]
        results[name] = (traj, acc)
        rows.append((name, lateral_error_m(left, x, y), lateral_error_m(own, x, y), max(abs(a) for a in acc)))

    print(f"车速 {SPEED_MPS:.0f} m/s，弯道半径 {RADIUS_M:.0f} m（光过弯就要 {SPEED_MPS ** 2 / RADIUS_M:.1f} m/s²）；"
          f"第 {CHANGE_START_S:.0f} 秒开始、用 {CHANGE_DURATION_S:.0f} 秒往左变道 {LANE_M} 米")
    print(f"{'':8}{'终点离左车道中心':>14}{'终点离本车道中心':>14}{'最大横向加速度':>14}")
    for name, d_left, d_own, a in rows:
        print(f"{name:8}{d_left:>12.2f} m{d_own:>12.2f} m{a:>11.2f} m/s²")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(7, 7))
    for dd, style in [(-LANE_M / 2, "-"), (LANE_M / 2, "--"), (LANE_M * 1.5, "-")]:
        line = [frenet_to_xy(ref, k * SPACING_M, dd) for k in range(int(length_m(ref) / SPACING_M) + 1)]
        ax.plot(*zip(*line), style, color="0.6", lw=1)
    ax.plot(*zip(*frenet), ":", color="tab:green", lw=1.5, label="planned: Frenet (s, d) -> (x, y)")
    ax.plot(*zip(*naive), ":", color="tab:red", lw=1.5, label="planned: map y + d")
    ax.plot(*zip(*results["Frenet"][0]), color="tab:green", lw=2.5, alpha=0.7, label="car following Frenet path")
    ax.plot(*zip(*results["直接挪"][0]), color="tab:red", lw=2.5, alpha=0.7, label="car following y + d path")
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Lane change in a left curve (R = 50 m, 10 m/s, 4 s)")
    ax.legend(loc="upper left", fontsize=8)
    out = Path("outputs") / "a7_lane_change.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    print(f"图：{out}")


if __name__ == "__main__":
    main()
