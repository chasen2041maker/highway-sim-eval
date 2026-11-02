"""B1 第 2 步：邻车加塞的回归测试。

数字来自 2026-11-01 晚第一次运行（笔记本 Windows 和云端 Linux 一样），考生已改成“只看我车道上的车”。
改之前（只看离我最近的车、不管车道）：陪跑题第 0 秒猛刹 -8（幽灵刹车），第 3 题反而没撞（剩 3.90 米）。
"""

import math

import pytest

pytest.importorskip("highway_env")

from examples.b1_cut_in import BANK, run  # noqa: E402
from examples.b1_highway_brake import idm_driver  # noqa: E402
from examples.b1_scenarios import judge  # noqa: E402

# (撞没撞, 最小车距, 判定)；inf = 它还没进我的车道（陪跑一直在旁边；第 3 题切到一半就擦上了）
EXPECTED = [(False, math.inf, "过"), (False, 2.18, "险过"), (True, math.inf, "不过")]


@pytest.mark.parametrize("n", range(len(EXPECTED)))
def test_bank(n):
    s = run(BANK[n])
    crashed, min_gap, verdict = EXPECTED[n]
    assert s["crashed"] is crashed
    if math.isinf(min_gap):
        assert math.isinf(s["min_gap_m"])
    else:
        assert s["min_gap_m"] == pytest.approx(min_gap, abs=0.01)
    assert judge(s) == verdict


def test_side_lane_car_is_not_the_lead():
    """旁边车道更近的车不算前车：第 1 行在旁边车道（y = -4），第 2 行才是我车道上的前车。"""
    ego = [1, 0.0, 4.0, 15.0, 0.0]
    side = [1, 15.0, -4.0, -5.0, 0.0]
    mine = [1, 35.0, 0.0, -5.0, 0.0]
    empty = [0, 0.0, 0.0, 0.0, 0.0]
    only_mine = idm_driver([ego, mine, empty, empty, empty])
    assert idm_driver([ego, side, mine, empty, empty]) == pytest.approx(only_mine)
    free_road = idm_driver([ego, empty, empty, empty, empty])
    assert idm_driver([ego, side, empty, empty, empty]) == pytest.approx(free_road)
