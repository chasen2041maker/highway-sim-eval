"""B2 第 4 步下半：从网格结果表里找平衡点（examples/b_eval/b2_balance.py）。

笔记本 1000 道题（64,000 行）权重 10 的结果（2026-11-05）：每种路况的 ★ 都是匀加速；干净 / 延迟是往前看 0.5 · 确认 1 帧，
噪声 / 噪声 + 延迟是往前看 0.5 · 确认 3 帧；四种加起来 ★ = 1.0 · 1 帧 · 匀加速（2098），第 2、3 名只多 6、16（不到 1%，不能直接说它最好）。
权重 1 → 往前看 0 秒；3 → 0.5 · 3 帧 · 匀加速；30、100 → 1.5 · 1 帧 · 匀加速：最好的那组由“撞车比白刹贵多少”决定。
种子 2 换 1000 道新题验证（2026-11-09，48 分钟，0 失败）：四种加起来 ★ 还是 1.0 · 1 帧 · 匀加速（2092），第 2 名变成 1.5 · 1 帧 · 匀加速（2270），种子 1 的第 2 名 0.5 · 3 帧 · 匀加速掉到第 6（2652）；
两批里同样设置下匀加速都比匀速好。差距比换批的晃动小的排名不算数。
"""

import csv

from examples.b_eval import b2_balance

FIELDS = ["question", "comes_in", "predict_s", "confirm_frames", "noise_y_m", "delay_s", "accel",
          "crashed", "missed", "false_brake"]


def _row(q, comes_in, predict, crashed=False, missed=False, false_brake=False):
    return {"question": q, "comes_in": comes_in, "predict_s": predict, "confirm_frames": 1, "noise_y_m": 0.0,
            "delay_s": 0.0, "accel": False, "crashed": crashed, "missed": missed, "false_brake": false_brake}


def test_count_groups_and_questions(tmp_path, monkeypatch):
    """两组（往前看 0 / 0.5）× 4 道题：表里读出来的都是文字，"False" 不能当真。"""
    rows = [
        _row(1, True, 0.0, crashed=True, missed=True),     # 不预测：会进来的第 1 题漏刹
        _row(2, False, 0.0),
        _row(3, True, 0.0, crashed=True),                   # 第 3 题踩死也躲不开：撞了但不算漏刹
        _row(4, False, 0.0),
        _row(1, True, 0.5),
        _row(2, False, 0.5, false_brake=True),              # 往前看 0.5：第 2 题误刹
        _row(3, True, 0.5, crashed=True),
        _row(4, False, 0.5, false_brake=True),
    ]
    path = tmp_path / "b2_grid_4.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(b2_balance, "OUT_DIR", tmp_path)
    table = b2_balance.load(4)
    assert table[0]["missed"] == "True" and table[1]["missed"] == "False"
    counts = b2_balance.count(table)
    assert counts[("0.0", "0.0", "0.0", "1", "False")] == [1, 0]     # [漏刹, 误刹]
    assert counts[("0.0", "0.0", "0.5", "1", "False")] == [0, 2]
    assert b2_balance.question_counts(table) == (1, 1, 2)            # 能躲开 1 道、躲不开 1 道、不进来 2 道


def test_load_seed_2_table(tmp_path, monkeypatch):
    """种子 2 读 b2_grid_<n>_seed2.csv，不会读到种子 1 那张表。"""
    for name, q in (("b2_grid_4.csv", 1), ("b2_grid_4_seed2.csv", 2)):
        with (tmp_path / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerow(_row(q, True, 0.0))
    monkeypatch.setattr(b2_balance, "OUT_DIR", tmp_path)
    assert b2_balance.load(4)[0]["question"] == "1"
    assert b2_balance.load(4, 2)[0]["question"] == "2"
