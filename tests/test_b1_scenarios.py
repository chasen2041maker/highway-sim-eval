"""B1 第 1 步：题库里五道“前车急刹”的回归测试。

数字来自 2026-10-30 第一次运行（笔记本 Windows 和云端 Linux 一样）。
第 3 题撞、第 4 / 5 题擦边（1.34 / 0.50 米）：哪天分数变了，先看是考生、考场还是题目改了。
"""

import pytest

pytest.importorskip("highway_env")

from examples.b_eval.b1_scenarios import BANK, judge, run  # noqa: E402
from scenarios.lead_brake import LeadBrake  # noqa: E402


def test_default_is_the_10_27_problem():
    assert LeadBrake() == LeadBrake(gap_m=25, ego_speed_mps=10, lead_speed_mps=10, lead_decel_mps2=5)


# (撞没撞, 最小车距, 判定)
EXPECTED = [(False, 4.95, "过"), (False, 4.95, "过"), (True, 0.15, "不过"), (False, 1.34, "险过"), (False, 0.50, "险过")]


@pytest.mark.parametrize("n", range(len(EXPECTED)))
def test_bank(n):
    s = run(BANK[n])
    crashed, min_gap, verdict = EXPECTED[n]
    assert s["crashed"] is crashed
    assert s["min_gap_m"] == pytest.approx(min_gap, abs=0.01)
    assert judge(s) == verdict


def test_judge_rules():
    """门槛 2 米、-6.0（11-01 定）：撞了不过；离得太近或刹得太猛险过；正好 -6.0 也算险过。"""
    ok = {"crashed": False, "min_gap_m": 4.95, "hardest_brake_mps2": -5.93}
    assert judge(ok) == "过"
    assert judge({**ok, "crashed": True}) == "不过"
    assert judge({**ok, "min_gap_m": 1.99}) == "险过"
    assert judge({**ok, "hardest_brake_mps2": -6.0}) == "险过"
