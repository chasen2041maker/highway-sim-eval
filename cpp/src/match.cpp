// match_tracks 的正文。对照 ads/tracking.py 的 match_tracks。
#include <algorithm>   // std::next_permutation、std::sort
#include <cmath>       // std::hypot
#include <limits>      // 无穷大

#include "tracking.hpp"

std::vector<std::pair<int, int>> match_tracks(const std::vector<XY>& pred_xy,
                                              const std::vector<XY>& det_xy,
                                              double gate_m) {
    std::vector<std::pair<int, int>> pairs;   // 结果，先是空的
    if (pred_xy.empty() || det_xy.empty()) {
        return pairs;
    }
    const int T = static_cast<int>(pred_xy.size());   // 几条轨迹（size() 相当于 len()）
    const int D = static_cast<int>(det_xy.size());    // 几个框

    // ① 距离表：T 行 D 列，dist[i][j] = 第 i 条轨迹猜的位置到第 j 个框的距离（你写）
    //    Python：
    //        for i in range(T):
    //            for j in range(D):
    //                dx = pred_xy[i][0] - det_xy[j][0]
    //                dy = pred_xy[i][1] - det_xy[j][1]
    //                dist[i, j] = np.hypot(dx, dy)
    std::vector<std::vector<double>> dist(T, std::vector<double>(D, 0.0));   // T 行 D 列，先全填 0
    // 在这里写两层 for 循环
    for (int i = 0; i < T; ++i){
        for (int j =0; j < D; ++j){
            double dx = pred_xy[i].x - det_xy[j].x;
            double dy = pred_xy[i].y - det_xy[j].y;
            dist[i][j] = std::hypot(dx, dy);
        }
    }


    // ② 全试一遍（助手写）：所有一对一的配法里挑总距离最小的。
    //    车少的时候（8 个以内）把所有排法试一遍，结果和匈牙利一样；车多了要用匈牙利，O(n³)。
    //    做法：把“多的那一边”的下标排成 perm，每一种排法 = 一种一对一配法；
    //    std::next_permutation 把 perm 换成下一种排法，全换完了返回 false。
    //    a ? b : c 是一行版的 if-else：a 成立取 b，不成立取 c。
    const bool rows_fewer = (T <= D);          // 轨迹比框少（或一样多）？
    const int n_few = rows_fewer ? T : D;
    const int n_many = rows_fewer ? D : T;
    std::vector<int> perm(n_many);
    for (int k = 0; k < n_many; ++k) {
        perm[k] = k;                            // 0, 1, 2, ……：从最小的排法开始
    }
    double best_total = std::numeric_limits<double>::infinity();
    std::vector<int> best_perm;
    do {
        double total = 0.0;
        for (int s = 0; s < n_few; ++s) {
            total += rows_fewer ? dist[s][perm[s]] : dist[perm[s]][s];
        }
        if (total < best_total) {
            best_total = total;
            best_perm = perm;
        }
    } while (std::next_permutation(perm.begin(), perm.end()));

    std::vector<int> rows;   // 和 scipy 的 rows、cols 一样：两个一样长，同一列（同一个下标）是一对
    std::vector<int> cols;
    for (int s = 0; s < n_few; ++s) {
        rows.push_back(rows_fewer ? s : best_perm[s]);
        cols.push_back(rows_fewer ? best_perm[s] : s);
    }

    // ③ 门槛：超过 gate_m 的那对扔掉，剩下的放进 pairs（你写）
    //    Python：
    //        for i, j in zip(rows, cols):
    //            if dist[i, j] <= gate_m:
    //                pairs.append((int(i), int(j)))
    //    C++ 没有 zip：用一个下标 k 从 0 走到 rows.size()，i = rows[k]，j = cols[k]
    // 在这里写

    for(size_t k = 0; k < rows.size(); ++k){
        int i = rows[k];
        int j = cols[k];
        if (dist[i][j] <= gate_m){
            pairs.push_back({i, j});
        };
    }


    std::sort(pairs.begin(), pairs.end());   // 按 i 从小到大排好（和 Python 的 sorted(pairs) 一样）
    return pairs;
}
