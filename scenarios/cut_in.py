"""逻辑场景：邻车加塞。

三层：
  功能场景：高速上，旁边车道一辆比我慢的车突然切到我前面。
  逻辑场景：下面 RANGES 里每个数的范围。
  具体场景：CutIn(...) 四个数都填好的一道题。

四个数都是“它开始切进来那一刻”的，所以它第 0 秒就开始切（10-30 前车急刹的教训：参数定在关键事件那一刻）。
cut_time_s = 0 表示它不切进来，一直在旁边车道开（“陪跑”题：用来考我会不会白刹车）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ads.planning import lane_change_d

CAR_LENGTH_M = 5.0          # HighwayEnv 里每辆车都是 5 米长
LANE_WIDTH_M = 4.0          # HighwayEnv 的车道宽 4 米


@dataclass(frozen=True)
class CutIn:
    """一道具体的题：它开始切进来那一刻的四个数。"""
    gap_m: float = 10.0             # 纵向车距：我的车头到它的车尾
    ego_speed_mps: float = 15.0     # 我的车速
    cut_speed_mps: float = 10.0     # 它的车速（比我慢才危险）
    cut_time_s: float = 2.0         # 它用几秒从旁边车道挪到我的车道；0 = 不切进来（陪跑）


# 逻辑场景：每个数能取的范围（B2 批量跑时在这里面取数）
RANGES = {
    "gap_m": (3.0, 40.0),
    "ego_speed_mps": (5.0, 30.0),
    "cut_speed_mps": (5.0, 30.0),
    "cut_time_s": (1.0, 5.0),
}


def build(sc: CutIn, dt_s: float, sim_time_s: float, max_brake_mps2: float, show: bool = False):
    """把一道题摆进 HighwayEnv：3 车道直路，我在中间车道，它在旁边车道（屏幕上方那条）、我前方 gap_m。返回 (env, 它)。"""
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
    x = ego.position[0] + CAR_LENGTH_M + sc.gap_m
    cutter = Vehicle(world.road, position=[x, ego.position[1] - LANE_WIDTH_M], heading=0.0, speed=sc.cut_speed_mps)
    world.road.vehicles.append(cutter)
    return env, cutter


def cutter_y(sc: CutIn, t_s: float, y_side: float, y_mine: float) -> float:
    """它在第 t_s 秒的横向位置：用 A7 的五次多项式 lane_change_d，cut_time_s 秒从旁边车道挪到我的车道。"""
    if sc.cut_time_s <= 0:
        return y_side                     # 陪跑：一直在旁边车道
    d, _, _, _ = lane_change_d(t_s, sc.cut_time_s, y_mine - y_side)
    return y_side + d
