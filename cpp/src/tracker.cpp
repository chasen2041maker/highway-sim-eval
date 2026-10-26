// Track 和 MultiTracker 的正文。对照 ads/tracking.py 的 Track、MultiTracker。
#include <utility>
#include <vector>

#include "tracking.hpp"

// ---------- Track ----------

// 冒号后面是“初始化列表”：建纸条的同时把每个成员建好。
// KalmanCV 没有“空的”建法（必须给 d0），所以 kx、ky 只能在这里建，不能等到大括号里再赋值。
Track::Track(int track_id, XY xy) : id(track_id), kx(xy.x), ky(xy.y), misses(0) {}

void Track::predict(double dt) {
    kx.predict(dt);
    ky.predict(dt);
}

void Track::update(XY xy) {
    kx.update(xy.x);
    ky.update(xy.y);
    misses = 0;
}

XY Track::xy() const {
    return XY{kx.x[0], ky.x[0]};   // 两个卡尔曼各自的位置 x[0]
}

// ---------- MultiTracker ----------

MultiTracker::MultiTracker(double gate_m_in, int max_misses_in)
    : gate_m(gate_m_in), max_misses(max_misses_in), next_id(1) {}

// Python：
//     for t in self.tracks:                                        ① 猜
//         t.predict(dt)
//     pre = np.array([t.xy for t in self.tracks])                  ② 配
//     pairs = match_tracks(pre, det_xy, self.gate_m)
//     for i, j in pairs:                                           ③ 改准
//         self.tracks[i].update(det_xy[j]); matched_t.add(i); matched_d.add(j)
//     keep = []                                                    ④ misses / 扔
//     for i, t in enumerate(self.tracks):
//         if i not in matched_t: t.misses += 1
//         if t.misses <= self.max_misses: keep.append(t)
//     self.tracks = keep
//     for j in range(len(det_xy)):                                 ⑤ 新编号
//         if j not in matched_d:
//             self.tracks.append(Track(self.next_id, det_xy[j])); self.next_id += 1
//     return self.tracks
const std::vector<Track>& MultiTracker::step(const std::vector<XY>& det_xy, double dt) {
    // ① 猜：每张纸条往前推一步。注意 Track& 的 &：不加 & 改的是复印件
    for (Track& t : tracks){
        t.predict(dt);
    }

    // ② 配：把每张纸条猜的位置排成一列，交给第 2 步写的 match_tracks
    std::vector<XY> pred;
    for (const Track& t : tracks){
        pred.push_back(t.xy());
    }
    std::vector<std::pair<int, int>> pairs = match_tracks(pred, det_xy, gate_m);

    // ③ 改准：配上的纸条用配给它的框 update；顺便记下谁配上了
    std::vector<bool> matched_t(tracks.size(), false);  // 第 i 张纸条配上了吗
    std::vector<bool> matched_d(det_xy.size(), false);  // 第 j 个框被认领了吗
    for (const auto& [i, j] : pairs){
        tracks[i].update(det_xy[j]);
        matched_t[i] = true;
        matched_d[j] = true;
    }

    // ④ 没配上的纸条 misses + 1；没超过上限的留下
    std::vector<Track> keep;
    for (size_t i = 0; i < tracks.size(); ++i){
        if (!matched_t[i]){
            tracks[i].misses += 1;
        }
        if (tracks[i].misses <= max_misses){
            keep.push_back(tracks[i]);
        }
    }
    tracks = keep;

    // ⑤ 没人认领的框：按下标从小到大，每个发一个新编号
    for (size_t j = 0; j < det_xy.size(); ++j){
        if (!matched_d[j]){
            tracks.push_back(Track(next_id, det_xy[j]));
            next_id += 1;
        }
    }



    return tracks;
}
