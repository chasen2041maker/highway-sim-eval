"""B2：轮流派 vs 谁空谁领（Ray 的 ActorPool）。

同样 240 个任务、16 个常驻考场。假装有 15 道题特别慢（每道多花 SLOW_S 秒），
而且它们正好是第 0、16、32……题——轮流派时全都派给 0 号考场。
比一比：轮流派（一开始就排好队）和谁空谁领（哪个考场空了再给它下一道），整批多久、每个考场考了几道。
两种的结果都要和一个一个跑的逐字一样。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b2_ray_pool 16
"""

from __future__ import annotations

import sys
import time

import numpy as np

from batch.ray_jobs import run_jobs_ray_actors
from examples.b_eval.b2_batch import OUT_DIR, make_jobs, make_questions, same_as_sequential, save_csv

np.seterr(divide="ignore")
SLOW_S = 2.0                       # 慢题多花几秒


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = make_jobs(make_questions())
    extra_s = []
    for i in range(len(jobs)):
        if i % workers == 0:
            extra_s.append(SLOW_S)          # 第 0、16、32……题是慢题
        else:
            extra_s.append(0.0)
    n_slow = 0
    for e in extra_s:
        if e > 0:
            n_slow += 1
    print(f"{len(jobs)} 个任务、{workers} 个常驻考场，其中 {n_slow} 道慢题，每道多花 {SLOW_S:g} 秒")

    for pull, name, file_name in ((False, "① 轮流派", "b2_jobs_ray_roundrobin.csv"),
                                  (True, "② 谁空谁领（ActorPool）", "b2_jobs_ray_pool.csv")):
        print(f"\n{name}")
        start = time.perf_counter()
        rows, counts = run_jobs_ray_actors(jobs, workers, extra_s=extra_s, pull=pull)
        print(f"  一共用了 {time.perf_counter() - start:.0f} 秒（含启动 Ray）")
        print(f"  每个考场考了几道：{counts}")
        path = OUT_DIR / file_name
        save_csv(rows, path)
        same_as_sequential(path)


if __name__ == "__main__":
    main()
