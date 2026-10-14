"""A3：在 CARLA 里用 PID 把车速控制到目标值（直线，不打方向盘）。"""
import math
import time
import carla
from ads.control import PID,to_pedals
from sim.carla_client import CarlaSim

TARGET_MPS = 8.0
DURATION_S = 8.0

with CarlaSim(dt_s=0.05) as sim:
    ego = sim.spawn_ego(spawn_index=0)
    pid = PID(kp=1.0 ,ki=0.2)
    top = 0.0
    for i in range(round(DURATION_S/ sim.dt_s)):
        v = ego.get_velocity()      # 1. 看车速
        speed = math.hypot(v.x, v.y)               # 2. PID 算 u        
        u = pid.update(TARGET_MPS - speed,sim.dt_s)        # 3. 换成油门 / 刹车
        throttle, brake = to_pedals(u)
        ego.apply_control(carla.VehicleControl(throttle=throttle,brake=brake))
        sim.tick()          # 4. 世界走一帧
        sim.follow(ego)
        time.sleep(sim.dt_s)
        top = max(top, speed)
        if i % 20 == 19:
            print(f"{(i + 1) * sim.dt_s:4.1f} 秒  车速 {speed:5.2f} m/s  "
                  f"u={u:6.2f}  油门 {throttle:.2f}  刹车 {brake:.2f}")
    print(f"最高车速 {top:.2f} m/s（目标 {TARGET_MPS}）")