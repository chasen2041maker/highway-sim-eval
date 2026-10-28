"""A5 搬进 CARLA（回家待办 ④）：用 CARLA 真的激光雷达扫一圈，跑 A5 的去地面 → DBSCAN → 框，再和真值对答案。

和纯 Python 版 examples/a5_eval.py 同一套流程，不同的是：
  点云来自 CARLA 的 sensor.lidar.ray_cast（32 线、50 米、装在车顶 1.8 米高），
  场景是 CARLA 地图里真的路：我的车 + 同车道前车 + 旁边车道一辆 + 后车 + 人行道上一个人（放得下才放），
  路边还有树、路灯杆、房子——这些不在真值表里。
CARLA 是左手系：雷达给的点 x 前、y 右、z 上；我们的 ads/perception.py 用 x 前、y 左、z 上，所以 y 要变号。

运行（在项目根目录，CARLA 要开着）：
    python -m examples.a5_carla_lidar            # y 变号（对的做法）
    python -m examples.a5_carla_lidar noflip     # 故意不变号，看会怎样
    python -m examples.a5_carla_lidar show       # 再在 CARLA 窗口里一步一步画出来（扫一圈 → 去地面 → 分堆 → 框），约 20 秒
俯视图存到 outputs/a5_carla_lidar.png（noflip 存到 outputs/a5_carla_lidar_noflip.png）。
"""

import math
import queue
import sys
import time
from pathlib import Path

import carla
import numpy as np

from ads.perception import cluster_points, cluster_to_box, remove_ground
from evaluation.metrics import detection_metrics
from sim.carla_client import CarlaSim

FLIP_Y = "noflip" not in sys.argv     # 命令行带 noflip 就故意不变号
SHOW = "show" in sys.argv             # 命令行带 show 就在 CARLA 窗口里画出来

SPAWN_INDEX = 80           # 前面 178 米直路（a4 用的那个出生点）
LIDAR_Z_M = 1.8            # 雷达装在车顶，离地 1.8 米（和假雷达一样）
Z_THRESHOLD_M = -1.6       # A5 的去地面门槛：比地面（−1.8）高 20 厘米以上才留下
EPS_M = 1.0                # A5 的 DBSCAN 参数
MIN_SAMPLES = 5
GATES_M = [0.5, 1.0, 2.0, 4.0]
ROI_X_M = (-20.0, 40.0)    # 只看车前后这一段路（米，雷达坐标）
ROI_Y_M = (-8.0, 8.0)      # 左右各 8 米：本车道、旁边车道和人行道


# ---------- 实验台（助手写的，不用敲）----------

def spawn_scene(sim, ego):
    """在我周围放几个“真东西”。返回 [(名字, actor)]；放不下的位置会跳过并打印出来。"""
    world, lib = sim.world, sim.world.get_blueprint_library()
    wp = world.get_map().get_waypoint(ego.get_location())
    placed = []

    def put(name, blueprint, location, rotation=carla.Rotation(), quiet=False):
        actor = world.try_spawn_actor(lib.find(blueprint), carla.Transform(location, rotation))
        if actor is None:
            if not quiet:
                print(f"  {name}：这个位置放不下，跳过")
            return False
        if isinstance(actor, carla.Vehicle):
            actor.apply_control(carla.VehicleControl(hand_brake=True))   # 拉上手刹，原地不动
        placed.append((name, actor))
        return True

    up = carla.Location(z=0.3)
    ahead = wp.next(15.0)[0]
    put("前车", "vehicle.tesla.model3", ahead.transform.location + up, ahead.transform.rotation)
    behind = wp.previous(12.0)[0]
    put("后车", "vehicle.audi.a2", behind.transform.location + up, behind.transform.rotation)

    side = wp.get_left_lane()
    if side is None or side.lane_type != carla.LaneType.Driving:
        side = wp.get_right_lane()
    if side is not None and side.lane_type == carla.LaneType.Driving:
        same_way = side.lane_id * wp.lane_id > 0                 # 同向车道往 next 走，对向车道往 previous 走
        s = (side.next(24.0) if same_way else side.previous(24.0))[0]
        put("旁边车道的车", "vehicle.lincoln.mkz_2020", s.transform.location + up, s.transform.rotation)
    else:
        print("  旁边车道：没找到能开车的车道，跳过")

    lane = wp
    for _ in range(4):                                           # 往右找人行道
        lane = lane.get_right_lane()
        if lane is None:
            break
        if lane.lane_type == carla.LaneType.Sidewalk:
            for d in (11.0, 9.0, 13.0, 7.0, 15.0):              # 放不下（撞到路灯、树）就沿人行道挪一挪
                p = (lane.next(d) if lane.lane_id * wp.lane_id > 0 else lane.previous(d))[0]
                if put("行人", "walker.pedestrian.0001", p.transform.location + carla.Location(z=1.0), quiet=True):
                    break
            else:
                print("  行人：人行道上试了 5 个位置都放不下，跳过")
            break
    else:
        print("  行人：右边没找到人行道，跳过")
    return placed


def truth_in_lidar_frame(ego, placed):
    """真值：每个真东西的框中心，换到雷达坐标（x 前、y 左），和检测结果用同一套坐标。只给打分用。"""
    tf = ego.get_transform()
    yaw = math.radians(tf.rotation.yaw)
    xy = []
    for _, actor in placed:
        c = actor.get_transform().transform(actor.bounding_box.location)   # 框中心（世界坐标）
        dx, dy = c.x - tf.location.x, c.y - tf.location.y
        forward = math.cos(yaw) * dx + math.sin(yaw) * dy                  # 沿我的车头往前多少
        right = -math.sin(yaw) * dx + math.cos(yaw) * dy                   # 往我的右边多少（CARLA 的 y）
        xy.append((forward, -right))                                       # 我们的 y 朝左
    return np.array(xy).reshape(-1, 2)


def crop(points):
    """只留路附近（ROI），再去掉打在自己车身上的点。"""
    x, y = points[:, 0], points[:, 1]
    roi = (x > ROI_X_M[0]) & (x < ROI_X_M[1]) & (y > ROI_Y_M[0]) & (y < ROI_Y_M[1])
    on_me = (np.abs(x) < 2.6) & (np.abs(y) < 1.2)
    return points[roi & ~on_me]


def report(pred_xy, true_xy, names):
    print(f"\n检测到 {len(pred_xy)} 个框，真值表里 {len(true_xy)} 个\n")
    print("门槛(米)  配上几对  召回率  精确率  平均位置误差(米)")
    for gate in GATES_M:
        r = detection_metrics(pred_xy, true_xy, gate)
        print(f"{gate:6.1f}   {len(r['matches']):5d}     {r['recall']:5.2f}   {r['precision']:5.2f}   {r['mean_error_m']:8.2f}")
    r = detection_metrics(pred_xy, true_xy, 2.0)
    print("\n门槛 2.0 米时谁配上了：")
    found = {j for _, j, _ in r["matches"]}
    for i, j, d in r["matches"]:
        print(f"  框 {i}（中心 {pred_xy[i, 0]:6.2f}, {pred_xy[i, 1]:6.2f}）认领 {names[j]}（真中心 {true_xy[j, 0]:6.2f}, {true_xy[j, 1]:6.2f}）差 {d:.2f} 米")
    for j, name in enumerate(names):
        if j not in found:
            print(f"  没找到（漏检）：{name}（真中心 {true_xy[j, 0]:6.2f}, {true_xy[j, 1]:6.2f}）")
    used = {i for i, _, _ in r["matches"]}
    for i in range(len(pred_xy)):
        if i not in used:
            print(f"  真值表里没有的框：框 {i}（中心 {pred_xy[i, 0]:6.2f}, {pred_xy[i, 1]:6.2f}）")


def plot(points, kept, labels, boxes, true_xy, names):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except ImportError:
        print("没有装 matplotlib，跳过画图")
        return
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.scatter(points[:, 0], points[:, 1], s=1, color="#c8c8c8", label="all points (cropped)")
    ax.scatter(kept[labels >= 0, 0], kept[labels >= 0, 1], s=3, c=labels[labels >= 0] % 10, cmap="tab10",
               label="kept points, colored by cluster")
    for k, (cx, cy, lx, ly) in enumerate(boxes):
        ax.add_patch(Rectangle((cx - lx / 2, cy - ly / 2), lx, ly, fill=False, edgecolor="#2a6bd1", linewidth=1.5))
        ax.text(cx, cy + ly / 2 + 0.3, f"box {k}", color="#2a6bd1", fontsize=8, ha="center")
    ax.scatter(true_xy[:, 0], true_xy[:, 1], marker="x", s=80, color="#d23c3c", label="truth centers")
    english = {"前车": "lead", "后车": "behind", "旁边车道的车": "side lane", "行人": "pedestrian"}
    for (tx, ty), name in zip(true_xy, names):
        ax.text(tx, ty - 0.9, english.get(name, name), color="#d23c3c", fontsize=9, ha="center")
    ax.scatter([0], [0], marker="^", s=120, color="black", label="me (lidar)")
    ax.set_xlim(*ROI_X_M)
    ax.set_ylim(*ROI_Y_M)
    ax.set_aspect("equal")
    ax.set_xlabel("x forward (m)")
    ax.set_ylabel("y left (m)")
    ax.set_title(f"CARLA lidar, top view ({'y flipped' if FLIP_Y else 'y NOT flipped'})")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(color="#e4e3dd", linewidth=0.8)
    fig.tight_layout()
    out = Path("outputs") / ("a5_carla_lidar.png" if FLIP_Y else "a5_carla_lidar_noflip.png")
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=110)
    print(f"\n俯视图已保存：{out}")


def show_in_carla(sim, ego, lidar, points, kept, labels, boxes, placed):
    """在 CARLA 窗口里一步一步画：① 扫一圈 ② 去地面 ③ 分堆 ④ 框 + 真值。镜头挪到车的正上方往下看。
    画的是算法“以为”的位置：noflip 时点会画在左右对调的地方。"""
    world, dbg = sim.world, sim.world.debug
    tf = ego.get_transform()
    up = carla.Location(x=tf.location.x, y=tf.location.y, z=tf.location.z + 35.0) + tf.get_forward_vector() * 8.0
    world.get_spectator().set_transform(carla.Transform(up, carla.Rotation(pitch=-90.0, yaw=tf.rotation.yaw)))
    # 我的车：绿框 + ME，整段都在（雷达装在它车顶，一圈一圈的地面点就围着它）
    dbg.draw_box(carla.BoundingBox(tf.transform(ego.bounding_box.location), ego.bounding_box.extent),
                 tf.rotation, 0.1, carla.Color(0, 220, 0), 40.0)
    dbg.draw_string(tf.location + carla.Location(z=3.0), "ME", True, carla.Color(0, 255, 0), 40.0)

    ltf = lidar.get_transform()
    yaw = math.radians(ltf.rotation.yaw)
    c, s = math.cos(yaw), math.sin(yaw)

    def to_world(x, y, z):
        """雷达坐标（x 前、y 左）→ CARLA 世界坐标。"""
        yc = -y                                                   # 我们的 y 朝左 → CARLA 的 y 朝右
        return carla.Location(x=ltf.location.x + c * x - s * yc, y=ltf.location.y + s * x + c * yc,
                              z=ltf.location.z + z + 0.05)

    def wait(seconds):
        for _ in range(round(seconds / sim.dt_s)):
            sim.tick()
            time.sleep(sim.dt_s)

    gray, white = carla.Color(120, 120, 120), carla.Color(255, 255, 255)
    palette = [carla.Color(255, 140, 0), carla.Color(160, 90, 255), carla.Color(0, 200, 200),
               carla.Color(230, 60, 230), carla.Color(140, 220, 40), carla.Color(255, 220, 0)]
    ground = points[points[:, 2] <= Z_THRESHOLD_M][::8]           # 地面点太多，只画八分之一
    az = np.degrees(np.arctan2(points[:, 1], points[:, 0])) % 360

    print("\n在 CARLA 窗口里看（镜头在车正上方 35 米，车头朝屏幕上方；绿框 + ME = 我的车）：")
    print("  ① 扫一圈：激光转一圈，一扇一扇画出来（地面点只画 1/8）")
    gaz = np.degrees(np.arctan2(ground[:, 1], ground[:, 0])) % 360
    for k in range(24):                                           # 24 扇，每扇 15°
        lo, hi = k * 15, (k + 1) * 15
        for x, y, z in ground[(gaz >= lo) & (gaz < hi)]:
            dbg.draw_point(to_world(x, y, z), size=0.06, color=gray, life_time=4.0)
        for x, y, z in points[(points[:, 2] > Z_THRESHOLD_M) & (az >= lo) & (az < hi)]:
            dbg.draw_point(to_world(x, y, z), size=0.06, color=white, life_time=4.0)
        wait(0.1)
    wait(2.0)
    print(f"  ② 去地面：只剩比地面高 20 厘米以上的 {len(kept)} 个点")
    for x, y, z in kept:
        dbg.draw_point(to_world(x, y, z), size=0.08, color=white, life_time=3.0)
    wait(3.0)
    print(f"  ③ 分堆：同一种颜色 = 同一堆（{len(boxes)} 堆），灰的是噪声")
    for (x, y, z), lab in zip(kept, labels):
        dbg.draw_point(to_world(x, y, z), size=0.1, color=palette[lab % len(palette)] if lab >= 0 else gray, life_time=16.0)
    wait(3.0)
    print("  ④ 画框：蓝框 = 算法找到的，红框 = 真值")
    for cx, cy, lx, ly in boxes:
        center = to_world(cx, cy, Z_THRESHOLD_M + 0.8)
        dbg.draw_box(carla.BoundingBox(center, carla.Vector3D(lx / 2 + 0.1, ly / 2 + 0.1, 0.8)),
                     carla.Rotation(yaw=ltf.rotation.yaw), 0.08, carla.Color(40, 120, 255), 13.0)
    for _, actor in placed:
        atf = actor.get_transform()
        dbg.draw_box(carla.BoundingBox(atf.transform(actor.bounding_box.location), actor.bounding_box.extent),
                     atf.rotation, 0.05, carla.Color(255, 40, 40), 13.0)
    print("  （停 12 秒给你看，然后车会被删掉）")
    wait(12.0)


# ---------- 感知：雷达的一帧 → 框（从这里开始手敲）----------

def detect(lidar_data):
    """CARLA 雷达的一帧 → (所有点, 去完地面的点, 每个点的堆号, 框)。坐标：x 前、y 左、z 上。"""
    pts = np.frombuffer(lidar_data.raw_data, dtype=np.float32).reshape(-1, 4)[:,:3].copy()
    if FLIP_Y:
        pts[:, 1] *= -1            # CARLA 的 y 朝右 → 我们的 y 朝左
    pts = crop(pts)                # 只留路附近，去掉打在自己车上的点（实验台写好的）
    kept, _ = remove_ground(pts,Z_THRESHOLD_M)
    labels = cluster_points(kept, EPS_M, MIN_SAMPLES)
    boxes = cluster_to_box(kept, labels)
    return pts, kept, labels, boxes


    


# ---------- 主程序 ----------

with CarlaSim(dt_s=0.05) as sim:
    ego = sim.spawn_ego(spawn_index=SPAWN_INDEX)
    ego.apply_control(carla.VehicleControl(hand_brake=True))
    print("放场景：")
    placed = spawn_scene(sim, ego)
    print("  放好了：" + "、".join(name for name, _ in placed))

    bp = sim.world.get_blueprint_library().find("sensor.lidar.ray_cast")
    hz = round(1 / sim.dt_s)                  # 每帧正好转一圈
    for key, value in {"channels": 32, "range": 50, "upper_fov": 10, "lower_fov": -30,
                       "rotation_frequency": hz, "points_per_second": 32 * 900 * hz,   # 一圈每 0.4° 打一次 = 900 次
                       "dropoff_general_rate": 0.0, "dropoff_intensity_limit": 1.0,
                       "dropoff_zero_intensity": 0.0}.items():
        bp.set_attribute(key, str(value))
    lidar = sim.world.spawn_actor(bp, carla.Transform(carla.Location(z=LIDAR_Z_M)), attach_to=ego)
    scans = queue.Queue()
    lidar.listen(scans.put)
    try:
        for _ in range(20):                   # 走 1 秒：车落地、站稳
            sim.tick()
        frame, _ = sim.tick()
        data = scans.get(timeout=5.0)
        while data.frame < frame:             # 只要这一帧的
            data = scans.get(timeout=5.0)
        print(f"\n雷达这一帧：{len(data)} 个点（第 {data.frame} 帧）；y {'已变号' if FLIP_Y else '没变号（故意的）'}")

        points, kept, labels, boxes = detect(data)
        boxes = np.asarray(boxes).reshape(-1, 4)
        names = [name for name, _ in placed]
        true_xy = truth_in_lidar_frame(ego, placed)
        print(f"路附近 {len(points)} 个点 → 去完地面 {len(kept)} 个 → 分成 {len(boxes)} 堆")
        report(boxes[:, :2], true_xy, names)
        plot(points, kept, labels, boxes, true_xy, names)
        if SHOW:
            show_in_carla(sim, ego, lidar, points, kept, labels, boxes, placed)
    finally:
        lidar.stop()
        lidar.destroy()
        for _, actor in placed:
            actor.destroy()
