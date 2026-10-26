// C++ 版跟踪器（E 块）：和 ads/tracking.py 一一对应，测试数字也和 Python 的一样。
//
// .hpp（头文件）= 目录：写清楚有哪些类、哪些函数、参数是什么；
// .cpp（源文件）= 正文：每个函数具体怎么做（src/kalman.cpp）。
#pragma once

// 匀速卡尔曼滤波（一维，沿车道方向）：跟踪前车的距离 d 和速度 v。对应 Python 的 KalmanCV。
//
// x[0] = d：前车离我多少米；x[1] = v：前车相对我的速度（m/s，负数 = 在靠近）。
// P[i][j]：有多没把握。P[0][0] = 距离的方差，P[1][1] = 速度的方差，P[0][1] = P[1][0] = 联动格。
// q：前车加减速有多猛（越大，每猜一步越没把握）。
// r：雷达量距离的方差：误差 0.2 米 → r = 0.04。
class KalmanCV {
public:
    // 参数和默认值都和 Python 一样：KalmanCV(d0, v0=0, p0_d=1, p0_v=25, q=1, r=0.04)
    KalmanCV(double d0, double v0 = 0.0, double p0_d = 1.0, double p0_v = 25.0,
             double q_in = 1.0, double r_in = 0.04);

    void predict(double dt);   // 猜：按现在的速度往前推 dt 秒，没把握变大
    void update(double z);     // 合：用雷达这一帧量到的距离 z 改准

    double x[2];       // [d, v]
    double P[2][2];    // 2 行 2 列
    double q;
    double r;
};
