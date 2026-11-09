"""运行清单（batch/manifest.py）：每跑完一批，在结果表旁边存一个同名 .json，记下这张表是怎么来的。"""

import json

from batch import manifest

ROWS = [
    {"question": 1, "status": "ok"},
    {"question": 2, "status": "ok"},
    {"question": 3, "status": "timeout"},     # 卡死：等到超时，记 timeout
    {"question": 4, "status": "error"},       # 每次都报错：重试用完，记 error
    {"question": 5, "status": "ok"},
]


def test_status_counts():
    """5 行：3 个 ok、1 个 timeout、1 个 error；没出现的 status 不放；空表就是空字典。"""
    assert manifest.status_counts(ROWS) == {"ok": 3, "timeout": 1, "error": 1}
    assert manifest.status_counts(ROWS[:2]) == {"ok": 2}
    assert manifest.status_counts([]) == {}


def test_snapshot_records_code_version():
    """快照里有提交号（至少 7 位）和没提交的改动（一个列表，可能是空的）。"""
    snap = manifest.snapshot()
    assert len(snap["commit"]) >= 7
    assert isinstance(snap["uncommitted_changes"], list)
    assert snap["python"].startswith("3.")


def test_write_manifest(tmp_path):
    """表叫 b2_grid_5_seed2.csv → 清单叫 b2_grid_5_seed2.json；快照、设置、行数、status、用时都在里面；中文原样存。"""
    table = tmp_path / "b2_grid_5_seed2.csv"
    snap = {"started_at": "2026-11-09T11:40:00+08:00", "commit": "abc1234", "uncommitted_changes": []}
    path = manifest.write_manifest(table, snap, {"n": 5, "seed": 2, "note": "种子 2 验证"}, ROWS, 12.345)
    assert path == tmp_path / "b2_grid_5_seed2.json"
    text = path.read_text(encoding="utf-8")
    assert "种子 2 验证" in text                      # 中文没变成 \u 乱码
    info = json.loads(text)
    assert info["commit"] == "abc1234" and info["started_at"] == "2026-11-09T11:40:00+08:00"
    assert info["settings"] == {"n": 5, "seed": 2, "note": "种子 2 验证"}
    assert info["table"] == "b2_grid_5_seed2.csv"
    assert info["rows"] == 5
    assert info["status"] == {"ok": 3, "timeout": 1, "error": 1}
    assert info["seconds"] == 12.3
