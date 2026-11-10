"""SQL 练习台：对网格结果表直接写 SQL，结果打成表格。

表名 grid = 两批网格结果（种子 1、种子 2，各 64,000 行）合在一起，question_seed 这一列分得开是哪一批。
另外拆成两张（第 4 课 JOIN 用，模仿公司里题目和结果分开存）：
  questions = 题目表，一道题一行（2 批 × 1000 = 2,000 行）：出题种子、题号、标准答案、题目 5 个数
  results   = 结果表，一次考试一行（128,000 行）：出题种子、题号、5 个旋钮、考得怎样，不再重复抄题目参数
先跑一次 python -m examples.b_eval.b3_duckdb，生成 Parquet。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.q "SELECT * FROM grid LIMIT 5"
    python -m examples.b_eval.q -f my.sql              长的 SQL 写在文件里
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"
FILES = [OUT_DIR / "b2_grid_1000.parquet", OUT_DIR / "b2_grid_1000_seed2.parquet"]


def connect():
    """开一个只在内存里的 DuckDB，建一个名字叫 grid 的“视图”：查 grid 就是查这两个 Parquet 文件。"""
    files = []
    for f in FILES:
        if f.exists():
            files.append(f.as_posix())
    if not files:
        raise SystemExit("还没有 Parquet 文件：先跑 python -m examples.b_eval.b3_duckdb")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW grid AS SELECT * FROM read_parquet({files!r})")
    con.execute("""CREATE VIEW questions AS
                   SELECT DISTINCT question_seed, question, comes_in,
                          gap_m, ego_speed_mps, cut_speed_mps, cut_time_s, cut_depth_m
                   FROM grid""")
    con.execute("""CREATE VIEW results AS
                   SELECT question_seed, question, predict_s, confirm_frames, accel, noise_y_m, delay_s,
                          crashed, min_gap_m, hardest_brake_mps2, missed, false_brake, status
                   FROM grid""")
    return con


def main():
    args = sys.argv[1:]
    if args and args[0] == "-f":
        sql = Path(args[1]).read_text(encoding="utf-8")
    else:
        sql = " ".join(args)
    connect().sql(sql).show(max_rows=40, max_width=250)


if __name__ == "__main__":
    main()
