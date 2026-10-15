import math
from ads.planning import idm_accel

def test_idm_hand_calc():
    """车速 10、前车 10、距离 40、目标 20：想加的 2.8125 − 怕撞的 0.75 = 2.0625。"""
    assert math.isclose(idm_accel(10.0, 10.0, 40.0, 20.0), 2.0625)

def test_idm_at_desired_gap_brakes_a_little():
    """距离正好是想保持的 20 米：刹车声音 3 比加速声音 2.81 大，轻轻减速 −0.1875。"""
    assert math.isclose(idm_accel(10.0, 10.0, 20.0, 20.0), -0.1875)

def test_idm_sees_brake_light():
    """同一时刻（车速 10.08、距离 19.78）：前车一样快只刹 −0.72；前车慢到 5，马上刹 −3.09。"""
    assert math.isclose(idm_accel(10.08, 10.08, 19.78, 15.0), -0.72, abs_tol=0.01)
    assert math.isclose(idm_accel(10.08, 5.0, 19.78, 15.0), -3.09, abs_tol=0.01)