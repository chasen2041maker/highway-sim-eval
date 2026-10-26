// Track / MultiTracker 的单元测试。前 8 个和 tests/test_tracking.py 里 A6 第 3 步的一样；
// 最后 2 个让 C++ 版跑同一段假路况，逐帧和 Python 版对答案（数据在 scene_data.hpp，由 make_scene_data.py 生成）。
#include <gtest/gtest.h>

#include <algorithm>
#include <map>
#include <set>
#include <vector>

#include "scene_data.hpp"
#include "tracking.hpp"

namespace {

std::vector<int> ids_of(const std::vector<Track>& tracks) {
    std::vector<int> ids;
    for (const Track& t : tracks) {
        ids.push_back(t.id);
    }
    return ids;
}

}  // namespace

TEST(Track, StartsAtBox) {
    Track t(7, XY{20.0, 3.5});
    EXPECT_EQ(t.id, 7);
    EXPECT_EQ(t.misses, 0);
    EXPECT_NEAR(t.xy().x, 20.0, 1e-9);
    EXPECT_NEAR(t.xy().y, 3.5, 1e-9);
}

TEST(Track, PredictMovesBothAxes) {
    // 速度先手动设好：x 方向每秒近 2 米、y 方向每秒往左 1 米 → 0.1 秒后在 (19.8, 0.1)
    Track t(1, XY{20.0, 0.0});
    t.kx.x[1] = -2.0;
    t.ky.x[1] = 1.0;
    t.predict(0.1);
    EXPECT_NEAR(t.xy().x, 19.8, 1e-9);
    EXPECT_NEAR(t.xy().y, 0.1, 1e-9);
}

TEST(Track, UpdatePullsTowardBoxAndClearsMisses) {
    Track t(1, XY{20.0, 0.0});
    t.misses = 3;
    t.update(XY{20.4, -0.4});
    EXPECT_EQ(t.misses, 0);
    EXPECT_GT(t.xy().x, 20.0);   // 往框那边挪了，但不会一步到位
    EXPECT_LT(t.xy().x, 20.4);
    EXPECT_LT(t.xy().y, 0.0);
    EXPECT_GT(t.xy().y, -0.4);
}

TEST(MultiTracker, FirstFrameEveryBoxGetsANewId) {
    MultiTracker mt;
    const std::vector<Track>& tracks = mt.step({XY{20.0, 0.0}, XY{12.0, 3.5}});
    ASSERT_EQ(ids_of(tracks), (std::vector<int>{1, 2}));
    EXPECT_NEAR(tracks[0].xy().x, 20.0, 1e-9);   // 1 号 = 第 0 个框
}

TEST(MultiTracker, ShuffledBoxesKeepTheirIds) {
    MultiTracker mt;
    mt.step({XY{20.0, 0.0}, XY{12.0, 3.5}});
    const std::vector<Track>& tracks = mt.step({XY{12.1, 3.5}, XY{19.8, 0.0}});   // 第二帧框的顺序反过来
    std::map<int, XY> where;
    for (const Track& t : tracks) {
        where[t.id] = t.xy();
    }
    ASSERT_EQ(where.size(), 2u);
    EXPECT_GT(where[1].x, 19.0);   // 1 号还是 20 米那辆
    EXPECT_LT(where[2].x, 13.0);   // 2 号还是 12 米那辆
}

TEST(MultiTracker, HiddenCarKeptThenDropped) {
    MultiTracker mt(2.0, 3);
    mt.step({XY{20.0, 0.0}});
    for (int k = 0; k < 3; ++k) {
        mt.step({});
    }
    ASSERT_EQ(ids_of(mt.tracks), (std::vector<int>{1}));   // 连着 3 帧没看到：还留着，只猜
    EXPECT_EQ(mt.tracks[0].misses, 3);
    mt.step({});
    EXPECT_TRUE(mt.tracks.empty());                         // 第 4 帧：超过 3，扔掉
}

TEST(MultiTracker, FarBoxGetsNewIdAndOldTrackMisses) {
    MultiTracker mt;
    mt.step({XY{20.0, 0.0}});
    const std::vector<Track>& tracks = mt.step({XY{8.0, -6.0}});   // 护栏误检：离 1 号 13 米多
    ASSERT_EQ(ids_of(tracks), (std::vector<int>{1, 2}));
    EXPECT_EQ(tracks[0].misses, 1);
    EXPECT_EQ(tracks[1].misses, 0);
}

TEST(MultiTracker, IdsAreNeverReused) {
    MultiTracker mt(2.0, 0);
    mt.step({XY{20.0, 0.0}});
    mt.step({});                                            // 1 号没配上，超过 0 帧，扔掉
    const std::vector<Track>& tracks = mt.step({XY{20.0, 0.0}});
    EXPECT_EQ(ids_of(tracks), (std::vector<int>{2}));      // 1 号不回收
}

// 跑整段假路况，逐帧把 C++ 手里的纸条（编号、位置）和 Python 版的比。
template <size_t N>
void expect_same_as_python(int max_misses, const TrackRow (&python)[N]) {
    MultiTracker mt(2.0, max_misses);
    size_t row = 0;   // 现在比到 Python 表的第几行
    for (int k = 0; k < kSceneFrames; ++k) {
        std::vector<XY> det;
        for (const DetRow& d : kSceneDets) {
            if (d.frame == k) {
                det.push_back(XY{d.x, d.y});
            }
        }
        for (const Track& t : mt.step(det)) {
            ASSERT_LT(row, N) << "C++ 第 " << k << " 帧的纸条比 Python 多";
            const TrackRow& p = python[row];
            ASSERT_EQ(p.frame, k) << "第 " << k << " 帧纸条张数和 Python 不一样";
            EXPECT_EQ(t.id, p.id) << "第 " << k << " 帧";
            EXPECT_NEAR(t.xy().x, p.x, 1e-9) << "第 " << k << " 帧 " << t.id << " 号";
            EXPECT_NEAR(t.xy().y, p.y, 1e-9) << "第 " << k << " 帧 " << t.id << " 号";
            ++row;
        }
    }
    EXPECT_EQ(row, N) << "C++ 的纸条比 Python 少";
}

TEST(MultiTracker, WholeSceneSameAsPythonMaxMisses10) {
    // 留 10 帧：1、2、3 号到底，护栏鬼影 4 号 3.5–4.5 秒
    expect_same_as_python(10, kPythonTracksMaxMisses10);
}

TEST(MultiTracker, WholeSceneSameAsPythonMaxMisses3) {
    // 留 3 帧：右车道 3 号 2.3 秒被扔、2.5 秒回来变 4 号，护栏鬼影 5 号
    expect_same_as_python(3, kPythonTracksMaxMisses3);
}
