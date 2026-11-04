"""B2 第 1 步：把“一道题 + 一组旋钮”打包成一个任务（Job），跑完得到一行结果。

一个任务要写清三样，任何一台电脑拿到都能跑出一模一样的结果：
  题目参数（CutIn 的 5 个数）+ 考生的旋钮（预测几秒、确认几帧、噪声、延迟、算不算加速度）+ 随机种子。
任务本身不带结果；结果是 run_job 跑出来的一行，存进表里。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from scenarios.cut_in import CutIn


@dataclass(frozen=True)
class Job:
    """一个任务。frozen：打包好就不能改，跑多少遍都一样。"""
    question: int                 # 第几题（随机题库里的题号）
    scenario: CutIn               # 题目参数
    comes_in: bool                # 出题人知道的答案：它会不会进我的车道
    predict_s: float = 0.0        # 旋钮：往前看几秒
    confirm_frames: int = 1       # 旋钮：连续几帧才算数
    noise_y_m: float = 0.0        # 故障：横向位置噪声（米）
    delay_s: float = 0.0          # 故障：看到的路况晚几秒
    accel: bool = False           # 旋钮：预测算不算横向加速度
    seed: int = 0                 # 噪声的随机种子


def run_job(job: Job) -> dict:
    """跑一个任务，返回一行结果：任务里写的所有东西 + 撞没撞、最小车距、最猛刹车、漏刹 / 误刹。"""
    from examples.b_eval.b1_cut_in import run                      # 用到时再导入（考场很重，导入要几秒）
    from examples.b_eval.b1_cut_in_random import avoidable

    s = run(job.scenario, job.predict_s, delay_s=job.delay_s, noise_y_m=job.noise_y_m,
            seed=job.seed, confirm_frames=job.confirm_frames, accel=job.accel)
    knobs = {k: v for k, v in asdict(job).items() if k != "scenario"}
    return {
        **knobs, **asdict(job.scenario),
        "crashed": bool(s["crashed"]),
        "min_gap_m": float(s["min_gap_m"]),
        "hardest_brake_mps2": float(s["hardest_brake_mps2"]),
        "missed": bool(job.comes_in and s["crashed"] and avoidable(job.scenario)),
        "false_brake": bool(not job.comes_in and s["hardest_brake_mps2"] < -0.5),
    }
