"""评测指标：先从“离车道中心多远”开始（B4 会用到）。"""

import math

def point_to_segment_m(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """车 P 到线段 AB 的最短距离（米）：垂足在线段上就垂直量，落在外面就量到近的那颗钉子。"""
    dx, dy  = bx - ax, by - ay    # 路的方向：A → B
    seg_len2 = dx * dx + dy * dy  # 路长²
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len2       # 垂足在 A→B 的几成处
    t = max(0.0, min(1.0, t))                          # 垂足落到线段外面时，拉回到端点（下一步专门试）
    fx, fy = ax + t * dx, ay + t * dy                  # 垂足坐标
    return math.hypot(px - fx, py - fy)

def lateral_error_m(path: list[tuple[float, float]], x_m: float, y_m: float) -> float:
    """车到中心线（一串红点连成的折线）的最短距离：每段量一次，取最小。"""
    segs = zip(path, path[1:])       # 相邻两颗红点配成一段
    return min(point_to_segment_m(x_m, y_m, ax, ay, bx, by)
                for (ax, ay), (bx, by) in segs)