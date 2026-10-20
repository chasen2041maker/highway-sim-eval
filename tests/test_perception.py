"""去地面的测试：高于门槛的留下，等于或低于门槛的扔掉；假雷达一圈的数字来自已核对的运行结果（2026-10-19）。"""

import numpy as np

from ads.perception import remove_ground
from sim.fake_lidar import scan


def test_keeps_only_points_above_threshold():
    """4 个点，门槛 −1.6：地面 −1.8 扔、车身 −1.0 留、正好 −1.6 扔（要“高于”才算）、−1.59 留。"""
    points = np.array([[5.0, 0.0, -1.8], [5.0, 0.0, -1.0], [5.0, 0.0, -1.6], [5.0, 0.0, -1.59]])
    kept, keep = remove_ground(points, -1.6)
    assert keep.tolist() == [False, True, False, True]
    assert kept.shape == (2, 3)
    assert kept[:, 2].tolist() == [-1.0, -1.59]


def test_fake_scan_threshold_20cm_removes_all_ground():
    """假雷达一圈，门槛 −1.6（离地 20 厘米）：地面点一个不剩，东西上的点留下 650 / 733（底下 20 厘米被一起切掉）。"""
    points, labels = scan()
    _, keep = remove_ground(points, -1.6)
    assert int(((labels == -1) & keep).sum()) == 0
    assert int(((labels >= 0) & keep).sum()) == 650


def test_fake_scan_threshold_1cm_lets_ground_noise_through():
    """门槛 −1.79（离地 1 厘米）：测距噪声把 1069 个地面点抖过门槛，会被当成障碍物。"""
    points, labels = scan()
    _, keep = remove_ground(points, -1.79)
    assert int(((labels == -1) & keep).sum()) == 1069


def test_cluster_two_groups_and_one_lonely_point():
    """两团各 3 个点（团内相距 0.1 米）、一个孤零零的点：eps 0.5、min_samples 3 → 两堆 + 1 个噪声。"""
    from ads.perception import cluster_points
    pts = np.array([[0, 0, 0], [0.1, 0, 0], [0.2, 0, 0], [5, 5, 0], [5.1, 5, 0], [5.2, 5, 0], [20, 0, 0]], dtype=float)
    labels = cluster_points(pts, 0.5, 3)
    assert labels[0] == labels[1] == labels[2] != labels[3] == labels[4] == labels[5]
    assert labels[6] == -1


def test_fake_scan_eps_window():
    """假雷达去地面后 650 个点，min_samples 5：eps 0.5 → 8 堆（车被切碎）、1.0 → 5 堆（正好）、5.0 → 4 堆（前车和路边停车粘一起）。"""
    from ads.perception import cluster_points
    points, _ = scan()
    kept, _ = remove_ground(points, -1.6)
    assert [int(cluster_points(kept, e, 5).max()) + 1 for e in (0.5, 1.0, 5.0)] == [8, 5, 4]
