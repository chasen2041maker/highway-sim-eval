// C++ 版跟踪器（E 块）：和 ads/tracking.py 一一对应，测试数字也和 Python 的一样。
//
// .hpp（头文件）= 目录：写清楚有哪些类、哪些函数、参数是什么；
// .cpp（源文件）= 正文：每个函数具体怎么做（src/kalman.cpp）。
#pragma once

#include <utility>   // std::pair
#include <vector>    // std::vector：长度可变的数组，相当于 Python 的 list

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

// 一个位置 (x, y)，米。相当于 Python 里 [x, y] 那一行。用的时候写 XY{20.0, 0.0}，读的时候写 p.x、p.y。
struct XY {
    double x;
    double y;
};

// 配对（A6 第 3 步）：这一帧雷达的框，各归哪条轨迹。对应 Python 的 match_tracks。
//
// pred_xy：每条轨迹猜的位置，第 i 个 = 第 i 条轨迹（T 个）。
// det_xy：雷达这一帧的框中心，顺序是乱的（D 个）。
// gate_m：门槛（米），距离超过它的不算配上。
// 返回：[(i, j), ...]，第 i 条轨迹配第 j 个框；按 i 从小到大排好。没有轨迹或没有框时返回空的。
// 规则和 Python 一样：一对一；所有一对一的配法里挑总距离最小的；挑出来以后超过 gate_m 的扔掉。
//
// const std::vector<XY>& = 只读借用（引用 &），不复制一份；const = 函数里不许改它。
std::vector<std::pair<int, int>> match_tracks(const std::vector<XY>& pred_xy,
                                              const std::vector<XY>& det_xy,
                                              double gate_m = 2.0);
