"""评测指标：先从“离车道中心多远”开始（B4 会用到）；A5 加了检测评测（召回率、精确率、位置误差）。"""

import math
import numpy as np

from ads.tracking import match_tracks  # A6 第 4 步：跟踪评测的配对规则和跟踪时一样

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
    
    P = len(pred_xy)
    T = len(true_xy)
    dist = np.zeros((P, T))
    for i in range(P):
        for j in range(T):
            dx = pred_xy[i][0] - true_xy[j][0]
            dy = pred_xy[i][1] - true_xy[j][1]
            dist[i, j] = math.hypot(dx, dy)

    matches = []
    for _ in range(min(P, T)):
        i, j = np.unravel_index(np.argmin(dist), dist.shape)
        d = dist[i, j]
        if d > max_dist_m:
            break
        matches.append((int(i), int(j), float(d)))
        dist[i, :] = np.inf
        dist[:, j] = np.inf

    n = len(matches)
    recall = n / T if T > 0 else 0.0
    precision = n / P if P > 0 else 0.0
    if n > 0:
        mean_error_m = sum(m[2] for m in matches) / n
    else:
        mean_error_m = float("nan")
    return {"matches": matches, "recall": recall, "precision": precision, "mean_error_m": mean_error_m}


def tracking_metrics(truth: list[dict], tracks: list[dict], gate_m: float = 2.0) -> dict:
    """跟踪评测（A6 第 4 步）：每一帧把跟踪器的纸条和真车一对一配上，再数错了多少。

    在系统里：跟踪器（ads/tracking.py）是被考的“学生”，这个函数是“考官”：手里有真值，
    每帧对一次答案，最后报几个数，用来比较两个跟踪器（例如 MAX_MISSES 10 vs 3）谁好。

    truth：长度 N 的列表（N 帧），第 k 帧是字典 {车名: (x, y, vx, vy)}：真车的位置（米）和速度（m/s）。
    tracks：长度 N 的列表，第 k 帧是字典 {编号: (x, y, vx, vy)}：跟踪器这一帧手里的纸条，估计的位置和速度。
            某一帧一张纸条都没有时是 {}。
    gate_m：真车和纸条离得超过这么多米，就不算配上。
    配对规则和跟踪时一样：一对一、总距离最小、超过门槛的扔掉，直接借用 ads.tracking.match_tracks。

    返回 dict，5 个键：
        "pos_err_m"：所有配上的对，位置误差（两点距离）的平均值；一对都没有时 float("nan")；
        "speed_err_mps"：所有配上的对，速度误差的平均值（速度向量之差的长度，np.hypot(dvx, dvy)）；一对都没有时 nan；
        "id_switches"：编号跳变次数：一辆真车这一帧配上的编号，和它【上一次配上】的编号不一样，记 1 次
                      （中间几帧没配上不算跳变；第一次配上也不算）；
        "missed"：漏：每帧没配上纸条的真车个数，加起来；
        "false_tracks"：多：每帧没配上真车的纸条张数，加起来（比如护栏误检留下的鬼影）。
    """
    pos_errs, speed_errs = [], []          # 每个配上的对的误差，最后取平均
    last_id = {}             # 每辆真车上一次配上的编号：{车名: 编号}
    switches = missed = false_tracks = 0
    for k in range(len(truth)):
        names = list(truth[k])
        ids = list(tracks[k])
        g = np.array([truth[k][n][:2] for n in names])      # 真车位置，G 行 2 列
        h = np.array([tracks[k][i][:2] for i in ids])       # 纸条位置，H 行 2 列
        pairs = match_tracks(g, h, gate_m)        # (a, b)：第 a 辆真车配第 b 张纸条

        for a,b in pairs:
            gx, gy, gvx, gvy = truth[k][names[a]]
            hx, hy, hvx, hvy = tracks[k][ids[b]]
            pos_errs.append(np.hypot(hx - gx, hy- gy))     # 位置差多远
            speed_errs.append(np.hypot(gvx - hvx, gvy - hvy))

            name, tid = names[a], ids[b]                         # 这辆真车叫什么、这一帧配上的编号
            if name in last_id and last_id[name] != tid:       # 以前配上过，而且编号变了
                switches += 1
            last_id[name] = tid                                # 记下这一次配上的编号