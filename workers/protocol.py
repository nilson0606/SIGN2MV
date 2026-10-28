"""Helpers every worker uses to talk to the SIGN2MV server.

Protocol (one JSON object per line on stdout):
  {"type": "progress", "percent": 0-100 or null, "stage": "...", "message": "..."}
  {"type": "log", "message": "..."}
  {"type": "result", "data": {...}}
  {"type": "error", "code": "english_code", "message": "details"}
The job input arrives as one JSON document on stdin. Exit code 0 means success.
Workers must not print anything else to stdout; use stderr for free text.
"""
from __future__ import annotations

import json
import sys
import threading
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def read_input() -> dict[str, Any]:
    data = sys.stdin.buffer.read()
    if not data.strip():
        return {}
    value = json.loads(data.decode("utf-8"))
    return value if isinstance(value, dict) else {}


_lock = threading.Lock()   # heartbeat threads emit too
_OUT = sys.stdout          # the real stdout, even while a worker redirects sys.stdout to stderr


def _emit(obj: dict[str, Any]) -> None:
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with _lock:
        _OUT.write(line)
        _OUT.flush()


class Heartbeat:
    """While a long call without its own progress runs, repeat the current progress every
    few seconds with the elapsed time appended, so the page shows it is still working."""

    def __init__(self, percent: float | None, stage: str, message: str = "", every: float = 3.0):
        self.percent, self.stage, self.message, self.every = percent, stage, message, every
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        import time
        start = time.time()
        while not self._stop.wait(self.every):
            s = int(time.time() - start)
            text = f"{self.message} · {s // 60}:{s % 60:02d}" if self.message else f"{s // 60}:{s % 60:02d}"
            progress(self.percent, self.stage, text)

    def __enter__(self) -> "Heartbeat":
        progress(self.percent, self.stage, self.message)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


def progress(percent: float | None, stage: str = "", message: str = "") -> None:
    _emit({"type": "progress", "percent": percent, "stage": stage, "message": message})


def log(message: str) -> None:
    _emit({"type": "log", "message": message})


def result(data: Any) -> None:
    _emit({"type": "result", "data": data})


def fail(code: str, message: str = "", exit_code: int = 1) -> None:
    _emit({"type": "error", "code": code, "message": message})
    sys.exit(exit_code)
