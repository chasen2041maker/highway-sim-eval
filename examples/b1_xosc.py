"""B1 第 4 步：同一道“前车急刹”写成 OpenSCENARIO（scenarios/lead_brake.xosc），读进来变成 LeadBrake，在 HighwayEnv 里考。

运行（在项目根目录）：
    python -m examples.b1_xosc                     用文件里的参数
    python -m examples.b1_xosc gap=12 egoSpeed=20  临时改参数（不改文件）
"""

from __future__ import annotations

import sys
from pathlib import Path

from examples.b1_scenarios import judge, run
from scenarios.xosc import load_lead_brake

XOSC = Path(__file__).resolve().parent.parent / "scenarios" / "lead_brake.xosc"


def main():
    overrides = dict(arg.split("=") for arg in sys.argv[1:])
    sc = load_lead_brake(XOSC, **overrides)
    print(sc)
    s = run(sc)
    print(f"判定 {judge(s)}  最小车距 {s['min_gap_m']:.2f}  最猛刹车 {s['hardest_brake_mps2']:.2f}  撞了 {s['crashed']}")


if __name__ == "__main__":
    main()
