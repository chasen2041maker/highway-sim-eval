// 第 0 步：确认 C++ 编译器能用。
// 顺便用 A6 卡尔曼动画里 4.0 秒那一帧算一次 predict：12.31 + (-1.81 * 0.1) = 12.129
#include <iostream>

int main() {
    double d = 12.31;     // 上一帧估计的车距（米）
    double v = -1.81;     // 上一帧估计的速度（m/s，负数 = 越来越近）
    double dt = 0.1;      // 一帧 0.1 秒

    double d_guess = d + v * dt;   // predict：按现在的速度往前推一帧

    std::cout << "C++ works. predict: " << d_guess << " m" << std::endl;
    return 0;
}
