"""Sing & record compatibility API (/sr) with the real engine (CPU)."""
from __future__ import annotations

import io
import json
import struct
import time
import uuid
import wave

import pytest

from conftest import engine_available
from test_p1_engine import import_file

pytestmark = pytest.mark.skipif(not engine_available(), reason="engine environment not configured")


def sr(client):
    token = client.get("/sr/session").json()["token"]
    return {"X-Karaoke-Token": token}


def wait_prepare(client, h, job_id, timeout=1200):
    deadline = time.time() + timeout
    seen = set()
    while time.time() < deadline:
        state = client.get(f"/sr/jobs/{job_id}", headers=h).json()
        seen.add(state["stage"])
        if state["stage"] in ("ready", "failed"):
            return state, seen
        time.sleep(0.5)
    raise AssertionError("prepare did not finish")


def wav_bytes(seconds=2.0, rate=48000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x10" * int(seconds * rate))
    return buf.getvalue()


def test_sing_prepare_key_and_recordings(client, root, tmp_path):
    song = import_file(client, tmp_path, video=True, secs=20)
    sid = song["song_id"]
    h = sr(client)
    assert client.get("/sr/health").json()["features"]
    # token required
    assert client.get("/sr/library").status_code == 403

    media = client.get("/sr/local-media", headers=h).json()["media"]
    row = next(m for m in media if m["songId"] == sid)
    vid = row["id"]
    assert vid.startswith("local_") and row["kind"] == "video"
    info = client.get(f"/sr/local-media/{vid}", headers=h).json()
    assert info["playbackPath"] == f"/media/{sid}/source/video.mp4"

    # invalid analysis ranges are refused (0 = whole song, or try the first 15/30/60 s)
    assert client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 20}).status_code == 400

    created = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 0, "preview": True}).json()
    state, seen = wait_prepare(client, h, created["id"])
    assert state["stage"] == "ready", state["message"]
    assert "separating" in seen or "reference" in seen
    ref = client.get(f"/sr/jobs/{created['id']}/reference", headers=h).json()
    assert ref["version"] == 1 and ref["videoId"] == vid and 0.02 <= ref["step"] <= 0.2
    assert ref["pitchShift"] == 0 and ref["hasPreview"] and "stems" not in ref
    cache_id = ref["cacheId"]
    assert cache_id == f"{vid}_0_v1"

    lib = client.get("/sr/library", headers=h).json()["songs"]
    assert [s["id"] for s in lib] == [cache_id] and lib[0]["bytes"] > 0
    voc = client.get(f"/sr/library/{cache_id}/vocals", headers=h)
    assert voc.status_code == 200 and voc.content[:4] == b"RIFF"

    # masks shared across models of the same media and range
    m = client.post(f"/sr/library/{cache_id}/masks", headers=h,
                    json={"masks": [{"start": 5, "end": 6}, {"start": 5.5, "end": 7}]}).json()
    assert m["masks"] == [{"start": 5.0, "end": 7.0}]
    assert client.get(f"/sr/library/{cache_id}/reference", headers=h).json()["masks"] == m["masks"]

    # second request with the same settings is served from the library
    again = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 0}).json()
    assert again["cached"] and again["ready"]

    # key version (+2) reuses the original stems
    key = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 0, "pitchShift": 2}).json()
    kstate, kseen = wait_prepare(client, h, key["id"])
    assert kstate["stage"] == "ready", kstate
    kref = client.get(f"/sr/jobs/{key['id']}/reference", headers=h).json()
    assert kref["cacheId"] == f"{vid}_0_v1_key_p2" and kref["pitchShift"] == 2
    assert kref["sourceCacheId"] == cache_id
    base_frames = [f for f in ref["frames"] if f]
    key_frames = [f for f in kref["frames"] if f]
    assert abs(key_frames[0] / base_frames[0] - 2 ** (2 / 12)) < 1e-6
    acc = client.get(f"/sr/library/{kref['cacheId']}/accompaniment", headers=h)
    assert acc.status_code == 200 and acc.content[:4] == b"RIFF"
    assert len(client.get("/sr/library", headers=h).json()["songs"]) == 2
    # the key copies are shared: the library page asks for the same tracks at +2 -> nothing to do
    from app.api_sing import SEP_MODELS
    lk = client.post(f"/api/songs/{sid}/key", json={"recipe": {"model": SEP_MODELS[kref["separationModel"]]},
                                                    "semitones": 2, "tracks": ["instrumental", "vocals"]}).json()
    assert lk["ready"] and lk["job"] is None
    inv = client.get(f"/api/songs/{sid}/stems").json()["items"]
    keys = [i for i in inv if i["type"] == "key"]
    assert len(keys) == 2 and all(len(k["parents"]) == 1 and k["used_by"] for k in keys)

    # "try the first 15 s": a clip is separated and analysed on its own, apart from the whole-song stems
    clip = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 15}).json()
    cstate, _ = wait_prepare(client, h, clip["id"])
    assert cstate["stage"] == "ready", cstate
    cref = client.get(f"/sr/jobs/{clip['id']}/reference", headers=h).json()
    assert cref["cacheId"] == f"{vid}_15_v1" and cref["rangeSeconds"] == 15 and cref["duration"] <= 15.2
    layers = [i for i in client.get(f"/api/songs/{sid}/stems").json()["items"] if i["type"] == "layer"]
    assert any(l["input"] == "sing/clips/clip_15s.wav" for l in layers)
    assert any(l["input"] == "source/audio.wav" for l in layers)        # the whole-song stems are untouched

    # recordings archive: bundle import, metadata update, audio, mp3, delete
    rec_id = str(uuid.uuid4())
    mix = wav_bytes()
    meta = {"id": rec_id, "title": "測試錄音", "mime": "audio/wav", "created": time.time() * 1000, "seconds": 2,
            "bytes": len(mix), "videoId": vid, "complete": True}
    raw = json.dumps(meta).encode()
    bundle = struct.pack("<I", len(raw)) + raw + mix
    listing = client.get("/sr/recordings", headers=h).json()
    stored = client.post(f"/sr/recordings/{rec_id}?root={listing['path']}", headers=h, content=bundle).json()
    assert stored["bytes"] == len(mix)
    assert client.get(f"/sr/recordings/{rec_id}/mix", headers=h).content == mix
    upd = client.post(f"/sr/recordings/{rec_id}/metadata", headers=h,
                      content=json.dumps({**meta, "score": 88}).encode()).json()
    assert upd["score"] == 88
    mp3 = client.post("/sr/recordings/mp3", headers=h, content=mix)
    assert mp3.status_code == 200 and mp3.headers["content-type"] == "audio/mpeg" and len(mp3.content) > 1000
    saved = client.post(f"/sr/recordings/{rec_id}/mp3", headers=h, content=mp3.content).json()
    assert saved["path"].endswith("export.mp3")
    assert len(client.get("/sr/recordings", headers=h).json()["records"]) == 1

    # hand a finished take to the MV workspace
    render = client.post(f"/sr/renders?videoId={vid}&title=take1&recordingId={rec_id}", headers=h, content=mix).json()
    assert render["song_id"] == sid and render["kind"] == "sing"
    assert (root / "library" / "songs" / sid / render["path"]).is_file()
    again = client.post(f"/sr/renders?videoId={vid}&title=take1&recordingId={rec_id}", headers=h, content=mix).json()
    assert again["id"] == render["id"] and again["reused"]                 # same take sent twice: one copy
    changed = client.post(f"/sr/renders?videoId={vid}&title=take1&recordingId={rec_id}", headers=h,
                          content=mix[:-2] + b"\x01\x02").json()
    assert changed["id"] != render["id"]                                   # re-processed take: a new copy

    assert client.delete(f"/sr/recordings/{rec_id}", headers=h).json() == {"deleted": True}
    assert client.get("/sr/recordings", headers=h).json()["records"] == []
    assert client.post(f"/sr/recordings/{rec_id}", headers=h, content=bundle).status_code == 400  # deleted stays deleted

    # deleting the key version frees its key copies (nothing else uses them); the original stays
    gone = client.delete(f"/sr/library/{kref['cacheId']}", headers=h).json()
    assert gone["deleted"] and gone["freedBytes"] > 0
    assert not [i for i in client.get(f"/api/songs/{sid}/stems").json()["items"] if i["type"] == "key"]
    assert sorted(x["id"] for x in client.get("/sr/library", headers=h).json()["songs"]) == sorted([cache_id, cref["cacheId"]])

    # "keep separated tracks" off: only the reference is kept, the stems this job made are removed
    nk = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 30, "preview": False}).json()
    nstate, _ = wait_prepare(client, h, nk["id"])
    assert nstate["stage"] == "ready", nstate
    nref = client.get(f"/sr/library/{vid}_30_v1/reference", headers=h).json()
    assert nref["hasPreview"] is False
    assert not any(i.get("input") == "sing/clips/clip_30s.wav"
                   for i in client.get(f"/api/songs/{sid}/stems").json()["items"])
    again = client.post("/sr/jobs", headers=h, json={"videoId": vid, "seconds": 30, "preview": False}).json()
    assert again.get("cached")                                             # reused without the tracks


def test_sing_diagnostics_roundtrip(client):
    tok = client.get("/sr/diagnostics/session").json()["token"]
    h = {"X-Diagnostic-Token": tok}
    did = str(uuid.uuid4())
    assert client.post(f"/sr/diagnostics/{did}", headers=h, json={"title": "t", "formatVersion": 1}).json() == {"id": did}
    assert client.post(f"/sr/diagnostics/{did}/events", headers=h, json={"kind": "event", "event": "x"}).json()["saved"]
    fin = client.post(f"/sr/diagnostics/{did}/finish", headers=h, json={}).json()
    assert fin["saved"]
    assert client.get("/sr/diagnostics", headers=h).json()["count"] == 1
    assert client.delete("/sr/diagnostics", headers=h).json()["cleared"] == 1


def test_link_preview_info(client, tmp_path):
    """Old YouTube preview card: title before importing; bad links are refused, unreachable ones say so."""
    assert client.get("/api/youtube/info", params={"url": "notaurl"}).status_code == 400
    r = client.get("/api/youtube/info", params={"url": "http://127.0.0.1:9/nothing.mp4"})
    assert r.status_code == 502 and r.json()["error"] == "youtube_info_failed"
    # a direct media link (generic extractor): title from the file name, nothing downloaded
    import functools
    import http.server
    import threading
    folder = tmp_path / "link"
    folder.mkdir()
    (folder / "song_preview.wav").write_bytes(wav_bytes(1.0))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler,
                                                                             directory=str(folder)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        info = client.get("/api/youtube/info", params={"url": f"http://127.0.0.1:{srv.server_port}/song_preview.wav"}).json()
        assert info["title"] == "song_preview" and info["id"]
    finally:
        srv.shutdown()
