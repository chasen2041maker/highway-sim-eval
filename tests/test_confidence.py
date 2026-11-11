"""B4 第 4 步：Wilson 置信区间。期望值手算：0 次时上限 = z² / (n + z²)。"""

import pytest

from evaluation.confidence import wilson_interval


def test_zero_out_of_ten_can_still_be_28_percent():
    """10 道一道没撞，真实碰撞率还可能高到 27.8%：没撞过 ≠ 不会撞。"""
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0
    assert hi == pytest.approx(1.96 ** 2 / (10 + 1.96 ** 2))     # 0.2775


def test_more_questions_narrower_interval():
    """同样 4%：25 道里 1 道，区间 0.7%–19.5%；500 道里 20 道，窄得多。"""
    lo_small, hi_small = wilson_interval(1, 25)
    lo_big, hi_big = wilson_interval(20, 500)
    assert lo_small == pytest.approx(0.0071, abs=1e-4)
    assert hi_small == pytest.approx(0.1954, abs=1e-4)
    assert (hi_big - lo_big) < (hi_small - lo_small) / 4
    assert lo_big < 0.04 < hi_big


def test_symmetric():
    """撞 k 道和不撞 k 道是镜像：区间也镜像。"""
    lo, hi = wilson_interval(3, 50)
    lo2, hi2 = wilson_interval(47, 50)
    assert lo2 == pytest.approx(1 - hi)
    assert hi2 == pytest.approx(1 - lo)


def test_empty_is_an_error():
    with pytest.raises(ValueError):
        wilson_interval(0, 0)
