"""B4 第 5 步：调参用的题和考试用的题分开。

只用“调参题”挑考生设置（16 种里挑代价最小的），再拿从没看过的“考试题”（种子 2 的 1000 道）给它打分。
同一批题既拿来挑、又拿来报分，分数会虚高（看着答案考试）；调参题太少，还会挑错。
代价 = 每 100 道题、4 种路况各考一遍：漏刹 × 10 + 误刹（越小越好）。
调参题试 4 种大小：种子 1 的前 50 / 100 / 200 道、全部 1000 道。
运行（在项目根目录，先 conda activate py310；先跑过 b3_export）：
    python -m examples.b_eval.b4_holdout
"""

from __future__ import annotations

from pathlib import Path

import duckdb

DATASETS = Path(__file__).resolve().parents[2] / "outputs" / "datasets"
TUNE, TEST = "b2_grid_1000", "b2_grid_1000_seed2"
WEIGHT = 10

COSTS = """
SELECT predict_s, confirm_frames, accel,
       (count_if(missed) * $weight + count_if(false_brake)) * 100.0 / count(DISTINCT question) AS cost
FROM read_parquet($file)
WHERE status = 'ok' AND question <= $n
GROUP BY predict_s, confirm_frames, accel
"""


def costs(dataset: str, n: int = 1000) -> dict[tuple, float]:
    """一批题的前 n 道：每种考生设置（往前看、确认帧数、匀加速）的代价。"""
    rows = duckdb.execute(COSTS, {"file": (DATASETS / f"{dataset}.parquet").as_posix(), "n": n, "weight": WEIGHT}).fetchall()
    return {(p, cf, acc): c for p, cf, acc, c in rows}


def pick_and_score(tune: dict, test: dict) -> tuple:
    """只用调参题挑（代价最小的那个设置），再报它在调参题和考试题上各是多少。"""
    pick = min(tune, key=tune.get)
    return pick, tune[pick], test[pick]


def name(setting: tuple) -> str:
    p, cf, acc = setting
    return f"{p:.1f} 秒 / {cf} 帧 / {'匀加速' if acc else '匀速'}"


def main():
    test = costs(TEST)
    best = min(test, key=test.get)
    print("调参题（种子 1）   挑中的设置               调参题上的代价   考试题（种子 2）上的代价")
    for n in (50, 100, 200, 1000):
        pick, on_tune, on_test = pick_and_score(costs(TUNE, n), test)
        print(f"前 {n:<4} 道         {name(pick):<20}   {on_tune:8.1f}        {on_test:8.1f}")
    print(f"（考试题上真正最好的：{name(best)}，{test[best]:.1f}）")
    print("代价 = 每 100 道题、4 种路况各一遍：漏刹 × 10 + 误刹，越小越好")


if __name__ == "__main__":
    main()
