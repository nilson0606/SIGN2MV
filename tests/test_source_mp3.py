"""Home library: download the song's own audio as an MP3, made from source/audio.wav."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.parse import unquote


from app.paths import get_paths


def _song_with_source(client, root: Path, title: str = "港邊/測試") -> str:
    sid = client.post("/api/songs", json={"title": title}).json()["song_id"]
    song_dir = next(p for p in root.rglob(sid) if (p / "song.json").is_file())
    src = song_dir / "source"
    src.mkdir()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=44100",
                    "-ac", "2", "-c:a", "pcm_f32le", str(src / "audio.wav")], check=True)
    (src / "source.json").write_text(json.dumps({"type": "file", "audio": "source/audio.wav", "duration": 3.0}),
                                     encoding="utf-8")
    return sid


def test_source_mp3_is_made_from_the_wav_and_not_kept(client, root):
    sid = _song_with_source(client, root)
    r = client.get(f"/api/songs/{sid}/source.mp3")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert r.content[:3] == b"ID3" or r.content[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    # the title's "/" cannot be in a Windows file name
    assert "港邊_測試.mp3" in unquote(r.headers["content-disposition"])
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,sample_rate,channels",
                            "-of", "compact", "-"], input=r.content, capture_output=True, text=False)
    out = probe.stdout.decode()
    assert "mp3" in out and "44100" in out and "channels=2" in out
    tmp = get_paths().tmp
    assert not list(tmp.glob("source_*.mp3"))          # removed after sending
    assert not list(root.rglob("*.mp3"))               # nothing added to the library


def test_source_mp3_without_a_source(client, root):
    sid = client.post("/api/songs", json={"title": "empty"}).json()["song_id"]
    assert client.get(f"/api/songs/{sid}/source.mp3").json()["error"] == "file_not_found"
    assert client.get("/api/songs/nosuchsong/source.mp3").status_code in (400, 404)
