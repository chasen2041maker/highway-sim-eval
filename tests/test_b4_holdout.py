"""B4 第 5 步：只用调参题挑，报分要用考试题。"""

from examples.b_eval.b4_holdout import pick_and_score


def test_pick_on_tune_score_on_test():
    """调参题上 A 最好（1 分），可考试题上 A 是 5 分、B 才 3 分：挑的还是 A，报 5 分，不报 1 分。"""
    tune = {"A": 1.0, "B": 2.0}
    test = {"A": 5.0, "B": 3.0}
    assert pick_and_score(tune, test) == ("A", 1.0, 5.0)
