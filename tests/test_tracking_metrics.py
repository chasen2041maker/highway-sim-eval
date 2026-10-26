import math

import numpy as np
import pytest

from ads.tracking import MultiTracker
from evaluation.metrics import tracking_metrics
from sim.fake_traffic import DT_S, default_cars, make_scene


def test_perfect_tracker_scores_zero():
    truth = [{"a": (20.0, 0.0, -2.0, 0.0)}, {"a": (19.8, 0.0, -2.0, 0.0)}]
    tracks = [{1: (20.0, 0.0, -2.0, 0.0)}, {1: (19.8, 0.0, -2.0, 0.0)}]
    m = tracking_metrics(truth, tracks)
    assert m["pos_err_m"] == 0.0 and m["speed_err_mps"] == 0.0
    assert m["id_switches"] == 0 and m["missed"] == 0 and m["false_tracks"] == 0


def test_position_and_speed_error():
    # 纸条往前偏 0.3 米、往左偏 0.4 米（距离 0.5）；速度估成 -1（真的是 -2），差 1
    truth = [{"a": (20.0, 0.0, -2.0, 0.0)}]
    tracks = [{1: (20.3, 0.4, -1.0, 0.0)}]
    m = tracking_metrics(truth, tracks)
    assert math.isclose(m["pos_err_m"], 0.5) and math.isclose(m["speed_err_mps"], 1.0)


def test_id_switch_counted_once():
    # 同一辆车：第 0、1 帧是 1 号，第 2 帧变成 4 号 → 跳变 1 次
    truth = [{"a": (20.0, 0.0, 0.0, 0.0)}] * 3
    tracks = [{1: (20.0, 0.0, 0.0, 0.0)}, {1: (20.0, 0.0, 0.0, 0.0)}, {4: (20.0, 0.0, 0.0, 0.0)}]
    assert tracking_metrics(truth, tracks)["id_switches"] == 1


def test_gap_with_same_id_is_not_a_switch():
    # 第 1 帧一张纸条都没有（漏 1 次），第 2 帧还是 3 号 → 不算跳变；比的是“上一次配上的”编号
    truth = [{"a": (20.0, 0.0, 0.0, 0.0)}] * 3
    tracks = [{3: (20.0, 0.0, 0.0, 0.0)}, {}, {3: (20.0, 0.0, 0.0, 0.0)}]
    m = tracking_metrics(truth, tracks)
    assert m["id_switches"] == 0 and m["missed"] == 1


def test_far_track_is_one_miss_and_one_false_track():
    # 纸条离真车 3 米，超过 2 米门槛：真车记漏 1、纸条记多 1；没有配上的对 → 误差是 nan
    truth = [{"a": (20.0, 0.0, 0.0, 0.0)}]
    tracks = [{1: (23.0, 0.0, 0.0, 0.0)}]
    m = tracking_metrics(truth, tracks)
    assert m["missed"] == 1 and m["false_tracks"] == 1
    assert math.isnan(m["pos_err_m"]) and math.isnan(m["speed_err_mps"])


def test_two_cars_shuffled_order():
    # 字典的顺序不重要：配对靠距离
    truth = [{"a": (20.0, 0.0, 0.0, 0.0), "b": (12.0, 3.5, 0.0, 0.0)}]
    tracks = [{2: (12.1, 3.5, 0.0, 0.0), 1: (20.1, 0.0, 0.0, 0.0)}]
    m = tracking_metrics(truth, tracks)
    assert m["missed"] == 0 and m["false_tracks"] == 0
    assert math.isclose(m["pos_err_m"], 0.1)


def _run_scene(max_misses):
    scene = make_scene()
    speed = {c.name: (c.vx_mps, 0.0) for c in default_cars()}
    mt = MultiTracker(max_misses=max_misses)
    truth, tracks = [], []
    for k, det in enumerate(scene.detections):
        mt.step(det, DT_S)
        truth.append({n: (*xy[k], *speed[n]) for n, xy in scene.truth.items()})
        tracks.append({t.id: (*t.xy, t.kx.x[1], t.ky.x[1]) for t in mt.tracks})
    return tracking_metrics(truth, tracks)


def test_whole_scene_max_misses_10_vs_3():
    # 留 10 帧：没有跳变；鬼影 4 号 11 帧都算“多”。留 3 帧：右车道车跳变 1 次，2.3、2.4 秒两帧漏了它
    m10, m3 = _run_scene(10), _run_scene(3)
    assert m10["id_switches"] == 0 and m10["missed"] == 0 and m10["false_tracks"] == 11
    assert m3["id_switches"] == 1 and m3["missed"] == 2 and m3["false_tracks"] == 4
    assert m3["speed_err_mps"] > m10["speed_err_mps"]
