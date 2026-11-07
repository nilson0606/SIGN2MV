"""Sing references follow the song's source: after a re-import they are made again from the new audio."""
from __future__ import annotations

import json
import time

from app.api_sing import cache_key, clip_name, reference_stale, source_mark, video_id_for

OLD = {"source": {"source_hash": "sha256:a", "imported_at": 1000.0}}
NEW = {"source": {"source_hash": "sha256:b", "imported_at": 2000.0}}


def test_fingerprint_and_clip_follow_the_source():
    ref = {"sourceHash": source_mark(OLD, 0)}
    assert not reference_stale(ref, OLD, 0) and reference_stale(ref, NEW, 0)
    assert source_mark(OLD, 15).endswith("#clip15")
    assert clip_name(OLD, 15) != clip_name(NEW, 15) and clip_name(OLD, 15).startswith("sing/clips/clip_15s_")


def test_old_references_without_fingerprint_use_the_save_time():
    saved_between = {"savedAt": "1970-01-01T00:25:00Z"}            # 1500 s: after OLD, before NEW
    assert not reference_stale(saved_between, OLD, 0) and reference_stale(saved_between, NEW, 0)
    assert not reference_stale({}, NEW, 0)                         # nothing to compare: kept


def test_library_marks_and_rebuilds_a_stale_reference(client):
    ctx = client.app.state.ctx
    sid = ctx.library().create("Changed")["song_id"]
    d = ctx.library().song_dir(sid)
    (d / "source").mkdir()
    (d / "source" / "audio.wav").write_bytes(b"RIFF")
    (d / "source" / "source.json").write_text(json.dumps({"audio": "source/audio.wav", "source_hash": "sha256:b",
                                                           "imported_at": time.time()}), encoding="utf-8")
    vid = video_id_for(sid)
    key_id = cache_key(vid, 0, "all", "demucs", "yin", "single")
    (d / "sing" / key_id).mkdir(parents=True)
    (d / "sing" / key_id / "reference.json").write_text(json.dumps({
        "title": "Changed", "pitchShift": 0, "duration": 10, "frames": [None] * 10, "sourceHash": "sha256:a",
        "stems": {}}), encoding="utf-8")
    h = {"X-Karaoke-Token": client.get("/sr/session").json()["token"]}
    row = next(s for s in client.get("/sr/library", headers=h).json()["songs"] if s["id"] == key_id)
    assert row["stale"] is True
    job = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 0, "preview": False}).json()
    assert job.get("cached") is not True and job.get("stage") != "ready"   # made again, not the old reference
    client.delete(f"/sr/jobs/{job['id']}", headers=h)
    ref = d / "sing" / key_id / "reference.json"
    ref.write_text(ref.read_text(encoding="utf-8").replace("sha256:a", "sha256:b"), encoding="utf-8")
    same = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 0, "preview": False}).json()
    assert same["cached"] is True                                          # same audio: loaded as before
