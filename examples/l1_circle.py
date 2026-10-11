"""A1：方向盘固定打一个角度，绕一圈，检查自行车模型。

运行（在项目根目录）：python -m examples.l1_circle
"""

import math
from pathlib import Path

from ads.vehicle import WHEELBASE_M, VehicleState, step

SPEED_MPS = 10.0
STEER_RAD = 0.1
DT_S = 0.1

def main():
    radius_m = WHEELBASE_M/ math.tan(STEER_RAD)  # 转弯半径 R = L / tan(转角)
    lap_time_s = 2 * math.pi * radius_m / SPEED_MPS  # 绕一圈的时间 = 周长 / 车速

    state = VehicleState(speed_mps=SPEED_MPS)
    xs, ys = [state.x_m], [state.y_m] # 把每一步的位置记下来，用来画图
    for _ in range(round(lap_time_s / DT_S)):  # 一圈需要多少步
        state = step(state, accel_mps2=0.0, steer_rad=STEER_RAD, dt_s=DT_S)
        xs.append(state.x_m)
        ys.append(state.y_m)
    print(f"理论直径 {2 * radius_m:.2f} m，实测直径 {max(ys) - min(ys):.2f} m")
    print(f"跑一圈理论用时 {lap_time_s:.2f} s，终点离起点 {math.hypot(state.x_m, state.y_m):.2f} m")
    plot(xs, ys)

    # ---------- 以下是画图，可以直接粘贴 ----------
def plot(xs, ys):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。需要的话运行：python -m pip install matplotlib")
        return
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(xs, ys)
    ax.plot(xs[0], ys[0], "go", label="start")
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("A1: constant steering")
    ax.legend()
    fig.savefig(out_dir / "l1_circle.png", dpi=120)
    print("图已保存：outputs/l1_circle.png")


if __name__ == "__main__":
    main()