"""B5：从回归对比里挑出一道题，两个版本逐帧对着看。

每一行：第几秒、我的车速、它在我前面几米（两车中心之差，负数 = 它已经在我后面）、
它的横向位置（0 = 旁边车道中心，2 = 我的车道线，4 = 我的车道中心；它车身边 = 这个数 + 1，所以过了 1 车身就压线了）、
考生认没认出前车、踩多大。只打前 4 秒，每 0.2 秒一行。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b5_look 25            第 25 题，干净路况
    python -m examples.b_eval.b5_look 25 0.2 0.3    第 25 题，噪声 0.2 米、延迟 0.3 秒
"""

from __future__ import annotations

import sys

from examples.b_eval.b1_cut_in import run
from examples.b_eval.b2_grid import make_questions
from examples.b_eval.b5_run import N_QUESTIONS, SEED, VERSIONS

SHOW_S = 4.0


def frames_of(version: str, q: int, noise_y_m: float = 0.0, delay_s: float = 0.0):
    """第 q 题让这个版本考一遍，边考边录：返回 (题目, 会不会进来, 成绩, 每一帧)。噪声种子 = 题号，和 b5_run 一样。"""
    sc, comes_in = make_questions(N_QUESTIONS, SEED)[q - 1]
    v = VERSIONS[version]
    frames = []
    s = run(sc, v["predict_s"], noise_y_m=noise_y_m, delay_s=delay_s, seed=q,
            confirm_frames=v["confirm_frames"], accel=v["accel"], frames=frames)
    return sc, comes_in, s, frames


def main():
    q = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    noise_y_m = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    delay_s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    for version in VERSIONS:
        sc, comes_in, s, frames = frames_of(version, q, noise_y_m, delay_s)
        if version == "v1":
            print(f"第 {q} 题（噪声 {noise_y_m} 延迟 {delay_s}）：{sc}，{'会切进来' if comes_in else '不会切进来'}")
        print(f"\n{version} {VERSIONS[version]}：{'撞了' if s['crashed'] else '没撞'}（录到第 {frames[-1]['t_s']:.1f} 秒）")
        print("  第几秒  我的车速  它在我前面  它的横向  认出前车  踩多大")
        for f in frames:
            k = round(f["t_s"] * 10)
            if f["t_s"] <= SHOW_S + 1e-9 and (k % 2 == 0 or f is frames[-1]):
                print(f"  {f['t_s']:5.1f}  {f['ego_v']:7.1f}  {f['cutter_x'] - f['ego_x']:9.1f}  {f['cutter_y']:7.2f}"
                      f"   {'是' if f['lead_seen'] else '否'}    {f['accel_cmd']:6.1f}")


if __name__ == "__main__":
    main()
