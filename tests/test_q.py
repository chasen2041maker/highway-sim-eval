"""SQL 练习台（examples/b_eval/q.py）：grid 视图 = 两批网格结果的 Parquet 合在一起。没装 duckdb 的电脑会跳过。"""

import pytest

duckdb = pytest.importorskip("duckdb")

from examples.b_eval import q  # noqa: E402


def test_grid_view_reads_both_files(tmp_path, monkeypatch):
    """两个 Parquet 各 2 行 → grid 有 4 行；question_seed 分得开。"""
    files = []
    for seed in (1, 2):
        f = tmp_path / f"g{seed}.parquet"
        duckdb.sql(f"COPY (SELECT {seed} AS question_seed, range AS question FROM range(2)) TO '{f.as_posix()}' (FORMAT parquet)")
        files.append(f)
    monkeypatch.setattr(q, "FILES", files)
    con = q.connect()
    assert con.execute("SELECT count(*), count(DISTINCT question_seed) FROM grid").fetchone() == (4, 2)
