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
