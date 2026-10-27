"""A7 变道的测试：MOBIL（第 1 步，数字都是手设的加速度）、五次多项式变道曲线（第 2 步）、Frenet 换地图坐标（第 3 步）。"""

import math

from ads.planning import frenet_to_xy, lane_change_d, mobil_should_change


def test_mobil_changes_when_safe_and_worth_it():
    # 我：-1.0 → 0.5（好处 1.5 > 0.2）；目标车道后车被我逼到 -1.0，没超过 -2 → 变
    assert mobil_should_change(-1.0, 0.5, 0.2, -1.0) is True


def test_mobil_unsafe_for_the_car_behind():
    # 好处很大（3.0），但目标车道后车要刹 -3.0，比 -2 狠 → 不变
    assert mobil_should_change(-2.0, 1.0, 0.0, -3.0) is False


def test_mobil_gain_too_small():
    # 我只多 0.1，不到门槛 0.2 → 不变（不为一点点好处来回变道）
    assert mobil_should_change(0.3, 0.4, 0.0, 0.0) is False


def test_mobil_politeness_counts_the_others():
    # 我多 0.5；目标车道后车从 0.2 变 -0.8（亏 1.0）
    # 自私（p = 0）：0.5 > 0.2 → 变；礼貌（p = 0.5）：0.5 - 0.5 × 1.0 = 0 → 不变
    assert mobil_should_change(0.0, 0.5, 0.2, -0.8, politeness=0.0) is True
    assert mobil_should_change(0.0, 0.5, 0.2, -0.8, politeness=0.5) is False


# ---------- 第 2 步：五次多项式变道曲线（左变道 3.5 米，用 4 秒） ----------

def test_lane_change_starts_and_ends_at_rest():
    # 起点、终点：位置分别是 0 和 3.5，横向速度、横向加速度都是 0（不会一上来就猛打方向）
    d, v, a, _ = lane_change_d(0.0, 4.0, 3.5)
    assert (d, v, a) == (0.0, 0.0, 0.0)
    d, v, a, _ = lane_change_d(4.0, 4.0, 3.5)
    assert math.isclose(d, 3.5) and abs(v) < 1e-12 and abs(a) < 1e-12


def test_lane_change_halfway():
    # 正中间 t = 2：走了一半 1.75 米；横向速度最大 3.5 × 1.875 / 4 = 1.640625；加速度刚好 0（从加速转成减速）
    d, v, a, _ = lane_change_d(2.0, 4.0, 3.5)
    assert math.isclose(d, 1.75) and math.isclose(v, 1.640625) and abs(a) < 1e-12


def test_lane_change_max_lateral_accel():
    # 最大横向加速度 = 10√3/3 × Δ / T² ≈ 5.7735 × 3.5 / 16 = 1.263 m/s²（在 τ ≈ 0.21 处）
    peak = max(abs(lane_change_d(k * 0.001, 4.0, 3.5)[2]) for k in range(4001))
    assert math.isclose(peak, 10 * math.sqrt(3) / 3 * 3.5 / 16, rel_tol=1e-4)


def test_lane_change_before_and_after():
    assert lane_change_d(-1.0, 4.0, 3.5) == (0.0, 0.0, 0.0, 0.0)    # 还没开始
    assert lane_change_d(5.0, 4.0, 3.5) == (3.5, 0.0, 0.0, 0.0)     # 已经变完


def test_lane_change_twice_as_fast_is_four_times_harder():
    # 用时减半（4 秒 → 2 秒）：最大横向加速度变成 4 倍（和 T² 成反比）
    peak4 = max(abs(lane_change_d(k * 0.001, 4.0, 3.5)[2]) for k in range(4001))
    peak2 = max(abs(lane_change_d(k * 0.0005, 2.0, 3.5)[2]) for k in range(4001))
    assert math.isclose(peak2 / peak4, 4.0, rel_tol=1e-3)


# ---------- 第 3 步：Frenet (s, d) → 地图 (x, y) ----------

def test_frenet_straight_road_along_x():
    # 路朝右（+x）开：s 就是 x，d 就是 y
    ref = [(float(i), 0.0) for i in range(21)]
    assert frenet_to_xy(ref, 10.0, 2.0) == (10.0, 2.0)


def test_frenet_road_heading_up_left_is_minus_x():
    # 路朝上（+y）开：往前 5 米、往左 3.5 米 → 地图上是 (-3.5, 5)（小检查那道题）
    ref = [(0.0, float(i)) for i in range(21)]
    x, y = frenet_to_xy(ref, 5.0, 3.5)
    assert math.isclose(x, -3.5) and math.isclose(y, 5.0)


def test_frenet_on_a_left_curve():
    # 半径 20 米左转 90°：圆心 (0, 20)，从 (0, 0) 朝 +x 出发，转完在 (20, 20) 朝 +y
    # 走完整个弯（s = 10π）、往左 3.5 米（弯的里侧）→ (16.5, 20)
    n = 2000
    ref = [(20 * math.sin(k / n * math.pi / 2), 20 - 20 * math.cos(k / n * math.pi / 2)) for k in range(n + 1)]
    x, y = frenet_to_xy(ref, 10 * math.pi, 3.5)
    # 参考线是一小段一小段的直线（这里 2000 段），每段的朝向和真圆差半段的角度，误差约 1 毫米
    assert math.isclose(x, 16.5, abs_tol=0.01) and math.isclose(y, 20.0, abs_tol=0.01)


def test_frenet_extends_past_the_end():
    ref = [(float(i), 0.0) for i in range(11)]          # 只有 0 到 10 米
    assert frenet_to_xy(ref, 12.0, 0.0) == (12.0, 0.0)   # 沿最后一段往外延长
