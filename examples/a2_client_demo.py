import math
import carla
from sim.carla_client import CarlaSim
from sim.transforms import carla_to_ours
import time

with CarlaSim(dt_s=0.05) as sim:
    ego = sim.spawn_ego()
    for i in range(60):
        ego.apply_control(carla.VehicleControl(throttle=0.5, steer=0.1))
        frame, sim_t = sim.tick()
        time.sleep(sim.dt_s)   # ← 新加：每走一帧等 0.05 秒，和现实同速
        if i % 20 == 19:
            t = ego.get_transform()
            v = ego.get_velocity()
            x, y, h = carla_to_ours(t.location.x, t.location.y, t.rotation.yaw)
            print(f"帧 {frame}  仿真时间 {sim_t:.2f}  "
                  f"我们的坐标 x={x:.2f} y={y:.2f} 角度={h:.3f} rad  车速={math.hypot(v.x, v.y):.2f} m/s")
print("出了 with：车已自动删除，服务器已还原")