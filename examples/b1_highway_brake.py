"""B 块第 1 步：在 HighwayEnv 里考一道“前车急刹”——最小闭环（题目 → 考场 → 考生 → 阅卷）。

和 A4 同一道题：两车都 10 m/s、车距 25 米，前车第 5 秒以 -5 m/s² 急刹到停；我用 IDM 跟车（最猛 -8）。
不同的是：A4 的世界是我们自己写的几行代码，这里换成别人写的模拟器 HighwayEnv。
  - 考生（IDM 司机）只看 obs（模拟器给的“眼睛看到的”），只交出一个加速度；
  - 阅卷只看模拟器里的真实状态（运行记录），不看考生的草稿纸。

运行（在项目根目录）：
    python -m examples.b1_highway_brake           不开窗口，打印分数
    python -m examples.b1_highway_brake --show    打开窗口看
"""

from __future__ import annotations

import os
import sys

from ads.planning import idm_accel

# ---------- ① 题目：场景参数（和 A4 一样） ----------
DT_S = 0.1                 # 每 0.1 秒：考生看一次、决定一次、世界往前走一步
SIM_TIME_S = 15.0
START_SPEED_MPS = 10.0     # 两车起步车速
START_GAP_M = 25.0         # 我的车头到前车车尾
BRAKE_AT_S = 5.0           # 前车第 5 秒开始急刹
LEAD_BRAKE_MPS2 = -5.0
TARGET_SPEED_MPS = 15.0    # IDM 想开到的车速
MAX_BRAKE_MPS2 = 8.0       # 我最猛能刹多少
CAR_LENGTH_M = 5.0         # HighwayEnv 里每辆车都是 5 米长

# ---------- ② 考场：把 HighwayEnv 摆成这道题 ----------
def make_brake_scenario(show: bool = False):
    """建一条没有别的车的 3 车道直路，自车在中间车道，前方 25 米放一辆前车。返回 (env, 前车)。"""
    if not show:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import gymnasium as gym
    import highway_env  # noqa: F401  导入后 gymnasium 才认识 highway-v0
    from highway_env.vehicle.kinematics import Vehicle

    config = {
        "lanes_count": 3,
        "vehicles_count": 0,                    # 不要随机背景车：这道题只有两辆车
        "initial_lane_id": 1,                   # 自车在中间车道
        "duration": SIM_TIME_S,
        "simulation_frequency": round(1 / DT_S),    # 物理每秒 10 步
        "policy_frequency": round(1 / DT_S),        # 考生每秒决定 10 次：一次 env.step = 一个物理步
        "observation": {"type": "Kinematics", "normalize": False},   # 米、米/秒，不归一化
        "action": {"type": "ContinuousAction", "longitudinal": True, "lateral": False,
                   "acceleration_range": [-MAX_BRAKE_MPS2, MAX_BRAKE_MPS2]},   # 只管油门刹车，-1~1 对应 -8~8
        "real_time_rendering": show,
    }
    env = gym.make("highway-v0", render_mode="human" if show else None, config = config)
    env.reset(seed=0)

    world = env.unwrapped
    ego = world.vehicle
    ego.speed = START_SPEED_MPS
    lead_x = ego.position[0] + CAR_LENGTH_M + START_GAP_M   # 位置是车的中心：中心差 = 车长 + 车距
    lead = Vehicle(world.road, position=[lead_x, ego.position[1]], heading=ego.heading, speed=START_SPEED_MPS)
    world.road.vehicles.append(lead)
    return env, lead

# ---------- ③ 考生：IDM 司机，只看 obs ----------
def idm_driver(obs) -> float:
    """obs 第 0 行是自车 [有车, x, y, vx, vy]（绝对值），第 1 行是最近的车（相对自车）。返回想要的加速度。"""
    ego_speed = obs[0][3]
    if obs[1][0] == 0:               # 前面没车：只按目标车速开
        return idm_accel(ego_speed, ego_speed, 1e9, TARGET_SPEED_MPS)
    gap_m = obs[1][1] - CAR_LENGTH_M         # 相对 x 是中心差，减掉一个车长才是车距
    lead_speed = ego_speed + obs[1][3]       # 相对速度 + 我的车速 = 前车车速
    return idm_accel(ego_speed, lead_speed, gap_m, TARGET_SPEED_MPS)

def to_action(accel: float, speed: float) -> list[float]:
    """加速度 → HighwayEnv 的动作（-1~1）。刹到 0 就不再往下刹：HighwayEnv 的车会倒着开。"""
    accel = max(-MAX_BRAKE_MPS2, accel, -speed / DT_S)
    return [accel / MAX_BRAKE_MPS2]

# ---------- ④ 闭环：每 0.1 秒 看 → 想 → 动 → 世界走一步 ----------
def run(show: bool = False) -> dict:
    env, lead = make_brake_scenario(show)
    world = env.unwrapped
    ego = world.vehicle
    obs = world.observation_type.observe()         #摆完车重新“看”一眼（reset 给的 obs 是摆车之前的）
    log = {"t": [], "gap": [], "ego_v": [], "lead_v": [], "accel": []}
    crashed = False
    try:
        for k in range(round(SIM_TIME_S / DT_S)):
            t_s = k * DT_S
            accel = idm_driver(obs)              # 考生：看 obs，交一个加速度
            action = to_action(accel,ego.speed)
            lead_a = LEAD_BRAKE_MPS2 if t_s >= BRAKE_AT_S else 0.0    # 剧本：前车第 5 秒起急刹
            lead.action = {"steering": 0.0, "acceleration": max(lead_a, -lead.speed / DT_S)}
            # 记录：用模拟器里的真实状态，不用考生看到的 obs
            log["t"].append(t_s)
            log["gap"].append(lead.position[0] - ego.position[0] - CAR_LENGTH_M)
            log["ego_v"].append(ego.speed)
            log["lead_v"].append(lead.speed)
            log["accel"].append(action[0] * MAX_BRAKE_MPS2)
            obs, reward, terminated, truncated, info = env.step(action)
            if info["crashed"]:
                crashed = True
                break
    finally: 
        env.close()
    return score(log, crashed)

# ---------- ⑤ 阅卷：只看运行记录 ----------
def score(log: dict, crashed: bool) -> dict:
    """最小车距、最猛刹车、最小 TTC（还有几秒撞上）、撞没撞。"""
    ttcs = [g / (ev - lv) for g, ev, lv in zip(log["gap"], log["ego_v"], log["lead_v"]) if ev - lv > 0.1]
    i = log["gap"].index(min(log["gap"]))
    return {"min_gap_m": log["gap"][i], "at_s": log["t"][i], "hardest_brake_mps2": min(log["accel"]),
            "min_ttc_s": min(ttcs) if ttcs else float("inf"), "crashed": crashed}


def main():
    s = run(show="--show" in sys.argv)
    print(f"最小车距 {s['min_gap_m']:.2f} 米（第 {s['at_s']:.1f} 秒）")
    print(f"我最猛的刹车 {s['hardest_brake_mps2']:.2f} m/s²")
    print(f"最小 TTC {s['min_ttc_s']:.2f} 秒")
    print("撞了！" if s["crashed"] else "没撞")


if __name__ == "__main__":
    main()