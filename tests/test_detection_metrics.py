"""A5 第 4 步：检测评测（召回率、精确率、位置误差）的测试。数字都是手算的。
助手先写好这些测试，本人写 evaluation/metrics.py 的 detection_metrics，直到全过：
    python -m pytest tests/test_detection_metrics.py -v
"""

import math

import numpy as np

from evaluation.metrics import detection_metrics


def pairs(r):
    """只看配上的 (预测下标, 真东西下标)，不看距离。"""
    return [tuple(int(v) for v in m[:2]) for m in r["matches"]]


def test_perfect():
    """两个真东西、两个预测，位置一模一样：召回 1、精确 1、误差 0。"""
    true = np.array([[10.0, 0.0], [20.0, 3.0]])
    r = detection_metrics(true.copy(), true, 2.0)
    assert r["recall"] == 1.0 and r["precision"] == 1.0
    assert r["mean_error_m"] == 0.0
    assert len(r["matches"]) == 2


def test_one_missed():
    """真东西 2 个，只预测出 1 个、偏了 0.5 米：召回 1/2、精确 1/1、误差 0.5。"""
    true = np.array([[10.0, 0.0], [20.0, 3.0]])
    pred = np.array([[10.5, 0.0]])
    r = detection_metrics(pred, true, 2.0)
    assert r["recall"] == 0.5 and r["precision"] == 1.0
    assert math.isclose(r["mean_error_m"], 0.5)
    assert pairs(r) == [(0, 0)]


def test_false_alarm():
    """真东西 1 个，预测 2 个（多出来的那个在 30 米外）：召回 1、精确 1/2、误差只算配上的那对 0.3。"""
    true = np.array([[10.0, 0.0]])
    pred = np.array([[10.0, 0.3], [30.0, -5.0]])
    r = detection_metrics(pred, true, 2.0)
    assert r["recall"] == 1.0 and r["precision"] == 0.5
    assert math.isclose(r["mean_error_m"], 0.3)


def test_too_far_does_not_count():
    """框中心在车尾 12.7、真中心 15.0（差 2.3 米）：门槛 2 米 → 算没找到；门槛 4 米 → 找到，误差 2.3。"""
    true = np.array([[15.0, 0.0]])
    pred = np.array([[12.7, 0.0]])
    r2 = detection_metrics(pred, true, 2.0)
    assert r2["recall"] == 0.0 and r2["precision"] == 0.0 and pairs(r2) == []
    assert math.isnan(r2["mean_error_m"])
    r4 = detection_metrics(pred, true, 4.0)
    assert r4["recall"] == 1.0 and math.isclose(r4["mean_error_m"], 2.3)


def test_one_to_one():
    """一个真东西、两个预测都挨着它（离 0.2 米、0.1 米）：只能配一个，配近的那个（下标 1）；另一个算误报。"""
    true = np.array([[10.0, 0.0]])
    pred = np.array([[10.2, 0.0], [9.9, 0.0]])
    r = detection_metrics(pred, true, 2.0)
    assert pairs(r) == [(1, 0)]
    assert r["recall"] == 1.0 and r["precision"] == 0.5
    assert math.isclose(r["mean_error_m"], 0.1)


def test_closest_pair_first():
    """先配全场最近的一对。真东西 A (0, 0)、B (3, 0)；预测 p (1.0, 0) 离 A 1.0、离 B 2.0；预测 q (0.2, 0) 离 A 0.2、离 B 2.8。门槛 2.5：
    先配 q-A（0.2），A 用掉了；再配 p-B（2.0）→ 两个都找到，误差 (0.2 + 2.0) / 2 = 1.1。
    如果按预测的顺序、各自抢离自己最近的：p 先抢走 A，q 只剩 B（2.8 > 2.5）配不上 → 召回只有 0.5（错）。"""
    true = np.array([[0.0, 0.0], [3.0, 0.0]])
    pred = np.array([[1.0, 0.0], [0.2, 0.0]])
    r = detection_metrics(pred, true, 2.5)
    assert pairs(r) == [(1, 0), (0, 1)]
    assert r["recall"] == 1.0 and r["precision"] == 1.0
    assert math.isclose(r["mean_error_m"], 1.1)


def test_nothing_detected():
    """一个预测都没有（形状 (0, 2)）：召回 0、精确 0（不能除以 0）、误差 nan。"""
    true = np.array([[10.0, 0.0]])
    r = detection_metrics(np.zeros((0, 2)), true, 2.0)
    assert r["recall"] == 0.0 and r["precision"] == 0.0 and pairs(r) == []
    assert math.isnan(r["mean_error_m"])
