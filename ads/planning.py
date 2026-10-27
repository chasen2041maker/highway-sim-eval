"""规划：跟车（IDM）、停车保持、变道（A7：MOBIL 决定要不要变，Frenet 画变道曲线）。"""

from __future__ import annotations
import math


def idm_accel(speed_mps: float, lead_speed_mps: float, gap_m: float, target_speed_mps: float, max_accel_mps2: float = 3.0, min_gap_m: float = 5.0,
              time_gap_s: float = 1.5, delta: float = 4.0, comfort_brake_mps2: float = 5.0) -> float:
    """IDM 跟车：加速度 = 本来想加的 − 怕撞要减的。gap_m：我的车头到前车车尾的距离。"""
    want = max_accel_mps2 * (1 - (speed_mps / target_speed_mps) ** delta)     # 本来想加的
    closing_mps = speed_mps - lead_speed_mps    # 我比前车快多少（追得多快）
    chase_m = speed_mps * closing_mps / (2 * math.sqrt(max_accel_mps2 * comfort_brake_mps2))   # 追得快，多留的那一截
    desired_gap_m = min_gap_m + max(0.0, speed_mps * time_gap_s + chase_m)     # 想保持的距离（最少 5 米）

    
    fear = max_accel_mps2 * (desired_gap_m / gap_m) ** 2
    return want - fear

from dataclasses import dataclass


@dataclass
class StopHold:
    """停车保持（ACC 的 stop & go）：跟着前车停下后就踩住刹车不动，等前车起步再走。

    进入（三个条件都满足）：我的车速 < enter_speed_mps，前车车速 < enter_lead_mps，车距 < enter_gap_m。
    退出（满足一个就行）：前车车速 > exit_lead_mps（前车起步了），或车距 > exit_gap_m（前车走远了）。
    进入和退出用不同的门槛（迟滞），防止在门槛附近一会儿进、一会儿出。
    """
    enter_speed_mps: float = 1.0
    enter_lead_mps: float = 0.5
    enter_gap_m: float = 8.0
    exit_lead_mps: float = 1.0
    exit_gap_m: float = 11.0
    holding: bool = False      # 现在是不是在停车保持（自己记着）

    def update(self, speed_mps: float, lead_speed_mps: float, gap_m: float) -> bool:
        """每帧调用一次：更新状态，返回这一帧要不要停车保持。"""
        if self.holding:
            if lead_speed_mps > self.exit_lead_mps or gap_m > self.exit_gap_m:
                self.holding = False
        elif speed_mps < self.enter_speed_mps and lead_speed_mps < self.enter_lead_mps and gap_m < self.enter_gap_m:
            self.holding = True
        return self.holding


# ---------- A7 变道 ----------

def mobil_should_change(me_now: float, me_after: float,
                        new_back_now: float, new_back_after: float,
                        old_back_now: float = 0.0, old_back_after: float = 0.0,
                        politeness: float = 0.0, max_brake_imposed: float = 2.0,
                        min_gain: float = 0.2) -> bool:
    """MOBIL：要不要变道（A7 第 1 步）。开车时“看后视镜”那一下。

    在系统里：每帧对左、右两条车道各问一次；回答 True 就交给第 2 步画变道曲线。
    所有参数都是用 IDM（idm_accel）算出来的加速度，单位 m/s²，负数 = 在刹车：
        me_now / me_after：我现在 / 变过去以后的加速度；
        new_back_now / new_back_after：目标车道后车现在 / 我插到它前面以后的加速度；
        old_back_now / old_back_after：本车道后车现在 / 我走了以后的加速度。
    politeness：礼貌系数，0 = 只管自己，1 = 别人的损失和自己的好处一样重要。
    两道检查（HighwayEnv 的默认值：politeness 0、max_brake_imposed 2、min_gain 0.2）：
        ① 安全：我插进去以后，目标车道后车要刹得比 max_brake_imposed 还狠 → 不变；
        ② 划算：我的好处 + politeness × (两辆后车的好处) > min_gain → 变，否则不变。
    """
    # ① 安全：别逼目标车道后车急刹
    if new_back_after < -max_brake_imposed:
        return False
    # ② 划算：我的好处 + 礼貌 × 两辆后车的好处
    gain = (me_after - me_now) + politeness * ((new_back_after - new_back_now) + (old_back_after - old_back_now))
    return gain > min_gain

def lane_change_d(t_s: float, duration_s: float, d_end_m: float, d_start_m: float = 0.0) -> tuple[float, float, float, float]:
    """变道曲线（A7 第 2 步）：五次多项式，横向偏移 d 随时间从 d_start_m 平滑地变到 d_end_m。

    在系统里：第 1 步 MOBIL 说“变”，这一步算出每个时刻车该往旁边偏多少（Frenet 坐标里的 d）；
    第 3 步再把 (s, d) 换回地图上的 (x, y)，交给 Pure Pursuit 去跟。
    d：离本车道中心线多远（米，左正）。变到左边一条车道：d 从 0 到 3.5（车道宽 3.5 米）。
    duration_s：变道用几秒（T）。
    返回这一刻的 (d, 横向速度, 横向加速度, 横向 jerk)，单位 m、m/s、m/s²、m/s³。
    t_s < 0（还没开始）或 t_s > duration_s（已经变完）：位置停在起点 / 终点，速度、加速度、jerk 都是 0。

    公式（τ = t / T 走到第几成，Δ = d_end - d_start）：
        d        = d_start + Δ · (10τ³ - 15τ⁴ + 6τ⁵)
        横向速度 = Δ · (30τ² - 60τ³ + 30τ⁴) / T
        横向加速度 = Δ · (60τ - 180τ² + 120τ³) / T²
        横向 jerk = Δ · (60 - 360τ + 360τ²) / T³
    为什么是这几个数：起点、终点各要满足“位置、横向速度 = 0、横向加速度 = 0”三个条件，一共 6 个，
    五次多项式正好 6 个系数，解出来就是 10、-15、6（这条曲线也是“jerk 最小”的那条）。
    """
    delta = d_end_m - d_start_m                  # 一共要横着挪多少米
    tau = min(max(t_s / duration_s, 0.0), 1.0)    # 走到第几成：0 → 1
    d = d_start_m + delta * (10 * tau**3 - 15 * tau**4 + 6 * tau**5)
    if t_s < 0.0 or t_s > duration_s:
        return d, 0.0, 0.0, 0.0                       # 还没开始 / 已经变完：横向不动
    v = delta * (30 * tau**2 - 60 * tau**3 + 30 * tau**4) / duration_s
    a = delta * (60 * tau - 180 * tau**2 + 120 * tau**3) / duration_s**2
    j = delta * (60 - 360 * tau + 360 * tau**2) / duration_s**3
    return d, v, a, j

def frenet_to_xy(ref_xy: list[tuple[float, float]], s_m: float, d_m: float) -> tuple[float, float]:
    """Frenet (s, d) 换成地图上的 (x, y)（A7 第 3 步）。

    在系统里：第 2 步在 (s, d) 里画好变道曲线（路再弯，d 也只是 0 → 3.5），
    这个函数把每个 (s, d) 换回地图坐标，交给 Pure Pursuit 去跟。
    ref_xy：参考线（本车道中心线）上的一串点，按前进方向排，点要密（比如每 0.5 米一个）。
    s_m：沿参考线走了多远（米）；d_m：离参考线多远（米，往路的左边为正）。
    做法：沿参考线一段一段量长度，找到 s 落在哪一段；在这段上插值出参考点 (xr, yr) 和这段的朝向 θ；
          再从参考点往“路的左边”走 d 米（路的左边 = 朝向转 90°，方向是 (-sin θ, cos θ)）。
    s 超出参考线两头时，沿第一段 / 最后一段往外延长。
    """
    walked = 0.0              # 前面几段一共多长
    for k in range(len(ref_xy) - 1):
        (x0, y0), (x1, y1) = ref_xy[k], ref_xy[k + 1]
        seg = math.hypot(x1 - x0,y1 - y0)      # 这一段多长
        if walked + seg >= s_m or k == len(ref_xy) - 2:
            r = (s_m -walked) / seg  # 在这一段上走了几成（< 0 或 > 1 就是往外延长）
            xr = x0 + r * (x1 - x0)                   # 参考点：本车道中心线上，走了 s 米的地方
            yr = y0 + r * (y1 - y0)
            theta = math.atan2(y1 - y0, x1 - x0)      # 这一段路朝哪个方向
            return xr - d_m * math.sin(theta), yr + d_m * math.cos(theta)   # 往路的左边走 d 米
        walked += seg