"""B2 第 3 步：故意混进三个坏任务，看批量跑会不会被拖垮（超时、重试、记失败）。

三个坏任务（题号 901–903，题目随便借一道正常的）：
  901 卡死：一直不交卷（睡一个小时）
  902 报错：每次都崩
  903 偶发：第一次崩、第二次正常（像 CARLA 偶尔断线）
运行（在项目根目录）：
    python -m examples.b_eval.b2_faults
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from batch.jobs import run_job, run_jobs_safe
from examples.b_eval.b2_batch import make_jobs, make_questions

np.seterr(divide="ignore")
FLAKY_MARK = Path(__file__).resolve().parents[2] / "outputs" / "b2_flaky_903.mark"   # 记“903 已经崩过一次”


def misbehaving_run_job(job):
    """正常任务照常考；901–903 故意捣乱。要放在文件最外层，别的进程才找得到它。"""
    if job.question == 901:
        time.sleep(3600)                                   # 卡死
    if job.question == 902:
        raise RuntimeError("考场崩了")                      # 每次都崩
    if job.question == 903 and not FLAKY_MARK.exists():
        FLAKY_MARK.touch()                                 # 留个记号，下次就正常
        raise ConnectionError("偶发：和考场断线了")
    return run_job(job)


def main():
    FLAKY_MARK.parent.mkdir(exist_ok=True)
    FLAKY_MARK.unlink(missing_ok=True)                     # 每次演示都从“903 还没崩过”开始
    good = make_jobs(make_questions())[:12]                # 12 个正常任务（第 1、2 题）
    bad = [replace(good[0], question=q) for q in (901, 902, 903)]
    jobs = good[:6] + bad + good[6:]                       # 坏任务夹在中间
    print(f"{len(jobs)} 个任务（12 个正常 + 3 个坏的），开 4 个进程，每个任务最多等 10 秒，报错重试 1 次……")
    start = time.perf_counter()
    rows = run_jobs_safe(jobs, workers=4, timeout_s=10, retries=1, fn=misbehaving_run_job)
    print(f"整批用了 {time.perf_counter() - start:.0f} 秒，{len(rows)} 行都收回来了。")
    print()
    print("题号  状态      试了几次  原因")
    for r in rows:
        print(f"{r['question']:>4}  {r['status']:<8}  {r['attempts']:>4}      {r['error']}")


if __name__ == "__main__":
    main()
