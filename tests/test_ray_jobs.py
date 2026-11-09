"""B2：Ray 跑同一批任务（batch/ray_jobs.py）。没装 Ray 或模拟器的电脑（比如 CI）会跳过。"""

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
