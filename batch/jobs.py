"""B2 第 1 步：把“一道题 + 一组旋钮”打包成一个任务（Job），跑完得到一行结果。

一个任务要写清三样，任何一台电脑拿到都能跑出一模一样的结果：
  题目参数（CutIn 的 5 个数）+ 考生的旋钮（预测几秒、确认几帧、噪声、延迟、算不算加速度）+ 随机种子。
任务本身不带结果；结果是 run_job 跑出来的一行，存进表里。
"""

from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
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
        "min_ttc_s": float(s["min_ttc_s"]),                          # B4 加：还有几秒撞上（最小）
        "max_jerk_mps3": float(s["max_jerk_mps3"]),                  # B4 加：刹得多急（最大急动度）
        "missed": bool(job.comes_in and s["crashed"] and avoidable(job.scenario)),
        "false_brake": bool(not job.comes_in and s["hardest_brake_mps2"] < -0.5),
    }


def run_jobs(jobs: list[Job], workers: int = 1) -> list[dict]:
    """跑一批任务，返回一样多行的结果，顺序和任务一样。
    workers = 1：一个一个跑；workers > 1：开 workers 个进程同时跑（进程池），每个进程有自己的一份考场。"""
    rows = []
    if workers == 1:
        for job in jobs:
            rows.append(run_job(job))
        return rows
    with ProcessPoolExecutor(max_workers=workers) as pool:          # 开 workers 个进程
        for row in pool.map(run_job, jobs, chunksize=8):            # 任务按顺序发出去（8 个一包），结果按顺序收回来
            rows.append(row)
    return rows


def job_fields(job: Job) -> dict:
    """任务单上写的所有格子：旋钮那几列 + 题目 5 列（失败的任务没有结果，也要留下这些）。"""
    fields = {}
    for k, v in asdict(job).items():
        if k != "scenario":
            fields[k] = v
    fields.update(asdict(job.scenario))
    return fields


def run_jobs_safe(jobs: list[Job], workers: int = 4, timeout_s: float = 30.0, retries: int = 1, fn=run_job,
                  progress_every: int = 0, on_row=None) -> list[dict]:
    """跑一批任务，不让一个坏任务拖垮整批。每个任务都有一行，status 写结果：
      ok：正常交卷；error：报错，重试 retries 次还报错；timeout：等它超过 timeout_s 秒没交卷（卡死），不重试。
    退出 with 时进程池被关掉，卡死的进程也一起关掉。
    progress_every > 0：每收回这么多个任务，打印一行进度（任务多、要跑几十分钟时用）。
    on_row：每收回一个任务就调一次 on_row(job, row)，比如马上把这一行存进硬盘（边考边存，见 batch/resume.py）。"""
    rows = []
    start = time.perf_counter()
    with multiprocessing.Pool(workers) as pool:
        pending = []
        for job in jobs:                                              # ① 全部任务先发出去
            pending.append(pool.apply_async(fn, (job,)))
        for job, res in zip(jobs, pending):                           # ② 按顺序一个一个收
            attempts = 1
            while True:
                try:
                    row = {**res.get(timeout=timeout_s), "status": "ok", "error": ""}
                    break
                except multiprocessing.TimeoutError:                  # ③ 等太久：记超时，接着收下一个
                    row = {**job_fields(job), "status": "timeout", "error": f"等了 {timeout_s:.0f} 秒没交卷"}
                    break
                except Exception as e:                                # ④ 报错：还有机会就重发一次
                    if attempts <= retries:
                        attempts += 1
                        res = pool.apply_async(fn, (job,))
                        continue
                    row = {**job_fields(job), "status": "error", "error": f"{type(e).__name__}: {e}"}
                    break
            row["attempts"] = attempts
            rows.append(row)
            if on_row is not None:
                on_row(job, row)
            if progress_every > 0 and len(rows) % progress_every == 0:
                print(f"  收回 {len(rows)} / {len(jobs)} 个（{time.perf_counter() - start:.0f} 秒）")
    return rows
