"""B1：随机出新题，检验“预测 0.5 秒”是不是真的好（参数随机采样 / 域随机化）。

预测 0.5 秒在题库那五道题上全对，可那五道题本来就是拿来挑它的（调参题 = 考试题 = 背答案）。
这里让程序随机出 40 道没见过的新题：20 道“会进来”（车身压过我的车道线）、20 道“不进来”（车身始终在线外），
同一个考生用四档预测各考一遍，数两种错：
  漏刹：会进来、而且一开始就踩死能躲开的题，却撞了
  误刹：根本不进来的题，却刹了车
随机数种子固定（SEED），每次跑出来的题都一样，结果能复现。

运行（在项目根目录，要 1–2 分钟）：
    python -m examples.b1_cut_in_random          不加延迟
    python -m examples.b1_cut_in_random 0.3      故障注入：考生看到的路况晚 0.3 秒
    python -m examples.b1_cut_in_random 0 0.2    故障注入：不加延迟，别的车的横向位置加 0.2 米噪声
    python -m examples.b1_cut_in_random 0 0.2 3  再加防噪声：连续 3 帧都挑出前车才算数
    python -m examples.b1_cut_in_random 0 0 1 1  预测算上横向加速度（匀加速外推），不加故障
"""

from __future__ import annotations

import random
import sys

import numpy as np

import examples.b1_cut_in as cut_in_exam
from examples.b1_cut_in import PREDICT_S, run
from scenarios.cut_in import CutIn

SEED = 0
N_EACH = 20          # “会进来”“不进来”各出几道

np.seterr(divide="ignore")   # 撞上那一刻车距是 0，IDM 公式里会除以 0；结果是无穷大，不影响判断，只是不让它刷屏


def sample_cut_in(rng: random.Random, comes_in: bool) -> CutIn:
    """随机出一道加塞题。comes_in = True：车身会压过我的车道线；False：车身始终在线外。"""
    return CutIn(
        gap_m=round(rng.uniform(3, 30), 1),
        ego_speed_mps=15.0,
        cut_speed_mps=round(rng.uniform(5, 15), 1),
        cut_time_s=round(rng.uniform(1, 4), 1),
        cut_depth_m=round(rng.uniform(1.2, 4.0) if comes_in else rng.uniform(0.3, 0.9), 2),
    )


def avoidable(sc: CutIn) -> bool:
    """一开始就把刹车踩死（-8）能不能躲开？躲不开的题，谁来考都撞，不算考生漏刹。"""
    real = cut_in_exam.follow
    cut_in_exam.follow = lambda obs, lead: -8.0          # 不管看到什么，一律踩死
    try:
        return not run(sc)["crashed"]
    finally:
        cut_in_exam.follow = real


def main():
    delay_s = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0     # 故障注入：考生看到的路况晚几秒
    noise_y_m = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0   # 故障注入：别的车横向位置的噪声（标准差，米）
    confirm = int(sys.argv[3]) if len(sys.argv) > 3 else 1         # 防噪声：连续几帧都挑出前车才算数
    accel = len(sys.argv) > 4 and sys.argv[4] == "1"               # 预测算不算横向加速度（1 = 匀加速外推）
    rng = random.Random(SEED)
    questions = [(sample_cut_in(rng, True), True) for _ in range(N_EACH)] + \
                [(sample_cut_in(rng, False), False) for _ in range(N_EACH)]
    can_avoid = [avoidable(sc) if comes_in else True for sc, comes_in in questions]
    n_in = sum(1 for (_, ci), ok in zip(questions, can_avoid) if ci and ok)
    print(f"随机出了 {len(questions)} 道新题：会进来 {N_EACH} 道（其中踩死能躲开 {n_in} 道）、不进来 {N_EACH} 道。")
    print(f"考生看到的路况晚 {delay_s:.1f} 秒，别的车横向位置噪声 {noise_y_m:.1f} 米，连续 {confirm} 帧确认，"
          f"预测按{'匀加速（算上横向加速度）' if accel else '匀速'}往外推。")
    print()
    print("预测几秒  |  漏刹（能躲开的却撞了）  误刹（不进来却刹了）")
    bad = {}
    for p in PREDICT_S:
        missed, false = [], []
        for n, ((sc, comes_in), ok) in enumerate(zip(questions, can_avoid), start=1):
            s = run(sc, p, delay_s=delay_s, noise_y_m=noise_y_m, seed=n, confirm_frames=confirm, accel=accel)   # 每道题的噪声种子固定，能复现
            if comes_in and ok and s["crashed"]:
                missed.append(n)
            if not comes_in and s["hardest_brake_mps2"] < -0.5:
                false.append(n)
        bad[p] = (missed, false)
        print(f"  {p:.1f} 秒   |  {len(missed):>2} / {n_in} 道               {len(false):>2} / {N_EACH} 道")
    print()
    for p, (missed, false) in bad.items():
        print(f"预测 {p:.1f} 秒  漏刹的题号 {missed}  误刹的题号 {false}")
    print()
    print("题号  车距  它的车速  几秒切完  挪多远")
    for n in sorted({n for m, f in bad.values() for n in m + f}):
        sc = questions[n - 1][0]
        print(f"{n:>3}  {sc.gap_m:>5.1f}  {sc.cut_speed_mps:>7.1f}  {sc.cut_time_s:>7.1f}  {sc.cut_depth_m:>6.2f}")


if __name__ == "__main__":
    main()
