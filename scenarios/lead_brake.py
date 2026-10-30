"""逻辑场景：前车急刹。

三层（ASAM / PEGASUS 的叫法）：
  功能场景：高速上，前车突然急刹。
  逻辑场景：下面 RANGES 里每个数的范围。
  具体场景：LeadBrake(...) 四个数都填好的一道题。

四个数都是“前车开始刹车那一刻”的，所以前车第 0 秒就刹。
（10-30 发现：前车第 5 秒才刹的话，IDM 会先把车距调回 20 米左右，起步车距就白设了。）
"""

from __future__ import annotations

import os
from dataclasses import dataclass

CAR_LENGTH_M = 5.0          # HighwayEnv 里每辆车都是 5 米长


@dataclass(frozen=True)
class LeadBrake:
    """一道具体的题：前车开始刹车那一刻的四个数。"""
    gap_m: float = 25.0      # 车距：我的车头到前车车尾
    ego_speed_mps: float = 10.0       # 我的车速
    lead_speed_mps: float = 10.0      # 前车车速
    lead_decel_mps2: float = 5.0      # 前车刹多猛（正数，-5 m/s² 就写 5）


# 逻辑场景：每个数能取的范围（B2 批量跑时在这里面取数）
RANGES = {
    "gap_m": (5.0, 40.0),
    "ego_speed_mps": (5.0, 30.0),
    "lead_speed_mps": (5.0, 30.0),
    "lead_decel_mps2": (2.0, 8.0),
}


def build(sc: LeadBrake, dt_s: float, sim_time_s: float, max_brake_mps2: float, show: bool = False):
    """把一道题摆进 HighwayEnv：3 车道直路，没有别的车，我在中间车道，前车在正前方。返回 (env, 前车)。"""
    if not show:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import gymnasium as gym
    import highway_env  # noqa: F401
    from highway_env.vehicle.kinematics import Vehicle

    config = {
        "lanes_count": 3,
        "vehicles_count": 0,
        "initial_lane_id": 1,
        "duration": sim_time_s,
        "simulation_frequency": round(1 / dt_s),
        "policy_frequency": round(1 / dt_s),
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
    lead_x = ego.position[0] + CAR_LENGTH_M + sc.gap_m
    lead = Vehicle(world.road, position=[lead_x, ego.position[1]], heading=ego.heading, speed=sc.lead_speed_mps)
    world.road.vehicles.append(lead)
    return env, lead
