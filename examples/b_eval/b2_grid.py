"""B2 第 4 步：多旋钮网格——一大批随机加塞题 × 每一组旋钮，找漏刹和误刹的平衡点。

五个旋钮分两种：
  考生的设置（工程师能选）：往前看几秒、连续几帧确认、匀速 / 匀加速
  路况（工程师选不了，只能每种都考一遍）：横向噪声、延迟
每道题 × 每一组 = 一个任务，开很多进程跑，一个任务一行，存成表。
边考边存：每交一张卷就往同名的 .jsonl 日志追加一行；中途断了，再跑同一条命令只补没考完的（11-09 加）。
这里只管跑和存表；从表里找平衡点是下一步。

运行（在项目根目录）：
    python -m examples.b_eval.b2_grid 50       先出 50 道题试跑，看要多久
    python -m examples.b_eval.b2_grid 1000     1000 道题（会进来、不进来各一半）
    python -m examples.b_eval.b2_grid 1000 8   第二个数 = 开几个进程（不写就用全部逻辑核）
    python -m examples.b_eval.b2_grid 1000 16 2   第三个数 = 种子（不写就是 1）：种子 2 = 另一批 1000 道新题，
                                                  存成 b2_grid_1000_seed2.csv，不会盖掉种子 1 那张表
    python -m examples.b_eval.b2_grid 1000 16 2 --fresh   删掉这一批的日志，从头考（比如想重新计时）
    python -m examples.b_eval.b2_grid 1000 16 2 --stop-after 5000   考到第 5000 张卷时假装断电（演示用）
日志在 outputs/b2_grid_<n>[_seed<种子>].jsonl。代码改过以后，旧日志里的结果自动不算数（代码指纹对不上）。
"""
from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

import numpy as np

from batch.jobs import Job
from batch.manifest import snapshot, write_manifest
from batch.resume import PowerCut, code_fingerprint, load_done, run_jobs_resumable
from examples.b_eval.b1_cut_in_random import sample_cut_in
from examples.b_eval.b2_batch import save_csv

np.seterr(divide="ignore")
OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"

SEED = 1                              # 默认种子：和 B1 那 40 道（种子 0）不是同一批题；命令行第三个数可以换

# 考生的设置：工程师能选
PREDICT_S = [0.0, 0.5, 1.0, 1.5]      # 往前看几秒
CONFIRM_FRAMES = [1, 3]               # 连续几帧都挑出它，才算前车
ACCEL = [False, True]                 # 预测按匀速（False）还是匀加速（True）往外推

# 路况：工程师选不了，每种都考一遍
NOISE_Y_M = [0.0, 0.2]                # 别的车横向位置的噪声（米）
DELAY_S = [0.0, 0.3]                  # 考生看到的路况晚几秒

TIMEOUT_S = 60                        # 一个任务等多久没交卷，就算卡死
RETRIES = 1                           # 报错以后再试几次

def make_questions(n: int, seed: int = SEED) -> list:
    """出 n 道新题。会进来、不进来交替出（第 1、3、5……道会进来），所以 50 道试跑的题就是 1000 道的前 50 道。
    种子不同 = 另一批题；种子一样 = 每次出的题一模一样。"""
    rng = random.Random(seed)
    questions = []
    for i in range(n):
        comes_in = (i % 2 == 0)
        questions.append((sample_cut_in(rng, comes_in), comes_in))
    return questions

def make_knob_sets() -> list[dict]:
    """把五个旋钮排列组合，每一组 = 一种路况 + 一个考生设置。"""
    knob_sets = []
    for noise in NOISE_Y_M:
        for delay in DELAY_S:
            for p in PREDICT_S:
                for c in CONFIRM_FRAMES:
                    for a in ACCEL:
                        knob_sets.append({"noise_y_m": noise, "delay_s": delay,
                                          "predict_s": p, "confirm_frames": c, "accel": a})
    return knob_sets

def make_jobs(questions: list, knob_sets: list[dict]) -> list[Job]:
    """每道题 × 每一组旋钮 = 一个任务。噪声的种子 = 题号，同一道题换旋钮时噪声一样。"""
    jobs = []
    for n, (scenario, comes_in) in enumerate(questions, start=1):
        for k in knob_sets:
            jobs.append(Job(question=n, scenario=scenario, comes_in=comes_in,
                            predict_s=k["predict_s"], confirm_frames=k["confirm_frames"],
                            noise_y_m=k["noise_y_m"], delay_s=k["delay_s"],
                            accel=k["accel"], seed=n))
    return jobs

def table_path(n: int, seed: int) -> Path:
    """结果表存在哪：种子 1 还叫 b2_grid_<n>.csv（和以前一样），别的种子名字后面加 _seed<种子>。"""
    if seed == SEED:
        return OUT_DIR / f"b2_grid_{n}.csv"
    return OUT_DIR / f"b2_grid_{n}_seed{seed}.csv"


def parse_args(argv: list[str]) -> tuple[int, int, int, bool, int | None]:
    """命令行：几道题、几个进程、种子（三个数，后面的可以不写），再加 --fresh、--stop-after N。"""
    numbers = []
    fresh = False
    stop_after = None
    i = 0
    while i < len(argv):
        if argv[i] == "--fresh":
            fresh = True
        elif argv[i] == "--stop-after":
            stop_after = int(argv[i + 1])
            i += 1
        else:
            numbers.append(int(argv[i]))
        i += 1
    n = numbers[0] if len(numbers) > 0 else 50                    # 出几道题
    workers = numbers[1] if len(numbers) > 1 else os.cpu_count()  # 开几个进程
    seed = numbers[2] if len(numbers) > 2 else SEED               # 出题的种子
    return n, workers, seed, fresh, stop_after


def main():
    n, workers, seed, fresh, stop_after = parse_args(sys.argv[1:])
    knob_sets = make_knob_sets()
    jobs = make_jobs(make_questions(n, seed), knob_sets)
    path = table_path(n, seed)
    log = path.with_suffix(".jsonl")                                      # 边考边存的日志，和表同名
    path.parent.mkdir(exist_ok=True)
    if fresh:
        log.unlink(missing_ok=True)
    print(f"种子 {seed}：{n} 道题 × {len(knob_sets)} 组旋钮 = {len(jobs)} 个任务，开 {workers} 个进程……")

    snap = snapshot()                                                     # 开跑前拍快照：什么时候、哪条命令、哪版代码
    start = time.perf_counter()
    try:
        rows, n_run = run_jobs_resumable(jobs, log, workers=workers, timeout_s=TIMEOUT_S, retries=RETRIES,
                                         stop_after=stop_after, progress_every=1000)
    except PowerCut as e:
        print(f"  {e}。日志里现在有 {len(load_done(log, code_fingerprint()))} 个交卷的（{log.name}）")
        print("  再跑同一条命令（去掉 --fresh 和 --stop-after），就接着考")
        return
    seconds = time.perf_counter() - start
    print(f"这次考了 {n_run} 个，用了 {seconds:.0f} 秒（{seconds / 60:.1f} 分钟）。")
    if n_run > 0:
        per_job = seconds / n_run
        print(f"平均每个任务 {per_job:.3f} 秒。")
        if n < 1000:
            print(f"照这个速度，1000 道题（{1000 * len(knob_sets)} 个任务）大约要 {per_job * 1000 * len(knob_sets) / 60:.0f} 分钟。")

    not_ok = 0
    for r in rows:
        if r["status"] != "ok":
            not_ok += 1
    print(f"没交卷的任务：{not_ok} 个")
    save_csv(rows, path)
    settings = {"n": n, "seed": seed, "workers": workers, "timeout_s": TIMEOUT_S, "retries": RETRIES,
                "predict_s": PREDICT_S, "confirm_frames": CONFIRM_FRAMES, "accel": ACCEL,
                "noise_y_m": NOISE_Y_M, "delay_s": DELAY_S,
                "resumed_from_log": len(jobs) - n_run, "ran_this_time": n_run}
    print(f"运行清单：{write_manifest(path, snap, settings, rows, seconds)}")


if __name__ == "__main__":
    main()