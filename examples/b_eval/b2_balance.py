"""B2 第 4 步（下半）：从网格结果表里，找漏刹和误刹的平衡点。

表里一行是一个任务。这里按“路况 + 考生设置”分组，数每组漏刹几道、误刹几道，
再按一个权重（漏刹 1 道算误刹几道那么糟）算代价，挑代价最小的考生设置。
不用重跑考场，只读表：表存下来了，想换个看法随时再算（B3 会把表放进数据库查）。

运行（在项目根目录）：
    python -m examples.b_eval.b2_balance 50 10      读 outputs/b2_grid_50.csv，漏刹 1 道 = 误刹 10 道
    python -m examples.b_eval.b2_balance 1000 10    读 1000 道的表
    python -m examples.b_eval.b2_balance 1000 10 2  读种子 2 那批新题的表 outputs/b2_grid_1000_seed2.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"
ROADS = [("0.0", "0.0", "干净"), ("0.0", "0.3", "延迟 0.3 秒"),
         ("0.2", "0.0", "噪声 0.2 米"), ("0.2", "0.3", "噪声 + 延迟")]
PREDICT_S = ["0.0", "0.5", "1.0", "1.5"]          # 表里读出来的都是文字，所以这里也写成文字
CONFIRM_FRAMES = ["1", "3"]
ACCEL = ["False", "True"]


def load(n: int, seed: int = 1) -> list[dict]:
    """读 outputs/b2_grid_<n>.csv（种子 2 就读 b2_grid_<n>_seed2.csv），一行变成一个字典：{列名: 这一格的文字}。"""
    if seed == 1:
        path = OUT_DIR / f"b2_grid_{n}.csv"
    else:
        path = OUT_DIR / f"b2_grid_{n}_seed{seed}.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"读了 {path.name}：{len(rows)} 行")
    return rows


def count(rows: list[dict]) -> dict:
    """按（噪声, 延迟, 往前看, 确认, 匀加速）分组，数每组漏刹几道、误刹几道。"""
    counts = {}
    for r in rows:
        key = (r["noise_y_m"], r["delay_s"], r["predict_s"], r["confirm_frames"], r["accel"])
        if key not in counts:
            counts[key] = [0, 0]                     # [漏刹, 误刹]
        if r["missed"] == "True":
            counts[key][0] += 1
        if r["false_brake"] == "True":
            counts[key][1] += 1
    return counts


def not_ok_groups(rows: list[dict]) -> dict:
    """没交卷（status 不是 ok：卡死 / 报错）的任务，按组数：{(噪声, 延迟, 往前看, 确认, 匀加速): 几个}。
    它们没有结果，漏刹 / 误刹格子是空的，数的时候等于“没漏刹、没误刹”——那几组的数会偏好看。"""
    groups = {}
    for r in rows:
        if r.get("status", "ok") != "ok":
            key = (r["noise_y_m"], r["delay_s"], r["predict_s"], r["confirm_frames"], r["accel"])
            if key not in groups:
                groups[key] = 0
            groups[key] += 1
    return groups


def question_counts(rows: list[dict]) -> tuple[int, int, int]:
    """数题：会进来的题里能躲开几道、踩死也躲不开几道（这种撞了不算漏刹），不进来的题几道。"""
    come_in, unavoidable, stay_out = set(), set(), set()
    for r in rows:
        if r["comes_in"] == "True":
            come_in.add(r["question"])
            if r["crashed"] == "True" and r["missed"] == "False":   # 撞了却不算漏刹 = 踩死也躲不开
                unavoidable.add(r["question"])
        else:
            stay_out.add(r["question"])
    return len(come_in) - len(unavoidable), len(unavoidable), len(stay_out)


def print_road(counts: dict, road: tuple, weight: float) -> None:
    """一种路况下，16 种考生设置各漏刹几道、误刹几道、代价多少；代价最小的打 ★。"""
    noise, delay, name = road
    table = []
    for p in PREDICT_S:
        for c in CONFIRM_FRAMES:
            for a in ACCEL:
                missed, false = counts[(noise, delay, p, c, a)]
                table.append((p, c, a, missed, false, missed * weight + false))
    best = table[0]
    for t in table:
        if t[5] < best[5]:                            # 代价更小就换；一样小的留前面那个（更简单的设置）
            best = t
    print()
    print(f"路况：{name}")
    print("  往前看  确认  预测方法   漏刹  误刹   代价")
    for t in table:
        p, c, a, missed, false, cost = t
        method = "匀加速" if a == "True" else "匀速  "
        star = "  ★" if t is best else ""
        print(f"  {p} 秒  {c} 帧   {method}   {missed:>4}  {false:>4}  {cost:>5g}{star}")


def print_overall(counts: dict, weight: float) -> None:
    """车上只能装一套设置：四种路况的代价加起来，挑总代价最小的。"""
    table = []
    for p in PREDICT_S:
        for c in CONFIRM_FRAMES:
            for a in ACCEL:
                total = 0
                for noise, delay, _ in ROADS:
                    missed, false = counts[(noise, delay, p, c, a)]
                    total += missed * weight + false
                table.append((p, c, a, total))
    best = table[0]
    for t in table:
        if t[3] < best[3]:
            best = t
    print()
    print("四种路况加起来（车上只能装一套）")
    print("  往前看  确认  预测方法   总代价")
    for t in table:
        p, c, a, total = t
        method = "匀加速" if a == "True" else "匀速  "
        star = "  ★" if t is best else ""
        print(f"  {p} 秒  {c} 帧   {method}   {total:>6g}{star}")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50              # 读哪张表
    weight = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0     # 漏刹 1 道算几道误刹
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1            # 读哪个种子的表
    rows = load(n, seed)
    bad = not_ok_groups(rows)
    if bad:
        print("注意：下面这几组有任务没交卷（卡死 / 报错），它们被当成没漏刹、没误刹，这几组的数偏好看。先重跑它们，再信 ★：")
        for key, k in bad.items():
            noise, delay, p, c, a = key
            print(f"  噪声 {noise} 米、延迟 {delay} 秒、往前看 {p} 秒、确认 {c} 帧、匀加速 {a}：{k} 个没交卷")
    n_avoidable, n_unavoidable, n_out = question_counts(rows)
    print(f"会进来的题：能躲开 {n_avoidable} 道（另有 {n_unavoidable} 道踩死也躲不开，撞了不算漏刹）；不进来的题 {n_out} 道")
    print(f"代价 = 漏刹 × {weight:g} + 误刹")
    counts = count(rows)
    for road in ROADS:
        print_road(counts, road, weight)
    print_overall(counts, weight)


if __name__ == "__main__":
    main()
