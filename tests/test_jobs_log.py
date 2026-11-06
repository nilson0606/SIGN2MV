"""Writing logs/jobs.log must never stop the queue (11-06 review, item 1)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from app.jobs import JobQueue, JobSpec

WORKERS = Path(__file__).resolve().parent.parent / "workers"


def _spec(title: str) -> JobSpec:
    return JobSpec(kind="demo", lane="gpu", args=[sys.executable, str(WORKERS / "demo_job.py")],
                   input={"seconds": 0.3}, timeout_s=30, title=title, cwd=str(WORKERS))


def _wait(q: JobQueue, job_id: str, seconds: float) -> str:
    deadline = time.time() + seconds
    while time.time() < deadline:
        status = q.get(job_id)["status"]
        if status not in ("queued", "running"):
            return status
        time.sleep(0.1)
    return q.get(job_id)["status"]


def test_a_title_with_a_broken_character_does_not_stall_the_lane(tmp_path):
    q = JobQueue({"gpu": 1})
    q.event_log = tmp_path / "jobs.log"
    try:
        broken = q.submit(_spec("half an emoji \ud83d"))     # an unpaired surrogate cannot be written as UTF-8
        after = q.submit(_spec("next song"))
        assert _wait(q, broken.id, 20) == "succeeded"
        assert _wait(q, after.id, 20) == "succeeded"           # the lane went on to the next job
    finally:
        q.stop()
    text = q.event_log.read_text(encoding="utf-8")
    assert "half an emoji \\ud83d: succeeded" in text and "next song: succeeded" in text


def test_an_unwritable_log_does_not_stall_the_lane(tmp_path):
    q = JobQueue({"gpu": 1})
    q.event_log = tmp_path / "missing-folder" / "jobs.log"
    try:
        job = q.submit(_spec("x"))
        assert _wait(q, job.id, 20) == "succeeded"
    finally:
        q.stop()
