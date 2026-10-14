import math

from ads.control import PID
from ads.vehicle import VehicleState, step
from ads.control import to_pedals

def test_p_only():
    """只有 P：差 10，kp 0.5 → 加速度 5。"""
    pid = PID(kp=0.5)
    assert pid.update(10.0, 0.1) == 5.0

def test_integral_adds_up():
    """差距一直是 2、每帧 0.1 秒：累计差距 0.2 → 0.4 → 0.6。"""
    pid = PID(kp=0.0, ki=1.0)
    pid.update(2.0, 0.1)
    pid.update(2.0, 0.1)
    pid.update(2.0, 0.1)
    assert math.isclose(pid.integral, 0.6)

def test_first_frame_no_derivative():
    """第一帧没有上一帧，D 当 0。"""
    pid = PID(kp=0.0, kd=1.0)
    assert pid.update(10.0, 0.1) == 0.0

def test_two_frames_by_hand():
    """今天手算过的两帧：6.0 和 3.8。"""
    pid = PID(kp=0.5, ki=1.0, kd=0.1)
    assert math.isclose(pid.update(10.0, 0.1), 6.0)
    assert math.isclose(pid.update(8.0, 0.1), 3.8)

def drive_uphill(pid: PID, seconds: float) -> float:
    """目标 10 m/s，上坡（-0.5 m/s²），开 seconds 秒，返回最后的车速。"""
    state = VehicleState()
    for _ in range(round(seconds / 0.1)):
        accel = pid.update(10.0 - state.speed_mps, 0.1)
        state = step(state, accel - 0.5, 0.0, 0.1)
    return state.speed_mps

def test_p_only_uphill_stalls_at_9():
    """只有 P：卡在 9，差 1 补不上（稳态误差）。"""
    assert math.isclose(drive_uphill(PID(kp=0.5), 60.0), 9.0, abs_tol=0.01)

def test_pi_uphill_reaches_10():
    """加上 I：最后能到 10。"""
    assert math.isclose(drive_uphill(PID(kp=1.0, ki=0.2), 60.0), 10.0, abs_tol=0.01)

def test_to_pedals_throttle():
    """u = 0.3：轻踩油门。"""
    assert to_pedals(0.3) == (0.3, 0.0)

def test_to_pedals_clamp():
    """u = 2.5：油门最多踩到底。"""
    assert to_pedals(2.5) == (1.0, 0.0)

def test_to_pedals_brake():
    """u = -0.4：踩刹车。"""
    assert to_pedals(-0.4) == (0.0, 0.4)