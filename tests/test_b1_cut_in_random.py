"""B1：随机出的 40 道加塞新题（种子 0）的回归测试。

数字来自 2026-11-02 实跑（笔记本 Windows 和云端 Linux 一样）。题库五道题上“预测 0.5 秒”全对，
换成没见过的新题：漏刹 1 道（第 14 题：离得近、开头挪得慢，预测再长也晚）、误刹 3 道（第 28、31、36 题：
冲着线过来、最后停在离线 0.1–0.3 米处，匀速往外推的预测以为它会进来）。
"""

import random

import pytest

pytest.importorskip("highway_env")

import numpy as np  # noqa: E402

from examples.b1_cut_in import run  # noqa: E402
from examples.b1_cut_in_random import N_EACH, SEED, avoidable, sample_cut_in  # noqa: E402

np.seterr(divide="ignore")


def _questions():
    rng = random.Random(SEED)
    return [(sample_cut_in(rng, True), True) for _ in range(N_EACH)] + \
           [(sample_cut_in(rng, False), False) for _ in range(N_EACH)]


def test_same_seed_same_questions():
    a, b = _questions(), _questions()
    assert a == b
    assert a[13][0].gap_m == 5.2 and a[13][0].cut_depth_m == 3.81


@pytest.mark.parametrize("predict_s,missed,false", [(0.0, [14, 15], []), (0.5, [14], [28, 31, 36])])
def test_missed_and_false_brakes(predict_s, missed, false):
    qs = _questions()
    got_missed, got_false = [], []
    for n, (sc, comes_in) in enumerate(qs, start=1):
        s = run(sc, predict_s)
        if comes_in and s["crashed"] and avoidable(sc):
            got_missed.append(n)
        if not comes_in and s["hardest_brake_mps2"] < -0.5:
            got_false.append(n)
    assert got_missed == missed
    assert got_false == false
