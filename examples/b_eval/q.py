"""SQL 练习台：对网格结果表直接写 SQL，结果打成表格。

表名 grid = 两批网格结果（种子 1、种子 2，各 64,000 行）合在一起，question_seed 这一列分得开是哪一批。
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
