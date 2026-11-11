"""Library: shift a song's audio up to ±2 s against its picture, only while nothing has been made from it."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

RATE = 44100


def _read_wav(path: Path) -> np.ndarray:
    b = path.read_bytes()
    i = b.index(b"data")
    n = int.from_bytes(b[i + 4:i + 8], "little")
    return np.frombuffer(b[i + 8:i + 8 + n], "<f4").reshape(-1, 2)


def _song(client, root: Path, original: bool = False) -> tuple[str, Path]:
    sid = client.post("/api/songs", json={"title": "shift"}).json()["song_id"]
    song_dir = next(p for p in root.rglob(sid) if (p / "song.json").is_file())
    src = song_dir / "source"
    src.mkdir()
    ff = ["ffmpeg", "-y", "-v", "error"]
    subprocess.run(ff + ["-f", "lavfi", "-i", f"sine=frequency=440:duration=3:sample_rate={RATE}",
                         "-ac", "2", "-c:a", "pcm_f32le", str(src / "audio.wav")], check=True)
    subprocess.run(ff + ["-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=3", "-i", str(src / "audio.wav"),
                         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                         "-c:a", "aac", "-shortest", str(src / "video.mp4")], check=True)
    rec = {"type": "youtube", "audio": "source/audio.wav", "video": "source/video.mp4", "duration": 3.0,
           "source_hash": "yt:abc", "imported_at": 1.0}
    if original:
        (src / "original.mp4").write_bytes(b"x")
        rec["original"] = "source/original.mp4"
    (src / "source.json").write_text(json.dumps(rec), encoding="utf-8")
    return sid, song_dir


def _packet_hashes(path: Path) -> str:
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "hash", "-"],
                          capture_output=True, text=True, check=True).stdout


def test_shift_later_pads_the_start_keeps_length_and_picture(client, root):
    sid, song_dir = _song(client, root, original=True)
    before = _read_wav(song_dir / "source" / "audio.wav").copy()
    pic = _packet_hashes(song_dir / "source" / "video.mp4")
    assert client.get(f"/api/songs/{sid}/audio-shift").json()["allowed"] is True
    r = client.post(f"/api/songs/{sid}/audio-shift", json={"target": 0.5})
    assert r.status_code == 200, r.text
    after = _read_wav(song_dir / "source" / "audio.wav")
    n = RATE // 2
    assert len(after) == len(before)
    assert np.abs(after[:n]).max() == 0 and np.array_equal(after[n:], before[:-n])
    assert _packet_hashes(song_dir / "source" / "video.mp4") == pic          # picture copied, not encoded again
    rec = json.loads((song_dir / "source" / "source.json").read_text(encoding="utf-8"))
    assert rec["audio_offset_s"] == 0.5 and rec["source_hash"] == "yt:abc#shift+500ms"
    assert "original" not in rec and not (song_dir / "source" / "original.mp4").exists()
    assert not (song_dir / "source.old").exists() and not (song_dir / "source.importing").exists()
    # the value is the total against the original: 0 goes back (the end cut at +0.5 stays silent)
    assert client.post(f"/api/songs/{sid}/audio-shift", json={"target": 0.5}).json()["error"] == "shift_same"
    assert client.post(f"/api/songs/{sid}/audio-shift", json={"target": 0}).status_code == 200
    rec = json.loads((song_dir / "source" / "source.json").read_text(encoding="utf-8"))
    assert rec["audio_offset_s"] == 0 and rec["source_hash"] == "yt:abc"
    back = _read_wav(song_dir / "source" / "audio.wav")
    assert np.array_equal(back[:-n], before[:-n]) and np.abs(back[-n:]).max() == 0
    # +0.3 from +0 then -0.2 total: moves by -0.5
    client.post(f"/api/songs/{sid}/audio-shift", json={"target": 0.3})
    client.post(f"/api/songs/{sid}/audio-shift", json={"target": -0.2})
    rec = json.loads((song_dir / "source" / "source.json").read_text(encoding="utf-8"))
    assert rec["audio_offset_s"] == -0.2 and rec["source_hash"] == "yt:abc#shift-200ms"


def test_shift_earlier_cuts_the_start_and_pads_the_end(client, root):
    sid, song_dir = _song(client, root)
    before = _read_wav(song_dir / "source" / "audio.wav").copy()
    assert client.post(f"/api/songs/{sid}/audio-shift", json={"target": -0.25}).status_code == 200
    after = _read_wav(song_dir / "source" / "audio.wav")
    n = round(0.25 * RATE)
    assert len(after) == len(before)
    assert np.array_equal(after[:-n], before[n:]) and np.abs(after[-n:]).max() == 0


def test_shift_is_refused_once_anything_was_made(client, root):
    sid, song_dir = _song(client, root)
    (song_dir / "stems").mkdir()                     # an empty folder does not count
    assert client.get(f"/api/songs/{sid}/audio-shift").json()["allowed"] is True
    (song_dir / "stems" / "k1").mkdir()
    (song_dir / "stems" / "k1" / "info.json").write_text("{}")
    st = client.get(f"/api/songs/{sid}/audio-shift").json()
    assert st["allowed"] is False and st["reason"] == "shift_processed"
    before = (song_dir / "source" / "audio.wav").read_bytes()
    r = client.post(f"/api/songs/{sid}/audio-shift", json={"target": 0.3})
    assert r.status_code == 409 and r.json()["error"] == "shift_processed"
    assert (song_dir / "source" / "audio.wav").read_bytes() == before


def test_shift_is_refused_when_the_song_has_takes(client, root):
    from app.api_sing import video_id_for
    sid, song_dir = _song(client, root)
    take = song_dir.parent.parent / "recordings" / "take1"
    take.mkdir(parents=True)
    (take / "metadata.json").write_text(json.dumps({"recording": {"videoId": video_id_for(sid)}}), encoding="utf-8")
    assert client.get(f"/api/songs/{sid}/audio-shift").json()["reason"] == "shift_processed"


def test_shift_range_and_songs_without_video(client, root):
    sid, _ = _song(client, root)
    for bad in (2.5, -3, "x", None):
        assert client.post(f"/api/songs/{sid}/audio-shift", json={"target": bad}).json()["error"] == "shift_range"
    assert client.post(f"/api/songs/{sid}/audio-shift", json={"target": 0}).json()["error"] == "shift_same"
    empty = client.post("/api/songs", json={"title": "empty"}).json()["song_id"]
    assert client.get(f"/api/songs/{empty}/audio-shift").json()["reason"] == "shift_no_video"
