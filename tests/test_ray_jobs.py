"""B2：Ray 跑同一批任务（batch/ray_jobs.py）。没装 Ray 或模拟器的电脑（比如 CI）会跳过。"""

import sys

import pytest

pytest.importorskip("ray")
pytest.importorskip("highway_env")

from batch.jobs import run_jobs  # noqa: E402
from batch.ray_jobs import run_jobs_ray, run_jobs_ray_actors  # noqa: E402
from examples.b_eval.b2_batch import make_jobs, make_questions  # noqa: E402

JOBS = make_jobs(make_questions())[78:90]          # 第 14、15 题的 12 个任务


def test_ray_tasks_same_as_one_by_one():
    """task：Ray 2 个工人跑出来的，和一个一个跑的一模一样，顺序也一样。"""
    assert run_jobs_ray(JOBS, workers=2) == run_jobs(JOBS, workers=1)


def test_ray_actors_same_and_take_turns():
    """actor：2 个常驻考场轮流考 12 道，各考 6 道；结果和一个一个跑的一模一样。"""
    rows, counts = run_jobs_ray_actors(JOBS, workers=2)
    assert rows == run_jobs(JOBS, workers=1)
    assert counts == [6, 6]


def test_ray_actor_pool_same_order():
    """谁空谁领：2 个考场考 12 道，第 0 题假装慢 1 秒；结果仍按任务顺序、和一个一个跑的一样；两个考场加起来 12 道。"""
    extra = [1.0] + [0.0] * (len(JOBS) - 1)
    rows, counts = run_jobs_ray_actors(JOBS, workers=2, extra_s=extra, pull=True)
    assert rows == run_jobs(JOBS, workers=1)
    assert sum(counts) == 12


@pytest.mark.skipif(sys.platform == "win32", reason="Windows 上 Ray（试验性支持）重开崩掉的 actor 时本机集群会失联（11-09 实测），等 Linux / WSL2 再测")
def test_ray_actor_crash_and_restart(tmp_path):
    """第 4 个任务把考场弄崩（只崩一次）：不重开，整批报错；自动重开 1 次，结果和一个一个跑的一样。"""
    mark = tmp_path / "crash.mark"
    with pytest.raises(Exception):
        run_jobs_ray_actors(JOBS, workers=2, pull=True, crash_at=3, crash_mark=str(mark), max_restarts=0)
    mark.unlink()
    rows, _ = run_jobs_ray_actors(JOBS, workers=2, pull=True, crash_at=3, crash_mark=str(mark), max_restarts=1)
    assert rows == run_jobs(JOBS, workers=1)
