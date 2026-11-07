"""A worker that has not read its input yet (still loading its libraries) can be cancelled and times out."""
from __future__ import annotations

import sys
import time

from app.jobs import JobQueue, JobSpec

NOT_READING = "import time\ntime.sleep(30)\n"


def _spec(tmp_path, timeout_s: float) -> JobSpec:
    w = tmp_path / "slow_start.py"
    w.write_text(NOT_READING, encoding="utf-8")
    return JobSpec(kind="demo", lane="gpu", args=[sys.executable, str(w)], input={"blob": "x" * 1_000_000},
                   timeout_s=timeout_s, title="slow start", cwd=str(tmp_path))


def _wait(q: JobQueue, job_id: str, seconds: float) -> str:
    deadline = time.time() + seconds
    while time.time() < deadline:
        status = q.get(job_id)["status"]
        if status not in ("queued", "running"):
            return status
        time.sleep(0.05)
    return q.get(job_id)["status"]


def test_timeout_covers_the_start(tmp_path):
    q = JobQueue({"gpu": 1})
    try:
        job = q.submit(_spec(tmp_path, 0.5))
        assert _wait(q, job.id, 5) == "timeout"
    finally:
        q.stop()


def test_cancel_reaches_a_worker_still_starting(tmp_path):
    q = JobQueue({"gpu": 1})
    try:
        job = q.submit(_spec(tmp_path, 60))
        time.sleep(0.5)
        q.cancel(job.id)
        assert _wait(q, job.id, 5) == "cancelled"
    finally:
        q.stop()
