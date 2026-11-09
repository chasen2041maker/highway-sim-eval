"""B2：边考边存 + 断点续跑（batch/resume.py）。"""

import json

import pytest

from batch.jobs import Job
from batch.resume import job_key, load_done
from scenarios.cut_in import CutIn


def test_job_key_same_card_same_key():
    """任务单一样，身份证就一样；种子不一样，就是另一个任务。"""
    a = Job(question=3, scenario=CutIn(), comes_in=True, predict_s=0.5, seed=3)
    b = Job(question=3, scenario=CutIn(), comes_in=True, predict_s=0.5, seed=3)
    c = Job(question=3, scenario=CutIn(), comes_in=True, predict_s=0.5, seed=4)
    assert job_key(a) == job_key(b)
    assert job_key(a) != job_key(c)


def test_load_done_only_ok_and_skips_half_line(tmp_path):
    """日志里只有 ok 的算交卷（timeout 下次重考）；断电时只写了一半的最后一行跳过。"""
    log = tmp_path / "log.jsonl"
    log.write_text(json.dumps({"job_key": "A", "status": "ok"}) + "\n"
                   + json.dumps({"job_key": "B", "status": "timeout"}) + "\n"
                   + '{"job_key": "C", "sta', encoding="utf-8")
    assert list(load_done(log)) == ["A"]
    assert load_done(tmp_path / "none.jsonl") == {}


def test_old_results_from_other_code_do_not_count(tmp_path):
    """代码指纹对不上（考生的代码改过）的旧结果不算数，免得新旧结果混在一张表里。"""
    log = tmp_path / "log.jsonl"
    log.write_text(json.dumps({"job_key": "A", "status": "ok", "code": "old"}) + "\n"
                   + json.dumps({"job_key": "B", "status": "ok", "code": "new"}) + "\n", encoding="utf-8")
    assert list(load_done(log, code="new")) == ["B"]
    assert list(load_done(log)) == ["A", "B"]


def test_code_fingerprint_is_stable():
    """同一份代码算两次，指纹一样，12 位。"""
    from batch.resume import code_fingerprint
    assert code_fingerprint() == code_fingerprint()
    assert len(code_fingerprint()) == 12


pytest.importorskip("highway_env")

from batch.jobs import run_jobs_safe  # noqa: E402
from batch.resume import PowerCut, run_jobs_resumable  # noqa: E402
from examples.b_eval.b2_batch import make_jobs, make_questions  # noqa: E402


def test_resume_after_power_cut(tmp_path):
    """12 个任务，考到第 5 张卷时假装断电：日志里留下 5 个；再跑只考剩下的 7 个，整张表和不断电一口气跑的一样。"""
    jobs = make_jobs(make_questions())[78:90]
    log = tmp_path / "log.jsonl"
    with pytest.raises(PowerCut):
        run_jobs_resumable(jobs, log, workers=2, timeout_s=60, stop_after=5)
    assert len(load_done(log)) == 5
    rows, n_run = run_jobs_resumable(jobs, log, workers=2, timeout_s=60)
    assert n_run == 7
    assert rows == run_jobs_safe(jobs, workers=2, timeout_s=60)
