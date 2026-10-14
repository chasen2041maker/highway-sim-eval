"""CARLA 连接与同步模式。

用法：
    with CarlaSim(dt_s=0.05) as sim:
        ...
出了 with（包括中途报错）：删掉我们生成的东西，把服务器还原成原来的设置。
"""

from __future__ import annotations
import carla

class CarlaSim:
    def __init__(self,host: str = "localhost", port: int = 2000, dt_s: float = 0.05):
        self.host = host
        self.port = port
        self.dt_s = dt_s    # 每帧代表多少秒（仿真时间）
        self.client = None
        self.world = None
        self._original_settings = None     # 进门前服务器的设置，出门时还原
        self._actors = []      # 我们生成的车和传感器，出门时统一删掉

    def __enter__(self)-> "CarlaSim":
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(10.0)
        self.world = self.client.get_world()
        self._original_settings = self.world.get_settings()

        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = self.dt_s
        self.world.apply_settings(settings)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for actor in self._actors:
            actor.destroy()
        self._actors.clear()
        if self._original_settings is not None:
            self.world.apply_settings(self._original_settings)

    def spawn_ego(self, blueprint: str = "vehicle.tesla.model3", spawn_index: int = 0):
        """在地图第 spawn_index 号出生点放一辆车。出门时自动删掉。"""
        bp = self.world.get_blueprint_library().find(blueprint)
        spawn_point = self.world.get_map().get_spawn_points()[spawn_index]
        ego = self.world.spawn_actor(bp, spawn_point)
        self._actors.append(ego)    # 记进名单，__exit__ 会删它
        self.world.tick()            # 走一帧，车才真正出现
        return ego

    def tick(self) -> tuple[int, float]:
        """让世界走一帧，返回 (帧号, 仿真时间秒)。"""
        frame = self.world.tick()
        sim_time_s = self.world.get_snapshot().timestamp.elapsed_seconds
        return frame, sim_time_s

    def follow(self, actor, back_m: float = 8.0, up_m: float = 4.0) -> None:
        """把窗口的旁观镜头放到 actor 后方 back_m 米、高 up_m 米处，朝车头方向看。
        每帧调用一次，就是跟车视角。只影响画面，不影响仿真结果。"""
        tf = actor.get_transform()
        cam_loc = tf.transform(carla.Location(x=-back_m, z=up_m))
        self.world.get_spectator().set_transform(
            carla.Transform(cam_loc, carla.Rotation(pitch=-15, yaw=tf.rotation.yaw))
        )