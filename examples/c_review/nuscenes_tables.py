"""C3：直接读 nuScenes 的 JSON 表（不装官方工具包），外加坐标换算和把 3D 框投到照片上。

表和表之间靠 token（编号）连起来：照片（sample_data）→ 关键帧（sample）；框（sample_annotation）→ 这是谁（instance）→ 这是什么（category）。
坐标：框和自车位置都记在地图坐标里；换到“我的坐标”（x 朝前、y 朝左）要先减去自车位置、再转回自车朝向。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2] / "data" / "nuscenes"
TABLES = ["scene", "sample", "sample_data", "ego_pose", "sample_annotation", "instance", "category",
          "sensor", "calibrated_sensor", "attribute", "visibility", "log"]


def load(root: Path = ROOT, version: str = "v1.0-mini") -> dict[str, dict[str, dict]]:
    """读 12 张表，每张表变成 {token: 那一行}，查的时候直接按编号取。"""
    return {name: {r["token"]: r for r in json.loads((root / version / f"{name}.json").read_text(encoding="utf-8"))}
            for name in TABLES}


def quat_to_rot(q) -> np.ndarray:
    """四元数 [w, x, y, z] → 3×3 旋转矩阵。"""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def yaw_of(q) -> float:
    """四元数的朝向角（绕竖直轴转了多少，弧度）。"""
    w, x, y, z = q
    return float(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


def to_ego(points: np.ndarray, ego_pose: dict) -> np.ndarray:
    """地图坐标的点（N×3）→ 我的坐标（x 朝前、y 朝左、z 朝上）：先减去自车位置，再转回自车朝向。"""
    return (points - np.array(ego_pose["translation"])) @ quat_to_rot(ego_pose["rotation"])


def box_corners(ann: dict) -> np.ndarray:
    """一个 3D 框的 8 个角（地图坐标，8×3）。size = [宽, 长, 高]；框自己的 x 朝车头、y 朝左。"""
    w, l, h = ann["size"]
    x = l / 2 * np.array([1, 1, 1, 1, -1, -1, -1, -1])
    y = w / 2 * np.array([1, -1, -1, 1, 1, -1, -1, 1])
    z = h / 2 * np.array([1, 1, -1, -1, 1, 1, -1, -1])
    return np.stack([x, y, z], axis=1) @ quat_to_rot(ann["rotation"]).T + np.array(ann["translation"])


def project(points_ego: np.ndarray, calib: dict) -> tuple[np.ndarray, np.ndarray]:
    """我的坐标的点 → 相机坐标（z 朝前）→ 照片上的像素。返回 (像素 N×2, 离相机的深度 N)。"""
    cam = (points_ego - np.array(calib["translation"])) @ quat_to_rot(calib["rotation"])
    k = np.array(calib["camera_intrinsic"])
    uvw = cam @ k.T
    depth = cam[:, 2]
    return uvw[:, :2] / np.where(np.abs(depth) < 1e-6, 1e-6, depth)[:, None], depth
