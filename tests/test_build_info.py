"""The code date shown on the home page (app/BUILD.txt, filled in by git archive / GitHub's Download ZIP)."""
from __future__ import annotations

from app import build


def test_filled_in_file_is_used(tmp_path, monkeypatch):
    f = tmp_path / "BUILD.txt"
    f.write_text("2026-11-08 732cd72\n", encoding="utf-8")
    monkeypatch.setattr(build, "_FILE", f)
    assert build._read() == {"date": "2026-11-08", "commit": "732cd72"}


def test_placeholder_outside_git_is_unknown(tmp_path, monkeypatch):
    f = tmp_path / "BUILD.txt"
    f.write_text("$Format:%cs %h$\n", encoding="utf-8")
    monkeypatch.setattr(build, "_FILE", f)            # tmp_path is not a git checkout
    assert build._read() == {"date": None, "commit": None}


def test_status_reports_it(client):
    b = client.get("/api/system/status").json()["build"]
    assert set(b) == {"date", "commit"}


def _fake(head_sha: str, compare: dict | None = None, fail: bool = False):
    def fetch(path):
        if fail:
            raise OSError("offline")
        if path == "commits/main":
            return {"sha": head_sha, "commit": {"committer": {"date": "2026-11-09T11:00:00Z"}}}
        if compare is None:
            raise OSError("404")
        return compare
    return fetch


def test_update_check_states(monkeypatch):
    monkeypatch.setattr(build, "_cache", {"date": "2026-11-08", "commit": "abc1234"})
    assert build.check_update(_fake("abc1234ffff"))["state"] == "latest"
    r = build.check_update(_fake("def5678aaaa", {"status": "ahead", "ahead_by": 3}))
    assert r["state"] == "update" and r["behind"] == 3 and r["latest"] == {"commit": "def5678", "date": "2026-11-09"}
    assert build.check_update(_fake("def5678aaaa", {"status": "behind"}))["state"] == "ahead"
    assert build.check_update(_fake("def5678aaaa"))["state"] == "unknown"          # commit not on GitHub
    assert build.check_update(_fake("", fail=True))["state"] == "offline"
    monkeypatch.setattr(build, "_cache", {"date": None, "commit": None})
    assert build.check_update(_fake("def5678aaaa"))["state"] == "unknown"


def test_update_check_route(client, monkeypatch):
    monkeypatch.setattr(build, "_github", lambda path: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(build.check_update, "__defaults__", (build._github,))
    assert client.get("/api/system/update-check").json()["state"] == "offline"
