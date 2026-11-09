"""B2：同一批任务改用 Ray 跑。

进程池只能在一台电脑上开考场；Ray 把“派活、收结果”这件事做成可以跨很多台电脑的，代码几乎不用改。
两种派法：
  task（任务）：一道题派一次，考完就散。run_jobs_ray
  actor（常驻工人）：先开好几个考场，一直开着，一道接一道地考。run_jobs_ray_actors
    —— CARLA 开一次（连服务器、加载地图）要几十秒，不能每道题都重开，所以要用常驻的。
没装 Ray 的电脑也能 import 这个文件：import ray 放在函数里面。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from batch.jobs import Job, run_job

ROOT = Path(__file__).resolve().parents[1]


def _start_ray(workers: int) -> None:
    """在本机开一个小集群，给它 workers 个 CPU（同时几个工人）。"""
    import ray

    # Ray 的工人是另外起的 Python 进程，要能 import 到本项目（batch、examples……），所以把项目根目录告诉它们
    os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
    start = time.perf_counter()
    ray.init(num_cpus=workers, include_dashboard=False, log_to_driver=False)
    print(f"  启动 Ray（{workers} 个工人）用了 {time.perf_counter() - start:.1f} 秒")


def open_exam_room(setup_s: float) -> None:
    """假装开一次考场要 setup_s 秒。HighwayEnv 开一次很快；CARLA 要连服务器、加载地图，几十秒。用 sleep 模拟这段时间。"""
    if setup_s > 0:
        time.sleep(setup_s)


def run_job_reopen(job: Job, setup_s: float = 0.0) -> dict:
    """task 的做法：每道题都重新开一次考场，再考。"""
    open_exam_room(setup_s)
    return run_job(job)


class Examiner:
    """常驻考场（Ray 里叫 actor）：创建时开一次考场，之后一道接一道地考，还记得自己考了几道。"""

    def __init__(self, setup_s: float = 0.0):
        open_exam_room(setup_s)       # 只在创建时开一次
        self.done = 0                 # 自己的状态：考了几道（task 做不到：考完就散，什么都不记得）

    def run(self, job: Job) -> dict:
        self.done += 1
        return run_job(job)

    def how_many(self) -> int:
        return self.done


def run_jobs_ray(jobs: list[Job], workers: int = 4, setup_s: float = 0.0) -> list[dict]:
    """task：一道题派一次，结果顺序和任务一样。setup_s > 0 时，每道题都要先等“开考场”。"""
    import ray

    _start_ray(workers)
    try:
        remote_job = ray.remote(run_job_reopen)              # 把函数变成“可以派给工人的任务”
        futures = []
        for job in jobs:
            futures.append(remote_job.remote(job, setup_s))  # 派出去，马上拿回一张“取件单”，不等它考完
        rows = ray.get(futures)                              # 凭取件单收结果，按派出去的顺序排好
    finally:
        ray.shutdown()                                       # 不管成功还是出错，都把这个小集群关掉
    return rows


def run_jobs_ray_actors(jobs: list[Job], workers: int = 4, setup_s: float = 0.0) -> tuple[list[dict], list[int]]:
    """actor：先开 workers 个常驻考场，任务轮流派给它们。返回（结果，每个考场考了几道）。"""
    import ray

    _start_ray(workers)
    try:
        remote_examiner = ray.remote(num_cpus=1)(Examiner)   # 把这个类变成“常驻工人”，每个占 1 个 CPU
        examiners = []
        for _ in range(workers):
            examiners.append(remote_examiner.remote(setup_s))   # 开考场：每个只开这一次
        futures = []
        for i, job in enumerate(jobs):
            examiner = examiners[i % workers]                # 轮流派：第 0 题给 0 号，第 1 题给 1 号……
            futures.append(examiner.run.remote(job))         # 同一个考场一次考一道，排队
        rows = ray.get(futures)
        count_futures = []
        for e in examiners:
            count_futures.append(e.how_many.remote())
        counts = ray.get(count_futures)
    finally:
        ray.shutdown()
    return rows, counts
