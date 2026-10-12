import math
from sim.transforms import carla_to_ours, ours_to_carla

def test_point_on_right():
    """CARLA 里在右边 3 米的点，我们的 y 是 -3。"""
    x, y, h = carla_to_ours(10.0, 3.0, 0.0)
    assert x == 10.0
    assert y == -3.0
    assert h == 0.0

def test_yaw_right_90():
    """CARLA 车头朝正右（yaw 90°），我们的 heading 是 -π/2。"""
    _, _, h = carla_to_ours(0.0, 0.0, 90.0)
    assert math.isclose(h, -math.pi / 2)

def test_yaw_left_30():
    """CARLA 车头往左偏 30°（yaw -30°），我们的 heading 是 +π/6。"""
    _, _, h = carla_to_ours(0.0, 0.0, -30.0)
    assert math.isclose(h, math.pi / 6)

def test_ours_to_carla():
    """我们这边：左边 1 米、车头朝正左（heading π/2）→ CARLA 里 y = -1、yaw = -90°。"""
    x, y, yaw = ours_to_carla(0.0, 1.0, math.pi / 2)
    assert x == 0.0
    assert math.isclose(y, -1.0)
    assert math.isclose(yaw, -90.0)

def test_round_trip():
    """我们 → CARLA → 我们，应该回到原来的数。"""
    x, y, yaw = ours_to_carla(5.0, -2.0, 0.3)
    x2, y2, h2 = carla_to_ours(x, y, yaw)
    assert math.isclose(x2, 5.0)
    assert math.isclose(y2, -2.0)
    assert math.isclose(h2, 0.3)