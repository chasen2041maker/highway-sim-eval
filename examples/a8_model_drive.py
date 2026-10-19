"""④ 三样合起来开一段路（纯 Python 预演，真值版 A8）。

场景：直道 40 m → 半径 20 m 左转 90° → 直道 40 m，红点每 0.5 米一颗。
两车都是 10 m/s、车距 25 米；前车第 3 秒（快进弯时）以 −5 急刹，停在弯里。
我的车：IDM 决定快慢（规划）→ 影子车车速 + PID 追它（纵向控制，和 CARLA 一样的结构）；
        Pure Pursuit 打方向（横向控制）；A1 自行车模型当“车”。
回家把 step() 换成 CARLA 的车（to_pedals + apply_control），其余原样搬。

这个实验要回答：三样一起上，会不会互相拖后腿？
  1. 边拐弯边急刹，离车道中心最远多少？（用新尺子 lateral_error_m）
  2. 加了 PID 下层，最小车距和“IDM 的加速度直接给车”比，变大还是变小？

运行（在项目根目录）：python -m examples.a8_model_drive
"""

import math
from pathlib import Path

from ads.control import PID, find_lookahead_point, pure_pursuit_steer
from ads.planning import StopHold, idm_accel
from ads.vehicle import VehicleState, step
from evaluation.metrics import lateral_error_m
from examples.a3_pure_pursuit import make_path

DT_S = 0.1
SIM_TIME_S = 15.0
SPACING_M = 0.5            # 红点间距（和 CARLA 里 wp.next(0.5) 一样）
CAR_LEN_M = 4.7            # 车距 = 两车中心的距离 − 车长（和 a4_carla_follow 一样）
START_SPEED_MPS = 10.0     # 两车一开始都是 10 m/s
TARGET_SPEED_MPS = 15.0    # 我想开到 15
START_GAP_M = 25.0         # 一开始车距 25 米
BRAKE_AT_S = 3.0           # 前车第 3 秒急刹（这时它快进弯了）
LEAD_BRAKE_MPS2 = -5.0
LOOKAHEAD_M = 5.0          # 10-16 在 CARLA 里选的 Ld
MAX_ACCEL_MPS2 = 3.0       # 车最猛加速 3、最猛刹车 −8
MAX_BRAKE_MPS2 = 8.0
HOLD_DECEL_MPS2 = 2.0      # 停车保持时踩住刹车（模型里用 −2 m/s²；CARLA 里是刹车踏板 0.3～0.4）


def point_at(path, s_m):
    """沿路线走 s_m 米落在哪（在两颗红点之间按比例取点）。前车就沿这条线开，不用打方向。"""
    i = min(int(s_m / SPACING_M), len(path) - 2)
    f = min(1.0, s_m / SPACING_M - i)
    (x0, y0), (x1, y1) = path[i], path[i + 1]
    return x0 + f * (x1 - x0), y0 + f * (y1 - y0)


def lead_step(t_s, speed_mps, s_m):
    """前车剧本：第 BRAKE_AT_S 秒起以 −5 刹到停；返回新车速、沿路线走过的米数。"""
    accel = LEAD_BRAKE_MPS2 if t_s >= BRAKE_AT_S else 0.0
    speed_mps = max(0.0, speed_mps + accel * DT_S)
    return speed_mps, s_m + speed_mps * DT_S


def record(log, **values):
    """把这一帧的数记进 log（每个名字一列）。"""
    for key, value in values.items():
        log.setdefault(key, []).append(value)


def simulate(closed_loop: bool, stop_hold: bool = False):
    """跑一遍。closed_loop=True：IDM → 影子车 → PID → 加速度；False：IDM 的加速度直接给车。stop_hold=True：加停车保持。"""
    path = make_path(SPACING_M)
    ego = VehicleState(speed_mps=START_SPEED_MPS)
    lead_s_m, lead_speed_mps = START_GAP_M + CAR_LEN_M, START_SPEED_MPS   # 前车沿路线的位置（中心）、车速
    shadow_mps = START_SPEED_MPS                                          # 影子车车速
    pid = PID(kp=1.0, ki=0.5, u_max=MAX_ACCEL_MPS2)
    hold = StopHold()
    log = {}

    for k in range(round(SIM_TIME_S / DT_S)):
        t_s = k * DT_S
        lead_x_m, lead_y_m = point_at(path, lead_s_m)
        # ---------- 从这里开始手敲 ----------
        
        gap_m = math.hypot(lead_x_m - ego.x_m, lead_y_m - ego.y_m) - CAR_LEN_M   # ① 量车距
        want = idm_accel(ego.speed_mps, lead_speed_mps, gap_m, TARGET_SPEED_MPS)  # ② 规划：IDM 想要的加速度
        shadow_mps = max(0.0, shadow_mps + want * DT_S)             #    影子车完全听 IDM
        if closed_loop:
            accel = pid.update(shadow_mps - ego.speed_mps, DT_S)         # ③ 纵向控制：PID 追影子车
        else:
            accel = want
        accel = max(-MAX_BRAKE_MPS2, min(MAX_ACCEL_MPS2, accel))            #    车做不到的截掉

        if stop_hold and hold.update(ego.speed_mps, lead_speed_mps, gap_m):
            pid.integral, pid.pre_error, shadow_mps = 0.0, None, 0.0    # 攒的清掉，影子车也停
            accel = -HOLD_DECEL_MPS2    #踩住刹车
        
        tx, ty = find_lookahead_point(path, ego, LOOKAHEAD_M)               # ④ 横向控制：Pure Pursuit
        steer = pure_pursuit_steer(ego, tx, ty)
        error = lateral_error_m(path, ego.x_m, ego.y_m)                     # ⑤ 新尺子：离中心线多远
        record(log, t=t_s, gap=gap_m, speed=ego.speed_mps, lead=lead_speed_mps, shadow=shadow_mps,
               want=want, accel=accel, err=error, x=ego.x_m, y=ego.y_m)
        ego = step(ego, accel, steer, DT_S)                                 # ⑥ 车往前开一步
        lead_speed_mps, lead_s_m = lead_step(t_s, lead_speed_mps, lead_s_m)    #    前车按剧本

        # ---------- 手敲到这里 ----------
    return path, log


def summarize(log):
    """打分：最小车距、离中心最远、平均离中心、最猛刹车、撞没撞。"""
    gaps, errs, accels, ts = log["gap"], log["err"], log["accel"], log["t"]
    i_gap = gaps.index(min(gaps))
    i_err = errs.index(max(errs))
    restarts, low = 0, False                  # 停下（< 1 m/s）后又起步（> 1 m/s）的次数
    for v in log["speed"]:
        if v < 1.0:
            low = True
        elif low:
            restarts, low = restarts + 1, False
    return (f"最小车距 {gaps[i_gap]:.2f} 米（{ts[i_gap]:.1f} 秒）｜离中心最远 {errs[i_err]:.2f} 米（{ts[i_err]:.1f} 秒）、"
            f"平均 {sum(errs) / len(errs):.3f}｜最猛刹车 {min(accels):.2f}｜停下后又起步 {restarts} 次｜最后停在 {gaps[-1]:.2f} 米｜"
            f"{'撞了！' if min(gaps) <= 0 else '没撞'}")


def main():
    results = {}
    for closed_loop, hold, name in ((False, False, "IDM 加速度直接给车"), (True, False, "IDM → 影子车 → PID"),
                                    (True, True, "PID + 停车保持")):
        path, log = simulate(closed_loop, hold)
        results[name] = log
        print(f"{name}：{summarize(log)}")
    plot(path, results)


# ---------- 以下是画图，助手写好的，不用手敲 ----------
COLORS = {"IDM 加速度直接给车": "#9a9a94", "IDM → 影子车 → PID": "#2a78d6", "PID + 停车保持": "#1baf7a"}
LABELS = {"IDM 加速度直接给车": "IDM accel -> car", "IDM → 影子车 → PID": "IDM -> shadow -> PID", "PID + 停车保持": "PID + stop hold"}


def plot(path, results):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。需要的话运行：python -m pip install matplotlib")
        return
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax_map, ax_v, ax_gap, ax_err = axes[0][0], axes[0][1], axes[1][0], axes[1][1]
    px, py = zip(*path)
    ax_map.plot(px, py, color="#d23b3b", linestyle="none", marker=".", markersize=3, label="lane center (0.5 m points)")
    for name, log in results.items():
        ax_map.plot(log["x"], log["y"], color=COLORS[name], linewidth=2, label=LABELS[name])
        ax_v.plot(log["t"], log["speed"], color=COLORS[name], linewidth=2, label=LABELS[name])
        ax_gap.plot(log["t"], log["gap"], color=COLORS[name], linewidth=2, label=LABELS[name])
        ax_err.plot(log["t"], log["err"], color=COLORS[name], linewidth=2, label=LABELS[name])
    closed = results["IDM → 影子车 → PID"]
    ax_v.plot(closed["t"], closed["shadow"], color="#2a78d6", linewidth=1, linestyle=":", label="shadow car")
    ax_v.plot(closed["t"], closed["lead"], color="#eb6834", linewidth=1.5, linestyle="--", label="lead car")
    ax_gap.axhline(5, color="#9a9a94", linewidth=1, linestyle=":", label="5 m (min_gap_m)")
    ax_map.set_aspect("equal")
    ax_map.set_title("top view (x forward, y left)")
    ax_v.set_ylabel("speed (m/s)")
    ax_gap.set_ylabel("gap to lead (m)")
    ax_err.set_ylabel("distance to lane center (m)")
    for ax in (ax_v, ax_gap, ax_err):
        ax.set_xlabel("time (s)")
        ax.axvline(BRAKE_AT_S, color="#eb6834", linewidth=1, linestyle="--")
    for ax in (ax_map, ax_v, ax_gap, ax_err):
        ax.grid(color="#e4e3dd", linewidth=0.8)
        ax.legend(frameon=False, fontsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / "a8_model_drive.png", dpi=110)
    print("图已保存：outputs/a8_model_drive.png")


if __name__ == "__main__":
    main()
