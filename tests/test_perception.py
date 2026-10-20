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


def test_cluster_to_box_two_groups_skip_noise():
    """两堆 + 1 个噪声：第 0 堆 x 1～3、y 0～1 → 中心 (2, 0.5)、长 2、宽 1；第 1 堆只有一个点 → 中心就是它、长宽 0；噪声不出框。"""
    from ads.perception import cluster_to_box
    pts = np.array([[1, 0, 0], [3, 1, 0], [2, 0.5, 0], [10, -2, 0], [50, 50, 0]], dtype=float)
    labels = np.array([0, 0, 0, 1, -1])
    boxes = cluster_to_box(pts, labels)
    assert boxes.shape == (2, 4)
    assert np.allclose(boxes[0], [2.0, 0.5, 2.0, 1.0])
    assert np.allclose(boxes[1], [10.0, -2.0, 0.0, 0.0])


def test_fake_scan_lead_car_box_sits_on_rear_face():
    """假雷达前车（真中心 x 15.0、车长 4.6）只被打到车尾一面：框中心 x = 12.70（车尾），比真值近 2.30 米 = 半个车长。"""
    from ads.perception import cluster_points, cluster_to_box
    points, _ = scan()
    kept, _ = remove_ground(points, -1.6)
    boxes = cluster_to_box(kept, cluster_points(kept, 1.0, 5))
    lead = boxes[np.argmin(np.hypot(boxes[:, 0] - 15.0, boxes[:, 1]))]
    assert round(float(lead[0]), 2) == 12.70
    assert lead[2] < 0.15                      # 框长只有车尾的厚度（噪声 2 厘米级）
    assert round(15.0 - float(lead[0]), 2) == 2.30
