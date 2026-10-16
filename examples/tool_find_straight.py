"""工具（助手写的，不用手敲）：找“车头前面有一长段直路”的出生点，给 CARLA 跟车实验用。

跟车要开 100 多米直线，出生点 0 前面 20 米就是路口左转，不够用。
这个脚本只读地图，不放车、不改设置。

运行（先开 CARLA）：python -m examples.tool_find_straight
"""

import carla

STEP_M = 2.0          # 沿车道每 2 米看一次
MAX_M = 200.0         # 最多往前看 200 米
MAX_TURN_DEG = 3.0    # 车道方向和出生点比，偏了超过 3° 就算“开始拐弯”了


def turn_deg(yaw_a, yaw_b):
    """两个朝向差几度（0 到 180）。"""
    return abs((yaw_a - yaw_b + 180.0) % 360.0 - 180.0)


client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
carla_map = client.get_world().get_map()

results = []
for i, sp in enumerate(carla_map.get_spawn_points()):
    wp = carla_map.get_waypoint(sp.location)
    yaw0 = wp.transform.rotation.yaw
    straight_m = 0.0
    while straight_m < MAX_M:
        options = wp.next(STEP_M)
        if not options:                       # 车道到头了
            break
        # 路口有几条路就有几个选项：挑方向最接近出生点的那条（= 直行）
        nxt = min(options, key=lambda w: turn_deg(w.transform.rotation.yaw, yaw0))
        if turn_deg(nxt.transform.rotation.yaw, yaw0) > MAX_TURN_DEG:
            break                             # 开始拐弯了
        wp = nxt
        straight_m += STEP_M
    results.append((straight_m, i, sp.location.x, sp.location.y))

results.sort(reverse=True)
print(f"地图 {carla_map.name}，共 {len(results)} 个出生点。前面直路最长的 8 个：")
for straight_m, i, x, y in results[:8]:
    print(f"  出生点 {i:3d}：前面直路 {straight_m:5.0f} 米   （CARLA 坐标 x={x:7.1f}  y={y:7.1f}）")
