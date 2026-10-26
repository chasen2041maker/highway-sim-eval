// match_tracks 的单元测试。前 5 个和 tests/test_tracking.py 里 A6 第 3 步的配对测试一样。
#include <gtest/gtest.h>

#include <utility>
#include <vector>

#include "tracking.hpp"

using Pairs = std::vector<std::pair<int, int>>;   // 起个短名字

TEST(MatchTracks, ShuffledBoxes) {
    // 两条轨迹猜在 0 米、10 米；框的顺序反过来给：框 0 在 10.2，框 1 在 0.1
    Pairs pairs = match_tracks({XY{0.0, 0.0}, XY{10.0, 0.0}}, {XY{10.2, 0.0}, XY{0.1, 0.0}});
    EXPECT_EQ(pairs, (Pairs{{0, 1}, {1, 0}}));
}

TEST(MatchTracks, GateDropsFarPair) {
    // 第 2 条轨迹离唯一剩下的框 3 米，超过门槛 2 米，不算配上
    Pairs pairs = match_tracks({XY{0.0, 0.0}, XY{10.0, 0.0}}, {XY{0.3, 0.0}, XY{13.0, 0.0}}, 2.0);
    EXPECT_EQ(pairs, (Pairs{{0, 0}}));
}

TEST(MatchTracks, Empty) {
    EXPECT_TRUE(match_tracks({}, {XY{1.0, 1.0}}).empty());
    EXPECT_TRUE(match_tracks({XY{1.0, 1.0}}, {}).empty());
}

TEST(MatchTracks, TotalDistanceNotGreedy) {
    // 圈 A (0, 0)、圈 B (2.2, 0)；框 p (1, 0)、框 q (-1.1, 0)
    // 贪心先拿最近的 A-p (1.0)，B 只剩 q (3.3)，合计 4.3；总距离最小是 A-q (1.1) + B-p (1.2) = 2.3
    Pairs pairs = match_tracks({XY{0.0, 0.0}, XY{2.2, 0.0}}, {XY{1.0, 0.0}, XY{-1.1, 0.0}}, 5.0);
    EXPECT_EQ(pairs, (Pairs{{0, 1}, {1, 0}}));
}

TEST(MatchTracks, Frame19FromTheExplainer) {
    // 动画 ① 那一帧（1.9 秒）：1 号↔框 2、2 号↔框 1、3 号↔框 0
    std::vector<XY> pred = {XY{16.096, -0.033}, XY{13.715, 3.552}, XY{24.468, -3.425}};
    std::vector<XY> det = {XY{24.222, -3.439}, XY{14.032, 3.551}, XY{15.946, 0.116}};
    EXPECT_EQ(match_tracks(pred, det), (Pairs{{0, 2}, {1, 1}, {2, 0}}));
}

TEST(MatchTracks, MoreTracksThanBoxes) {
    // C++ 版新加：3 条轨迹、只有 1 个框（另外两辆被挡住）——框归离它最近的 1 号轨迹
    Pairs pairs = match_tracks({XY{0.0, 0.0}, XY{10.0, 0.0}, XY{20.0, 0.0}}, {XY{10.3, 0.0}});
    EXPECT_EQ(pairs, (Pairs{{1, 0}}));
}
