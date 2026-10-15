"""A4：跟车。前车 10 m/s，第 5 秒急刹（-5 m/s²）直到停下；我用 IDM 跟在后面。

直线上跟车，不打方向；x 就当成“车头位置”。看三件事：
  - 最近的时候离前车几米（最小车距）
  - 我最猛踩了多大的刹车
  - 撞没撞

运行（在项目根目录）：python -m examples.a4_follow
"""

from pathlib import Path

from ads.planning import idm_accel
from ads.vehicle import VehicleState, step

DT_S = 0.1
SIM_TIME_S = 15.0
TARGET_SPEED_MPS = 15.0        # 我想开到 15 m/s（54 km/h），但前车只开 10
START_SPEED_MPS = 10.0         # 两辆车一开始都是 10 m/s
START_GAP_M = 25.0             # 一开始离前车车尾 25 米
BRAKE_AT_S = 5.0               # 前车第 5 秒开始急刹
LEAD_BRAKE_MPS2 = -5.0         # 前车刹车：每秒车速减 5，2 秒停下
MAX_BRAKE_MPS2 = 8.0           # 我的车最猛也只能刹到 -8（轮胎抓地力的极限）


def simulate():
    """跑一遍，返回每一步的时间、车距、我的车速、前车车速、我的加速度。"""
    ego = VehicleState(x_m=0.0, speed_mps=START_SPEED_MPS)
    lead_x_m, lead_speed_mps = START_GAP_M, START_SPEED_MPS     # 前车车尾的位置、前车车速
    ts, gaps, ego_speeds, lead_speeds, accels = [], [], [], [], []
    # >>> 你手敲的循环放在这里（替换掉这一行）
    return ts, gaps, ego_speeds, lead_speeds, accels


def main():
    ts, gaps, ego_speeds, lead_speeds, accels = simulate()
    i_min = gaps.index(min(gaps))
    hardest = min(accels)
    crashed = min(gaps) <= 0
    print(f"最小车距 {gaps[i_min]:.2f} 米（第 {ts[i_min]:.1f} 秒）")
    print(f"我最猛的刹车 {hardest:.2f} m/s²")
    print("撞了！" if crashed else "没撞")
    plot(ts, gaps, ego_speeds, lead_speeds, accels)


# ---------- 以下是画图，助手写好的，不用手敲 ----------
EGO_COLOR, LEAD_COLOR, MARK_COLOR = "#2a78d6", "#9a9a94", "#eb6834"


def plot(ts, gaps, ego_speeds, lead_speeds, accels):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("没有装 matplotlib，跳过画图。需要的话运行：python -m pip install matplotlib")
        return
    fig, (ax_v, ax_gap, ax_a) = plt.subplots(3, 1, figsize=(8, 8), sharex=True)
    ax_v.plot(ts, lead_speeds, color=LEAD_COLOR, linewidth=2, linestyle="--", label="lead car")
    ax_v.plot(ts, ego_speeds, color=EGO_COLOR, linewidth=2, label="me (IDM)")
    ax_v.set_ylabel("speed (m/s)")
    ax_v.legend(frameon=False, loc="upper right")
    ax_gap.plot(ts, gaps, color=EGO_COLOR, linewidth=2)
    ax_gap.axhline(0, color=MARK_COLOR, linewidth=1.5, label="crash")
    ax_gap.axhline(5, color=LEAD_COLOR, linewidth=1, linestyle=":", label="5 m (min_gap_m)")
    ax_gap.set_ylabel("gap to lead (m)")
    ax_gap.legend(frameon=False, loc="upper right")
    ax_a.plot(ts, accels, color=EGO_COLOR, linewidth=2)
    ax_a.axhline(0, color=LEAD_COLOR, linewidth=1)
    ax_a.set_ylabel("my accel (m/s²)")
    ax_a.set_xlabel("time (s)")
    for ax in (ax_v, ax_gap, ax_a):
        ax.axvline(BRAKE_AT_S, color=MARK_COLOR, linewidth=1, linestyle="--")
        ax.grid(color="#e4e3dd", linewidth=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    ax_v.set_title("A4: lead car brakes hard at t = 5 s")
    fig.tight_layout()
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    fig.savefig(out_dir / "a4_follow.png", dpi=120)
    print("图已保存：outputs/a4_follow.png")


if __name__ == "__main__":
    main()
