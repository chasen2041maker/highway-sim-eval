"""A5 第 5 步：路面有坡时，按高度一刀切去地面会怎样？（假激光雷达，纯 Python）

只改第 23、24 行做实验：
  GROUND_SLOPE：路面坡度 = 往前每走 1 米，路面高多少米。0 = 平地，0.04 = 上坡 4%，-0.04 = 下坡 4%。
  METHOD："height" = 第 1 步的 remove_ground（按离雷达的高度一刀切）；
          "ransac" = 先用 RANSAC 找出地面这个平面，再按“离地面多高”切（讲完 RANSAC 再打开）。
会打印：还剩多少地面点被当成障碍物、最近的离雷达几米、5 个东西各留下几个点、
        DBSCAN 分出几堆、门槛 2 米时的召回率 / 精确率。
真值 labels 只在这里拿来打分，去地面、聚类本身看不到它。

运行（在项目根目录）：python -m examples.a5_slope
"""

import numpy as np

from ads.perception import cluster_points, cluster_to_box, remove_ground
from evaluation.metrics import detection_metrics
from sim.fake_lidar import DEFAULT_SCENE, scan

# ---------------------------------------------------------------------------
# 实验旋钮
# ---------------------------------------------------------------------------
GROUND_SLOPE = 0.04        # 上坡 4%：往前每走 1 米，路面高 0.04 米（0 = 平地）
METHOD = "height"          # "height" = 按高度一刀切；"ransac" = 先拟合地面平面再切
Z_THRESHOLD_M = -1.6       # height 用：z 比它高才算障碍物（车脚下的地面往上 0.20 米）
ABOVE_GROUND_M = 0.20      # ransac 用：离拟合出的地面高过 0.20 米才算障碍物（同样是 20 厘米）
EPS_M = 1.0
MIN_SAMPLES = 5
GATE_M = 2.0
NAMES = {"lead car": "前车", "left-lane car": "左车道车", "parked car": "路边停车",
         "pedestrian": "行人", "car behind": "后车"}


def ransac_ground_plane(points, n_iter=50, inlier_m=0.15, seed=0):
    """演示（助手写，懂思路即可）：RANSAC 找地面平面。

    每次随机抽 3 个点 → 3 个点定一个平面 → 数离这个平面不到 inlier_m 米的点有几个（投票）
    → 抽 n_iter 次，留票最多的那个平面（地面点最多，所以票最多的就是地面）。
    返回 (normal, d, votes)：平面写成 normal · p + d = 0，normal 是朝上的单位向量；
    点 p 离地面的高度 = normal · p + d（地面上 ≈ 0，车顶 ≈ 1.5）。
    """
    rng = np.random.default_rng(seed)
    best_votes, best = -1, None
    for _ in range(n_iter):
        p1, p2, p3 = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(p2 - p1, p3 - p1)            # 垂直于这个平面的方向
        length = np.linalg.norm(normal)
        if length < 1e-9:                                # 3 个点在一条直线上，定不出平面
            continue
        normal = normal / length
        if normal[2] < 0:                                # 统一朝上
            normal = -normal
        d = -normal @ p1
        votes = int((np.abs(points @ normal + d) < inlier_m).sum())
        if votes > best_votes:
            best_votes, best = votes, (normal, d)
    return best[0], best[1], best_votes


def main():
    points, labels = scan(ground_slope=GROUND_SLOPE)
    ground = labels == -1
    print(f"坡度 {GROUND_SLOPE:+.2f}（往前每走 1 米，路面高 {GROUND_SLOPE * 100:+.0f} 厘米）")
    print(f"一圈 {len(points)} 个点，其中地面点 {int(ground.sum())} 个\n")

    if METHOD == "height":
        print(f"去地面：按高度一刀切，z > {Z_THRESHOLD_M:.2f} 才留下")
        kept, keep = remove_ground(points, Z_THRESHOLD_M)
    else:
        normal, d, votes = ransac_ground_plane(points)
        a, b, c = -d / normal[2], -normal[0] / normal[2], -normal[1] / normal[2]
        print(f"去地面：RANSAC 抽 50 次，票最多的平面 z = {a:.2f} {b:+.3f}·x {c:+.3f}·y（{votes} 个点离它不到 0.15 米）")
        print(f"        离这个平面高过 {ABOVE_GROUND_M:.2f} 米才留下")
        keep = points @ normal + d > ABOVE_GROUND_M
        kept = points[keep]

    leak = ground & keep
    if leak.any():
        dist = np.hypot(points[leak, 0], points[leak, 1])
        i = int(np.argmin(dist))
        side = "前" if points[leak][i, 0] > 0 else "后"
        print(f"地面点还剩 {int(leak.sum())} 个（会被当成障碍物），最近的一个离雷达 {dist[i]:.1f} 米（在{side}方）")
    else:
        print("地面点还剩 0 个")

    print("东西上的点：")
    for k, box in enumerate(DEFAULT_SCENE):
        n = int((labels == k).sum())
        m = int(((labels == k) & keep).sum())
        print(f"  {NAMES[box.name]:5s} {n:4d} → {m:4d}")

    cl = cluster_points(kept, EPS_M, MIN_SAMPLES)
    boxes = cluster_to_box(kept, cl)
    true_xy = np.array([[b.cx_m, b.cy_m] for b in DEFAULT_SCENE])
    r = detection_metrics(boxes[:, :2], true_xy, GATE_M) if len(boxes) else None
    print(f"\nDBSCAN（eps {EPS_M}）分出 {len(boxes)} 堆（真东西 5 个）")
    if r:
        print(f"门槛 {GATE_M} 米：配上 {len(r['matches'])} 对，召回率 {r['recall']:.2f}，精确率 {r['precision']:.2f}")


if __name__ == "__main__":
    main()
