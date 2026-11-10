"""B3 第 3 步：录像存成 MCAP、按轨道和时间段读回来（examples/b_eval/b3_mcap.py）。没装 mcap 的电脑会跳过。"""

import pytest

pytest.importorskip("mcap")

from examples.b_eval import b3_mcap  # noqa: E402


def _frames(n):
    frames = []
    for k in range(n):
        frames.append({"t_s": round(k * 0.1, 1), "ego_x": 10.0 * k, "ego_y": 4.0, "ego_v": 15.0,
                       "cutter_x": 10.0 * k + 8, "cutter_y": 0.5 * k, "seen": [[1.0, 10.0 * k, 4.0, 15.0, 0.0]],
                       "lead_seen": k >= 3, "accel_cmd": -8.0 if k >= 3 else 0.0})
    return frames


def test_write_then_read_by_topic_and_time(tmp_path):
    """5 帧 × 4 条轨道 = 20 条消息；目录里每条轨道 5 条；只读 /decision 第 0.2–0.4 秒（不含 0.4）= 第 0.2、0.3 秒两条。"""
    path = tmp_path / "q.mcap"
    b3_mcap.write_mcap(_frames(5), path)
    assert b3_mcap.summary(path) == {"/ego": 5, "/cutter": 5, "/seen": 5, "/decision": 5}
    assert len(list(b3_mcap.read_mcap(path))) == 20
    got = list(b3_mcap.read_mcap(path, topics=["/decision"], start_s=0.2, end_s=0.4))
    assert [(topic, round(t, 1), msg["lead_seen"]) for topic, t, msg in got] == [
        ("/decision", 0.2, False), ("/decision", 0.3, True)]
    _, _, seen = list(b3_mcap.read_mcap(path, topics=["/seen"], start_s=0.1, end_s=0.15))[0]
    assert seen == {"rows": [[1.0, 10.0, 4.0, 15.0, 0.0]]}
