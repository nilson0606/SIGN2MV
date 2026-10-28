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


def _emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def progress(percent: float | None, stage: str = "", message: str = "") -> None:
    _emit({"type": "progress", "percent": percent, "stage": stage, "message": message})


def log(message: str) -> None:
    _emit({"type": "log", "message": message})


def result(data: Any) -> None:
    _emit({"type": "result", "data": data})


def fail(code: str, message: str = "", exit_code: int = 1) -> None:
    _emit({"type": "error", "code": code, "message": message})
    sys.exit(exit_code)
