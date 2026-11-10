"""B3 第 3 步：逐帧录像 + 回灌（examples/b_eval/b3_record.py、b3_replay.py）。没装模拟器的电脑会跳过。

回灌第一件事：用和录像时同样的设置原样回放，每一帧的决定要和录像一模一样；
换成往前看 0.5 秒，切入 5 米那道题第一次刹车要比录像早。靠线那道（不该刹）往前看 0.5 秒不刹、1.0 秒会刹（和 B1 闭环结果一致）。
"""

import pytest

pytest.importorskip("highway_env")

from examples.b_eval.b1_cut_in import BANK, run  # noqa: E402
from examples.b_eval.b3_replay import first_brake, replay  # noqa: E402


def _record(n):
    frames = []
    run(BANK[n - 1], 0.0, frames=frames)          # 不预测的老考生
    return frames


def test_replay_same_settings_matches_recording():
    frames = _record(3)                            # 切入 5 米：录像里撞了
    recorded = [f["accel_cmd"] for f in frames]
    times = [f["t_s"] for f in frames]
    assert replay(frames, 0.0) == recorded         # 原样回放：一帧不差
    assert first_brake(times, replay(frames, 0.5)) < first_brake(times, recorded)


def test_replay_lane_hugger():
    frames = _record(5)                            # 靠线：车身始终在线外，不该刹
    times = [f["t_s"] for f in frames]
    assert first_brake(times, [f["accel_cmd"] for f in frames]) is None
    assert first_brake(times, replay(frames, 0.5)) is None
    assert first_brake(times, replay(frames, 1.0)) is not None
