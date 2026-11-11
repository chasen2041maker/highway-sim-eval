"""B4 实验（计划外，2026-11-11）：给考生的刹车加急动度上限，看舒服了多少、安全上付出多少。

考生只改“怎么踩”，不改“什么时候踩”：踩的深浅每 0.1 秒最多变 上限 × 0.1。
上限：不限（原来的开关式，0.1 秒一脚到 −8，急动度 80）、20、10、5 m/s³
（10 = 每 0.1 秒最多多踩 1，要 0.8 秒才踩到 −8；5 要 1.6 秒）。
默认考生往前看 0.5 秒（B1 五道题全对的那位），可以换：
笔记本实测（往前看 0.5 秒）：
  第 2 题最小车距 5.68 / 4.98 / 4.14 / 2.77 米、最小 TTC 2.40 / 1.60 / 1.37 / 1.18 秒（越舒服越近）；
  第 3 题（切入 5 米）只要加上限就撞，连 20 也撞：紧急时要放开上限，一脚到底。
  上限 5 时第 2 题最大急动度报 45：上限也限制“松刹车”，从 −7 每 0.1 秒只能松 0.5，
  车速 3.45 → 0（第 3.3 秒），在高速上停住了（前车还在开 10 m/s）；停住那一刻“别倒车”把 −4.5 改成 0，才跳了 45。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b4_jerk_limit          往前看 0.5 秒
    python -m examples.b_eval.b4_jerk_limit 1.0      往前看 1.0 秒
"""

from __future__ import annotations

import math
import sys

from examples.b_eval.b1_cut_in import BANK, run
from examples.b_eval.b1_scenarios import judge

LIMITS = [None, 20.0, 10.0, 5.0]
NAMES = ["陪跑", "切入 10 米", "切入 5 米", "压线", "靠线"]


def num(x: float) -> str:
    return f"{'-':>6}" if math.isinf(x) else f"{x:6.2f}"


def main():
    predict_s = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    print(f"考生往前看 {predict_s} 秒；只改急动度上限（m/s³）")
    print("题            上限   判定   最小车距  最小TTC  最猛刹车  最大急动度")
    for n, sc in enumerate(BANK, start=1):
        for lim in LIMITS:
            s = run(sc, predict_s, jerk_limit_mps3=lim)
            ttc = f"{'撞':>5}" if s["crashed"] else num(s["min_ttc_s"])
            name = f"{n} {NAMES[n - 1]}" if lim is None else ""
            cap = "不限" if lim is None else f"{lim:.0f}"
            print(f"{name:<12} {cap:>4}   {judge(s):<4}  {num(s['min_gap_m'])}   {ttc}   {s['hardest_brake_mps2']:7.2f}  {s['max_jerk_mps3']:8.1f}")
    print("最小车距 - = 它一直没在我前面压进我的车道；最小 TTC - = 没在接近它")


if __name__ == "__main__":
    main()
