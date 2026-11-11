"""B4 第 3 步：舒适度。加塞题库 5 道 × 4 种往前看，每格两个数：最猛刹车、最大急动度。

最猛刹车（m/s²，负 = 刹车）：踩得多深。
最大急动度（m/s³）：踩得多急 = 加速度每秒变多少。0.1 秒里从 0 一下踩到 −8，就是 80；
花 4 秒从 0 慢慢加到 −8，只有 2。数越大，乘客越往前栽。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b4_comfort
"""

from __future__ import annotations

from examples.b_eval.b1_cut_in import BANK, PREDICT_S, run

NAMES = ["陪跑", "切入 10 米", "切入 5 米", "压线", "靠线"]


def main():
    print("题           |  " + "    ".join(f"往前看 {p:.1f} 秒  " for p in PREDICT_S))
    for n, sc in enumerate(BANK, start=1):
        cells = []
        for p in PREDICT_S:
            s = run(sc, p)
            cells.append(f"{s['hardest_brake_mps2']:6.2f} {s['max_jerk_mps3']:6.1f}")
        print(f"{n} {NAMES[n - 1]:<10} |  " + "    ".join(cells))
    print("每格：最猛刹车（m/s²）  最大急动度（m/s³）")


if __name__ == "__main__":
    main()
