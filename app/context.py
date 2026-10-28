"""Shared server context: paths, job queue, library, worker launching."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

from . import settings as settings_mod
from .childenv import child_env
from .jobs import JobQueue, JobSpec
from .library import Library
from .paths import Paths


class Context:
    def __init__(self, paths: Paths, jobs: JobQueue):
        self.paths = paths
        self.jobs = jobs
        self._lock = threading.Lock()
        # song_id -> set of job ids that touch the song (prevents deleting a busy song)
        self._song_jobs: dict[str, set[str]] = {}
        # (song_id, dedupe key) -> job id (avoid running the same work twice at once)
        self._dedupe: dict[tuple[str, str], str] = {}

    # ---------- library ----------
    def library(self) -> Library:
        return Library(Path(settings_mod.load(self.paths)["library_dir"]))

    def settings(self) -> dict[str, Any]:
        return settings_mod.load(self.paths)

    # ---------- pythons ----------
    def python(self, env_name: str) -> str:
        override = os.environ.get(f"SIGN2MV_{env_name.upper()}_PYTHON")
        if override:
            return override
        exe = self.paths.env_python(env_name)
        return str(exe) if exe.exists() else sys.executable

    # ---------- jobs ----------
    def submit(self, *, kind: str, lane: str, script: str, input: dict[str, Any], title: str,
               song_id: str | None = None, timeout_s: float = 1800.0, env_name: str = "engine",
               dedupe: str | None = None, extra_env: dict[str, str] | None = None,
               cwd: Path | None = None, args: list[str] | None = None) -> dict[str, Any]:
        with self._lock:
            if song_id and dedupe:
                existing = self._dedupe.get((song_id, dedupe))
                if existing:
                    job = self.jobs.get(existing)
                    if job and job["status"] in ("queued", "running"):
                        return job
            cmd = args or [self.python(env_name), "-u", str(self.paths.workers / script)]
            spec = JobSpec(kind=kind, lane=lane, args=cmd, input=input, timeout_s=timeout_s,
                           title=title[:120], env=child_env(self.paths, extra_env),
                           cwd=str(cwd or self.paths.workers))
            job = self.jobs.submit(spec)
            if song_id:
                self._song_jobs.setdefault(song_id, set()).add(job.id)
                if dedupe:
                    self._dedupe[(song_id, dedupe)] = job.id
            return self.jobs.get(job.id)

    def song_busy(self, song_id: str) -> bool:
        with self._lock:
            ids = self._song_jobs.get(song_id, set())
        for jid in list(ids):
            job = self.jobs.get(jid)
            if job and job["status"] in ("queued", "running"):
                return True
        return False

    def pending_job(self, song_id: str, dedupe: str) -> dict[str, Any] | None:
        with self._lock:
            jid = self._dedupe.get((song_id, dedupe))
        job = self.jobs.get(jid) if jid else None
        return job if job and job["status"] in ("queued", "running") else None
