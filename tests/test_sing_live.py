"""RMVPE scoring worker (app/sing_live.py): a worker that stops answering must not hold the lock forever."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

from app import sing_live
from app.paths import Paths

# answers "ready", then either echoes every piece back or (HANG) never answers
FAKE = r'''
import json, os, sys
print(json.dumps({"ready": True, "device": "fake"}), flush=True)
for line in sys.stdin:
    if os.environ.get("FAKE_HANG") == "1":
        continue
    print(json.dumps({"id": json.loads(line)["id"], "f0": [0.0], "hop": 0.01}), flush=True)
'''


def _pitch(tmp_path, monkeypatch, hang: bool):
    workers = tmp_path / "workers"
    workers.mkdir()
    (workers / "sing_live_pitch.py").write_text(FAKE, encoding="utf-8")
    monkeypatch.setenv("FAKE_HANG", "1" if hang else "0")
    monkeypatch.setattr(sing_live, "PIECE_TIMEOUT_S", 1.5)
    class TestPaths(Paths):
        @property
        def workers(self) -> Path:
            return workers
    ctx = SimpleNamespace(paths=TestPaths(tmp_path), python=lambda name: sys.executable)
    return sing_live.LivePitch(ctx)


def test_live_pitch_answers(tmp_path, monkeypatch):
    lp = _pitch(tmp_path, monkeypatch, hang=False)
    try:
        assert lp.pitch(b"\0\0" * 160, 16000)["f0"] == [0.0]
    finally:
        lp.stop()


def test_live_pitch_stuck_worker_is_stopped(tmp_path, monkeypatch):
    lp = _pitch(tmp_path, monkeypatch, hang=True)
    try:
        t0 = time.monotonic()
        assert lp.pitch(b"\0\0" * 160, 16000) == {"error": "live_pitch_timeout"}
        assert 1.0 < time.monotonic() - t0 < 10
        assert not lp._lock.locked()          # the next piece is not stuck behind it
        monkeypatch.setenv("FAKE_HANG", "0")    # the next piece starts a new worker, which answers
        assert lp.pitch(b"\0\0" * 160, 16000)["f0"] == [0.0]
    finally:
        lp.stop()


def test_worker_stuck_while_loading_is_stopped(tmp_path, monkeypatch):
    lp = _pitch(tmp_path, monkeypatch, hang=False)
    (tmp_path / "workers" / "sing_live_pitch.py").write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(lp, "LOAD_TIMEOUT_S", 0.8)
    try:
        lp.warm()
        stuck = lp._proc
        before = lp._last_used
        time.sleep(0.2)
        lp.warm()                                   # asking again while loading does not reset the idle clock
        assert lp._last_used == before
        time.sleep(1.2)
        assert lp._proc is None and stuck.popen.poll() is not None
        assert lp.state()["error"] == "live_pitch_load_timeout"
    finally:
        lp.stop()
