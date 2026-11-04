"""B2 第 1 步：任务单（Job）和批量跑（examples/b_eval/b2_batch.py）。

一个任务 = 题目参数 + 考生的旋钮 + 随机种子，打包好不能改；批量跑的结果要和 B1 随机新题一模一样（2026-11-04 核对）。
第 2 步进程池：笔记本（16 个逻辑核）1 / 4 / 8 / 16 个进程 88 / 26 / 22 / 16 秒，结果逐行一模一样；
快不到核数那么多倍：每个进程要自己启动、导入考场，任务单和结果要来回传，240 个任务太少，这些固定开销占了大头。
"""

import dataclasses

import pytest

from batch.jobs import Job
from scenarios.cut_in import CutIn


def test_job_defaults_and_frozen():
    job = Job(question=14, scenario=CutIn(), comes_in=True, predict_s=1.0)
    assert job.accel is False and job.confirm_frames == 1 and job.noise_y_m == 0.0 and job.seed == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        job.predict_s = 0.5                       # 任务单封了口，不能改


pytest.importorskip("highway_env")

from batch.jobs import run_job, run_jobs  # noqa: E402
from examples.b_eval.b2_batch import make_jobs, make_questions  # noqa: E402


def test_jobs_count_and_order():
    """最里层的循环变得最快：先换预测方法，再换预测秒数，最后才换题号。"""
    jobs = make_jobs(make_questions())
    assert len(jobs) == 40 * 3 * 2
    first = [(j.question, j.predict_s, j.accel) for j in jobs[:8]]
    assert first == [(1, 0.0, False), (1, 0.0, True), (1, 0.5, False), (1, 0.5, True),
                     (1, 1.0, False), (1, 1.0, True), (2, 0.0, False), (2, 0.0, True)]
    q14 = jobs[83]
    assert (q14.question, q14.predict_s, q14.accel, q14.seed) == (14, 1.0, True, 14)
    assert q14.scenario.gap_m == 5.2 and q14.comes_in


def test_run_job_row_for_question_14():
    """第 14 题：匀加速往前看 0.5 秒还是漏刹，往前看 1.0 秒救回来（和 B1 一样）。"""
    jobs = make_jobs(make_questions())
    late, saved = run_job(jobs[81]), run_job(jobs[83])     # 题 14、0.5 秒、匀加速 / 题 14、1.0 秒、匀加速
    assert (late["predict_s"], late["accel"], late["missed"]) == (0.5, True, True)
    assert (saved["predict_s"], saved["accel"], saved["missed"], saved["crashed"]) == (1.0, True, False, False)
    assert saved["gap_m"] == 5.2 and saved["false_brake"] is False   # 题目参数也展开成了列


def test_parallel_same_as_sequential():
    """进程池跑出来的行和一个一个跑的一模一样，顺序也一样（任务单写死了题目、旋钮、种子；pool.map 按任务顺序收结果）。"""
    jobs = make_jobs(make_questions())[78:90]          # 第 14、15 题的 12 个任务
    assert run_jobs(jobs, workers=2) == run_jobs(jobs, workers=1)
