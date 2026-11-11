"""B4 第 3 步：急动度 = 加速度每秒变多少（m/s³），取整道题里变得最急的那一下。"""

import pytest

from examples.b_eval.b1_cut_in import limit_jerk
from examples.b_eval.b1_highway_brake import score


def _log(accel):
    n = len(accel)
    return {"t": [k * 0.1 for k in range(n)], "gap": [10.0] * n, "ego_v": [15.0] * n, "lead_v": [10.0] * n,
            "accel": accel}


def test_slamming_the_brake_is_80():
    """0.1 秒里从 0 踩到 −8：急动度 80；后面从 −8 松到 −4 是 40，取最大的 80。"""
    s = score(_log([0.0, 0.0, -8.0, -8.0, -4.0]), False)
    assert s["max_jerk_mps3"] == pytest.approx(80.0)
    assert s["hardest_brake_mps2"] == pytest.approx(-8.0)


def test_slow_ramp_is_gentle():
    """花 4 秒从 0 慢慢加到 −8（每 0.1 秒多踩 0.2）：踩得一样深，急动度只有 2。"""
    s = score(_log([-0.2 * k for k in range(41)]), False)
    assert s["max_jerk_mps3"] == pytest.approx(2.0)
    assert s["hardest_brake_mps2"] == pytest.approx(-8.0)


def test_no_braking_no_jerk():
    assert score(_log([0.0] * 10), False)["max_jerk_mps3"] == pytest.approx(0.0)


def test_limit_jerk_spreads_a_slam_over_several_steps():
    """上限 10 m/s³、每 0.1 秒最多变 1：想一脚踩到 −8，只能先到 −1；急刹后想马上踩油门 +2.8，只能松到 −7。"""
    assert limit_jerk(0.0, -8.0, 10.0) == pytest.approx(-1.0)
    assert limit_jerk(-8.0, 2.8, 10.0) == pytest.approx(-7.0)
    assert limit_jerk(-3.0, -3.5, 10.0) == pytest.approx(-3.5)     # 只差 0.5，没超上限，照踩
    a, steps = 0.0, 0
    while a > -8.0 + 1e-9:
        a, steps = limit_jerk(a, -8.0, 10.0), steps + 1
    assert steps == 8                                               # 0.8 秒才踩到 −8
