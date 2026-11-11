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


def test_ttc_is_gap_over_closing_speed_minimum():
    """B4 第 2 步：TTC = 车距 ÷（我 − 它）；只在我比它快时算；取整道题最小的。我 15、它 10：10 / 8 / 6 米 → 2.0 / 1.6 / 1.2 秒。"""
    log = {"t": [0.0, 0.1, 0.2], "gap": [10.0, 8.0, 6.0], "ego_v": [15.0] * 3, "lead_v": [10.0] * 3, "accel": [0.0] * 3}
    assert score(log, False)["min_ttc_s"] == pytest.approx(1.2)
    log["lead_v"] = [16.0] * 3                                         # 它比我快：不会撞上
    assert score(log, False)["min_ttc_s"] == float("inf")
    log["lead_v"], log["gap"] = [10.0] * 3, [float("inf")] * 3         # 一直没量到前车（车距 inf）
    assert score(log, False)["min_ttc_s"] == float("inf")
