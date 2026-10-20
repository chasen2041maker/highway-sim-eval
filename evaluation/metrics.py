"""评测指标：先从“离车道中心多远”开始（B4 会用到）；A5 加了检测评测（召回率、精确率、位置误差）。"""

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


def detection_metrics(pred_xy, true_xy, max_dist_m: float) -> dict:
    """检测评测：把算出来的框中心和真东西的中心一对一配对，算召回率、精确率、位置误差。

    pred_xy：形状 (P, 2)，算法给的 P 个框的中心 (x, y)，单位米（cluster_to_box 结果的前两列）。
    true_xy：形状 (T, 2)，T 个真东西的中心 (x, y)。
    max_dist_m：中心相距不超过这么多米才算“找到了”（nuScenes 用 0.5 / 1 / 2 / 4 米四档）。
    配对规则：一个预测最多配一个真东西，一个真东西最多被配一次；
              在所有（预测，真东西）两两的距离里，先配最近的那一对，再在剩下没用过的里找最近的……
              直到剩下最近的也超过 max_dist_m 为止。
    返回 dict，4 个键：
        "matches"：配上的对，列表，每项是 (预测下标 i, 真东西下标 j, 距离米)，按配上的先后（距离从小到大）；
        "recall"：召回率 = 配上的对数 ÷ 真东西个数（T 为 0 时记 0.0）；
        "precision"：精确率 = 配上的对数 ÷ 预测个数（P 为 0 时记 0.0）；
        "mean_error_m"：位置误差 = 配上的那些对的距离的平均值（没配上的不算；一对都没有时是 float("nan")）。
    """
    # 第 4 步：本人写（先用中文说思路），直到 python -m pytest tests/test_detection_metrics.py -v 全过
    raise NotImplementedError("detection_metrics 还没写")
