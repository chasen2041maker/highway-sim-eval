"""SQL 练习台（examples/b_eval/q.py）：grid = 两批网格结果的 Parquet 合在一起；questions / results 是拆开的题目表和结果表。
没装 duckdb 的电脑会跳过。"""

import pytest

duckdb = pytest.importorskip("duckdb")

from examples.b_eval import q  # noqa: E402

ROW = """SELECT {seed} AS question_seed, range AS question, true AS comes_in,
                 5.0 AS gap_m, 15.0 AS ego_speed_mps, 7.0 AS cut_speed_mps, 2.0 AS cut_time_s, 3.0 AS cut_depth_m,
                 p AS predict_s, 1 AS confirm_frames, false AS accel, 0.0 AS noise_y_m, 0.0 AS delay_s,
                 false AS crashed, 1.0 AS min_gap_m, -2.0 AS hardest_brake_mps2, false AS missed, false AS false_brake,
                 'ok' AS status
          FROM range(2), (VALUES (0.0), (0.5)) t(p)"""


def test_views(tmp_path, monkeypatch):
    """两个 Parquet 各 2 道题 × 2 组旋钮 = 4 行 → grid 8 行；questions 一道题一行 = 4 行；results 8 行。
    JOIN 要用两把钥匙（出题种子 + 题号），只用题号会把两批里同号的题都拼上，行数翻倍。"""
    files = []
    for seed in (1, 2):
        f = tmp_path / f"g{seed}.parquet"
        duckdb.sql(f"COPY ({ROW.format(seed=seed)}) TO '{f.as_posix()}' (FORMAT parquet)")
        files.append(f)
    monkeypatch.setattr(q, "FILES", files)
    con = q.connect()
    assert con.execute("SELECT count(*) FROM grid").fetchone()[0] == 8
    assert con.execute("SELECT count(*) FROM questions").fetchone()[0] == 4
    assert con.execute("SELECT count(*) FROM results").fetchone()[0] == 8
    two_keys = """SELECT count(*) FROM results r JOIN questions q
                  ON r.question_seed = q.question_seed AND r.question = q.question WHERE r.question_seed = 2"""
    one_key = """SELECT count(*) FROM results r JOIN questions q
                 ON r.question = q.question WHERE r.question_seed = 2"""
    assert con.execute(two_keys).fetchone()[0] == 4
    assert con.execute(one_key).fetchone()[0] == 8
