"""A4 进 CARLA：前车按剧本开（10 m/s，第 5 秒以 -5 急刹到停），我用 IDM 跟在后面。
和纯 Python 版 examples/a4_follow.py 同一个场景，最后比两边的数字。"""
import math
import time
import carla
from ads.control import to_pedals
from ads.planning import idm_accel
from sim.carla_client import CarlaSim

SPAWN_INDEX = 80          # 前面 178 米直路（tool_find_straight 找的）
TARGET_MPS = 15.0         # 我想开 15，前车只开 10
START_MPS = 10.0          # 两辆车都从 10 m/s 开始
START_GAP_M = 25.0        # 我的车头到前车车尾 25 米
WARMUP_S = 1.0            # 前 1 秒两辆车都被“推着”跑 10 m/s（滚动起步），然后 IDM 接手
BRAKE_AT_S = 5.0          # IDM 接手后第 5 秒，前车开始急刹
LEAD_BRAKE_MPS2 = -5.0    # 前车每秒车速减 5，2 秒停下
DURATION_S = 12.0         # IDM 接手后开 12 秒

def push(car, speed_mps):
    """剧本：不踩油门，直接把车速设成 speed_mps（沿车头方向）。只给前车和滚动起步用。"""
    car.set_target_velocity(car.get_transform().get_forward_vector() * speed_mps)

def speed_of(car):
    v = car.get_velocity()
    return math.hypot(v.x, v.y)

with CarlaSim(dt_s=0.05) as sim:
    ego = sim.spawn_ego(spawn_index=SPAWN_INDEX)
    half_len = ego.bounding_box.extent.x              # 半个车长（车中心到车头）
    lead = sim.spawn_ahead(ego,START_GAP_M + 2 * half_len)    # 前车也是 Model 3：车中心距 = 车距 + 两个半车长
    lead_speed = START_MPS
    min_gap, hardest, real_hardest, last_speed = 99.0, 0.0, 0.0, START_MPS

    for i in range(round((WARMUP_S + DURATION_S) / sim.dt_s)):
        t = i * sim.dt_s - WARMUP_S    # IDM 接手那一刻 t = 0

        # ① 前车：按剧本开
        if t >= BRAKE_AT_S:
            lead_speed = max(0.0, lead_speed + LEAD_BRAKE_MPS2 * sim.dt_s)
        push(lead,lead_speed)

        # ② 量车距：两车中心的距离 − 两个半车长
        gap = ego.get_location().distance(lead.get_location()) - 2 * half_len
        speed = speed_of(ego)

        if t < 0:      # 滚动起步：还没轮到 IDM
            push(ego, START_MPS)
            accel, throttle, brake = 0.0, 0.0, 0.0
        else:          # ③ IDM 算加速度 → ④ 直接当踏板
            accel = idm_accel(speed, speed_of(lead), gap, TARGET_MPS)
            throttle, brake = to_pedals(accel)
            ego.apply_control(carla.VehicleControl(throttle=throttle,brake=brake))
            min_gap = min(min_gap, gap)
            hardest = min(hardest, accel)

        if i % 10 == 0:           # 每 0.5 秒看一次
            real = (speed - last_speed) / 0.5      # 过去 0.5 秒，车速实际每秒变了多少
            last_speed = speed
            if t >= 0:
                real_hardest = min(real_hardest, real)
                print(f"{t:4.1f} 秒  前车 {speed_of(lead):5.2f}  我 {speed:5.2f}  车距 {gap:5.2f}  "
                      f"IDM 要 {accel:5.2f}  油门 {throttle:.2f}  刹车 {brake:.2f}  实际 {real:5.2f}")
        sim.tick()
        sim.follow(ego)
        time.sleep(sim.dt_s)
    print(f"最小车距 {min_gap:.2f} 米，IDM 最猛要 {hardest:.2f}，实际最猛 {real_hardest:.2f} m/s²")
    print("撞了！" if min_gap <= 0 else "没撞")