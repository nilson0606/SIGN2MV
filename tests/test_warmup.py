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
    deadline = time.time() + 10   # wait for the line, not the file: it exists (empty) a moment before the write
    while time.time() < deadline and (not log.is_file() or "warm-up" not in log.read_text()):
        time.sleep(0.1)
    w.stop()
    assert "skipped (a graphics-card job is running)" in log.read_text()
    monkeypatch.setenv("SIGN2MV_NO_WARMUP", "1")
    assert not wm.Warmup(paths, lambda: False, log).start()
    assert not wm.Warmup(Paths(tmp_path / "empty"), lambda: False, log).start()   # nothing installed


def test_applio_plan_loads_only_libraries_and_names_what_failed(tmp_path):
    # Applio's own code checks the graphics card on import and stops while the card is hidden (11-05)
    assert "rvc" not in wm.PLAN["applio"] and "torch" in wm.PLAN["applio"]
    import subprocess
    r = subprocess.run([sys.executable, "-c", wm._import_all(("json", "no_such_module_xyz"))],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "not loaded: no_such_module_xyz: ModuleNotFoundError" in r.stderr
    assert "json" not in r.stderr


def test_a_log_line_with_a_broken_character_is_still_written(tmp_path):
    log = tmp_path / "jobs.log"
    w = wm.Warmup(Paths(tmp_path / "app"), lambda: False, log)
    w._note("warm-up applio: 1.0 s (exit 1: bad \ud83d)")
    assert "bad \\ud83d" in log.read_text(encoding="utf-8")
