"""C3 第 2 步挑片段的几把尺子。数字都是手算的小例子，不读 nuScenes。"""

import math

from examples.c_review.c3_pick import (accel, closing_speed, in_straight_lane, min_ttc, my_path, on_my_path, path_dist,
                                       pick_scene, same_direction)


def car(inst, ex, ey, xy=None, w=1.8, cat="vehicle.car"):
    """一个框。自车在原点、车头朝 +x 时，地图坐标就等于我的坐标。"""
    return {"inst": inst, "ann": inst, "cat": cat, "ex": ex, "ey": ey, "xy": xy or (ex, ey), "w": w, "l": 4.5}


def frame(t, v, objs, ego_xy=(0.0, 0.0), ego_yaw=0.0):
    return {"t": t, "v": v, "objs": objs, "ego_xy": ego_xy, "ego_yaw": ego_yaw}


def test_path_dist_clamps_to_segment_end():
    path = [(0, 0), (10, 0)]
    assert path_dist(path, (5, 2)) == 2                     # 垂足在线段中间
    assert path_dist(path, (13, 4)) == 5                    # 超出终点：量到终点 (10, 0)，3-4-5


def test_turning_left_straight_lane_picks_but_real_path_does_not():
    # 我左转 90°：路 (0,0) → (5,0) → (5,10)。它在 (10, −1)：直尺里（|−1| < 1.75 + 0.9），离真实的路 √(5² + 1²) ≈ 5.10
    worker = car("w", 10, -1, w=1.8)
    path = [(0, 0), (5, 0), (5, 10)]
    assert in_straight_lane(worker)
    assert math.isclose(path_dist(path, worker["xy"]), math.sqrt(26))
    assert not on_my_path(worker, path)


def test_barriers_and_cars_behind_do_not_count():
    assert not in_straight_lane(car("b", 10, 0, cat="movable_object.barrier"))
    assert not in_straight_lane(car("c", -10, 0))


def test_my_path_extends_straight_from_last_pose():
    # 两帧停在原地、车头朝 +y：路 = 原地两个点 + 顺着车头接 30 米到 (0, 30)
    frames = [frame(0.0, None, [], (0.0, 0.0), math.pi / 2), frame(0.5, 0.0, [], (0.0, 0.0), math.pi / 2)]
    path = my_path(frames, 0)
    assert path[:2] == [(0.0, 0.0), (0.0, 0.0)]
    assert math.isclose(path[-1][0], 0.0, abs_tol=1e-9) and math.isclose(path[-1][1], 30.0)


def test_closing_speed_uses_previous_and_next_frame():
    # 前方几米 20 → 17 → 14，每 0.5 秒少 3 米 = 6 m/s；中间那帧用前后两帧：(20 − 14) ÷ 1.0
    frames = [frame(0.0, None, [car("a", 20, 0)]), frame(0.5, 6.0, [car("a", 17, 0)]), frame(1.0, 6.0, [car("a", 14, 0)])]
    assert closing_speed(frames, 1, "a") == 6.0
    assert closing_speed(frames, 0, "a") == 6.0             # 第 1 帧没有上一帧：用这一帧和下一帧
    assert closing_speed(frames, 2, "a") == 6.0             # 最后一帧没有下一帧：用上一帧和这一帧


def test_min_ttc_only_counts_closing():
    # a：17 米、接近 6 m/s → TTC 17 / 6；b：离我越来越远，不算
    frames = [frame(0.0, None, [car("a", 20, 0), car("b", 10, 0.5)]),
              frame(0.5, 6.0, [car("a", 17, 0), car("b", 12, 0.5)]),
              frame(1.0, 6.0, [car("a", 14, 0), car("b", 14, 0.5)])]
    ttc, who = min_ttc(frames, 1, in_straight_lane)
    assert math.isclose(ttc, 17 / 6) and who["inst"] == "a"
    frames_far = [frame(0.0, None, [car("b", 10, 0)]), frame(0.5, 6.0, [car("b", 12, 0)])]
    assert min_ttc(frames_far, 0, in_straight_lane) == (None, None)


def test_accel_skips_first_two_frames():
    # 第 1 帧车速算不出来（None），第 2 帧会用到它；第 3 帧：(8 − 9) ÷ 0.5 = −2
    frames = [frame(0.0, None, []), frame(0.5, 9.0, []), frame(1.0, 8.0, [])]
    assert accel(frames, 0) is None and accel(frames, 1) is None
    assert accel(frames, 2) == -2.0


def test_pick_scene_rules():
    # 第 2 帧：前车 12 米、接近 6 m/s → TTC 2.0 < 3，挑；第 3 帧：9 → 7 一下掉 2，0.5 秒 = −4 < −3，急刹
    frames = [frame(0.0, None, [car("a", 15, 0)]), frame(0.5, 9.0, [car("a", 12, 0)]),
              frame(1.0, 7.0, [car("a", 9, 0)])]
    picked = pick_scene(frames, use_path=False, same_dir=False)
    rules = [(p["k"], p["rule"]) for p in picked]
    assert (1, "TTC") in rules and (2, "急刹") in rules
    ttc_row = next(p for p in picked if p["k"] == 1)
    assert math.isclose(ttc_row["value"], 2.0)


def test_same_direction_looks_at_where_it_moves():
    # 我车头朝 +x。它每 0.5 秒：往 −x 走 3 米（迎面 6 m/s）、往 +x 走 3 米（同向）、往 +y 走 3 米（横穿，差 90°）、只挪 0.2 米（基本停着）
    def two(dx, dy):
        return [frame(0.0, 5.0, [car("o", 10, 0, xy=(10, 0))]), frame(0.5, 5.0, [car("o", 10, 0, xy=(10 + dx, dy))])]
    assert not same_direction(two(-3, 0), 0, {"inst": "o"})
    assert same_direction(two(3, 0), 0, {"inst": "o"})
    assert not same_direction(two(0, 3), 0, {"inst": "o"})
    assert same_direction(two(0.2, 0), 0, {"inst": "o"})     # 0.4 m/s < 1：停着照算


def test_stopped_ego_oncoming_car_is_not_picked():
    # 我停着；对面的车朝我开过来：前方 10 → 7 → 4，地图上往 −x 走 6 m/s。不管方向会算出 TTC 7 / 6 < 3 被挑；同方向规则去掉它
    frames = [frame(0.0, None, [car("c", 10, 0)]), frame(0.5, 0.0, [car("c", 7, 0)]), frame(1.0, 0.0, [car("c", 4, 0)])]
    assert any(p["rule"] == "TTC" for p in pick_scene(frames, use_path=True, same_dir=False))
    assert not any(p["rule"] == "TTC" for p in pick_scene(frames, use_path=True, same_dir=True))
