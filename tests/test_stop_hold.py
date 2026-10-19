"""停车保持的测试：进入要三个条件都满足，退出满足一个就行，中间有迟滞。"""

from ads.planning import StopHold


def test_normal_driving_does_not_hold():
    """正常跟车（我 10 m/s、前车 10 m/s、车距 25 米）：不保持。"""
    assert StopHold().update(10.0, 10.0, 25.0) is False


def test_stopped_behind_stopped_lead_holds():
    """我快停了（0.2）、前车停着（0）、车距 6 米：进入保持。"""
    assert StopHold().update(0.2, 0.0, 6.0) is True


def test_still_far_away_does_not_hold():
    """我慢（0.5）、前车停着，但车距 15 米：还离得远，允许慢慢靠近，不保持。"""
    assert StopHold().update(0.5, 0.0, 15.0) is False


def test_hysteresis_keeps_holding_until_lead_really_moves():
    """保持中，前车往前蹭到 0.8 m/s（高于进入门槛 0.5、低于退出门槛 1.0）：继续保持；前车到 1.2 m/s：松开。"""
    h = StopHold()
    assert h.update(0.0, 0.0, 6.0) is True
    assert h.update(0.0, 0.8, 6.2) is True
    assert h.update(0.0, 1.2, 6.5) is False


def test_release_when_gap_opens():
    """保持中，车距拉到 12 米（超过退出门槛 11 米）：松开。"""
    h = StopHold()
    h.update(0.0, 0.0, 6.0)
    assert h.update(0.0, 0.3, 12.0) is False
