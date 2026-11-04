import time
import carla

client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()

original = world.get_settings()        # 记下原来的设置，最后还原
settings = world.get_settings()
settings.synchronous_mode = True       # 世界等我们下令才走
settings.fixed_delta_seconds = 0.05    # 每走一步 = 仿真里的 0.05 秒
world.apply_settings(settings)

try:
    a = world.get_snapshot()
    time.sleep(1)
    b = world.get_snapshot()
    print("同步模式下等 1 秒：帧号差", b.frame - a.frame)

    for _ in range(20):
        world.tick()                   # 让世界走一步
    c = world.get_snapshot()
    print("tick 20 次：帧号差", c.frame - b.frame,
          "仿真时间差", round(c.timestamp.elapsed_seconds - b.timestamp.elapsed_seconds, 3), "秒")
finally:
    world.apply_settings(original)     # 还原成异步，否则服务器会一直停着等人下令
    print("已还原为异步模式")