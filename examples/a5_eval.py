"""A5 第 4 步：给检测结果打分（召回率、精确率、位置误差），按 nuScenes 的四档门槛各算一遍。

流程：假雷达扫一圈 → 去地面（门槛 −1.6）→ DBSCAN 分堆（eps 1.0、min_samples 5）→ cluster_to_box 画框
      → 框的中心 = 检测结果 pred_xy，场景表里的真中心 = 真值 true_xy → evaluation.metrics.detection_metrics 打分。
注意：真值只在打分时用，检测算法（ads/perception.py）从头到尾没看过它。

运行（在项目根目录）：python -m examples.a5_eval
"""

import numpy as np

from ads.perception import cluster_points, cluster_to_box, remove_ground
from evaluation.metrics import detection_metrics
from sim.fake_lidar import DEFAULT_SCENE, scan

EPS_M = 1.0
MIN_SAMPLES = 5
Z_THRESHOLD_M = -1.6
GATES_M = [0.5, 1.0, 2.0, 4.0]          # nuScenes 的四档中心距离门槛
NAMES = {"lead car": "前车", "left-lane car": "左车道车", "parked car": "路边停车",
         "pedestrian": "行人", "car behind": "后车"}


def main():
    points, _ = scan()                                   # 真值标签这里用不到，丢掉
    kept, _ = remove_ground(points, Z_THRESHOLD_M)
    labels = cluster_points(kept, EPS_M, MIN_SAMPLES)
    boxes = cluster_to_box(kept, labels)

    pred_xy = boxes[:, :2]                               # 检测结果：每个框的中心
    true_xy = np.array([[b.cx_m, b.cy_m] for b in DEFAULT_SCENE])   # 真值：每个真东西的中心
    print(f"检测到 {len(pred_xy)} 个框，真东西 {len(true_xy)} 个\n")

    print("门槛(米)  配上几对  召回率  精确率  平均位置误差(米)")
    results = {}
    for gate in GATES_M:
        r = detection_metrics(pred_xy, true_xy, gate)
        results[gate] = r
        print(f"{gate:6.1f}   {len(r['matches']):5d}     {r['recall']:5.2f}   {r['precision']:5.2f}   {r['mean_error_m']:8.2f}")

    for gate in (2.0,):
        r = results[gate]
        print(f"\n门槛 {gate} 米时谁配上了：")
        found = set()
        for i, j, d in r["matches"]:
            found.add(j)
            print(f"  框 {i}（中心 {pred_xy[i, 0]:6.2f}, {pred_xy[i, 1]:5.2f}）认领 {NAMES[DEFAULT_SCENE[j].name]:4s}  差 {d:.2f} 米")
        for j, b in enumerate(DEFAULT_SCENE):
            if j not in found:
                print(f"  没找到（漏检）：{NAMES[b.name]}（真中心 {b.cx_m:6.2f}, {b.cy_m:5.2f}）")
        used = {i for i, _, _ in r["matches"]}
        for i in range(len(pred_xy)):
            if i not in used:
                print(f"  白画的框（误报）：框 {i}（中心 {pred_xy[i, 0]:6.2f}, {pred_xy[i, 1]:5.2f}）")


if __name__ == "__main__":
    main()
