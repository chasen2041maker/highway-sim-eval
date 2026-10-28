"""A8 真值版搬进 CARLA（回家待办 ③）：边拐弯边跟车，前车在弯里急刹。

和纯 Python 预演 examples/a8_model_drive.py 同一个结构：
  IDM 决定快慢（规划）→ 影子车车速 + PID 追它 → 踏板（纵向控制）；
  Pure Pursuit 打方向（横向控制）；新尺子 lateral_error_m 量离车道中心多远。
不同的是“车”换成了 CARLA 的车（有重量、刹车延迟、真的轮胎），路换成了 CARLA 地图里一个真的路口左转（程序自己在所有出生点里挑：前面先直 35–60 米、再左转）。

场景：挑出来的出生点起步，前面先直、再路口左转；两车都是 10 m/s、车距 25 米；
     前车进弯 5 米后以 −5 急刹，停在弯里。前车按剧本沿红线“滑”（关了物理，每帧摆到红线上），车速用剧本里的数（真值）。

运行（在项目根目录，CARLA 要开着）：
    python -m examples.a8_carla_drive 1          # PID 的 kp = 1
    python -m examples.a8_carla_drive 3          # kp = 3
    python -m examples.a8_carla_drive 1 hold     # 再加停车保持
纯 Python 对照（examples/a8_model_drive.py）：kp 1 → 最小车距 4.36 米、最猛刹车 −4.46；kp 3 → 4.97、−3.51；离中心最远 0.09–0.10 米。
"""

import math
import sys
import time

import carla

from ads.control import PID, find_lookahead_point, pure_pursuit_steer, to_pedals
from ads.planning import StopHold, idm_accel
from ads.vehicle import VehicleState
from evaluation.metrics import lateral_error_m
from sim.carla_client import CarlaSim
from sim.transforms import carla_to_ours

KP = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0   # PID 的 kp：命令行第一个数
USE_STOP_HOLD = "hold" in sys.argv                         # 命令行带 hold 就开停车保持

STRAIGHT_M = (35.0, 60.0)  # 挑路线：起点后先直 35–60 米再开始拐
TURN_DEG = (60.0, 120.0)   # 一共左转 60°–120°
SPACING_M = 0.5            # 红点间距
PATH_POINTS = 240          # 240 颗 × 0.5 米 = 120 米路线
START_MPS = 10.0           # 两车一开始都是 10 m/s
TARGET_MPS = 15.0          # 我想开到 15
START_GAP_M = 25.0         # 我的车头到前车车尾 25 米
WARMUP_S = 1.0             # 前 1 秒两车都被“推着”跑 10 m/s（滚动起步），然后 IDM 接手
LEAD_BRAKE_MPS2 = -5.0     # 前车急刹：每秒车速减 5
BRAKE_AFTER_TURN_M = 5.0   # 前车进弯 5 米后开始急刹
DURATION_S = 15.0          # IDM 接手后开 15 秒
LOOKAHEAD_M = 5.0          # Pure Pursuit 的 Ld（10-16 选的 5）
HOLD_BRAKE = 0.35          # 停车保持时踩住的刹车踏板


# ---------- 实验台（助手写的，不用敲）----------

def speed_of(car):
    v = car.get_velocity()
    return math.hypot(v.x, v.y)


def push(car, speed_mps):
    """滚动起步：不踩油门，直接把车速设成 speed_mps（沿车头方向）。"""
    car.set_target_velocity(car.get_transform().get_forward_vector() * speed_mps)


def build_path(start_wp):
    """红线：从 start_wp 沿车道每 0.5 米一颗，共 PATH_POINTS 颗；路口有几条路就有几个，取 [0]。
    返回 (CARLA 的 waypoint 列表, 我们坐标的 [(x, y)])；路走到头了 waypoint 列表会短一些。"""
    wps = [start_wp]
    while len(wps) < PATH_POINTS:
        nxt = wps[-1].next(SPACING_M)
        if not nxt:
            break
        wps.append(nxt[0])
    path = []
    for wp in wps:
        loc = wp.transform.location
        x, y, _ = carla_to_ours(loc.x, loc.y, 0.0)
        path.append((x, y))
    return wps, path


def pick_spawn(carla_map):
    """在地图所有出生点里挑第一个合适的：起点后先直 STRAIGHT_M 米、再左转 TURN_DEG 度。
    （10-28 前两版用出生点 0 猜路线，一次走成直行、一次起步就在拐，所以改成让程序自己找。）"""
    for idx, sp in enumerate(carla_map.get_spawn_points()):
        wps, path = build_path(carla_map.get_waypoint(sp.location))
        if len(wps) < PATH_POINTS:
            continue
        turn_s, total_turn = find_turn(wps)
        if STRAIGHT_M[0] <= turn_s <= STRAIGHT_M[1] and TURN_DEG[0] <= -total_turn <= TURN_DEG[1]:
            return idx, wps, path
    raise SystemExit("地图里没找到“先直 35–60 米、再左转”的出生点，把这行发给助手")


def find_turn(wps):
    """红线从哪开始拐弯（车头方向偏离起点超过 5°），一共转了多少度。"""
    def turned(wp):
        d = wp.transform.rotation.yaw - wps[0].transform.rotation.yaw
        return (d + 180.0) % 360.0 - 180.0          # 换到 −180 ~ 180
    turn_i = next((i for i, wp in enumerate(wps) if abs(turned(wp)) > 5.0), len(wps) - 1)
    return turn_i * SPACING_M, turned(wps[-1])


def pose_on_path(wps, s_m):
    """沿红线走 s_m 米的位置和朝向（在两颗红点之间按比例取），给前车用。"""
    i = min(int(s_m / SPACING_M), len(wps) - 2)
    f = min(1.0, s_m / SPACING_M - i)
    a, b = wps[i].transform, wps[i + 1].transform
    loc = carla.Location(x=a.location.x + f * (b.location.x - a.location.x),
                         y=a.location.y + f * (b.location.y - a.location.y),
                         z=a.location.z + f * (b.location.z - a.location.z) + 0.05)
    return carla.Transform(loc, a.rotation)


def summarize(log):
    """打分：每个数都带上“发生在第几秒”。"""
    t, gaps, errs, speeds, wants = log["t"], log["gap"], log["err"], log["speed"], log["want"]
    i_gap = gaps.index(min(gaps))
    i_err = errs.index(max(errs))
    i_want = wants.index(min(wants))
    n = round(0.5 / (t[1] - t[0]))                     # 0.5 秒有几帧
    real = [(speeds[k] - speeds[k - n]) / 0.5 for k in range(n, len(speeds))]
    i_real = real.index(min(real)) + n
    restarts, low = 0, False
    for v in speeds:
        if v < 1.0:
            low = True
        elif low:
            restarts, low = restarts + 1, False
    print(f"kp {KP:g}，停车保持{'开' if USE_STOP_HOLD else '关'}：")
    print(f"  最小车距 {gaps[i_gap]:.2f} 米（{t[i_gap]:.1f} 秒）｜最后停在 {gaps[-1]:.2f} 米｜{'撞了！' if min(gaps) <= 0 else '没撞'}")
    print(f"  IDM 最猛要 {wants[i_want]:.2f}（{t[i_want]:.1f} 秒）｜实际最猛 {real[i_real - n]:.2f}（0.5 秒平均，到 {t[i_real]:.1f} 秒）")
    print(f"  离车道中心最远 {errs[i_err]:.2f} 米（{t[i_err]:.1f} 秒）、平均 {sum(errs) / len(errs):.3f} 米｜停下后又起步 {restarts} 次")


# ---------- 主程序 ----------

with CarlaSim(dt_s=0.05) as sim:
    # 起点：程序在所有出生点里挑一个“先直、再左转”的
    spawn_index, wps, path = pick_spawn(sim.world.get_map())
    ego = sim.spawn_ego(spawn_index=spawn_index)
    turn_s, total_turn = find_turn(wps)
    print(f"出生点 {spawn_index}：路线 {len(path) * SPACING_M:.0f} 米；起点后 {turn_s:.1f} 米开始拐弯，"
          f"一共转了 {total_turn:.0f}°（CARLA 里负数 = 左转）")
    for wp in wps:
        sim.world.debug.draw_point(wp.transform.location + carla.Location(z=0.5), size=0.05,
                                   color=carla.Color(255, 0, 0), life_time=WARMUP_S + DURATION_S + 5)

    half_len = ego.bounding_box.extent.x
    max_steer_rad = math.radians(ego.get_physics_control().wheels[0].max_steer_angle)
    lead = sim.spawn_ahead(ego, START_GAP_M + 2 * half_len)
    lead.set_simulate_physics(False)                  # 前车不靠物理，每帧直接摆到红线上
    lead_s, lead_speed, brake_at = START_GAP_M + 2 * half_len, START_MPS, None

    shadow = START_MPS
    pid = PID(kp=KP, ki=0.5, u_max=1.0)
    hold = StopHold()
    log = {}

    for i in range(round((WARMUP_S + DURATION_S) / sim.dt_s)):
        t = i * sim.dt_s - WARMUP_S                   # IDM 接手那一刻 t = 0

        # 前车：按剧本沿红线开，进弯 5 米后急刹（先改车速，再挪位置）
        if t >= 0 and brake_at is None and lead_s >= turn_s + BRAKE_AFTER_TURN_M:
            brake_at = t
            print(f"—— {t:.1f} 秒：前车进弯 {BRAKE_AFTER_TURN_M:g} 米，开始急刹 ——")
        if brake_at is not None:
            lead_speed = max(0.0, lead_speed + LEAD_BRAKE_MPS2 * sim.dt_s)
        lead_s += lead_speed * sim.dt_s
        lead.set_transform(pose_on_path(wps, lead_s))

        if t < 0:                                      # 滚动起步：还没轮到 IDM
            push(ego, START_MPS)
        else:
            # ---------- 从这里开始手敲（聊天里的 ①–⑤，敲完删掉下面 raise 那一行）----------
            
            # ① 量：我的车在哪、朝哪、多快（换成我们的坐标）；离前车多远
            tf = ego.get_transform()
            x, y, heading = carla_to_ours(tf.location.x, tf.location.y, tf.rotation.yaw)
            speed = speed_of(ego)
            state = VehicleState(x_m=x, y_m=y, heading_rad=heading, speed_mps=speed)
            gap = ego.get_location().distance(lead.get_location()) - 2 * half_len

            # ② 规划：IDM 想要的加速度 → 影子车照着开
            want = idm_accel(speed, lead_speed, gap, TARGET_MPS)
            shadow = max(0.0, shadow + want * sim.dt_s)

            # ③ 纵向控制：PID 追影子车的车速 → 油门 / 刹车；停车保持接管时踩住刹车
            u = pid.update(shadow - speed, sim.dt_s)
            throttle, brake = to_pedals(u)
            if USE_STOP_HOLD and hold.update(speed, lead_speed, gap):
                pid.integral, pid.pre_error, shadow = 0.0, None, 0.0
                throttle, brake = 0.0, HOLD_BRAKE

            # ④ 横向控制：Pure Pursuit 算前轮转角 → CARLA 的 steer（右正，−1 ~ 1）
            tx, ty = find_lookahead_point(path, state, LOOKAHEAD_M)
            delta = pure_pursuit_steer(state, tx, ty)
            steer = max(-1.0, min(1.0, -delta / max_steer_rad))

            # ⑤ 踩下去；新尺子量离车道中心多远
            ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
            err = lateral_error_m(path, x, y)





            # ---------- 手敲到这里 ----------

            for key, value in (("t", t), ("gap", gap), ("speed", speed), ("want", want), ("err", err)):
                log.setdefault(key, []).append(value)
            if i % 10 == 0:                            # 每 0.5 秒看一次
                print(f"{t:4.1f} 秒  前车 {lead_speed:5.2f}  我 {speed:5.2f}  影子 {shadow:5.2f}  车距 {gap:5.2f}  "
                      f"IDM 要 {want:5.2f}  油门 {throttle:.2f}  刹车 {brake:.2f}  steer {steer:5.2f}  "
                      f"离中心 {err:.2f}  {'保持中' if hold.holding else ''}")

        sim.tick()
        sim.follow(ego)
        time.sleep(sim.dt_s)

    summarize(log)
