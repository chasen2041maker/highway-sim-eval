"""A6 第 4 步：给多车跟踪器打分——同一段假路况，MAX_MISSES 10 和 3 各跑一遍，对答案。

场景和第 3 步一样（sim/fake_traffic.py）：三辆车，右车道 2.0–2.4 秒被挡住，3.5 秒护栏误检一次。
跟踪器：ads/tracking.py 的 MultiTracker（本人写）；考官：evaluation/metrics.py 的 tracking_metrics（本人写）。

运行（在项目根目录）：python -m examples.a6_track_eval
"""

from ads.tracking import MultiTracker
from evaluation.metrics import tracking_metrics
from sim.fake_traffic import DT_S, default_cars, make_scene

GATE_M = 2.0


def run(max_misses):
    """跑一整段，记下每帧的真值和纸条，交给考官。"""
    scene = make_scene()
    speed = {c.name: (c.vx_mps, 0.0) for c in default_cars()}   # 真车速度（匀速，y 方向不动）
    mt = MultiTracker(gate_m=GATE_M, max_misses=max_misses)
    truth, tracks = [], []
    for k, det in enumerate(scene.detections):
        mt.step(det, DT_S)
        truth.append({name: (*xy[k], *speed[name]) for name, xy in scene.truth.items()})
        tracks.append({t.id: (*t.xy, t.kx.x[1], t.ky.x[1]) for t in mt.tracks})
    return tracking_metrics(truth, tracks, GATE_M)


def main():
    rows = [("位置误差（米）", "pos_err_m", "{:.2f}"), ("速度误差（m/s）", "speed_err_mps", "{:.2f}"),
            ("编号跳变（次）", "id_switches", "{}"), ("漏（真车没配上，帧·辆）", "missed", "{}"),
            ("多（纸条没配上，帧·张）", "false_tracks", "{}")]
    results = {mm: run(mm) for mm in (10, 3)}
    print("51 帧 × 3 辆车 = 153 次对答案；左边 MAX_MISSES = 10，右边 MAX_MISSES = 3")
    for label, key, fmt in rows:
        print(f"{label}：{fmt.format(results[10][key])}  |  {fmt.format(results[3][key])}")


if __name__ == "__main__":
    main()
