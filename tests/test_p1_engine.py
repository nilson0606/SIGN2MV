"""P1: import + separation + key, with the real engine (CPU)."""
from __future__ import annotations

import json
import subprocess

import pytest
import soundfile as sf

from conftest import engine_available, make_song_media, wait_job

pytestmark = pytest.mark.skipif(not engine_available(), reason="engine environment not configured")


def ffprobe_streams(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return sorted(s["codec_type"] for s in json.loads(out)["streams"])


def seconds(path):
    i = sf.info(str(path))
    return i.frames / i.samplerate


def import_file(client, tmp_path, video=True, secs=20):
    media = make_song_media(tmp_path / ("in.mp4" if video else "in.wav"), secs, video)
    song = client.post("/api/songs", json={"title": "測試歌"}).json()
    with open(media, "rb") as fh:
        job = client.post(f"/api/songs/{song['song_id']}/import/file",
                          files={"file": ("我的歌.mp4" if video else "我的歌.wav", fh)}).json()
    done = wait_job(client, job["id"], 300)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    return client.get(f"/api/songs/{song['song_id']}").json()


def test_import_video_and_separate(client, root, tmp_path):
    song = import_file(client, tmp_path, video=True)
    src = song["source"]
    sid = song["song_id"]
    song_dir = root / "library" / "songs" / sid
    assert src["type"] == "video" and src["video"] == "source/video.mp4"
    assert ffprobe_streams(song_dir / src["video"]) == ["audio", "video"]
    assert abs(src["duration"] - 20) < 0.2
    assert src["source_hash"].startswith("sha256:")
    assert (song_dir / "source" / "original.mp4").is_file()
    # media served with range support
    r = client.get(f"/media/{sid}/{src['video']}", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100

    res = client.post(f"/api/songs/{sid}/stems", json={"recipe": {"model": "demucs"}}).json()
    assert not res["ready"] and res["job"]
    done = wait_job(client, res["job"]["id"], 900)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    for name in ("vocals", "instrumental"):
        assert abs(seconds(song_dir / res["tracks"][name]) - 20) < 0.15
    again = client.post(f"/api/songs/{sid}/stems", json={"recipe": {"model": "demucs"}}).json()
    assert again["ready"] and again["job"] is None  # cached

    # second pass reuses layer 1 (only one new layer)
    sp = client.post(f"/api/songs/{sid}/stems", json={"recipe": {"model": "demucs", "second_pass": True}}).json()
    assert not sp["ready"]
    done = wait_job(client, sp["job"]["id"], 900)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    assert done["result"]["layers"] and len(done["result"]["layers"]) == 1
    for name in ("instrumental", "residual_vocals"):
        assert abs(seconds(song_dir / sp["tracks"][name]) - 20) < 0.15

    # key change keeps the length
    k = client.post(f"/api/songs/{sid}/key", json={"recipe": {"model": "demucs"}, "semitones": 3,
                                                   "tracks": ["instrumental", "vocals"]}).json()
    done = wait_job(client, k["job"]["id"], 300)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    for rel in k["tracks"].values():
        assert abs(seconds(song_dir / rel) - 20) < 0.02

    # busy songs cannot be deleted; idle ones can
    assert client.delete(f"/api/songs/{sid}").json()["ok"]


def test_lead_split_roformer(client, root, tmp_path):
    song = import_file(client, tmp_path, video=False, secs=12)
    sid = song["song_id"]
    assert song["source"]["video"] is None
    res = client.post(f"/api/songs/{sid}/stems", json={"recipe": {"model": "demucs", "lead": True}}).json()
    done = wait_job(client, res["job"]["id"], 1800)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    song_dir = root / "library" / "songs" / sid
    for name in ("lead", "backing"):
        assert abs(seconds(song_dir / res["tracks"][name]) - 12) < 0.15


def test_bs_roformer(client, root, tmp_path):
    song = import_file(client, tmp_path, video=False, secs=10)
    sid = song["song_id"]
    res = client.post(f"/api/songs/{sid}/stems", json={"recipe": {"model": "bs_roformer"}}).json()
    done = wait_job(client, res["job"]["id"], 1800)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
