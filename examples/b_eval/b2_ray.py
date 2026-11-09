"""B2：和第 2 步同样的 240 个任务（40 道题 × 3 档预测 × 2 种方法），改用 Ray 跑。

要看两件事：结果和一个一个跑的是不是逐字一样；比进程池快还是慢（进程池 16 个进程是 16 秒）。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b2_ray 16        16 个工人
"""

from __future__ import annotations

import sys
import time

import numpy as np

from batch.ray_jobs import run_jobs_ray
from examples.b_eval.b2_batch import OUT_DIR, make_jobs, make_questions, same_as_sequential, save_csv

np.seterr(divide="ignore")


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = make_jobs(make_questions())
    print(f"{len(jobs)} 个任务，用 Ray 跑……")
    start = time.perf_counter()
    rows = run_jobs_ray(jobs, workers)
    seconds = time.perf_counter() - start
    print(f"一共用了 {seconds:.0f} 秒（含启动 Ray）。")
    path = OUT_DIR / f"b2_jobs_ray_{workers}.csv"
    save_csv(rows, path)
    same_as_sequential(path)


if __name__ == "__main__":
    main()
