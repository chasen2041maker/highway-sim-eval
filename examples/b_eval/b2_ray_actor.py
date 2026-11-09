"""B2：常驻考场（Ray actor）。

假装开一次考场要 SETUP_S 秒（CARLA 连服务器、加载地图要几十秒），同样 240 个任务比两种派法：
  每道题都重开（task）vs 每个工人只开一次、一直开着（actor）。
两种的结果都要和一个一个跑的逐字一样。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b2_ray_actor 16
"""

from __future__ import annotations

import sys
import time

import numpy as np

from batch.ray_jobs import run_jobs_ray, run_jobs_ray_actors
from examples.b_eval.b2_batch import OUT_DIR, make_jobs, make_questions, same_as_sequential, save_csv

np.seterr(divide="ignore")
SETUP_S = 1.0                      # 假装开一次考场要几秒


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = make_jobs(make_questions())
    print(f"{len(jobs)} 个任务、{workers} 个工人，假装开一次考场要 {SETUP_S:g} 秒")

    print("\n① 每道题都重开考场（task）")
    start = time.perf_counter()
    rows = run_jobs_ray(jobs, workers, setup_s=SETUP_S)
    print(f"  一共用了 {time.perf_counter() - start:.0f} 秒（含启动 Ray）")
    path = OUT_DIR / "b2_jobs_ray_task_reopen.csv"
    save_csv(rows, path)
    same_as_sequential(path)

    print("\n② 常驻考场，每个只开一次（actor）")
    start = time.perf_counter()
    rows, counts = run_jobs_ray_actors(jobs, workers, setup_s=SETUP_S)
    print(f"  一共用了 {time.perf_counter() - start:.0f} 秒（含启动 Ray）")
    print(f"  每个考场考了几道：{counts}")
    path = OUT_DIR / "b2_jobs_ray_actor.csv"
    save_csv(rows, path)
    same_as_sequential(path)


if __name__ == "__main__":
    main()
