"""模拟器入口：本项目里只有这个文件直接创建 HighwayEnv 环境。

策略只拿到 obs、只返回动作；评测只读运行记录。以后换模拟器（比如 nuPlan），主要改这里。
"""
from __future__ import annotations

import os

# 评测用的场景配置。改这里会影响所有实验结果，改之前想清楚旧结果要不要重跑。
CONFIG = {
    "lanes_count": 4,
    "vehicles_count": 20,          # 背景车数量
    "duration": 40,                # 一局最长 40 秒（仿真时间）
    "simulation_frequency": 5,     # 物理每秒更新 5 次
    "policy_frequency": 1,         # 每秒决策 1 次：一次 env.step = 5 个物理小步
    "observation": {               # 5 行 × [presence, x, y, vx, vy]；第 0 行是自车（绝对值），其余相对自车
        "type": "Kinematics",
        "normalize": False,        # 不归一化：单位直接是米、米/秒
    },
    "action": {"type": "DiscreteMetaAction"},  # 0 左变道 1 保持 2 右变道 3 加速 4 减速
}

ENV_ID = "highway-fast-v0"


def make_env(render: bool = False):
    """创建环境。render=True 时打开窗口，按真实时间播放。"""
    if not render:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # 不开窗口时，pygame 不需要显示器
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    import gymnasium as gym
    import highway_env  # noqa: F401  导入后 gymnasium 才认识 highway-fast-v0

    config = dict(CONFIG, real_time_rendering=render)
    return gym.make(ENV_ID, render_mode="human" if render else None, config=config)
