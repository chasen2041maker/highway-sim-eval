import numpy as np

from ads.tracking import diff_speed


def test_diff_speed_constant_closing():
    # 每 0.1 秒近 0.2 米 = 以 2 m/s 接近，4 帧距离 → 3 个速度，都是 -2
    v = diff_speed(np.array([20.0, 19.8, 19.6, 19.4]), 0.1)
    assert v.shape == (3,)
    assert np.allclose(v, [-2.0, -2.0, -2.0])


def test_diff_speed_one_noisy_frame():
    # 第 2 帧多测了 0.3 米：它前后两个速度一个 +3、一个 -3（各偏 3 m/s），噪声被 ÷ 0.1 放大 10 倍
    v = diff_speed(np.array([20.0, 20.3, 20.0]), 0.1)
    assert np.allclose(v, [3.0, -3.0])
