import numpy as np

from ads.tracking import diff_speed, match_tracks


def test_diff_speed_constant_closing():
    # 每 0.1 秒近 0.2 米 = 以 2 m/s 接近，4 帧距离 → 3 个速度，都是 -2
    v = diff_speed(np.array([20.0, 19.8, 19.6, 19.4]), 0.1)
    assert v.shape == (3,)
    assert np.allclose(v, [-2.0, -2.0, -2.0])


def test_diff_speed_one_noisy_frame():
    # 第 2 帧多测了 0.3 米：它前后两个速度一个 +3、一个 -3（各偏 3 m/s），噪声被 ÷ 0.1 放大 10 倍
    v = diff_speed(np.array([20.0, 20.3, 20.0]), 0.1)
    assert np.allclose(v, [3.0, -3.0])


# ---------------- A6 第 2 步：KalmanCV（数字都是手算的）

from ads.tracking import KalmanCV


def test_predict_moves_by_speed():
    # 猜：12.31 + (-1.81 × 0.1) = 12.129，速度不变
    kf = KalmanCV(12.31, -1.81)
    kf.predict(0.1)
    assert np.allclose(kf.x, [12.129, -1.81])


def test_predict_grows_uncertainty():
    # P = diag(0.01, 0.04)，q = 1，dt = 0.1：
    # F P Fᵀ = [[0.01 + 0.04×0.01, 0.04×0.1], [0.04×0.1, 0.04]]；再加 Q = [[0.000025, 0.0005], [0.0005, 0.01]]
    kf = KalmanCV(10.0, -2.0)
    kf.P = np.diag([0.01, 0.04])
    kf.predict(0.1)
    assert np.allclose(kf.P, [[0.010425, 0.0045], [0.0045, 0.05]])


def test_update_when_measurement_equals_guess():
    # 量的正好等于猜的：估计不动，但更有把握了（P[0, 0] 变小）
    kf = KalmanCV(10.0, -2.0)
    kf.P = np.array([[0.04, 0.02], [0.02, 0.1]])
    kf.update(10.0)
    assert np.allclose(kf.x, [10.0, -2.0])
    assert kf.P[0, 0] < 0.04


def test_update_hand_numbers():
    # y = 11 - 10 = 1；S = 0.04 + 0.04 = 0.08；K = [0.04, 0.02] / 0.08 = [0.5, 0.25]
    # x = [10 + 0.5, -2 + 0.25]；P = P - outer(K, P[0]) = [[0.02, 0.01], [0.01, 0.095]]
    kf = KalmanCV(10.0, -2.0, r=0.04)
    kf.P = np.array([[0.04, 0.02], [0.02, 0.1]])
    kf.update(11.0)
    assert np.allclose(kf.x, [10.5, -1.75])
    assert np.allclose(kf.P, [[0.02, 0.01], [0.01, 0.095]])


def test_tracks_closing_speed():
    # 第 1 步那组数据（真实接近速度 -2，测距噪声 0.2 米）：1 秒以后卡尔曼的速度误差都在 0.5 m/s 以内
    t = np.arange(0.0, 5.0 + 1e-9, 0.1)
    z = 20.0 - 2.0 * t + np.random.default_rng(0).normal(0.0, 0.2, len(t))
    kf = KalmanCV(z[0])
    speeds = [kf.x[1]]
    for k in range(1, len(t)):
        kf.predict(0.1)
        kf.update(z[k])
        speeds.append(kf.x[1])
    err = np.abs(np.array(speeds[10:]) + 2.0)
    assert err.max() < 0.5


# ---------- A6 第 3 步：配对 match_tracks ----------

def test_match_shuffled_boxes():
    # 两条轨迹猜在 0 米、10 米；框的顺序反过来给：框 0 在 10.2，框 1 在 0.1
    pairs = match_tracks(np.array([[0.0, 0.0], [10.0, 0.0]]), np.array([[10.2, 0.0], [0.1, 0.0]]))
    assert sorted(pairs) == [(0, 1), (1, 0)]


def test_match_gate_drops_far_pair():
    # 第 2 条轨迹离唯一剩下的框 3 米，超过门槛 2 米，不算配上
    pairs = match_tracks(np.array([[0.0, 0.0], [10.0, 0.0]]), np.array([[0.3, 0.0], [13.0, 0.0]]), gate_m=2.0)
    assert sorted(pairs) == [(0, 0)]


def test_match_empty():
    assert match_tracks(np.zeros((0, 2)), np.array([[1.0, 1.0]])) == []
    assert match_tracks(np.array([[1.0, 1.0]]), np.zeros((0, 2))) == []


def test_match_total_distance_not_greedy():
    # 圈 A (0, 0)、圈 B (2.2, 0)；框 p (1, 0)、框 q (-1.1, 0)
    # 贪心先拿最近的 A-p (1.0)，B 只剩 q (3.3)，合计 4.3；总距离最小是 A-q (1.1) + B-p (1.2) = 2.3
    pairs = match_tracks(np.array([[0.0, 0.0], [2.2, 0.0]]), np.array([[1.0, 0.0], [-1.1, 0.0]]), gate_m=5.0)
    assert sorted(pairs) == [(0, 1), (1, 0)]


def test_match_frame_19_from_the_explainer():
    # 动画 ① 那一帧（1.9 秒）：1 号↔框 2、2 号↔框 1、3 号↔框 0
    pred = np.array([[16.096, -0.033], [13.715, 3.552], [24.468, -3.425]])
    det = np.array([[24.222, -3.439], [14.032, 3.551], [15.946, 0.116]])
    assert sorted(match_tracks(pred, det)) == [(0, 2), (1, 1), (2, 0)]


# ---------- A6 第 3 步：编号管理 Track / MultiTracker ----------

from ads.tracking import MultiTracker, Track  # noqa: E402
from sim.fake_traffic import make_scene  # noqa: E402


def test_track_starts_at_box():
    t = Track(7, (20.0, 3.5))
    assert t.id == 7 and t.misses == 0
    assert np.allclose(t.xy, [20.0, 3.5])


def test_track_predict_moves_both_axes():
    # 速度先手动设好：x 方向每秒近 2 米、y 方向每秒往左 1 米 → 0.1 秒后在 (19.8, 0.1)
    t = Track(1, (20.0, 0.0))
    t.kx.x[1] = -2.0
    t.ky.x[1] = 1.0
    t.predict(0.1)
    assert np.allclose(t.xy, [19.8, 0.1])


def test_track_update_pulls_toward_box_and_clears_misses():
    t = Track(1, (20.0, 0.0))
    t.misses = 3
    t.update((20.4, -0.4))
    assert t.misses == 0
    assert 20.0 < t.xy[0] < 20.4 and -0.4 < t.xy[1] < 0.0   # 往框那边挪了，但不会一步到位


def test_first_frame_every_box_gets_a_new_id():
    mt = MultiTracker()
    tracks = mt.step(np.array([[20.0, 0.0], [12.0, 3.5]]))
    assert [t.id for t in tracks] == [1, 2]
    assert np.allclose(tracks[0].xy, [20.0, 0.0])            # 1 号 = 第 0 个框


def test_shuffled_boxes_keep_their_ids():
    mt = MultiTracker()
    mt.step(np.array([[20.0, 0.0], [12.0, 3.5]]))
    tracks = mt.step(np.array([[12.1, 3.5], [19.8, 0.0]]))    # 第二帧框的顺序反过来
    where = {t.id: t.xy for t in tracks}
    assert sorted(where) == [1, 2]
    assert where[1][0] > 19.0 and where[2][0] < 13.0          # 1 号还是 20 米那辆，2 号还是 12 米那辆


def test_hidden_car_kept_then_dropped():
    mt = MultiTracker(max_misses=3)
    mt.step(np.array([[20.0, 0.0]]))
    nothing = np.zeros((0, 2))
    for _ in range(3):
        mt.step(nothing)
    assert [t.id for t in mt.tracks] == [1] and mt.tracks[0].misses == 3   # 连着 3 帧没看到：还留着，只猜
    mt.step(nothing)
    assert mt.tracks == []                                                   # 第 4 帧：超过 3，扔掉


def test_far_box_gets_new_id_and_old_track_misses():
    mt = MultiTracker()
    mt.step(np.array([[20.0, 0.0]]))
    tracks = mt.step(np.array([[8.0, -6.0]]))      # 护栏误检：离 1 号 13 米多，超过 2 米门槛
    assert [t.id for t in tracks] == [1, 2]
    assert tracks[0].misses == 1 and tracks[1].misses == 0


def test_ids_are_never_reused():
    mt = MultiTracker(max_misses=0)
    mt.step(np.array([[20.0, 0.0]]))
    mt.step(np.zeros((0, 2)))                       # 1 号没配上，超过 0 帧，扔掉
    tracks = mt.step(np.array([[20.0, 0.0]]))
    assert [t.id for t in tracks] == [2]            # 1 号不回收


def test_whole_scene_matches_the_explainer():
    # 动画 ②、③：留 10 帧 → 三辆车 1、2、3 号到底，护栏鬼影 4 号 4.6 秒扔掉；
    #            留 3 帧 → 右车道 3 号 2.3 秒被扔、2.5 秒回来变 4 号，护栏鬼影 5 号
    for max_misses, ever, end in [(10, [1, 2, 3, 4], [1, 2, 3]), (3, [1, 2, 3, 4, 5], [1, 2, 4])]:
        scene = make_scene()
        mt = MultiTracker(max_misses=max_misses)
        seen = set()
        for det in scene.detections:
            seen.update(t.id for t in mt.step(det))
        assert sorted(seen) == ever
        assert sorted(t.id for t in mt.tracks) == end
