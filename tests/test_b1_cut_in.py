"""B1 第 2 步：邻车加塞的回归测试。

数字来自 2026-11-01 晚 → 11-02 实跑（笔记本 Windows 和云端 Linux 一样）。考生的判断：
  车身边（中心点减半个车宽）过了我的车道线 = 前车；预测 predict_s 秒：正往我这边挪、照现在的横向速度
  predict_s 秒内车身边会压线，也提前当前车。
五道题：1 陪跑（不该刹）、2 / 3 切入 10 / 5 米（该刹）、4 压线（车身进来 0.8 米，该刹）、5 靠线（车身始终在线外，不该刹）。
不预测：5 米切入撞了；预测 0.5 秒：五道全对；预测 1.0 秒：第 5 题误刹 -8。
"""

import math

import pytest

pytest.importorskip("highway_env")

from examples.b_eval.b1_cut_in import BANK, run  # noqa: E402
from examples.b_eval.b1_highway_brake import idm_driver  # noqa: E402
from examples.b_eval.b1_scenarios import judge  # noqa: E402

INF = math.inf
# 预测秒数 -> 每道题 (撞没撞, 最小车距, 判定, 刹没刹)；最小车距 inf = 它的中心没进我的车道
EXPECTED = {
    0.0: [(False, INF, "过", False), (False, 4.18, "险过", True), (True, None, "不过", True), (False, INF, "险过", True), (False, INF, "过", False)],
    0.5: [(False, INF, "过", False), (False, 5.68, "险过", True), (False, 0.68, "险过", True), (False, INF, "险过", True), (False, INF, "过", False)],
    1.0: [(False, INF, "过", False), (False, 6.18, "险过", True), (False, 1.18, "险过", True), (False, INF, "险过", True), (False, INF, "险过", True)],
}


@pytest.mark.parametrize("predict_s,n", [(p, n) for p in EXPECTED for n in range(len(BANK))])
def test_bank(predict_s, n):
    s = run(BANK[n], predict_s)
    crashed, min_gap, verdict, braked = EXPECTED[predict_s][n]
    assert bool(s["crashed"]) is crashed
    if min_gap is INF:
        assert math.isinf(s["min_gap_m"])
    elif min_gap is not None:
        assert s["min_gap_m"] == pytest.approx(min_gap, abs=0.01)
    assert judge(s) == verdict
    assert bool(s["hardest_brake_mps2"] < -0.5) is braked


EGO = [1, 0.0, 4.0, 15.0, 0.0]
EMPTY = [0, 0.0, 0.0, 0.0, 0.0]


def test_side_lane_car_is_not_the_lead():
    """旁边车道更近的车不算前车：第 1 行在旁边车道（y = -4），第 2 行才是我车道上的前车。"""
    side = [1, 15.0, -4.0, -5.0, 0.0]
    mine = [1, 35.0, 0.0, -5.0, 0.0]
    assert idm_driver([EGO, side, mine, EMPTY, EMPTY]) == pytest.approx(idm_driver([EGO, mine, EMPTY, EMPTY, EMPTY]))
    assert idm_driver([EGO, side, EMPTY, EMPTY, EMPTY]) == pytest.approx(idm_driver([EGO, EMPTY, EMPTY, EMPTY, EMPTY]))


def test_body_edge_counts_not_centre():
    """中心离我车道中心 2.5 米（中心在线外 0.5），车身边 1.5 米（压进来 0.5）：算前车。"""
    half_in = [1, 15.0, -2.5, -5.0, 0.0]
    free = idm_driver([EGO, EMPTY, EMPTY, EMPTY, EMPTY])
    assert idm_driver([EGO, half_in, EMPTY, EMPTY, EMPTY]) < free - 1.0


def test_prediction_threshold():
    """车身边离线 0.5 米、每秒朝我挪 1 米：0.5 秒后压线。预测 0.4 秒不管它，预测 0.6 秒提前当前车。"""
    coming = [1, 15.0, -3.5, -5.0, 1.0]
    free = idm_driver([EGO, EMPTY, EMPTY, EMPTY, EMPTY])
    assert idm_driver([EGO, coming, EMPTY, EMPTY, EMPTY], predict_s=0.4) == pytest.approx(free)
    assert idm_driver([EGO, coming, EMPTY, EMPTY, EMPTY], predict_s=0.6) < free - 1.0


def test_will_cross_constant_acceleration():
    """11-03：匀加速外推。第 14 题第 0.2 秒：离线 0.98 米、朝我 0.25 m/s、加速度 1.8。"""
    from examples.b_eval.b1_highway_brake import will_cross
    assert not will_cross(0.98, 0.25, 0.0, 1.0)        # 只看速度：1 秒挪 0.25 米，到不了
    assert will_cross(0.98, 0.25, 1.8, 1.0)            # 算上加速度：0.25 + ½·1.8 = 1.15 米，够到线
    assert will_cross(0.2, 1.0, -2.0, 1.5)             # 在减速：0.5 秒后横向停下，最多挪 0.25 米
    assert not will_cross(0.3, 1.0, -2.0, 1.5)         # （不截到停下那一刻的话，1.5 秒会算成往回挪 0.75 米）
    assert not will_cross(0.1, 0.0, -1.0, 1.0)         # 已经不朝我挪、还在往回减：不会压线
