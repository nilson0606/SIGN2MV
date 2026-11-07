"""Old "keep the singer's timbre" key versions (R2 engine, cache id suffix _f) stay loadable for the
recordings made on them, but are never made again (new ones are _t)."""
from __future__ import annotations

import json

from app.api_sing import cache_key, parse_cache_key, video_id_for

def _song_with_legacy_version(client):
    ctx = client.app.state.ctx
    song = ctx.library().create("Legacy")
    sid = song["song_id"]
    d = ctx.library().song_dir(sid)
    (d / "source").mkdir()
    (d / "source" / "audio.wav").write_bytes(b"RIFF")
    (d / "source" / "source.json").write_text(json.dumps({"audio": "source/audio.wav", "source_hash": "abc"}),
                                              encoding="utf-8")
    vid = video_id_for(sid)
    key_id = cache_key(vid, 0, "all", "demucs", "rmvpe", "single", -4, True, legacy=True)
    (d / "keys" / "x_m4f").mkdir(parents=True)
    (d / "keys" / "x_m4f" / "vocals.wav").write_bytes(b"v")
    (d / "keys" / "y_m4").mkdir(parents=True)
    (d / "keys" / "y_m4" / "instrumental.wav").write_bytes(b"a")
    ref = d / "sing" / key_id
    ref.mkdir(parents=True)
    (ref / "reference.json").write_text(json.dumps({
        "title": "Legacy · 降 4 Key · 保留原唱音色", "pitchShift": -4, "keyFormant": True, "duration": 10,
        "frames": [None] * 10, "stems": {"vocals": "keys/x_m4f/vocals.wav", "accompaniment": "keys/y_m4/instrumental.wav"}}),
        encoding="utf-8")
    return vid, key_id


def test_cache_ids():
    vid = "local_" + "a" * 64
    old = cache_key(vid, 0, "all", "demucs", "yin", "single", -4, True, legacy=True)
    new = cache_key(vid, 0, "all", "demucs", "yin", "single", -4, True)
    assert old.endswith("_key_m4_f") and new.endswith("_key_m4_t")
    assert parse_cache_key(old)["keyLegacy"] is True and parse_cache_key(old)["keyFormant"] is True
    assert parse_cache_key(new)["keyLegacy"] is False


def test_legacy_version_loads_but_is_not_rebuilt(client):
    vid, key_id = _song_with_legacy_version(client)
    h = {"X-Karaoke-Token": client.get("/sr/session").json()["token"]}
    row = next(s for s in client.get("/sr/library", headers=h).json()["songs"] if s["id"] == key_id)
    assert row["keyLegacy"] is True and row["keyFormant"] is True
    # what a recording's post-processing reads
    assert client.get(f"/sr/library/{key_id}/reference", headers=h).json()["keyLegacy"] is True
    assert client.get(f"/sr/library/{key_id}/accompaniment", headers=h).status_code == 200
    body = {"videoId": vid, "seconds": 0, "pitchShift": -4, "keyFormant": True, "keyLegacy": True, "pitchMethod": "rmvpe"}
    loaded = client.post("/sr/jobs", headers=h, json=body)
    assert loaded.status_code == 202
    assert client.get(f"/sr/jobs/{loaded.json()['id']}/reference", headers=h).json()["cacheId"] == key_id
    again = client.post("/sr/jobs", headers=h, json={**body, "force": True})
    assert again.status_code == 400   # never made again with the old method
