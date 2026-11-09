"""B2：边考边存 + 断点续跑。

以前是全部考完才一次存表：中途断了（关了窗口、电脑休眠、断电、程序崩了），已经考完的也全丢。
现在每交一张卷，就往日志文件末尾追加一行（JSON Lines：一行一个 JSON，各行的列可以不一样）。
整批中途断了，再跑同一条命令：先读日志，已经交卷（status 是 ok）的任务跳过，只考剩下的。
任务的“身份证”就是任务单本身（题目 + 旋钮 + 种子）。同一张任务单考几次结果都一样（幂等），所以跳过它是安全的。
"""

from __future__ import annotations

import json
from pathlib import Path

from batch.jobs import Job, job_fields, run_job, run_jobs_safe


class PowerCut(Exception):
    """假装断电：这次考到第 stop_after 张卷时，整批突然停下（用来演示断点续跑）。"""


def job_key(job: Job) -> str:
    """任务的身份证：把任务单上所有格子按名字排好，拼成一串文字。任务单一样，身份证就一样。"""
    return json.dumps(job_fields(job), sort_keys=True)


def load_done(log_path: Path) -> dict:
    """读日志，返回 {身份证: 那一行结果}，只要 status 是 ok 的（卡死 / 报错的下次重考）。
    日志不存在就是空的；断电时最后一行可能只写了一半，读不出来就跳过它。"""
    done = {}
    if not log_path.exists():
        return done
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "ok":
                done[row["job_key"]] = row
    return done


def run_jobs_resumable(jobs: list[Job], log_path: Path, workers: int = 4, timeout_s: float = 30.0,
                       retries: int = 1, fn=run_job, stop_after: int | None = None,
                       progress_every: int = 0) -> tuple[list[dict], int]:
    """边考边存：日志里已经交卷的跳过，剩下的每交一张就追加进日志。
    返回（全部结果，按任务顺序排好；这次真正考了几个）。stop_after：这次考到第几张卷时假装断电。"""
    done = load_done(log_path)
    todo = []
    for job in jobs:
        if job_key(job) not in done:
            todo.append(job)
    print(f"  日志里已经交卷 {len(jobs) - len(todo)} 个，这次考剩下的 {len(todo)} 个")

    new = {}
    with log_path.open("a", encoding="utf-8") as log:
        def save(job, row):                                        # 每收回一张卷，马上记一行
            key = job_key(job)
            new[key] = row
            log.write(json.dumps({**row, "job_key": key}, ensure_ascii=False) + "\n")
            log.flush()                                            # 马上交给系统写进硬盘，不在程序里攒着
            if stop_after is not None and len(new) >= stop_after:
                raise PowerCut(f"假装断电：这次考到第 {len(new)} 张卷时停下")

        run_jobs_safe(todo, workers, timeout_s, retries, fn, progress_every, on_row=save)

    rows = []
    for job in jobs:                                               # 按任务顺序拼回整张表：这次考的 + 日志里以前考的
        key = job_key(job)
        if key in new:
            row = dict(new[key])
        else:
            row = dict(done[key])
        row.pop("job_key", None)
        rows.append(row)
    return rows, len(todo)
