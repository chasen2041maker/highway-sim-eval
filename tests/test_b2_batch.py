"""B2 第 1 步：任务单（Job）和批量跑（examples/b_eval/b2_batch.py）。

一个任务 = 题目参数 + 考生的旋钮 + 随机种子，打包好不能改；批量跑的结果要和 B1 随机新题一模一样（2026-11-04 核对）。
第 3 步坏任务（11-04）：卡死的等到超时记 timeout、不重试；报错的重试 1 次还崩记 error；偶发的重试后 ok；其余照常，整批 13 秒收回。
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


def test_save_csv_when_first_job_failed(tmp_path):
    """第 1 个任务卡死：它没有结果那几列。表头要按所有行合起来，不能只看第一行，否则整张表存不下来（11-09 发现）。"""
    import csv

    from examples.b_eval.b2_batch import all_columns, save_csv
    failed = {"question": 1, "status": "timeout", "error": "等了 60 秒没交卷", "attempts": 1}
    ok = {"question": 2, "missed": False, "false_brake": True, "status": "ok", "error": "", "attempts": 1}
    assert all_columns([failed, ok]) == ["question", "status", "error", "attempts", "missed", "false_brake"]
    assert all_columns([ok, failed]) == ["question", "missed", "false_brake", "status", "error", "attempts"]
    path = tmp_path / "first_failed.csv"
    save_csv([failed, ok], path)
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["status"] == "timeout" and rows[0]["missed"] == ""     # 卡死的那行：结果格子空着
    assert rows[1]["false_brake"] == "True"


pytest.importorskip("highway_env")

from batch.jobs import run_job, run_jobs, run_jobs_safe  # noqa: E402
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


def test_bad_jobs_do_not_sink_the_batch():
    """卡死 → timeout（不重试）；每次都崩 → error（试 2 次）；偶发 → 重试后 ok；正常的照常。"""
    from dataclasses import replace

    from examples.b_eval.b2_faults import FLAKY_MARK, misbehaving_run_job
    FLAKY_MARK.parent.mkdir(exist_ok=True)
    FLAKY_MARK.unlink(missing_ok=True)
    good = make_jobs(make_questions())[:2]
    bad = [replace(good[0], question=q) for q in (901, 902, 903)]
    rows = run_jobs_safe([good[0], *bad, good[1]], workers=3, timeout_s=3, retries=1, fn=misbehaving_run_job)
    got = [(r["question"], r["status"], r["attempts"]) for r in rows]
    assert got == [(1, "ok", 1), (901, "timeout", 1), (902, "error", 2), (903, "ok", 2), (1, "ok", 1)]
    assert rows[2]["error"] == "RuntimeError: 考场崩了"
    assert rows[1]["gap_m"] == good[0].scenario.gap_m          # 失败的任务也留下了任务单上的格子
    FLAKY_MARK.unlink(missing_ok=True)
