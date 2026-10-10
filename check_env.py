"""检查环境能不能跑：建环境，一直保持（IDLE）跑 10 步，打印每步车速、奖励、有没有撞车。

运行：
    python check_env.py           不开窗口
    python check_env.py --show    打开窗口看
"""
from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

from sim_env import ENV_ID, make_env


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "未找到"


def main() -> None:
    env = make_env(render="--show" in sys.argv)
    try:
        obs, info = env.reset(seed=0)
        print("highway-env", package_version("highway-env"), "| gymnasium", package_version("gymnasium"))
        print("环境：", ENV_ID, " obs 形状：", obs.shape, " 动作空间：", env.action_space)
        for step in range(10):
            obs, reward, terminated, truncated, info = env.step(1)  # 1 = IDLE
            print(f"第 {step + 1:2d} 步  车速 {info['speed']:5.1f} m/s  奖励 {reward:.3f}  撞车 {info['crashed']}")
            if terminated or truncated:
                break
    finally:
        env.close()
    print("环境正常。")


if __name__ == "__main__":
    main()
