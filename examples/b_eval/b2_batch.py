"""B2 第 1 步：批量跑——40 道随机加塞题 × 几组旋钮，一个任务一行，存成表（outputs/b2_jobs.csv）。

这一步先在一台电脑上一个一个顺序跑，看要多久；并行、超时、重试是后面几步。
运行（在项目根目录）：
    python -m examples.b_eval.b2_batch        一个一个跑
    python -m examples.b_eval.b2_batch 4      开 4 个进程同时跑（第 2 步）；跑完和一个一个跑的结果逐行比对
"""

from __future__ import annotations

import csv
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

from batch.jobs import Job, run_jobs
from examples.b_eval.b1_cut_in_random import N_EACH, SEED, sample_cut_in

np.seterr(divide="ignore")
OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"
PREDICT_S = [0.0, 0.5, 1.0]        # 旋钮 1：往前看几秒，三档
ACCEL = [False, True]              # 旋钮 2：匀速 / 匀加速，两种


def make_questions() -> list:
    """出题：和 B1 随机新题同一个种子，所以就是那 40 道。每道题记（题目, 会不会进来）。"""
    rng = random.Random(SEED)
    questions = []
    for _ in range(N_EACH):
        questions.append((sample_cut_in(rng, True), True))      # 前 20 道：会进来
    for _ in range(N_EACH):
        questions.append((sample_cut_in(rng, False), False))    # 后 20 道：不进来
    return questions


def make_jobs(questions: list) -> list[Job]:
    """排列组合：每道题 × 每档预测 × 每种方法 = 一个任务。"""
    jobs = []
    for n, (scenario, comes_in) in enumerate(questions, start=1):   # 第 n 道题（从 1 数）
        for p in PREDICT_S:                                           # 每档预测
            for a in ACCEL:                                           # 每种方法
                jobs.append(Job(question=n, scenario=scenario, comes_in=comes_in,
                                predict_s=p, accel=a, seed=n))
    return jobs


def all_columns(rows: list[dict]) -> list[str]:
    """所有行里出现过的列名合起来，按第一次出现的顺序排，不重复。
    卡死 / 报错的行没有结果那几列，所以表头不能只看第一行（11-09 发现：第 1 个任务卡死，整张表存不下来）。
    例子：[{"a": 1, "status": "timeout"}, {"a": 2, "missed": True, "status": "ok"}] → ["a", "status", "missed"]
    """
    columns = []
    for r in rows:
        for name in r:
            if name not in columns:
                columns.append(name)
    return columns


def save_csv(rows: list[dict], path: Path) -> None:
    """一个任务一行，存成表格文件（Excel 能直接打开）。某一行缺的列留空。"""
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns(rows))   # 表头 = 所有行出现过的列名
        writer.writeheader()
        writer.writerows(rows)
    print(f"结果表：{path}（{len(rows)} 行）")


def same_as_sequential(path: Path) -> None:
    """并行跑完，和一个一个跑的那张表逐行比对：结果必须一模一样。"""
    seq = OUT_DIR / "b2_jobs_1.csv"
    if not seq.exists():
        print("还没有一个一个跑的结果表（先跑一次不带数字的命令），没法比对。")
        return
    same = seq.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")
    print(f"和一个一个跑的结果逐行比对：{'一模一样' if same else '不一样！'}")


def print_summary(rows: list[dict]) -> None:
    """按旋钮分组，数漏刹和误刹。"""
    print()
    print("预测几秒  预测方法   漏刹  误刹")
    for p in PREDICT_S:
        for a in ACCEL:
            missed = false = 0
            for r in rows:
                if r["predict_s"] == p and r["accel"] == a:
                    missed += r["missed"]                  # True 当 1、False 当 0
                    false += r["false_brake"]
            print(f"  {p:.1f}     {'匀加速' if a else '匀速  '}    {missed:>3}   {false:>3}")


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 1        # 开几个进程；不写就是 1 = 一个一个跑
    jobs = make_jobs(make_questions())
    how = "一个一个跑" if workers == 1 else f"开 {workers} 个进程同时跑（这台电脑有 {os.cpu_count()} 个逻辑核）"
    print(f"{len(jobs)} 个任务（40 道题 × {len(PREDICT_S)} 档预测 × {len(ACCEL)} 种预测方法），{how}……")
    start = time.perf_counter()
    rows = run_jobs(jobs, workers)
    seconds = time.perf_counter() - start
    print(f"用了 {seconds:.0f} 秒，平均每个任务 {seconds / len(jobs):.2f} 秒。")
    path = OUT_DIR / f"b2_jobs_{workers}.csv"
    save_csv(rows, path)
    if workers > 1:
        same_as_sequential(path)
    print_summary(rows)


if __name__ == "__main__":
    main()
