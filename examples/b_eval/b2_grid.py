"""B2 第 4 步：多旋钮网格——一大批随机加塞题 × 每一组旋钮，找漏刹和误刹的平衡点。

五个旋钮分两种：
  考生的设置（工程师能选）：往前看几秒、连续几帧确认、匀速 / 匀加速
  路况（工程师选不了，只能每种都考一遍）：横向噪声、延迟
每道题 × 每一组 = 一个任务，用 run_jobs_safe 开很多进程跑，一个任务一行，存成表。
这里只管跑和存表；从表里找平衡点是下一步。

运行（在项目根目录）：
    python -m examples.b_eval.b2_grid 50       先出 50 道题试跑，看要多久
    python -m examples.b_eval.b2_grid 1000     1000 道题（会进来、不进来各一半）
    python -m examples.b_eval.b2_grid 1000 8   第二个数 = 开几个进程（不写就用全部逻辑核）
"""
from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

import numpy as np

from batch.jobs import Job, run_jobs_safe
from examples.b_eval.b1_cut_in_random import sample_cut_in
from examples.b_eval.b2_batch import save_csv

np.seterr(divide="ignore")
OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"

SEED = 1                              # 新种子：和 B1 那 40 道（种子 0）不是同一批题

# 考生的设置：工程师能选
PREDICT_S = [0.0, 0.5, 1.0, 1.5]      # 往前看几秒
CONFIRM_FRAMES = [1, 3]               # 连续几帧都挑出它，才算前车
ACCEL = [False, True]                 # 预测按匀速（False）还是匀加速（True）往外推

# 路况：工程师选不了，每种都考一遍
NOISE_Y_M = [0.0, 0.2]                # 别的车横向位置的噪声（米）
DELAY_S = [0.0, 0.3]                  # 考生看到的路况晚几秒

def make_questions(n: int) -> list:
    """出 n 道新题。会进来、不进来交替出（第 1、3、5……道会进来），所以 50 道试跑的题就是 1000 道的前 50 道。"""
    rng = random.Random(SEED)
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

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50                     # 出几道题
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else os.cpu_count()   # 开几个进程
    knob_sets = make_knob_sets()
    jobs = make_jobs(make_questions(n), knob_sets)
    print(f"{n} 道题 × {len(knob_sets)} 组旋钮 = {len(jobs)} 个任务，开 {workers} 个进程……")

    start = time.perf_counter()
    rows = run_jobs_safe(jobs, workers=workers, timeout_s=60, retries=1, progress_every=1000)
    seconds = time.perf_counter() - start
    print(f"用了 {seconds:.0f} 秒（{seconds / 60:.1f} 分钟），平均每个任务 {seconds / len(jobs):.3f} 秒。")
    if n < 1000:
        print(f"照这个速度，1000 道题（{1000 * len(knob_sets)} 个任务）大约要 {seconds / n * 1000 / 60:.0f} 分钟。")

    not_ok = 0
    for r in rows:
        if r["status"] != "ok":
            not_ok += 1
    print(f"没交卷的任务：{not_ok} 个")
    save_csv(rows, OUT_DIR / f"b2_grid_{n}.csv")


if __name__ == "__main__":
    main()