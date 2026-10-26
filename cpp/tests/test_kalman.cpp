// KalmanCV 的单元测试。数字和 tests/test_tracking.py 里 A6 第 2 步那 5 个测试一样（都是手算的）。
// EXPECT_NEAR(a, b, 误差) 相当于 Python 的 np.allclose；TEST(组名, 测试名) 相当于 def test_xxx()。
#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>

#include "tracking.hpp"

TEST(KalmanCV, PredictMovesBySpeed) {
    // 猜：12.31 + (-1.81 × 0.1) = 12.129，速度不变
    KalmanCV kf(12.31, -1.81);
    kf.predict(0.1);
    EXPECT_NEAR(kf.x[0], 12.129, 1e-9);
    EXPECT_NEAR(kf.x[1], -1.81, 1e-9);
}

TEST(KalmanCV, PredictGrowsUncertainty) {
    // P = diag(0.01, 0.04)，q = 1，dt = 0.1：
    // F P Fᵀ = [[0.0104, 0.004], [0.004, 0.04]]；再加 Q = [[0.000025, 0.0005], [0.0005, 0.01]]
    KalmanCV kf(10.0, -2.0);
    kf.P[0][0] = 0.01;  kf.P[0][1] = 0.0;
    kf.P[1][0] = 0.0;   kf.P[1][1] = 0.04;
    kf.predict(0.1);
    EXPECT_NEAR(kf.P[0][0], 0.010425, 1e-9);
    EXPECT_NEAR(kf.P[0][1], 0.0045, 1e-9);
    EXPECT_NEAR(kf.P[1][0], 0.0045, 1e-9);
    EXPECT_NEAR(kf.P[1][1], 0.05, 1e-9);
}

TEST(KalmanCV, UpdateWhenMeasurementEqualsGuess) {
    // 量的正好等于猜的：估计不动，但更有把握了（P[0][0] 变小）
    KalmanCV kf(10.0, -2.0);
    kf.P[0][0] = 0.04;  kf.P[0][1] = 0.02;
    kf.P[1][0] = 0.02;  kf.P[1][1] = 0.1;
    kf.update(10.0);
    EXPECT_NEAR(kf.x[0], 10.0, 1e-9);
    EXPECT_NEAR(kf.x[1], -2.0, 1e-9);
    EXPECT_LT(kf.P[0][0], 0.04);
}

TEST(KalmanCV, UpdateHandNumbers) {
    // y = 11 - 10 = 1；S = 0.04 + 0.04 = 0.08；K = [0.04, 0.02] / 0.08 = [0.5, 0.25]
    // x = [10 + 0.5, -2 + 0.25]；P = P - outer(K, P 的第 0 行) = [[0.02, 0.01], [0.01, 0.095]]
    KalmanCV kf(10.0, -2.0, 1.0, 25.0, 1.0, 0.04);
    kf.P[0][0] = 0.04;  kf.P[0][1] = 0.02;
    kf.P[1][0] = 0.02;  kf.P[1][1] = 0.1;
    kf.update(11.0);
    EXPECT_NEAR(kf.x[0], 10.5, 1e-9);
    EXPECT_NEAR(kf.x[1], -1.75, 1e-9);
    EXPECT_NEAR(kf.P[0][0], 0.02, 1e-9);
    EXPECT_NEAR(kf.P[0][1], 0.01, 1e-9);
    EXPECT_NEAR(kf.P[1][0], 0.01, 1e-9);
    EXPECT_NEAR(kf.P[1][1], 0.095, 1e-9);
}

TEST(KalmanCV, TracksClosingSpeedSameAsPython) {
    // 和 Python 第 5 个测试同一组数据：前车每秒近 2 米，测距噪声 = numpy default_rng(0).normal(0, 0.2, 51)（保留 6 位）。
    // 1 秒以后速度误差最大 0.35 m/s——和 Python 版算出来的一模一样
    const double noise[51] = {
        0.025146, -0.026421, 0.128085, 0.020980, -0.107134, 0.072319, 0.260800, 0.189416, -0.140747, -0.253084,
        -0.124655, 0.008265, -0.465006, -0.043758, -0.249182, -0.146453, -0.108852, -0.063260, 0.082326, 0.208503,
        -0.025707, 0.273293, -0.133039, 0.070302, 0.180694, 0.018802, -0.148700, -0.184345, -0.091545, 0.044039,
        -0.201924, -0.041835, -0.031845, 0.108169, 0.042932, 0.071075, -0.130766, -0.025923, 0.156795, 0.298686,
        -0.251813, 0.302785, 0.269175, 0.156262, 0.052891, -0.062785, 0.291604, 0.392052, 0.360327, 0.263021,
        0.071476};
    KalmanCV kf(20.0 + noise[0]);
    double worst = 0.0;
    for (int k = 1; k <= 50; ++k) {
        double z = 20.0 - 2.0 * (0.1 * k) + noise[k];
        kf.predict(0.1);
        kf.update(z);
        if (k >= 10) {
            worst = std::max(worst, std::abs(kf.x[1] + 2.0));
        }
    }
    EXPECT_LT(worst, 0.5);
    EXPECT_NEAR(worst, 0.350865, 1e-5);
}
