"""B5 第 2 步：给每一行定结果等级，再把两个版本同一道题、同一种路况配成一对，看变好还是变差。"""

import math

from examples.b_eval.b5_compare import compare, level

INF = math.inf


def row(q, missed=False, crashed=False, false_brake=False, gap=INF, ttc=INF, noise=0.0, delay=0.0):
    return {"question": q, "noise_y_m": noise, "delay_s": delay, "missed": missed, "crashed": crashed or missed,
            "false_brake": false_brake, "min_gap_m": gap, "min_ttc_s": ttc}


def test_levels():
    assert level(row(1, missed=True)) == 3                 # 能躲开却撞了
    assert level(row(1, crashed=True)) is None            # 踩死也躲不开：不参与比较
    assert level(row(1, false_brake=True)) == 2
    assert level(row(1, gap=3.0, ttc=1.2)) == 1           # TTC < 1.5 秒
    assert level(row(1, gap=-2.4, ttc=-12.0)) == 1        # 并排擦过去（车身压进我车道、前后距离 < 0）
    assert level(row(1, gap=5.0, ttc=2.4)) == 0


def test_pairs_same_question_same_road():
    old = [row(1), row(2, missed=True), row(3, ttc=1.0, gap=2.0), row(3, noise=0.2)]
    new = [row(1, false_brake=True), row(2), row(3, ttc=1.0, gap=2.0), row(3, noise=0.2, missed=True)]
    changes = [p["change"] for p in compare(old, new)]
    assert changes == ["变差", "变好", "不变", "变差"]      # 第 3 题两种路况分开配对
