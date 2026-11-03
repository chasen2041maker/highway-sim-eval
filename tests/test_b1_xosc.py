"""B1 第 4 步：前车急刹写成 OpenSCENARIO（scenarios/lead_brake.xosc）。

换题目格式，分数不能变：读进来必须是同一个 LeadBrake，考出来和题库一样（2026-11-03 核对）。
文件已用 CARLA ScenarioRunner 自带的 OpenSCENARIO 1.0 schema 校验过（schema 不放进仓库）。
"""

from pathlib import Path

import pytest

from scenarios.lead_brake import LeadBrake
from scenarios.xosc import load_lead_brake

XOSC = Path(__file__).resolve().parent.parent / "scenarios" / "lead_brake.xosc"


def test_file_defaults_are_the_bank_question_1():
    assert load_lead_brake(XOSC) == LeadBrake()


def test_override_without_editing_the_file():
    assert load_lead_brake(XOSC, gap="12", egoSpeed="20") == LeadBrake(gap_m=12, ego_speed_mps=20)


def test_unknown_parameter_is_an_error():
    with pytest.raises(KeyError):
        load_lead_brake(XOSC, gapp=3)


def test_center_distance_trigger_is_rejected(tmp_path):
    """触发距离要按车头到车尾（freespace）；按车中心量的话差一个车长，不能当成 gap_m。"""
    bad = tmp_path / "bad.xosc"
    bad.write_text(XOSC.read_text(encoding="utf-8").replace('freespace="true"', 'freespace="false"'), encoding="utf-8")
    with pytest.raises(ValueError):
        load_lead_brake(bad)


pytest.importorskip("highway_env")

from examples.b1_scenarios import judge, run  # noqa: E402


@pytest.mark.parametrize("overrides, verdict, min_gap", [({}, "过", 4.95), ({"gap": 12, "egoSpeed": 20}, "不过", 0.15)])
def test_same_score_as_the_python_bank(overrides, verdict, min_gap):
    s = run(load_lead_brake(XOSC, **overrides))
    assert judge(s) == verdict
    assert s["min_gap_m"] == pytest.approx(min_gap, abs=0.01)
