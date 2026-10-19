"""假激光雷达：纯 Python 造一帧点云（A5 预演用；回家换成 CARLA 的 sensor.lidar.ray_cast）。

坐标（雷达坐标系）：x 前、y 左、z 上，原点就在雷达上（和 ads/vehicle.py 同向）。
雷达装在离地 1.8 米高的车顶，所以平地上的点 z ≈ −1.8。
CARLA 的激光雷达是 y 朝右（左手系），回家时 y 要变号，见 sim/transforms.py。

参数仿 CARLA 常用设置：32 线（竖着排 32 根激光，向上 10° 到向下 30°），
一圈 360° 每 0.4° 打一次，最远 50 米。每根激光打到最近的东西（地面或盒子）回来一个点。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LIDAR_HEIGHT_M = 1.8


@dataclass
class Box:
    """立在地上的长方体（车、人）。cx, cy 是它底面中心在雷达坐标里的位置，yaw 往左转为正。"""
    name: str
    cx_m: float
    cy_m: float
    length_m: float
    width_m: float
    height_m: float
    yaw_rad: float = 0.0


# 一个路口前的场景：同车道前车、左车道一辆、右边停一辆、人行道上一个人、后面跟一辆
DEFAULT_SCENE = [
    Box("lead car", 15.0, 0.0, 4.6, 1.9, 1.5),
    Box("left-lane car", 24.0, 3.6, 4.6, 1.9, 1.6, 0.05),
    Box("parked car", 9.0, -4.5, 4.4, 1.8, 1.5, -0.25),
    Box("pedestrian", 11.0, 6.0, 0.6, 0.6, 1.7),
    Box("car behind", -12.0, 0.3, 4.6, 1.9, 1.5),
]


def ray_directions(channels=32, upper_deg=10.0, lower_deg=-30.0, h_res_deg=0.4):
    """所有激光的方向（单位向量），形状 (channels × 一圈几次, 3)。"""
    elev = np.radians(np.linspace(upper_deg, lower_deg, channels))
    azim = np.radians(np.arange(0.0, 360.0, h_res_deg))
    e, a = np.meshgrid(elev, azim, indexing="ij")
    d = np.stack([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)], axis=-1)
    return d.reshape(-1, 3)


def _hit_box(d, box, ground_z):
    """每根激光打到这个盒子的距离 t（打不到是 inf）。在盒子自己的坐标里用"三对平行面"求交。"""
    c, s = np.cos(-box.yaw_rad), np.sin(-box.yaw_rad)
    # 雷达在盒子坐标里的位置 p，激光方向 db（都转到盒子坐标）
    ox, oy, oz = -box.cx_m, -box.cy_m, -ground_z
    p = np.array([c * ox - s * oy, s * ox + c * oy, oz])
    db = np.stack([c * d[:, 0] - s * d[:, 1], s * d[:, 0] + c * d[:, 1], d[:, 2]], axis=1)
    lo = np.array([-box.length_m / 2, -box.width_m / 2, 0.0])
    hi = np.array([box.length_m / 2, box.width_m / 2, box.height_m])
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = (lo - p) / db
        t2 = (hi - p) / db
    t_near = np.nanmax(np.minimum(t1, t2), axis=1)
    t_far = np.nanmin(np.maximum(t1, t2), axis=1)
    hit = (t_far >= t_near) & (t_near > 0)
    return np.where(hit, t_near, np.inf)


def scan(scene=DEFAULT_SCENE, channels=32, upper_deg=10.0, lower_deg=-30.0, h_res_deg=0.4,
         range_m=50.0, height_m=LIDAR_HEIGHT_M, ground_slope=0.0, noise_m=0.02, seed=0):
    """扫一圈。返回 (points, labels)：
    points 形状 (N, 3)，每行一个点 (x, y, z)，单位米，雷达坐标；
    labels 形状 (N,)，−1 = 地面，k = 打在 scene[k] 上（真值，只给评测和画图用，算法不许偷看）。
    ground_slope：地面坡度（前方每走 1 米升高多少米），0 = 平地；以后讲 RANSAC 时用。
    """
    rng = np.random.default_rng(seed)
    d = ray_directions(channels, upper_deg, lower_deg, h_res_deg)
    # 地面 z = −height + slope·x；激光 t·d 落在地面上 → t = −height / (dz − slope·dx)
    denom = d[:, 2] - ground_slope * d[:, 0]
    with np.errstate(divide="ignore"):
        t_ground = np.where(denom < 0, -height_m / denom, np.inf)
    ts = [t_ground]
    for box in scene:
        ground_z = -height_m + ground_slope * box.cx_m   # 盒子底面贴着它脚下的地面
        ts.append(_hit_box(d, box, ground_z))
    ts = np.stack(ts, axis=1)
    which = np.argmin(ts, axis=1)
    t = ts[np.arange(len(d)), which]
    keep = t < range_m                       # 打向天空、或超过 50 米的激光没有回来
    t = t[keep] + rng.normal(0.0, noise_m, keep.sum())   # 测距有 2 厘米左右的误差
    points = d[keep] * t[:, None]
    labels = which[keep] - 1                 # 0 号是地面 → −1；盒子 k → k
    return points, labels
