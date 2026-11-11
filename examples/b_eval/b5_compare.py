"""B5 第 2 步：两个版本的结果表一道一道对比——哪些题变好、哪些变差、哪些不变。

先给每一行（一道题 × 一种路况）定一个“结果等级”，数越大越糟：
  3 撞了：会进来、能躲开（一开始就踩死能躲开），却撞了（B2 的表里叫“漏刹”；刹晚了、或者刹了反而撞上都算）
  2 误刹：不进来，却踩了刹车
  1 险：没撞、没误刹，但最小 TTC < 1.5 秒，或者和它并排擦过去（车身压进我车道、前后距离 < 0）
  0 正常
  躲不开：踩死也躲不开的题，谁考都撞，不参与比较
再把两个版本同一道题、同一种路况的两行配成一对：新版本等级更高 = 变差，更低 = 变好，一样 = 不变。
运行（在项目根目录，先 conda activate py310；先跑过 b5_run v1 和 v2）：
    python -m examples.b_eval.b5_compare            v1 → v2
    python -m examples.b_eval.b5_compare v2 v1      反过来
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import duckdb

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "regression"
TTC_RISKY_S = 1.5                     # 最小 TTC 低于这个算“险”（C0 难例挖掘也用这个门槛）
NAMES = {3: "撞了", 2: "误刹", 1: "险", 0: "正常", None: "躲不开"}
KEY = ("question", "noise_y_m", "delay_s")


def level(r: dict) -> int | None:
    """一行结果 → 结果等级（越大越糟）；躲不开的题返回 None。"""
    if r["missed"]:
        return 3
    if r["crashed"]:
        return None
    if r["false_brake"]:
        return 2
    if r["min_gap_m"] < 0 or r["min_ttc_s"] < TTC_RISKY_S:
        return 1
    return 0


def compare(old_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """同一道题、同一种路况配成一对，返回每一对：键、两边等级、变化（变差 / 变好 / 不变 / 躲不开）、两边原始行。"""
    new_by_key = {tuple(r[k] for k in KEY): r for r in new_rows}
    pairs = []
    for old in old_rows:
        key = tuple(old[k] for k in KEY)
        new = new_by_key[key]
        a, b = level(old), level(new)
        if a is None or b is None:
            change = "躲不开"
        elif b > a:
            change = "变差"
        elif b < a:
            change = "变好"
        else:
            change = "不变"
        pairs.append({"key": key, "old": a, "new": b, "change": change, "old_row": old, "new_row": new})
    return pairs


def load(version: str) -> list[dict]:
    rel = duckdb.sql(f"""SELECT * FROM read_csv('{(OUT_DIR / f"{version}.csv").as_posix()}',
                         types = {{'min_gap_m': 'DOUBLE', 'min_ttc_s': 'DOUBLE', 'max_jerk_mps3': 'DOUBLE'}})
                         WHERE status = 'ok' ORDER BY question, noise_y_m, delay_s""")
    names = [d[0] for d in rel.description]
    return [dict(zip(names, row)) for row in rel.fetchall()]


def road(r: dict) -> str:
    return f"噪声 {r['noise_y_m']:.1f} 延迟 {r['delay_s']:.1f}"


def detail(r: dict) -> str:
    gap = "-" if r["min_gap_m"] == float("inf") else ("并排" if r["min_gap_m"] < 0 else f"{r['min_gap_m']:.2f}")
    ttc = "-" if r["min_ttc_s"] == float("inf") or r["min_gap_m"] < 0 else f"{r['min_ttc_s']:.2f}"
    return f"车距 {gap:>5}  TTC {ttc:>5}  最猛刹车 {r['hardest_brake_mps2']:6.2f}"


def main():
    old_v, new_v = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("v1", "v2")
    pairs = compare(load(old_v), load(new_v))
    counts = Counter(p["change"] for p in pairs)
    print(f"{old_v} → {new_v}：{len(pairs)} 对（同一道题、同一种路况）")
    print("  " + "  ".join(f"{c} {counts[c]}" for c in ("变差", "变好", "不变", "躲不开")))

    print(f"\n怎么变的（{old_v} → {new_v}，不含不变的）")
    moves = Counter((NAMES[p["old"]], NAMES[p["new"]]) for p in pairs if p["change"] in ("变差", "变好"))
    for (a, b), n in sorted(moves.items(), key=lambda kv: -kv[1]):
        print(f"  {a:<3} → {b:<3} {n:>4}")

    worse = sorted((p for p in pairs if p["change"] == "变差"), key=lambda p: (-p["new"], p["key"]))
    print(f"\n变差的前 10 对（最糟的在前）")
    for p in worse[:10]:
        o, n = p["old_row"], p["new_row"]
        print(f"  题 {o['question']:>3}  {road(o)}  {NAMES[p['old']]} → {NAMES[p['new']]}")
        print(f"        {old_v}: {detail(o)}")
        print(f"        {new_v}: {detail(n)}")


if __name__ == "__main__":
    main()
