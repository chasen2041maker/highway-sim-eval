"""A8 感知版的回归测试：真值版 vs 感知版的数字，和 2026-10-29 在笔记本上跑出来的一样。"""

import math

import pytest

from examples.a8_perception_drive import simulate


@pytest.fixture(scope="module")
def runs():
    """真值版、感知版各跑一遍（感知版约 4 秒）。"""
    return simulate(False)[1], simulate(True)[1]


def test_truth_version_matches_a8_model_drive(runs):
    truth, _ = runs
    assert min(truth["gap"]) == pytest.approx(7.61, abs=0.02)
    assert min(truth["accel"]) == pytest.approx(-4.46, abs=0.02)


def test_lidar_version_brakes_much_harder_but_does_not_crash(runs):
    truth, lidar = runs
    assert min(lidar["gap"]) > 0
    assert min(lidar["accel"]) == pytest.approx(-6.88, abs=0.05)
    assert min(lidar["accel"]) < min(truth["accel"]) - 2      # 看晚了约 1 秒，最后一脚猛了 2 以上


def test_lidar_sees_the_gap_shorter(runs):
    _, lidar = runs
    errs = [s - g for s, g in zip(lidar["seen_gap"], lidar["gap"]) if not math.isnan(s)]
    assert sum(errs) / len(errs) == pytest.approx(-0.80, abs=0.05)
    assert min(errs) == pytest.approx(-2.36, abs=0.05)        # 直道上只打到车尾，差半个车长


def test_parked_car_never_picked_and_lead_id_switches_once(runs):
    _, lidar = runs
    assert sorted({i for i in lidar["lead_id"] if i}) == [1, 5]   # 进弯后框中心一跳，1 号丢了、新发 5 号
