"""B5 第 1 步：同一批考试题，让一个“版本”的考生考一遍，存一张结果表 + 运行清单。

版本 = 一组考生设置（以后也可以是一版代码）：
  v1：B1 挑的（往前看 0.5 秒、确认 1 帧、匀速预测）
  v2：B2 调出来的冠军（往前看 1.0 秒、确认 1 帧、匀加速预测）
考试题：种子 4 的 200 道新题（B2 调参用的是种子 1、2，这批谁都没见过）× 4 种路况 = 800 个任务。
两个版本考一模一样的题、一模一样的噪声（噪声种子 = 题号），第 2 步才能一道一道对比。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b5_run v1
    python -m examples.b_eval.b5_run v2
结果：outputs/regression/<版本>.csv，旁边同名 .json 是运行清单。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

from batch.jobs import Job, run_jobs_safe
from batch.manifest import snapshot, write_manifest
from examples.b_eval.b2_batch import save_csv
from examples.b_eval.b2_grid import make_jobs, make_questions

np.seterr(divide="ignore")
OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "regression"

VERSIONS = {
    "v1": {"predict_s": 0.5, "confirm_frames": 1, "accel": False},   # B1 挑的
    "v2": {"predict_s": 1.0, "confirm_frames": 1, "accel": True},    # B2 调出来的冠军
}
ROADS = [                                                            # 4 种路况，每个版本都考一遍
    {"noise_y_m": 0.0, "delay_s": 0.0},
    {"noise_y_m": 0.0, "delay_s": 0.3},
    {"noise_y_m": 0.2, "delay_s": 0.0},
    {"noise_y_m": 0.2, "delay_s": 0.3},
]
N_QUESTIONS, SEED = 200, 4
TIMEOUT_S, RETRIES = 60, 1


def version_jobs(version: str, n: int = N_QUESTIONS, seed: int = SEED) -> list[Job]:
    """一个版本的全部任务：同一批题 × 4 种路况，旋钮换成这个版本的。"""
    knob_sets = [{**VERSIONS[version], **road} for road in ROADS]
    return make_jobs(make_questions(n, seed), knob_sets)


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else (os.cpu_count() or 4)
    jobs = version_jobs(version)
    path = OUT_DIR / f"{version}.csv"
    print(f"版本 {version} {VERSIONS[version]}：{N_QUESTIONS} 道题 × {len(ROADS)} 种路况 = {len(jobs)} 个任务，开 {workers} 个进程……")
    snap = snapshot()
    start = time.perf_counter()
    rows = run_jobs_safe(jobs, workers=workers, timeout_s=TIMEOUT_S, retries=RETRIES, progress_every=200)
    seconds = time.perf_counter() - start
    not_ok = sum(1 for r in rows if r["status"] != "ok")
    print(f"用了 {seconds:.0f} 秒；没交卷的任务 {not_ok} 个")
    save_csv(rows, path)
    settings = {"version": version, **VERSIONS[version], "roads": ROADS, "n": N_QUESTIONS, "seed": SEED,
                "workers": workers, "timeout_s": TIMEOUT_S, "retries": RETRIES}
    print(f"运行清单：{write_manifest(path, snap, settings, rows, seconds)}")


if __name__ == "__main__":
    main()
