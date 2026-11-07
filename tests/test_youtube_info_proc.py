"""Looking up a YouTube link runs yt-dlp as a process tree; a failure answers 502."""
from __future__ import annotations

import sys


def test_failed_lookup_answers_502(client, monkeypatch):
    monkeypatch.setattr(client.app.state.ctx, "python", lambda name: sys.executable)   # no yt_dlp here: exits 1
    r = client.get("/api/youtube/info", params={"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa"})
    assert r.status_code == 502 and r.json()["error"] == "youtube_info_failed"


def test_lookup_reads_the_answer(client, monkeypatch, tmp_path):
    import os

    from app import childenv
    fake = tmp_path / "fake" / "yt_dlp"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("")
    (fake / "__main__.py").write_text('import json\nprint(json.dumps({"id": "aaaaaaaaaaa", "title": "Song"}))\n')
    monkeypatch.setattr(client.app.state.ctx, "python", lambda name: sys.executable)
    monkeypatch.setattr(childenv, "child_env", lambda paths: {**os.environ, "PYTHONPATH": str(tmp_path / "fake")})
    r = client.get("/api/youtube/info", params={"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa"})
    assert r.status_code == 200 and r.json()["title"] == "Song"
