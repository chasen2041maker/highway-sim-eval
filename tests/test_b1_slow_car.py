"""B1 第 3 种题：慢车挡路的回归测试。

数字来自 2026-11-03 第一次运行（笔记本 Windows 和云端 Linux 一样）。
判定只看安全，所以第 3 题“险过”，可 15 秒少走 170 米：这个考生只会跟车、不会换道。
第 4 题慢车和我一样快，是无效题（考的其实是“开局离太近”），is_valid 把它挡掉。
"""

import pytest

from scenarios.slow_car import SlowCar, is_valid


def test_default():
    assert SlowCar() == SlowCar(gap_m=40, ego_speed_mps=15, slow_speed_mps=8)


def test_is_valid():
    assert is_valid(SlowCar(slow_speed_mps=8))
    assert not is_valid(SlowCar(slow_speed_mps=15))   # 一样快：不是慢车
    assert not is_valid(SlowCar(slow_speed_mps=16))   # 比我快：更不是


highway_env = pytest.importorskip("highway_env")

from examples.b_eval.b1_scenarios import judge  # noqa: E402
from examples.b_eval.b1_slow_car import BANK, run  # noqa: E402

# (判定, 最小车距, 最猛刹车, 少走了多少米)
EXPECTED = [("过", 18.90, -0.79, 44), ("险过", 15.55, -8.00, 103), ("险过", 8.86, -8.00, 170)]


@pytest.mark.parametrize("n", range(len(EXPECTED)))
def test_bank(n):
    s = run(BANK[n])
    verdict, min_gap, brake, lost = EXPECTED[n]
    assert s["crashed"] is False
    assert judge(s) == verdict
    assert s["min_gap_m"] == pytest.approx(min_gap, abs=0.01)
    assert s["hardest_brake_mps2"] == pytest.approx(brake, abs=0.01)
    assert s["lost_m"] == pytest.approx(lost, abs=0.5)


def test_bank_4_is_invalid():
    assert not is_valid(BANK[3])
