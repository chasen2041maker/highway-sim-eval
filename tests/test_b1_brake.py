"""B 块第 1 步：HighwayEnv 里“前车急刹”最小闭环的回归测试。

数字来自 2026-10-27 第一次运行（笔记本 Windows 和云端 Linux 一样）。
哪天分数变了，先看是考生（ads/planning.py）改了、考场（HighwayEnv 版本、配置）变了，还是阅卷改了。
"""

import pytest

pytest.importorskip("highway_env")

from examples.b1_highway_brake import run  # noqa: E402


def test_lead_brake_in_highway_env():
    s = run()
    assert not s["crashed"]
    assert s["min_gap_m"] == pytest.approx(4.95, abs=0.01)          # 和 A4 一样
    assert s["hardest_brake_mps2"] == pytest.approx(-3.44, abs=0.01)  # A4 是 -3.69：前车“先挪再改速度”
    assert s["min_ttc_s"] == pytest.approx(2.15, abs=0.01)
