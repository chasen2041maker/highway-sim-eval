import math
from evaluation.metrics import point_to_segment_m, lateral_error_m

PATH = [(0.0, 0.0), (0.5, 0.0), (1.0, 0.0)]   # 红点每 0.5 米一颗：A、B、C

def test_on_line_between_points_is_zero():
    """车压在中心线上、站在 A、B 正中间：新尺子 0（老尺子会报 0.25）。"""
    assert math.isclose(lateral_error_m(PATH, 0.25, 0.0), 0.0, abs_tol=1e-9)

def test_beside_segment_is_perpendicular():
    """车在 A、B 之间、偏左 0.30：垂直量 0.30；往前挪到 0.40 还是 0.30（前后挪不影响）。"""
    assert math.isclose(point_to_segment_m(0.25, 0.30, 0.0, 0.0, 0.5, 0.0), 0.30)
    assert math.isclose(point_to_segment_m(0.40, 0.30, 0.0, 0.0, 0.5, 0.0), 0.30)

def test_outside_segment_measures_to_end():
    """只给 A→B 一段：开过 B 0.20 拉回 B，在 A 后面 0.20 拉回 A，都斜着量 √(0.20² + 0.30²) ≈ 0.36。"""
    assert math.isclose(point_to_segment_m(0.70, 0.30, 0.0, 0.0, 0.5, 0.0), math.hypot(0.20, 0.30))
    assert math.isclose(point_to_segment_m(-0.20, 0.30, 0.0, 0.0, 0.5, 0.0), math.hypot(0.20, 0.30))

def test_min_over_segments():
    """整条中心线（A→B、B→C 两段）：开过 B 时 B→C 能垂直量到，取最小 → 0.30。"""
    assert math.isclose(lateral_error_m(PATH, 0.70, 0.30), 0.30)