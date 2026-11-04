import math
import time
import carla

from sim.transforms import carla_to_ours

client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()

original = world.get_settings()
settings = world.get_settings()
settings.synchronous_mode = True
settings.fixed_delta_seconds = 0.05
world.apply_settings(settings)

ego = None
try:
    bp = world.get_blueprint_library().find("vehicle.tesla.model3")   # 车型
    spawn = world.get_map().get_spawn_points()[0]                     # 地图自带的第 0 个出生点
    ego = world.spawn_actor(bp, spawn)
    world.tick()                                                      # 走一帧，车才真正出现

    # 把观察镜头放到车后 8 米、高 4 米的位置，方便在窗口里看到它
    tf = ego.get_transform()
    cam_loc = tf.transform(carla.Location(x=-8, z=4))
    world.get_spectator().set_transform(
        carla.Transform(cam_loc, carla.Rotation(pitch=-15, yaw=tf.rotation.yaw)))

    for i in range(60):                                               # 60 帧 × 0.05 = 3 秒
        ego.apply_control(carla.VehicleControl(throttle=0.5, steer=0.1))
        world.tick()
        time.sleep(0.05)                                              # 只是为了让你看清楚，不影响仿真
        if i % 20 == 19:                                              # 每 1 秒打印一次
            t = ego.get_transform()
            v = ego.get_velocity()
            speed = math.hypot(v.x, v.y)
            sim_t = world.get_snapshot().timestamp.elapsed_seconds
            print(f"仿真时间 {sim_t:.2f}  x={t.location.x:.2f}  y={t.location.y:.2f}  "
                  f"yaw={t.rotation.yaw:.2f}  车速={speed:.2f} m/s")
            ox, oy, oh = carla_to_ours(t.location.x, t.location.y, t.rotation.yaw)    # ← 新加
            print(f"    我们的坐标  x={ox:.2f}  y={oy:.2f}  角度={oh:.3f} rad")        # ← 新加
finally:
    if ego is not None:
        ego.destroy()                                                 # 删掉车，否则下次运行会越堆越多
    world.apply_settings(original)
    print("车已删除，已还原为异步模式")