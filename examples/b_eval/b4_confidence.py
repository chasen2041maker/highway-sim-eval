"""B4 第 4 步：给漏刹率、误刹率加 95% 置信区间，看“50 道”和“1000 道”的结论各能信多少。

数据：b3_export 导出的 outputs/datasets/*.parquet（50 道试跑、1000 道种子 1、1000 道种子 2）。
只看干净路况、确认 1 帧、匀加速预测，4 种往前看。
漏刹率的分母 = 能躲开的会进来的题（和 b2_balance 一样：踩死也躲不开的不算）；误刹率的分母 = 不进来的题。
运行（在项目根目录，先 conda activate py310；先跑过 b3_export）：
    python -m examples.b_eval.b4_confidence
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from evaluation.confidence import wilson_interval

DATASETS = Path(__file__).resolve().parents[2] / "outputs" / "datasets"
NAMES = ["b2_grid_50", "b2_grid_1000", "b2_grid_1000_seed2"]

RATES = """
WITH grid AS (
    SELECT * FROM read_parquet($files) WHERE status = 'ok'
),
unavoidable AS (                       -- 踩死也躲不开的题（撞了也不算漏刹）
    SELECT DISTINCT dataset, question FROM grid WHERE crashed AND NOT missed
),
questions AS (                         -- 每批题：能躲开的会进来的题几道、不进来的题几道
    SELECT dataset,
           count_if(comes_in AND u.question IS NULL) AS n_in,
           count_if(NOT comes_in)                    AS n_out
    FROM (SELECT DISTINCT dataset, question, comes_in FROM grid) q
    LEFT JOIN unavoidable u USING (dataset, question)
    GROUP BY dataset
)
SELECT g.dataset, g.predict_s, count_if(g.missed) AS missed, q.n_in, count_if(g.false_brake) AS false_n, q.n_out
FROM grid g JOIN questions q USING (dataset)
WHERE g.noise_y_m = 0 AND g.delay_s = 0 AND g.confirm_frames = 1 AND g.accel
GROUP BY g.dataset, g.predict_s, q.n_in, q.n_out
ORDER BY g.dataset, g.predict_s
"""


def cell(k: int, n: int) -> str:
    lo, hi = wilson_interval(k, n)
    return f"{k:>3}/{n:<3} {k / n:6.1%}  [{lo:5.1%}, {hi:5.1%}]"


def main():
    files = [(DATASETS / f"{name}.parquet").as_posix() for name in NAMES]
    rows = duckdb.execute(RATES, {"files": files}).fetchall()
    print("干净路况、确认 1 帧、匀加速预测；[ ] = 95% 置信区间")
    print("哪批题               往前看   漏刹                           误刹")
    for dataset, predict_s, missed, n_in, false_n, n_out in sorted(rows, key=lambda r: (NAMES.index(r[0]), r[1])):
        print(f"{dataset:<20} {predict_s:>4.1f} 秒   {cell(missed, n_in)}   {cell(false_n, n_out)}")


if __name__ == "__main__":
    main()
