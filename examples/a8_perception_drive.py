"""A8：把“真值前车”换成“雷达看到的前车”（纯 Python 预演，A 块最后一课）。

场景和 a8_model_drive 一样：直道 40 m → 半径 20 m 左转 90° → 直道；两车都是 10 m/s、车距 25 米，
前车第 3 秒以 −5 急刹，停在弯里。另外在弯道入口的右边车道停了一辆车（不在我的车道上）。

真值版（a8_model_drive 第三种：PID + 停车保持）：IDM 用的车距、前车车速直接问模拟器要，等于开卷考试。
感知版（这个文件）：每 0.1 秒
  ① 假雷达扫一圈（A5 的 sim/fake_lidar）
  ② 去地面 → DBSCAN 分堆 → 画框（A5）
  ③ 多车跟踪（A6 的 MultiTracker）
  ④ 挑前车：在我前面、在我的车道里、最近的那条轨迹
  ⑤ 车距 = 框中心的距离 − 车长；前车车速 = 我的车速 + 沿视线方向的相对速度
  ⑥ 后面和真值版一模一样：IDM → 影子车 → PID + 停车保持；Pure Pursuit 打方向
阅卷永远用真值（车到底离前车多远、撞没撞），这是“考生只看传感器、阅卷看真相”。

这个实验要回答：
  1. 雷达看到的车距和真的差多少？往哪边差？
  2. 换成雷达以后，最小车距、最猛刹车和真值版比，变大还是变小？
  3. 右边车道停的那辆车，会不会被当成前车？

运行（项目根目录）：python -m examples.a8_perception_drive
"""

import math
from pathlib import Path

import numpy as np

from ads.control import PID, find_lookahead_point, pure_pursuit_steer
from ads.perception import cluster_points, cluster_to_box, remove_ground
from ads.planning import StopHold, idm_accel
from ads.tracking import MultiTracker
from ads.vehicle import VehicleState, step
from evaluation.metrics import lateral_error_m
from examples.a3_pure_pursuit import make_path
from examples.a8_model_drive import (CAR_LEN_M, DT_S, HOLD_DECEL_MPS2, LOOKAHEAD_M, MAX_ACCEL_MPS2, MAX_BRAKE_MPS2,
                                     SIM_TIME_S, SPACING_M, START_GAP_M, START_SPEED_MPS, TARGET_SPEED_MPS,
                                     lead_step, point_at, record)
from sim.fake_lidar import Box, scan

Z_THRESHOLD_M = -1.6       # A5 的去地面门槛
EPS_M = 1.0                # A5 的 DBSCAN 参数
MIN_SAMPLES = 5
CAR_W_M, CAR_H_M = 1.9, 1.5
LANE_HALF_M = 1.75         # 轨迹离我的路线中心线不到 1.75 米（半条车道），才算在我的车道里
PARKED_S_M = 36.0          # 停着的车：沿路线 36 米处……
PARKED_RIGHT_M = 3.5       # ……往右一条车道（3.5 米）
NO_LEAD_GAP_M = 1000.0     # 没看到前车：当成前面 1 公里都没车


def heading_at(path, s_m):
    """路线在 s_m 米处的朝向（前车沿路线开，车头就朝这个方向）。"""
    x0, y0 = point_at(path, s_m)
    x1, y1 = point_at(path, s_m + SPACING_M)
    return math.atan2(y1 - y0, x1 - x0)


def to_ego(ego, x_m, y_m):
    """地图坐标 → 我的车的坐标（x 向前、y 向左，原点在我车上，雷达就装在这）。"""
    dx, dy = x_m - ego.x_m, y_m - ego.y_m
    c, s = math.cos(ego.heading_rad), math.sin(ego.heading_rad)
    return c * dx + s * dy, -s * dx + c * dy


def to_map(ego, x_m, y_m):
    """我的车的坐标 → 地图坐标（to_ego 反过来）。"""
    c, s = math.cos(ego.heading_rad), math.sin(ego.heading_rad)
    return ego.x_m + c * x_m - s * y_m, ego.y_m + s * x_m + c * y_m


def parked_pose(path):
    """停着的那辆车在地图上的位置和朝向：路线 36 米处往右挪一条车道。"""
    x, y = point_at(path, PARKED_S_M)
    h = heading_at(path, PARKED_S_M)
    return x + PARKED_RIGHT_M * math.sin(h), y - PARKED_RIGHT_M * math.cos(h), h


def build_scene(path, ego, lead_s_m):
    """这一帧雷达面前有什么：前车 + 停着的车，都换到我的车的坐标里（模拟器干的活，算法看不到）。"""
    lx, ly = to_ego(ego, *point_at(path, lead_s_m))
    px, py, ph = parked_pose(path)
    px, py = to_ego(ego, px, py)
    return [Box("lead car", lx, ly, CAR_LEN_M, CAR_W_M, CAR_H_M, heading_at(path, lead_s_m) - ego.heading_rad),
            Box("parked car", px, py, CAR_LEN_M, CAR_W_M, CAR_H_M, ph - ego.heading_rad)]


def detect(points):
    """A5：去地面 → 分堆 → 画框，返回每个框的中心，形状 (D, 2)。"""
    kept, _ = remove_ground(points, Z_THRESHOLD_M)
    if len(kept) == 0:
        return np.zeros((0, 2))
    labels = cluster_points(kept, EPS_M, MIN_SAMPLES)
    if labels.max() < 0:
        return np.zeros((0, 2))
    return cluster_to_box(kept, labels)[:, :2]


def pick_lead(path, ego, tracks):
    """挑前车：在我前面（x > 0）、换回地图后离路线中心线不到半条车道、最近的那条轨迹。没有就返回 None。"""
    best, best_r = None, math.inf
    for t in tracks:
        x, y = t.xy
        if x <= 0:
            continue
        if lateral_error_m(path, *to_map(ego, x, y)) > LANE_HALF_M:
            continue
        r = math.hypot(x, y)
        if r < best_r:
            best, best_r = t, r
    return best


def simulate(use_lidar: bool):
    """跑一遍。use_lidar=False：真值版（开卷）；True：感知版（雷达 → 跟踪 → 挑前车）。"""
    path = make_path(SPACING_M)
    ego = VehicleState(speed_mps=START_SPEED_MPS)
    lead_s_m, lead_speed_mps = START_GAP_M + CAR_LEN_M, START_SPEED_MPS
    shadow_mps = START_SPEED_MPS
    pid = PID(kp=1.0, ki=0.5, u_max=MAX_ACCEL_MPS2)
    hold = StopHold()
    tracker = MultiTracker(gate_m=2.0, max_misses=10)
    log = {}

    for k in range(round(SIM_TIME_S / DT_S)):
        t_s = k * DT_S
        lead_x_m, lead_y_m = point_at(path, lead_s_m)
        true_gap_m = math.hypot(lead_x_m - ego.x_m, lead_y_m - ego.y_m) - CAR_LEN_M   # 阅卷用的真车距
        lead_id = 0
        if use_lidar:
            # ---------- 从这里开始手敲（①–⑤，完整代码在聊天里） ----------
            points, _ = scan(build_scene(path, ego, lead_s_m), seed=k)    # ① 扫一圈（第二个返回值是真值，不许看）
            det_xy = detect(points)                                        # ② 找框：每个框的中心
            tracker.step(det_xy, DT_S)                                     # ③ 跟踪：猜 → 配 → 管编号
            lead = pick_lead(path, ego, tracker.tracks)                    # ④ 挑前车
            if lead is None:
                gap_m, lead_v_mps = NO_LEAD_GAP_M, TARGET_SPEED_MPS        #    没看到：当成路是空的
            else:
                x, y = lead.xy
                r = math.hypot(x, y)
                v_rel = (x * lead.kx.x[1] + y * lead.ky.x[1]) / r          # ⑤ 沿视线方向的相对速度（负 = 在靠近我）
                gap_m = r - CAR_LEN_M                                      #    车距 = 框中心的距离 − 车长
                lead_v_mps = max(0.0, ego.speed_mps + v_rel)               #    前车车速 = 我的车速 + 相对速度
                lead_id = lead.id

            # ---------- 手敲到这里 ----------
        else:
            gap_m, lead_v_mps = true_gap_m, lead_speed_mps

        # 下面和 a8_model_drive 的“PID + 停车保持”一模一样
        want = idm_accel(ego.speed_mps, lead_v_mps, gap_m, TARGET_SPEED_MPS)
        shadow_mps = max(0.0, shadow_mps + want * DT_S)
        accel = pid.update(shadow_mps - ego.speed_mps, DT_S)
        accel = max(-MAX_BRAKE_MPS2, min(MAX_ACCEL_MPS2, accel))
        if hold.update(ego.speed_mps, lead_v_mps, gap_m):
            pid.integral, pid.pre_error, shadow_mps = 0.0, None, 0.0
            accel = -HOLD_DECEL_MPS2
        tx, ty = find_lookahead_point(path, ego, LOOKAHEAD_M)
        steer = pure_pursuit_steer(ego, tx, ty)
        record(log, t=t_s, gap=true_gap_m, seen_gap=gap_m if gap_m < NO_LEAD_GAP_M else math.nan,
               lead=lead_speed_mps, seen_lead=lead_v_mps if gap_m < NO_LEAD_GAP_M else math.nan,
               speed=ego.speed_mps, accel=accel, x=ego.x_m, y=ego.y_m, lead_id=lead_id,
               lead_x=lead_x_m, lead_y=lead_y_m)
        ego = step(ego, accel, steer, DT_S)
        lead_speed_mps, lead_s_m = lead_step(t_s, lead_speed_mps, lead_s_m)
    return path, log


def summarize(log, use_lidar):
    """打分（全用真值）+ 感知版多报几个“雷达看得准不准”。"""
    gaps, accels, ts = log["gap"], log["accel"], log["t"]
    i = gaps.index(min(gaps))
    restarts, low = 0, False
    for v in log["speed"]:
        if v < 1.0:
            low = True
        elif low:
            restarts, low = restarts + 1, False
    text = (f"最小车距 {gaps[i]:.2f} 米（{ts[i]:.1f} 秒）｜最猛刹车 {min(accels):.2f}｜停下后又起步 {restarts} 次｜"
            f"最后停在 {gaps[-1]:.2f} 米｜{'撞了！' if min(gaps) <= 0 else '没撞'}")
    if use_lidar:
        err = np.array(log["seen_gap"]) - np.array(gaps)
        verr = np.array(log["seen_lead"]) - np.array(log["lead"])
        seen = ~np.isnan(err)
        ids = sorted({j for j in log["lead_id"] if j})
        text += (f"\n    雷达车距 − 真车距：平均 {np.nanmean(err):+.2f}、最小 {np.nanmin(err):+.2f}、最大 {np.nanmax(err):+.2f} 米｜"
                 f"前车车速误差平均 {np.nanmean(np.abs(verr)):.2f} m/s｜没看到前车 {int((~seen).sum())} 帧｜"
                 f"当过前车的编号 {ids}")
    return text


def main():
    results = {}
    for use_lidar, name in ((False, "真值版"), (True, "感知版")):
        path, log = simulate(use_lidar)
        results[name] = log
        print(f"{name}：{summarize(log, use_lidar)}")
    plot(path, results)


# ---------- 以下是画图，助手写好的，不用手敲 ----------
def plot(path, results):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。")
        return
    truth, lidar = results["真值版"], results["感知版"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax_map, ax_gap, ax_v, ax_a = axes[0][0], axes[0][1], axes[1][0], axes[1][1]
    px, py = zip(*path)
    ax_map.plot(px, py, color="#d23b3b", linestyle="none", marker=".", markersize=2, label="lane center")
    ax_map.plot(truth["x"], truth["y"], color="#9a9a94", linewidth=2, label="me, truth version")
    ax_map.plot(lidar["x"], lidar["y"], color="#2a78d6", linewidth=2, linestyle="--", label="me, lidar version")
    ax_map.plot(lidar["lead_x"][-1], lidar["lead_y"][-1], "s", color="#eb6834", markersize=9, label="lead car stops here")
    x, y, _ = parked_pose(path)
    ax_map.plot(x, y, "s", color="#7a5af5", markersize=9, label="parked car (right lane)")
    ax_map.set_aspect("equal")
    ax_map.set_title("top view")
    ax_gap.plot(truth["t"], truth["gap"], color="#9a9a94", linewidth=2, label="truth version: real gap")
    ax_gap.plot(lidar["t"], lidar["gap"], color="#2a78d6", linewidth=2, label="lidar version: real gap")
    ax_gap.plot(lidar["t"], lidar["seen_gap"], color="#2a78d6", linewidth=1, linestyle=":", label="lidar version: gap it sees")
    ax_gap.axhline(5, color="#9a9a94", linewidth=1, linestyle=":")
    ax_gap.set_ylabel("gap to lead (m)")
    ax_v.plot(lidar["t"], lidar["lead"], color="#eb6834", linewidth=2, label="lead speed (truth)")
    ax_v.plot(lidar["t"], lidar["seen_lead"], color="#eb6834", linewidth=1, linestyle=":", label="lead speed it sees")
    ax_v.plot(truth["t"], truth["speed"], color="#9a9a94", linewidth=2, label="my speed, truth version")
    ax_v.plot(lidar["t"], lidar["speed"], color="#2a78d6", linewidth=2, label="my speed, lidar version")
    ax_v.set_ylabel("speed (m/s)")
    ax_a.plot(truth["t"], truth["accel"], color="#9a9a94", linewidth=2, label="truth version")
    ax_a.plot(lidar["t"], lidar["accel"], color="#2a78d6", linewidth=2, label="lidar version")
    ax_a.set_ylabel("accel (m/s^2)")
    for ax in (ax_gap, ax_v, ax_a):
        ax.set_xlabel("time (s)")
    for ax in (ax_map, ax_gap, ax_v, ax_a):
        ax.grid(color="#e4e3dd", linewidth=0.8)
        ax.legend(frameon=False, fontsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / "a8_perception_drive.png", dpi=110)
    print("图已保存：outputs/a8_perception_drive.png")


if __name__ == "__main__":
    main()
