"""A YouTube song whose picture did not arrive: the import says so, and the picture alone can be fetched
again without touching the audio (workers/import_media.fetch_youtube_video)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from conftest import wait_job

# a stand-in for yt-dlp: writes a short audio or video file where "-o" says; the video fails while
# the file named by FAKE_YT_VIDEO_FAIL exists
FAKE = r'''
import os, subprocess, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
fmt = args[args.index("-f") + 1]
ff = ["ffmpeg", "-y", "-v", "error"]
if fmt.startswith("bestaudio"):
    subprocess.run(ff + ["-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:a", "aac", out.replace("%(ext)s", "m4a")], check=True)
    open(out.replace(".%(ext)s", ".info.json"), "w", encoding="utf-8").write('{"title": "Fake Song", "uploader": "Somebody"}')
else:
    if os.path.exists(os.environ.get("FAKE_YT_VIDEO_FAIL", "")):
        print("ERROR: unable to download video data: Connection reset by peer")
        sys.exit(1)
    subprocess.run(ff + ["-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=4", "-c:v", "libx264", "-preset", "ultrafast",
                         "-pix_fmt", "yuv420p", out.replace("%(ext)s", "mp4")], check=True)
'''
URL = "https://www.youtube.com/watch?v=aaaaaaaaaaa"


def _setup(client, monkeypatch, tmp_path) -> Path:
    fake = tmp_path / "fake" / "yt_dlp"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("")
    (fake / "__main__.py").write_text(FAKE, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "fake"))
    monkeypatch.setattr(client.app.state.ctx, "python", lambda name: sys.executable)
    flag = tmp_path / "video_fails"
    monkeypatch.setenv("FAKE_YT_VIDEO_FAIL", str(flag))
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")), raising=False)
    return flag


def _import(client, root, flag: Path, fail: bool) -> tuple[str, Path, dict]:
    flag.write_text("x") if fail else flag.unlink(missing_ok=True)
    sid = client.post("/api/songs", json={"title": "yt"}).json()["song_id"]
    job = wait_job(client, client.post(f"/api/songs/{sid}/import/youtube", json={"url": URL}).json()["id"])
    assert job["status"] == "succeeded", job
    sd = next(p for p in root.rglob(sid) if (p / "song.json").is_file())
    return sid, sd, job


def _rec(sd: Path) -> dict:
    return json.loads((sd / "source" / "source.json").read_text(encoding="utf-8"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_import_without_picture_says_so_and_the_picture_can_be_fetched_again(client, root, monkeypatch, tmp_path):
    flag = _setup(client, monkeypatch, tmp_path)
    sid, sd, job = _import(client, root, flag, fail=True)
    rec = _rec(sd)
    assert rec["video"] is None and rec["video_missing"] is True and job["result"]["video_missing"] is True
    audio = _sha(sd / "source" / "audio.wav")
    # still failing: the song stays as it was, with the reason on the job
    again = wait_job(client, client.post(f"/api/songs/{sid}/import/video").json()["id"])
    assert again["status"] == "failed" and again["error_code"] == "video_fetch_failed"
    assert _rec(sd) == rec and not (sd / "source" / "video.fetching").exists() and not (sd / "source" / "video.mp4").exists()
    # the network is back
    flag.unlink()
    done = wait_job(client, client.post(f"/api/songs/{sid}/import/video").json()["id"])
    assert done["status"] == "succeeded", done
    now = _rec(sd)
    assert now["video"] == "source/video.mp4" and now["video_size"] == [320, 180] and "video_missing" not in now
    assert (sd / "source" / "video.mp4").is_file() and not (sd / "source" / "video.fetching").exists()
    assert _sha(sd / "source" / "audio.wav") == audio and now["source_hash"] == rec["source_hash"]     # the audio is not touched
    assert sorted(p.name for p in sd.iterdir()) == ["song.json", "source"]                             # nothing else appeared
    assert client.get(f"/api/songs/{sid}/audio-shift").json()["allowed"] is True                       # a fresh song with a picture
    # nothing to fetch any more
    assert client.post(f"/api/songs/{sid}/import/video").json()["error"] == "video_fetch_has_video"


def test_a_complete_import_has_no_such_mark(client, root, monkeypatch, tmp_path):
    flag = _setup(client, monkeypatch, tmp_path)
    sid, sd, job = _import(client, root, flag, fail=False)
    assert _rec(sd)["video"] == "source/video.mp4" and "video_missing" not in _rec(sd) and "video_missing" not in job["result"]
    assert client.post(f"/api/songs/{sid}/import/video").json()["error"] == "video_fetch_has_video"


def test_fetched_picture_becomes_the_original_under_a_lyric_picture_and_stems_stay(client, root, monkeypatch, tmp_path):
    flag = _setup(client, monkeypatch, tmp_path)
    sid, sd, _ = _import(client, root, flag, fail=True)
    (sd / "stems").mkdir()
    (sd / "stems" / "kept.txt").write_text("made from the audio")
    lines = [{"start": 1.0, "end": 2.0, "text": "風吹過了小河"}]
    made = wait_job(client, client.post(f"/api/songs/{sid}/lyric-video", json={"lines": lines, "style": "plain", "lead": 0.5}).json()["job"]["id"])
    assert made["status"] == "succeeded", made
    lyric = _rec(sd)["video"]
    assert client.get(f"/api/songs/{sid}/lyric-video").json()["styles"] == ["plain"]
    flag.unlink()
    done = wait_job(client, client.post(f"/api/songs/{sid}/import/video").json()["id"])
    assert done["status"] == "succeeded", done
    rec = _rec(sd)
    assert rec["video"] == lyric and rec["video_original"] == {"video": "source/video.mp4", "video_size": [320, 180]}
    assert (sd / "stems" / "kept.txt").read_text() == "made from the audio"
    st = client.get(f"/api/songs/{sid}/lyric-video").json()
    assert st["active"] is True and st["has_picture"] is True and st["styles"] == ["plain", "overlay"]
    back = client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": False}).json()
    assert back["active"] is False and _rec(sd)["video"] == "source/video.mp4"


def test_only_youtube_songs_without_a_picture(client, root):
    sid = client.post("/api/songs", json={"title": "empty"}).json()["song_id"]
    assert client.post(f"/api/songs/{sid}/import/video").json()["error"] == "video_fetch_not_youtube"
    sd = next(p for p in root.rglob(sid) if (p / "song.json").is_file())
    (sd / "source").mkdir()
    (sd / "source" / "audio.wav").write_bytes(b"RIFF")
    (sd / "source" / "source.json").write_text(json.dumps({"type": "audio", "audio": "source/audio.wav", "video": None, "duration": 3.0}))
    assert client.post(f"/api/songs/{sid}/import/video").json()["error"] == "video_fetch_not_youtube"
    assert client.post("/api/songs/nope/import/video").status_code in (400, 404)
