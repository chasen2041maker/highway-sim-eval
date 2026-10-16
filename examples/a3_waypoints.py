"""A3：看看 CARLA 地图里的车道中心线（路点）。"""
import time
import carla
from sim.carla_client import CarlaSim
from sim.transforms import carla_to_ours

with CarlaSim(dt_s=0.05) as sim:
    ego = sim.spawn_ego()
    sim.follow(ego, back_m = 12, up_m = 8)             # 镜头拉高一点，看得远
    carla_map = sim.world.get_map()
    wp = carla_map.get_waypoint(ego.get_location())   # 车脚下最近的那面旗子

    path = []
    for _ in range(30):
        loc = wp.transform.location
        x, y, _ = carla_to_ours(loc.x, loc.y, wp.transform.rotation.yaw)
        path.append((x, y))
        sim.world.debug.draw_point(loc + carla.Location(z=0.5), size=0.1,
                                   color=carla.Color(255, 0, 0), life_time=15.0)
        wp = wp.next(2.0)[0]

    for _ in range(100):
        sim.tick()
        time.sleep(sim.dt_s)

    for i in (0, 10, 20, 29):
        print(f"第 {i:2d} 面旗子（我们的坐标）：x={path[i][0]:.2f}  y={path[i][1]:.2f}")