"""B3 第 2 步：导出带来源的数据集（examples/b_eval/b3_export.py）。没装 duckdb 的电脑会跳过。

笔记本 2026-11-10：5 张网格结果表里，只有 b2_grid_20_seed3（b56e3d8、代码指纹 1396932bf8c4）可追溯；
b2_grid_2_seed3 跑的时候有没提交的改动；1000 道题的两张和 50 道那张是有运行清单之前跑的，来源不明。
"""

import csv
import json

import pytest

duckdb = pytest.importorskip("duckdb")

from examples.b_eval import b3_export  # noqa: E402

FIELDS = ["question", "comes_in", "predict_s", "min_gap_m", "missed", "false_brake", "status"]


def _write_csv(path, n_rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i in range(n_rows):
            w.writerow({"question": i + 1, "comes_in": True, "predict_s": 0.5, "min_gap_m": "inf",
                        "missed": False, "false_brake": False, "status": "ok"})


def test_export_and_catalog(tmp_path):
    """有运行清单的表带上提交号、指纹、开跑时间；没有的来源一栏是空的，目录里标“来源不明”；有没提交改动的单独标出来。"""
    _write_csv(tmp_path / "b2_grid_3_seed2.csv", 3)
    (tmp_path / "b2_grid_3_seed2.json").write_text(json.dumps({
        "commit": "abc1234", "uncommitted_changes": [], "code_fingerprint": "f00d",
        "started_at": "2026-11-10T09:00:00+08:00"}), encoding="utf-8")
    _write_csv(tmp_path / "b2_grid_2.csv", 2)                                   # 没有运行清单
    _write_csv(tmp_path / "b2_grid_4_seed5.csv", 4)
    (tmp_path / "b2_grid_4_seed5.json").write_text(json.dumps({
        "commit": "def5678", "uncommitted_changes": ["a.py"]}), encoding="utf-8")
    out = tmp_path / "datasets"
    out.mkdir()
    con = duckdb.connect()
    files = []
    for name in ("b2_grid_2", "b2_grid_3_seed2", "b2_grid_4_seed5"):
        files.append(b3_export.export(con, tmp_path / f"{name}.csv", out).as_posix())
    rows = con.execute(b3_export.CATALOG, {"files": files}).fetchall()
    assert [(r[0], r[1], r[2], r[3], r[4], r[6]) for r in rows] == [
        ("b2_grid_2", 1, 2, 2, None, "来源不明"),
        ("b2_grid_3_seed2", 2, 3, 3, "abc1234", "可追溯"),
        ("b2_grid_4_seed5", 5, 4, 4, "def5678", "有没提交的改动"),
    ]
    started = con.execute("SELECT DISTINCT run_started_at FROM read_parquet($f)", {"f": files[1]}).fetchone()[0]
    assert started is not None
    assert con.execute("SELECT typeof(min_gap_m) FROM read_parquet($f) LIMIT 1", {"f": files[0]}).fetchone()[0] == "DOUBLE"
