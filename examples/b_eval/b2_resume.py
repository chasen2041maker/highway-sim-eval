"""B2：边考边存 + 断点续跑。

同样 240 个任务（b2_batch 那批），每交一张卷就往 outputs/b2_jobs_resume.jsonl 末尾追加一行。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b2_resume 16 --fresh --stop-after 100   删掉旧日志从头考，考到第 100 张卷时假装断电
    python -m examples.b_eval.b2_resume 16                              再跑：日志里有的跳过，只考剩下的
全部考完后存成 outputs/b2_jobs_resume.csv，和一个一个跑的逐字比对。
"""

from __future__ import annotations

import sys
import time

import numpy as np

from batch.resume import PowerCut, code_fingerprint, load_done, run_jobs_resumable
from examples.b_eval.b2_batch import OUT_DIR, make_jobs, make_questions, same_as_sequential, save_csv

np.seterr(divide="ignore")


def main():
    args = sys.argv[1:]
    workers = int(args[0]) if args and args[0].isdigit() else 4
    stop_after = None
    if "--stop-after" in args:
        stop_after = int(args[args.index("--stop-after") + 1])
    log = OUT_DIR / "b2_jobs_resume.jsonl"
    OUT_DIR.mkdir(exist_ok=True)
    if "--fresh" in args:
        log.unlink(missing_ok=True)                    # 从头考：删掉旧日志
    jobs = make_jobs(make_questions())
    print(f"{len(jobs)} 个任务，开 {workers} 个进程，边考边存到 {log.name}")
    start = time.perf_counter()
    try:
        rows, n_run = run_jobs_resumable(jobs, log, workers=workers, timeout_s=60, retries=1, stop_after=stop_after)
    except PowerCut as e:
        print(f"  {e}。日志里现在有 {len(load_done(log, code_fingerprint()))} 个交卷的（用了 {time.perf_counter() - start:.0f} 秒）")
        print("  再跑一次，去掉 --fresh 和 --stop-after，就接着考")
        return
    print(f"  这次考了 {n_run} 个，用了 {time.perf_counter() - start:.0f} 秒")
    save_csv(rows, OUT_DIR / "b2_jobs_resume.csv")            # 完整的表：带 status / error / attempts
    results_only = []                                          # 一个一个跑的那张表没有这三列，去掉再比
    for r in rows:
        plain = {}
        for k, v in r.items():
            if k not in ("status", "error", "attempts"):
                plain[k] = v
        results_only.append(plain)
    path = OUT_DIR / "b2_jobs_resume_results_only.csv"
    save_csv(results_only, path)
    same_as_sequential(path)


if __name__ == "__main__":
    main()
