"""B3 第 1 步：结果表进 Parquet，用 DuckDB 写 SQL 查（examples/b_eval/b3_duckdb.py）。没装 duckdb 的电脑会跳过。

笔记本 2026-11-09：两张 64,000 行的表 CSV 6.5 MB → Parquet 0.16 MB；同一个查询读 CSV 约 100 毫秒、读 Parquet 约 10 毫秒；
SQL 挑出的 ★ 和两批并排的代价、名次，和 b2_balance（Python 一行行数）逐个对上。
"""

import csv

import pytest

duckdb = pytest.importorskip("duckdb")

from examples.b_eval import b3_duckdb as b3  # noqa: E402

FIELDS = ["question", "comes_in", "predict_s", "confirm_frames", "noise_y_m", "delay_s", "accel",
          "min_gap_m", "crashed", "missed", "false_brake", "status"]


def _row(q, predict, missed=False, false_brake=False, gap="inf", status="ok"):
    return {"question": q, "comes_in": True, "predict_s": predict, "confirm_frames": 1, "noise_y_m": 0.0,
            "delay_s": 0.0, "accel": True, "min_gap_m": gap, "crashed": missed, "missed": missed,
            "false_brake": false_brake, "status": status}


def test_parquet_types_and_star(tmp_path):
    """CSV → Parquet：min_gap_m 是小数（"inf" 也是），True / False 是布尔；SQL 挑 ★ 时不数没交卷的。"""
    rows = [
        _row(1, 0.0, missed=True, gap="1.5"),     # 往前看 0 秒：漏刹 1 道 → 代价 10
        _row(2, 0.0),
        _row(1, 0.5, false_brake=True),           # 往前看 0.5 秒：误刹 2 道 → 代价 2（★）
        _row(2, 0.5, false_brake=True),
        _row(3, 0.5, false_brake=True, status="timeout"),   # 没交卷：不算
    ]
    csv_file, pq = tmp_path / "t.csv", tmp_path / "t.parquet"
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    con = duckdb.connect()
    b3.to_parquet(con, csv_file, pq, seed=2)
    types = {}
    for name, typ, *_ in con.execute("DESCRIBE SELECT * FROM read_parquet($f)", {"f": pq.as_posix()}).fetchall():
        types[name] = typ
    assert types["min_gap_m"] == "DOUBLE" and types["missed"] == "BOOLEAN" and types["question_seed"] == "INTEGER"
    assert con.execute("SELECT count(*) FROM read_parquet($f) WHERE isinf(min_gap_m)", {"f": pq.as_posix()}).fetchone()[0] == 4
    stars = con.execute(b3.ROAD_STARS, {"weight": 10.0, "file": pq.as_posix()}).fetchall()
    assert stars == [(0.0, 0.0, 0.5, 1, True, 0, 2, 2.0)]
