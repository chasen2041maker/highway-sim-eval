"""A3：在 CARLA 里用 Pure Pursuit 沿车道中心线开（速度用 PID）。"""
import math
import time
import sys
import carla
from ads.control import PID, to_pedals, pure_pursuit_steer, find_lookahead_point
from evaluation.metrics import lateral_error_m
from ads.vehicle import VehicleState
from sim.carla_client import CarlaSim
from sim.transforms import carla_to_ours, ours_to_carla

TARGET_MPS = 6.0  # 目标车速：要过路口拐弯，开慢点
LOOKAHEAD_M = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0  # 前视距离 Ld：命令行给，不给就用 5
DURATION_S = 12.0

with CarlaSim(dt_s=0.05) as sim:
    ego = sim.spawn_ego()
    # ① 这辆车的前轮最多能打多少度（CARLA 的 steer = 1 就是打到这个角度）
    max_steer_rad = math.radians(ego.get_physics_control().wheels[0].max_steer_angle)

    # 取路线：沿车道每 0.5 米一面旗子，共 80 米，画成红点
    wp = sim.world.get_map().get_waypoint(ego.get_location())   # 车脚下最近的那面旗子
    path = []
    for _ in range(160):
        loc = wp.transform.location
        x, y, _ = carla_to_ours(loc.x, loc.y, 0.0)
        path.append((x, y))
        sim.world.debug.draw_point(loc + carla.Location(z=0.5), size=0.05,
                                   color = carla.Color(255, 0, 0), life_time=DURATION_S + 5)
        wp = wp.next(0.5)[0]

    pid = PID(kp=1.0, ki=0.5, u_max=1.0)
    worst_m = 0.0  # 每秒打印的离红线距离里，最大的那个
    for i in range(round(DURATION_S / sim.dt_s)):
        # ② 把 CARLA 里车的状态换成我们的坐标，装进 A1 的 VehicleState
        tf = ego.get_transform()
        v = ego.get_velocity()
        x, y, heading = carla_to_ours(tf.location.x, tf.location.y, tf.rotation.yaw)
        state = VehicleState(x_m=x, y_m=y, heading_rad=heading, speed_mps=math.hypot(v.x, v.y))

        # 方向盘：找前视点 → 算前轮转角（我们的坐标，左转为正）
        tx, ty = find_lookahead_point(path, state, LOOKAHEAD_M)
        delta = pure_pursuit_steer(state, tx, ty)

        # ③ 换成 CARLA 的 steer：右转为正，所以加负号；再除以最大转角，变成 −1 到 1
        steer = max(-1.0, min(1.0, -delta/max_steer_rad))

        # 油门刹车：PID（第 ① 步调好的参数）
        u = pid.update(TARGET_MPS - state.speed_mps, sim.dt_s)
        throttle, brake = to_pedals(u)

        ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))

        #把前视点画成绿点，看车在追哪里（只给人看）
        cx, cy, _ = ours_to_carla(tx, ty, 0.0)
        sim.world.debug.draw_point(carla.Location(x=cx, y=cy, z=tf.location.z + 1.0),
                                   size=0.1, color=carla.Color(0, 255, 0), life_time=0.1)

        sim.tick()
        sim.follow(ego)
        time.sleep(sim.dt_s)

        if i % 20 == 19:
            off = lateral_error_m(path, x, y)
            worst_m = max(worst_m, off)
            print(f"{(i + 1) * sim.dt_s:4.1f} 秒  车速 {state.speed_mps:4.2f}  "
                  f"前轮 {math.degrees(delta):6.2f}°  steer {steer:5.2f}  离红线 {off:.2f} m")
    print(f"Ld {LOOKAHEAD_M} 米：每秒打印里离红线最大 {worst_m:.2f} m")