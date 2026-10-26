// KalmanCV 的正文。对照 ads/tracking.py 的 KalmanCV。
#include "tracking.hpp"

// 建好时：x = [d0, v0]，P = diag(p0_d, p0_v)
KalmanCV::KalmanCV(double d0, double v0, double p0_d, double p0_v, double q_in, double r_in) {
    x[0] = d0;
    x[1] = v0;
    P[0][0] = p0_d;  P[0][1] = 0.0;
    P[1][0] = 0.0;   P[1][1] = p0_v;
    q = q_in;
    r = r_in;
}

// Python：
//     F = [[1, dt], [0, 1]]
//     Q = q * [[dt^4/4, dt^3/2], [dt^3/2, dt^2]]
//     self.x = F @ self.x
//     self.P = F @ self.P @ F.T + Q
void KalmanCV::predict(double dt) {
    // 在这里写（C++ 没有 numpy 的 @，矩阵乘法展开成一个一个格子）
    x[0] = x[0] + x[1] * dt;      // 距离 = 距离 + 速度 × dt；速度 x[1] 不变

    P[0][0] = P[0][0] + dt * (P[0][1] + P[1][0]) + dt * dt * P[1][1] + q * dt * dt * dt * dt / 4;
    P[0][1] = P[0][1] + dt * P[1][1] + q * dt * dt * dt / 2;
    P[1][0] = P[1][0] + dt * P[1][1] + q * dt * dt * dt / 2;
    P[1][1] = P[1][1] + q * dt * dt;
}

// Python：
//     y = z - self.x[0]
//     S = self.P[0, 0] + self.r
//     K = self.P[:, 0] / S
//     self.x = self.x + K * y
//     self.P = self.P - np.outer(K, self.P[0, :])
void KalmanCV::update(double z) {
    double y = z - x[0];          // 量的 - 猜的
    double S = P[0][0] + r;       // 一共多没把握
    double k0 = P[0][0] / S;      // K：距离信雷达几成
    double k1 = P[1][0] / S;      //    速度跟着改几成（靠 P 的联动格）

    x[0] = x[0] + k0 * y;
    x[1] = x[1] + k1 * y;

    double p00 = P[0][0];         // 先把第 0 行的旧值存下来
    double p01 = P[0][1];
    P[0][0] = P[0][0] - k0 * p00;
    P[0][1] = P[0][1] - k0 * p01;
    P[1][0] = P[1][0] - k1 * p00;
    P[1][1] = P[1][1] - k1 * p01;
}