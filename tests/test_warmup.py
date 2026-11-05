"""The file-cache warm-up imports each environment's modules in a background child and times it."""
from __future__ import annotations

import sys
import time

from app import warmup as wm
from app.paths import Paths


def test_warmup_runs_each_environment_and_logs(tmp_path, monkeypatch):
    root = tmp_path / "app"
    paths = Paths(root)
    for name in ("applio", "engine"):              # stand-in environments: this Python
        exe = paths.env_python(name)
        exe.parent.mkdir(parents=True)
        exe.symlink_to(sys.executable)
    paths.applio.mkdir(parents=True)
    paths.workers.mkdir(parents=True)
    monkeypatch.setattr(wm, "PLAN", {"applio": "import json", "engine": "raise SystemExit('boom')"})
    monkeypatch.setattr(wm, "FIRST_DELAY_S", 0.0)
    log = tmp_path / "jobs.log"
    busy = {"v": False}
    w = wm.Warmup(paths, lambda: busy["v"], log)
    assert w.start()
    deadline = time.time() + 30
    while time.time() < deadline and (not log.is_file() or log.read_text().count("warm-up") < 2):
        time.sleep(0.2)
    w.stop()
    text = log.read_text()
    assert "warm-up applio:" in text and " s" in text
    assert "warm-up engine:" in text and "exit 1: boom" in text


def test_warmup_skips_while_the_gpu_is_busy_and_can_be_turned_off(tmp_path, monkeypatch):
    root = tmp_path / "app"
    paths = Paths(root)
    exe = paths.env_python("applio")
    exe.parent.mkdir(parents=True)
    exe.symlink_to(sys.executable)
    paths.applio.mkdir(parents=True)
    monkeypatch.setattr(wm, "PLAN", {"applio": "pass"})
    monkeypatch.setattr(wm, "FIRST_DELAY_S", 0.0)
    log = tmp_path / "jobs.log"
    w = wm.Warmup(paths, lambda: True, log)
    assert w.start()
    deadline = time.time() + 10
    while time.time() < deadline and not log.is_file():
        time.sleep(0.1)
    w.stop()
    assert "skipped (a graphics-card job is running)" in log.read_text()
    monkeypatch.setenv("SIGN2MV_NO_WARMUP", "1")
    assert not wm.Warmup(paths, lambda: False, log).start()
    assert not wm.Warmup(Paths(tmp_path / "empty"), lambda: False, log).start()   # nothing installed
