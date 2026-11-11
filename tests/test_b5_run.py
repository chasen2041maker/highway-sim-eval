"""B5 第 1 步：两个版本考的必须是同一批题、同样的噪声，只有考生设置不一样，才能一道一道对比。"""

from examples.b_eval.b5_run import ROADS, VERSIONS, version_jobs


def test_two_versions_take_the_same_exam():
    v1, v2 = version_jobs("v1", n=6), version_jobs("v2", n=6)
    assert len(v1) == len(v2) == 6 * len(ROADS)
    for a, b in zip(v1, v2):
        assert (a.question, a.scenario, a.comes_in, a.noise_y_m, a.delay_s, a.seed) == \
               (b.question, b.scenario, b.comes_in, b.noise_y_m, b.delay_s, b.seed)
        assert (b.predict_s, b.confirm_frames, b.accel) == tuple(VERSIONS["v2"].values())
