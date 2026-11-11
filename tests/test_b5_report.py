"""B5 第 3 步：回归报告的数据——变差排在前面、最糟的最前，每一对带两个版本的录像。"""

from examples.b_eval.b5_report import changed_pairs, report_data


def pair(q, old, new, change):
    row = {"comes_in": True, "gap_m": 9.0, "ego_speed_mps": 15.0, "cut_speed_mps": 6.0, "cut_time_s": 2.0, "cut_depth_m": 2.0}
    return {"key": (q, 0.0, 0.0), "old": old, "new": new, "change": change, "old_row": row, "new_row": row}


def test_worst_regressions_first():
    pairs = [pair(1, 0, 2, "变差"), pair(2, 3, 0, "变好"), pair(3, 0, 3, "变差"), pair(4, 1, 1, "不变")]
    assert [p["key"][0] for p in changed_pairs(pairs)] == [3, 1, 2]      # 新撞的 → 新误刹 → 变好的


def test_report_data_has_both_runs():
    pairs = [pair(3, 0, 3, "变差"), pair(4, 1, 1, "不变")]
    runs = {("v1", (3, 0.0, 0.0)): {"crashed": False}, ("v2", (3, 0.0, 0.0)): {"crashed": True}}
    data = report_data("v1", "v2", pairs, runs)
    assert data["counts"] == {"变差": 1, "变好": 0, "不变": 1, "躲不开": 0}
    assert data["moves"] == [["正常", "撞了", 1]]
    item = data["items"][0]
    assert (item["q"], item["old"], item["new"]) == (3, "正常", "撞了")
    assert item["runs"]["v2"]["crashed"] is True
