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
    # 考场崩了重开要几秒（Windows 上要起一个新的 Python 进程、重新导入考场）。重考的题别立刻发过去，隔 1 秒再发
    os.environ.setdefault("RAY_task_retry_delay_ms", "1000")
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

    def run(self, job: Job, extra_s: float = 0.0, crash_mark: str = "") -> dict:
        """考一道。extra_s > 0：假装这道题特别慢（多花 extra_s 秒），用来看慢题会不会堵住别人。
        crash_mark 不是空的：假装考场在这道题上崩了（像 CARLA 闪退）——只崩一次，崩之前留个记号文件，重考时就不崩了。"""
        if crash_mark and not os.path.exists(crash_mark):
            Path(crash_mark).touch()                # 留记号：只崩这一次
            os._exit(1)                             # 整个工人进程直接没了，来不及交卷
        if extra_s > 0:
            time.sleep(extra_s)
        self.done += 1
        return run_job(job)

    def run_numbered(self, i: int, job: Job, extra_s: float = 0.0, crash_mark: str = "") -> tuple[int, dict]:
        """考一道，连同它是第几个任务一起交回（谁空谁领时，收回来的顺序是乱的，要靠这个编号排回去）。"""
        return i, self.run(job, extra_s, crash_mark)

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


def run_jobs_ray_actors(jobs: list[Job], workers: int = 4, setup_s: float = 0.0,
                        extra_s: list[float] | None = None, pull: bool = False,
                        crash_at: int | None = None, crash_mark: str = "",
                        max_restarts: int = 0) -> tuple[list[dict], list[int]]:
    """actor：先开 workers 个常驻考场，再把任务派给它们。返回（结果，每个考场考了几道），结果顺序和任务一样。
    pull = False：轮流派（第 i 题给 i % workers 号），一开始就排好队；
    pull = True ：谁空谁领（Ray 的 ActorPool），哪个考场考完了，再给它下一道。
      要用 map_unordered：有序的 map 必须按任务顺序收卷，前面的慢题没收，后面考完的考场也空不出来，
      结果和轮流派一样（11-09 实测：每个考场还是 15 道）。
    extra_s：每道题假装多花几秒（None = 都不多花）。
    crash_at：第几个任务（从 0 数）假装把考场弄崩（只崩一次，记号文件 crash_mark）。
    max_restarts：考场崩了 Ray 自动重开几次；重开后，崩的时候没考完的那道题自动再考。0 = 不重开，整批报错停下。
      重开期间送过去的题会撞上“考场暂时不在”（ActorUnavailableError），每撞一次算用掉一次重试，
      所以重试次数给 10、每次隔 1 秒（11-09 实测：只给 1 次，重开还没好就用完了，整批停下）。"""
    import ray
    from ray.util import ActorPool

    if extra_s is None:
        extra_s = [0.0] * len(jobs)
    _start_ray(workers)
    try:
        task_retries = 10 if max_restarts > 0 else 0
        remote_examiner = ray.remote(num_cpus=1, max_restarts=max_restarts,        # 把这个类变成“常驻工人”，每个占 1 个 CPU；
                                     max_task_retries=task_retries)(Examiner)   # 崩了自动重开，没考完的题等它重开好再考
        examiners = []
        for _ in range(workers):
            examiners.append(remote_examiner.remote(setup_s))   # 开考场：每个只开这一次
        if pull:
            pool = ActorPool(examiners)

            def give(examiner, item):                        # 把一道题交给一个空着的考场
                i, job, extra, mark = item
                return examiner.run_numbered.remote(i, job, extra, mark)

            items = []
            for i, (job, extra) in enumerate(zip(jobs, extra_s)):
                mark = crash_mark if i == crash_at else ""
                items.append((i, job, extra, mark))
            rows = [None] * len(jobs)
            for i, row in pool.map_unordered(give, items):   # 谁先考完先收谁，收了它就马上空出来领下一道
                rows[i] = row                                # 按编号放回原来的位置
        else:
            futures = []
            for i, job in enumerate(jobs):
                examiner = examiners[i % workers]            # 轮流派：第 0 题给 0 号，第 1 题给 1 号……
                mark = crash_mark if i == crash_at else ""
                futures.append(examiner.run.remote(job, extra_s[i], mark))   # 同一个考场一次考一道，排队
            rows = ray.get(futures)
        count_futures = []
        for e in examiners:
            count_futures.append(e.how_many.remote())
        counts = ray.get(count_futures)
    finally:
        ray.shutdown()
    return rows, counts
