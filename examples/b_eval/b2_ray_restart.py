"""B2：考场崩了怎么办（Ray actor 自动重开）。

同样 240 个任务、16 个常驻考场、谁空谁领。第 CRASH_AT 个任务假装把考场弄崩（整个工人进程直接没了，像 CARLA 闪退），只崩一次。
  ① 不重开：看整批会怎样
  ② 自动重开 1 次（max_restarts=1）：Ray 重开那个考场，崩的时候没考完的那道题自动再考一次
结果要和一个一个跑的逐字一样。

11-09 笔记本（Windows，Ray 2.60）实测：① 一个考场崩了，整批报错停下，一行结果都拿不到。
② 自动重开没救回来：先是重试只给 1 次、考场还在重开就用完了（ActorUnavailableError，已改成 10 次、隔 1 秒）；
改完以后本机集群的管理员（raylet）被判定失联、所有考场一起没了（ActorDiedError），16 个和 4 个考场都一样，不是太忙。
Ray 在 Windows 上是试验性支持；真的仿真平台跑在 Linux 上，② 留到 Linux / WSL2 再试。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b2_ray_restart 16
"""

from __future__ import annotations

import sys
import time

import numpy as np

from batch.ray_jobs import run_jobs_ray_actors
from examples.b_eval.b2_batch import OUT_DIR, make_jobs, make_questions, same_as_sequential, save_csv

np.seterr(divide="ignore")
CRASH_AT = 100                     # 第 101 个任务把考场弄崩


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = make_jobs(make_questions())
    mark = OUT_DIR / "b2_ray_crash.mark"
    print(f"{len(jobs)} 个任务、{workers} 个常驻考场、谁空谁领；第 {CRASH_AT + 1} 个任务把考场弄崩（只崩一次）")

    for restarts, name in ((0, "① 不重开"), (1, "② 崩了自动重开 1 次")):
        print(f"\n{name}")
        mark.unlink(missing_ok=True)                    # 删掉上次的记号，保证这次会崩
        start = time.perf_counter()
        try:
            rows, counts = run_jobs_ray_actors(jobs, workers, pull=True, crash_at=CRASH_AT,
                                               crash_mark=str(mark), max_restarts=restarts)
        except Exception as e:
            print(f"  整批报错停下：{type(e).__name__}（用了 {time.perf_counter() - start:.0f} 秒，一行结果都没拿到）")
            continue
        print(f"  一共用了 {time.perf_counter() - start:.0f} 秒（含启动 Ray）")
        print(f"  每个考场考了几道：{counts}（加起来 {sum(counts)}）")
        path = OUT_DIR / "b2_jobs_ray_restart.csv"
        save_csv(rows, path)
        same_as_sequential(path)
    mark.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
