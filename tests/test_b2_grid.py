"""B2 第 4 步：多旋钮网格（examples/b_eval/b2_grid.py）。

五个旋钮排列组合 = 64 组：路况（噪声 × 延迟，工程师选不了）4 种 × 考生设置（往前看 × 确认帧数 × 匀速 / 匀加速）16 种。
每道题 × 64 组 = 64 个任务，噪声种子 = 题号：同一道题换旋钮时每一帧抖得一模一样，比较才公平。
笔记本 16 个进程试跑 50 道（3,200 个任务）134 秒，平均每个任务 0.042 秒（240 个任务时 0.067 秒：任务多了，开进程的固定开销被摊薄），
照这个速度 1000 道（64,000 个任务）约 45 分钟（2026-11-04）。
"""

import pytest

pytest.importorskip("highway_env")

from batch.jobs import run_job, run_jobs_safe  # noqa: E402
from examples.b_eval.b2_grid import make_jobs, make_knob_sets, make_questions  # noqa: E402


def test_knob_sets_count_and_order():
    """最里层（匀速 / 匀加速）变得最快，最外层（噪声）前 32 组都是 0.0，第 33 组才变。"""
    ks = make_knob_sets()
    assert len(ks) == 64
    assert ks[0] == {"noise_y_m": 0.0, "delay_s": 0.0, "predict_s": 0.0, "confirm_frames": 1, "accel": False}
    assert ks[1]["accel"] is True and ks[1]["predict_s"] == 0.0
    assert ks[6] == {"noise_y_m": 0.0, "delay_s": 0.0, "predict_s": 0.5, "confirm_frames": 3, "accel": False}   # 第 7 列
    assert [k["delay_s"] for k in (ks[15], ks[16], ks[31], ks[32])] == [0.0, 0.3, 0.3, 0.0]
    assert all(k["noise_y_m"] == 0.0 for k in ks[:32]) and all(k["noise_y_m"] == 0.2 for k in ks[32:])


def test_questions_alternate_and_trial_is_prefix():
    """会进来、不进来交替出；50 道试跑的题就是 1000 道的前 50 道；新种子 1，不是 B1 那 40 道。"""
    q50, q1000 = make_questions(50), make_questions(1000)
    assert [ci for _, ci in q50[:6]] == [True, False, True, False, True, False]
    assert q1000[:50] == q50
    assert sum(1 for _, ci in q1000 if ci) == 500
    sc8 = q50[7][0]                                        # 动画「任务单与种子」里的第 8 题
    assert (sc8.gap_m, sc8.cut_speed_mps, sc8.cut_time_s, sc8.cut_depth_m) == (14.8, 10.0, 1.7, 0.44)


def test_jobs_seed_is_question_number():
    """3 道题 × 64 组 = 192 个任务；第 2 题的 64 个任务种子都是 2；第 87 个任务 = 第 2 题、只有延迟、往前看 0.5 · 确认 3 帧 · 匀速。"""
    jobs = make_jobs(make_questions(3), make_knob_sets())
    assert len(jobs) == 192
    assert {j.seed for j in jobs[64:128]} == {2}
    j = jobs[86]
    assert (j.question, j.noise_y_m, j.delay_s, j.predict_s, j.confirm_frames, j.accel) == (2, 0.0, 0.3, 0.5, 3, False)


def test_question_8_same_seed_is_a_fair_comparison():
    """第 8 题（不进来）、噪声 0.2：种子 8 时往前看 0.5 不刹、1.0 误刹；确认 3 帧滤掉；1.0 换种子 1008 也不刹（只换骰子结果就变）。"""
    jobs = make_jobs(make_questions(8), make_knob_sets())
    by_knobs = {}
    for j in jobs:
        if j.question == 8:
            by_knobs[(j.noise_y_m, j.delay_s, j.predict_s, j.confirm_frames, j.accel)] = j
    look_05 = run_job(by_knobs[(0.2, 0.0, 0.5, 1, False)])
    look_10 = run_job(by_knobs[(0.2, 0.0, 1.0, 1, False)])
    confirm_3 = run_job(by_knobs[(0.2, 0.0, 1.0, 3, False)])
    assert (look_05["false_brake"], look_10["false_brake"], confirm_3["false_brake"]) == (False, True, False)
    from dataclasses import replace
    other_dice = run_job(replace(by_knobs[(0.2, 0.0, 1.0, 1, False)], seed=1008))
    assert other_dice["false_brake"] is False


def test_progress_lines(capsys):
    """progress_every = 2：收回第 2、4 个时各打印一行；默认 0 不打印（以前的调用不受影响）。"""
    jobs = make_jobs(make_questions(1), make_knob_sets())[:4]
    rows = run_jobs_safe(jobs, workers=2, progress_every=2)
    out = capsys.readouterr().out
    assert "收回 2 / 4 个" in out and "收回 4 / 4 个" in out
    assert [r["status"] for r in rows] == ["ok"] * 4
    run_jobs_safe(jobs[:2], workers=2)
    assert "收回" not in capsys.readouterr().out
