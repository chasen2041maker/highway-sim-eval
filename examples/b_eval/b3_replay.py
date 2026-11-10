"""B3 第 3 步（下）：回灌（开环回放）。

不开模拟器：把录像里考生每一帧“看到的”，一帧一帧喂给考生（可以换设置），看它每一帧的决定和录像里一不一样。
  ① 原样回放（和录像时同样的设置）：每一帧的决定必须和录像一模一样——检查回灌系统本身没问题
  ② 换成往前看 0.5 秒：第一次踩刹车比录像早多少
开环的局限：新考生刹得早了，录像里的世界不会跟着变（车还是照录像里的样子往前开），
所以只有“第一次决定不一样”之前的帧可信；换了考生撞不撞，要回到闭环（重新跑模拟器）才知道。
运行（在项目根目录，先 conda activate py310；先跑过 b3_record）：
    python -m examples.b_eval.b3_replay          换成往前看 0.5 秒
    python -m examples.b_eval.b3_replay 1.0      换成往前看 1.0 秒
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np

from examples.b_eval.b1_highway_brake import MAX_BRAKE_MPS2, follow, pick_lead, to_action

np.seterr(divide="ignore")
REC = Path(__file__).resolve().parents[2] / "outputs" / "recordings" / "b1_bank_p0.parquet"
BRAKE = -0.5                       # 比这更猛算“踩了刹车”（和 B1 判误刹的门槛一样）


def load(path: Path) -> dict[int, list[dict]]:
    """读录像：{第几题: [一帧一个字典，按时间排好]}。"""
    rows = duckdb.execute(
        "SELECT question, k, t_s, seen, ego_v, accel_cmd, crashed FROM read_parquet($p) ORDER BY question, k",
        {"p": path.as_posix()}).fetchall()
    by_question = {}
    for question, k, t_s, seen, ego_v, accel_cmd, crashed in rows:
        by_question.setdefault(question, []).append(
            {"k": k, "t_s": t_s, "seen": seen, "ego_v": ego_v, "accel_cmd": accel_cmd, "crashed": crashed})
    return by_question


def replay(frames: list[dict], predict_s: float, confirm_frames: int = 1, accel: bool = False) -> list[float]:
    """把录像一帧一帧喂给考生，返回考生每一帧要踩多大（和 b1_cut_in.run 里考生那几行一模一样，只是不开模拟器）。"""
    out = []
    prev = None
    streak = 0
    for f in frames:
        seen = np.array(f["seen"])
        lead = pick_lead(seen, predict_s, prev if accel else None)    # ① 挑前车
        prev = seen
        streak = streak + 1 if lead is not None else 0
        if streak < confirm_frames:
            lead = None
        action = to_action(follow(seen, lead), f["ego_v"])            # ② 算刹车（刹到停为止，用录像里的真车速）
        out.append(float(action[0] * MAX_BRAKE_MPS2))
    return out


def first_brake(times: list[float], accels: list[float]):
    """第一次踩刹车是第几秒；一直没刹就是 None。"""
    for t, a in zip(times, accels):
        if a < BRAKE:
            return t
    return None


def show(t) -> str:
    return "没刹" if t is None else f"第 {t:.1f} 秒"


def main():
    new_p = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    rec = load(REC)
    names = ["陪跑（不该刹）", "切入 10 米", "切入 5 米", "压线（该刹）", "靠线（不该刹）"]
    print(f"录像：不预测（往前看 0 秒）；回灌换成：往前看 {new_p:g} 秒\n")
    print("题  题目            录像里撞没撞  ① 原样回放一致？  录像第一次刹车   换考生后第一次刹车   提前多少")
    for n, frames in rec.items():
        times = [f["t_s"] for f in frames]
        recorded = [f["accel_cmd"] for f in frames]
        same = replay(frames, 0.0) == recorded
        t_old = first_brake(times, recorded)
        t_new = first_brake(times, replay(frames, new_p))
        earlier = "-" if t_old is None or t_new is None else f"{t_old - t_new:.1f} 秒"
        print(f"{n:<3} {names[n - 1]:<14} {'撞了' if frames[0]['crashed'] else '没撞':<10} {'一模一样' if same else '不一样！':<12}"
              f"   {show(t_old):<12} {show(t_new):<16} {earlier}")


if __name__ == "__main__":
    main()
