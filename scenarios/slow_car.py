"""逻辑场景：慢车挡路。

三层：
  功能场景：高速上，我的车道前方有一辆慢车，一直慢慢开（不刹车、不变道）。
  逻辑场景：下面 RANGES 里每个数的范围。
  具体场景：SlowCar(...) 三个数都填好的一道题。

前面两道题考“会不会刹”；这道题真正想考的是“被堵住以后怎么办”。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

CAR_LENGTH_M = 5.0


@dataclass(frozen=True)
class SlowCar:
    """一道具体的题：开考那一刻的三个数。"""
    gap_m: float = 40.0             # 车距：我的车头到慢车车尾
    ego_speed_mps: float = 15.0     # 我的车速
    slow_speed_mps: float = 8.0     # 慢车车速（一直不变）


RANGES = {
    "gap_m": (10.0, 100.0),
    "ego_speed_mps": (10.0, 15.0),
    "slow_speed_mps": (3.0, 15.0),
}


def is_valid(sc: SlowCar) -> bool:
    """慢车要真比我慢，否则这道题考的不是“慢车挡路”。"""
    return sc.slow_speed_mps < sc.ego_speed_mps


def build(sc: SlowCar, dt_s: float, sim_time_s: float, max_brake_mps2: float, show: bool = False):
    """3 车道直路，我在中间车道，同一车道前方 gap_m 处放一辆慢车。返回 (env, 慢车)。"""
    if not show:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import gymnasium as gym
    import highway_env  # noqa: F401
    from highway_env.vehicle.kinematics import Vehicle

    config = {
        "lanes_count": 3, "vehicles_count": 0, "initial_lane_id": 1, "duration": sim_time_s,
        "simulation_frequency": round(1 / dt_s), "policy_frequency": round(1 / dt_s),
        "observation": {"type": "Kinematics", "normalize": False},
        "action": {"type": "ContinuousAction", "longitudinal": True, "lateral": False,
                   "acceleration_range": [-max_brake_mps2, max_brake_mps2]},
        "real_time_rendering": show,
    }
    env = gym.make("highway-v0", render_mode="human" if show else None, config=config)
    env.reset(seed=0)
    world = env.unwrapped
    ego = world.vehicle
    ego.speed = sc.ego_speed_mps
    slow = Vehicle(world.road, position=[ego.position[0] + CAR_LENGTH_M + sc.gap_m, ego.position[1]],
                   heading=0.0, speed=sc.slow_speed_mps)
    world.road.vehicles.append(slow)
    return env, slow
