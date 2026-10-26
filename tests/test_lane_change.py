"""A7 变道的测试：MOBIL（第 1 步）。数字都是手设的加速度，方便手算。"""

from ads.planning import mobil_should_change


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
