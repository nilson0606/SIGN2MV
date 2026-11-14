"""Temporary diagnosis switch file for the app window (app/browser.py, backlog #22)."""
from __future__ import annotations

from app import browser
from app.paths import get_paths


def test_only_listed_switches_are_taken(root, monkeypatch):
    paths = get_paths()
    assert browser.window_flags(paths) == []                       # no file
    paths.config.mkdir(parents=True, exist_ok=True)
    f = paths.config / "window_flags.txt"
    f.write_text("", encoding="utf-8")
    assert browser.window_flags(paths) == []                       # empty file
    f.write_text("\ufeff  --disable-direct-composition-video-overlays  \n# a note\n--remote-debugging-port=9222\n"
                 "--user-data-dir=C:\\x\n--disable-accelerated-video-decode --disable-gpu\n", encoding="utf-8")
    assert browser.window_flags(paths) == ["--disable-direct-composition-video-overlays"]
    f.write_text("--disable-gpu\r\n--disable-accelerated-video-decode\r\n", encoding="utf-8")
    assert browser.window_flags(paths) == ["--disable-accelerated-video-decode", "--disable-gpu"]


def test_switches_reach_the_window_command(root, monkeypatch):
    paths = get_paths()
    paths.config.mkdir(parents=True, exist_ok=True)
    (paths.config / "window_flags.txt").write_text("--disable-direct-composition-video-overlays\n", encoding="utf-8")
    seen = []
    monkeypatch.delenv("SIGN2MV_NO_BROWSER", raising=False)
    monkeypatch.setattr(browser.os, "name", "nt")
    monkeypatch.setattr(browser, "find_edge", lambda: "msedge.exe")
    monkeypatch.setattr(browser.subprocess, "Popen", lambda args, **kw: seen.append(args))
    browser.open_app_window(paths, "http://127.0.0.1:9700/")
    assert seen and seen[0][-1] == "--disable-direct-composition-video-overlays" and seen[0][1] == "--app=http://127.0.0.1:9700/"
    (paths.config / "window_flags.txt").write_text("", encoding="utf-8")
    browser.open_app_window(paths, "http://127.0.0.1:9700/")
    assert not any(a.startswith("--disable-direct") for a in seen[1])
