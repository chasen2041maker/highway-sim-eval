import math 
from ads.vehicle import MAX_STEER_RAD, WHEELBASE_M, VehicleState, step

def test_straight_line():
    """不转向：1 秒走 10 米，y 不变。"""
    s = VehicleState(speed_mps=10.0)
    for _ in range(10):
        s = step(s,accel_mps2=0.0, steer_rad=0.0, dt_s=0.1)
    assert math.isclose(s.x_m,10.0)
    assert math.isclose(s.y_m,0.0, abs_tol=1e-9)

def test_acceleration():
    """加速度 2，1 秒后速度从 10 变成 12。"""
    s = VehicleState(speed_mps= 10.0)
    for _ in range(10):
        s = step(s, accel_mps2=2.0, steer_rad=0.0, dt_s=0.1)
    assert math.isclose(s.speed_mps, 12.0)

def test_no_reverse():
    """一直刹车，速度停在 0，不会变成负数。"""
    s = VehicleState(speed_mps=1.0)
    for _ in range(10):
        s = step(s, accel_mps2=-5.0, steer_rad=0.0, dt_s=0.1)
    assert s.speed_mps == 0.0

def test_heading_rate():
    """车头每秒转动 = v / L × tan(转角)。"""
    s = step(VehicleState(speed_mps=10.0), accel_mps2=0.0, steer_rad=0.1, dt_s=0.1)
    assert math.isclose(s.heading_rad, 10.0 / WHEELBASE_M * math.tan(0.1) * 0.1)

def test_steer_is_clipped():
    """转角超过上限时，按上限算。"""
    a = step(VehicleState(speed_mps=10.0), accel_mps2=0.0, steer_rad=1.0,dt_s=0.1)
    b = step(VehicleState(speed_mps=10.0), accel_mps2=0.0, steer_rad=MAX_STEER_RAD, dt_s=0.1)
    assert math.isclose(a.heading_rad, b.heading_rad)

def test_first_step_goes_straight():
    """先按旧的车头方向走完这一步，再转车头；起步时车头朝正前方，所以第一步 y 不变。"""
    s = step(VehicleState(speed_mps=10.0), accel_mps2=0.0, steer_rad=0.1, dt_s=1.0)
    assert math.isclose(s.y_m, 0.0, abs_tol=1e-9)
    assert s.heading_rad > 0.0