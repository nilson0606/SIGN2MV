"""Job queue with three lanes.

* "gpu" lane: one job at a time. Everything that uses the graphics card's memory
  (separation, RVC, training, Whisper) goes here, so jobs never fight over it.
* "mv" lane: one MV render at a time. Rendering draws frames on the CPU and encodes
  with NVENC (no CUDA memory), so like the old MV studio it starts right away even
  while a model is training.
* "cpu" lane: a small number of jobs in parallel (downloads, conversions,
  key shifting, mixing).

Every job runs a worker program as a separate process (see workers.py for the
line protocol). Jobs report progress, can be cancelled, and have a timeout.
"""
from __future__ import annotations

import itertools
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .proc import ManagedProcess

LANES = {"gpu": 1, "mv": 1, "cpu": 2}
LOG_LINES = 3000
FINISHED = ("succeeded", "failed", "cancelled", "timeout")
MAX_FINISHED_KEPT = 200


@dataclass
class JobSpec:
    """What to run. `args` is the full command line of the worker process."""
    kind: str
    lane: str
    args: list[str]
    input: dict[str, Any] = field(default_factory=dict)
    timeout_s: float = 1800.0
    title: str = ""
    env: dict[str, str] | None = None
    cwd: str | None = None


@dataclass
class Job:
    id: str
    spec: JobSpec
    seq: int
    status: str = "queued"
    percent: float | None = None
    stage: str = ""
    message: str = ""
    result: Any = None
    error_code: str = ""
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    log_tail: list[str] = field(default_factory=list)
    # full log for the log viewer (stage changes, worker messages, program output), with a running
    # count so the page can fetch only new lines
    log: list[str] = field(default_factory=list)
    log_total: int = 0
    cancel_requested: bool = False

    def add_log(self, text: str) -> None:
        for part in str(text).replace("\r\n", "\n").split("\n"):
            part = part.split("\r")[-1].rstrip()   # progress bars redraw with \r: keep the last state
            if not part:
                continue
            self.log.append(time.strftime("%H:%M:%S ") + part[:500])
            self.log_total += 1
        del self.log[:-LOG_LINES]
    process: ManagedProcess | None = None

    def public(self, position: int | None) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.spec.kind,
            "lane": self.spec.lane,
            "title": self.spec.title,
            "status": self.status,
            "position": position,
            "percent": self.percent,
            "stage": self.stage,
            "message": self.message,
            "result": self.result,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "timeout_s": self.spec.timeout_s,
        }


class JobQueue:
    def __init__(self, lanes: dict[str, int] | None = None,
                 on_change: Callable[[], None] | None = None):
        self.lanes = dict(lanes or LANES)
        self._jobs: dict[str, Job] = {}
        self._seq = itertools.count(1)
        self._cv = threading.Condition()
        self._stopping = False
        self._on_change = on_change
        self._threads: list[threading.Thread] = []
        for lane, slots in self.lanes.items():
            for n in range(slots):
                t = threading.Thread(target=self._lane_loop, args=(lane,),
                                     name=f"lane-{lane}-{n}", daemon=True)
                t.start()
                self._threads.append(t)

    # ---------- public API ----------
    def submit(self, spec: JobSpec) -> Job:
        if spec.lane not in self.lanes:
            raise ValueError("unknown_lane")
        with self._cv:
            if self._stopping:
                raise RuntimeError("shutting_down")
            job = Job(id=uuid.uuid4().hex[:12], spec=spec, seq=next(self._seq))
            self._jobs[job.id] = job
            self._prune_locked()
            self._cv.notify_all()
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._cv:
            job = self._jobs.get(job_id)
            return job.public(self._position_locked(job)) if job else None

    def log(self, job_id: str, after: int = 0) -> dict[str, Any] | None:
        """Log lines after the first `after` ones: {"lines", "next", "status"}."""
        with self._cv:
            job = self._jobs.get(job_id)
            if not job:
                return None
            first = job.log_total - len(job.log)         # number of the oldest kept line
            start = max(0, after - first)
            return {"lines": job.log[start:], "next": job.log_total, "skipped": max(0, first - after),
                    "status": job.status}

    def list(self) -> list[dict[str, Any]]:
        with self._cv:
            jobs = sorted(self._jobs.values(), key=lambda j: j.seq)
            return [j.public(self._position_locked(j)) for j in jobs]

    def active(self) -> list[dict[str, Any]]:
        return [j for j in self.list() if j["status"] in ("queued", "running")]

    def cancel(self, job_id: str) -> bool:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None or job.status in FINISHED:
                return False
            job.cancel_requested = True
            if job.status == "queued":
                self._finish_locked(job, "cancelled")
            proc = job.process
        if proc is not None:
            proc.kill_tree()
        return True

    def clear_finished(self) -> int:
        """Forget finished jobs (the list on the Jobs page). Running and queued jobs stay."""
        with self._cv:
            done = [jid for jid, j in self._jobs.items() if j.status in FINISHED]
            for jid in done:
                self._jobs.pop(jid, None)
        self._changed()
        return len(done)

    def cancel_all(self) -> int:
        ids = [j["id"] for j in self.active()]
        return sum(1 for job_id in ids if self.cancel(job_id))

    def stop(self, wait_s: float = 10.0) -> None:
        """Cancel everything and stop the lane threads (used on shutdown)."""
        with self._cv:
            self._stopping = True
            self._cv.notify_all()
        self.cancel_all()
        deadline = time.time() + wait_s
        for t in self._threads:
            t.join(max(0.0, deadline - time.time()))

    # ---------- internals ----------
    def _position_locked(self, job: Job | None) -> int | None:
        if job is None or job.status != "queued":
            return None
        ahead = [j for j in self._jobs.values()
                 if j.spec.lane == job.spec.lane and j.status == "queued" and j.seq < job.seq]
        return len(ahead) + 1

    def _prune_locked(self) -> None:
        finished = sorted((j for j in self._jobs.values() if j.status in FINISHED),
                          key=lambda j: j.seq)
        for job in finished[:-MAX_FINISHED_KEPT] if len(finished) > MAX_FINISHED_KEPT else []:
            self._jobs.pop(job.id, None)

    def _changed(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def _finish_locked(self, job: Job, status: str, code: str = "", message: str = "") -> None:
        job.status = status
        job.finished_at = time.time()
        if code:
            job.error_code = code
        if message:
            job.error_message = message
        took = f" ({job.finished_at - job.started_at:.0f} s)" if job.started_at else ""
        job.add_log(("✔ " if status == "succeeded" else "■ ") + status + took + (f" — {code}" if code else ""))
        self._cv.notify_all()

    def _next_locked(self, lane: str) -> Job | None:
        queued = [j for j in self._jobs.values() if j.spec.lane == lane and j.status == "queued"]
        return min(queued, key=lambda j: j.seq) if queued else None

    def _lane_loop(self, lane: str) -> None:
        while True:
            with self._cv:
                job = self._next_locked(lane)
                while job is None and not self._stopping:
                    self._cv.wait(timeout=1.0)
                    job = self._next_locked(lane)
                if self._stopping:
                    return
                job.status = "running"
                job.started_at = time.time()
                job.add_log(f"▶ {job.spec.title}")
            self._changed()
            try:
                self._run(job)
            except Exception as exc:  # never let one job kill the lane
                with self._cv:
                    if job.status == "running":
                        self._finish_locked(job, "failed", "internal_error", str(exc))
            finally:
                if job.process is not None:
                    job.process.close()
                    job.process = None
            self._changed()

    def _run(self, job: Job) -> None:
        spec = job.spec
        payload = json.dumps(spec.input, ensure_ascii=False).encode("utf-8")
        try:
            proc = ManagedProcess(spec.args, env=spec.env, cwd=spec.cwd, stdin_data=payload)
        except OSError as exc:
            with self._cv:
                self._finish_locked(job, "failed", "worker_start_failed", str(exc))
            return
        with self._cv:
            job.process = proc
            cancelled_early = job.cancel_requested
        if cancelled_early:
            proc.kill_tree()

        timed_out = threading.Event()

        def watchdog() -> None:
            if proc.popen.poll() is None:
                timed_out.set()
                proc.kill_tree()

        timer = threading.Timer(spec.timeout_s, watchdog)
        timer.daemon = True
        timer.start()

        stderr_tail: list[str] = []

        def read_stderr() -> None:
            assert proc.popen.stderr is not None
            for raw in proc.popen.stderr:
                line = raw.decode("utf-8", "replace").rstrip()
                stderr_tail.append(line)
                del stderr_tail[:-40]
                with self._cv:
                    job.add_log(line)

        err_thread = threading.Thread(target=read_stderr, daemon=True)
        err_thread.start()

        final_result: Any = None
        reported_error: tuple[str, str] | None = None
        assert proc.popen.stdout is not None
        for raw in proc.popen.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                with self._cv:
                    job.log_tail.append(line)
                    del job.log_tail[:-40]
                    job.add_log(line)
                continue
            if not isinstance(msg, dict):
                continue
            mtype = msg.get("type")
            with self._cv:
                if mtype == "progress":
                    pct = msg.get("percent")
                    job.percent = None if pct is None else max(0.0, min(100.0, float(pct)))
                    stage = str(msg.get("stage", job.stage))[:80]
                    if stage and stage != job.stage:
                        job.add_log(f"▶ [{stage}] {str(msg.get('message', ''))[:200]}".rstrip())
                    job.stage = stage
                    job.message = str(msg.get("message", ""))[:300]
                elif mtype == "result":
                    final_result = msg.get("data")
                elif mtype == "error":
                    reported_error = (str(msg.get("code", "worker_error"))[:60],
                                      str(msg.get("message", ""))[:500])
                    job.add_log(f"✖ {reported_error[0]}: {reported_error[1]}")
                elif mtype == "log":
                    job.log_tail.append(str(msg.get("message", ""))[:300])
                    del job.log_tail[:-40]
                    job.add_log(str(msg.get("message", "")))
            self._changed()

        rc = proc.popen.wait()
        timer.cancel()
        err_thread.join(timeout=2.0)
        with self._cv:
            if job.cancel_requested:
                self._finish_locked(job, "cancelled")
            elif timed_out.is_set():
                self._finish_locked(job, "timeout", "timeout",
                                    f"stopped after {int(spec.timeout_s)} s")
            elif rc == 0 and reported_error is None:
                job.result = final_result
                job.percent = 100.0
                self._finish_locked(job, "succeeded")
            else:
                code, message = reported_error or ("worker_failed", "\n".join(stderr_tail[-10:]))
                self._finish_locked(job, "failed", code, message or f"exit code {rc}")
