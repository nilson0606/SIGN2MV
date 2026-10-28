"""P0: server skeleton, security guard, settings, library, queue."""
from __future__ import annotations

import time

from conftest import wait_job


def test_status_and_guard(client):
    st = client.get("/api/system/status").json()
    assert st["app"] == "SIGN2MV" and st["api_level"] >= 1
    # other hosts are refused (DNS rebinding)
    assert client.get("/api/system/status", headers={"host": "evil.example"}).status_code == 403
    # changing requests need the control header
    r = client.post("/api/songs", json={"title": "x"}, headers={"X-SIGN2MV": ""})
    assert r.status_code == 403


def test_settings_language(client):
    s = client.put("/api/settings", json={"language": "en"}).json()
    assert s["language"] == "en" and s["effective_language"] == "en"
    assert client.put("/api/settings", json={"language": "fr"}).status_code == 400
    assert client.put("/api/settings", json={"nope": 1}).status_code == 400


def test_library_crud(client):
    s = client.post("/api/songs", json={"title": "  南都夜曲  "}).json()
    assert s["title"] == "南都夜曲" and s["song_id"].startswith("s")
    assert client.post("/api/songs", json={"title": ""}).status_code == 400
    s2 = client.patch(f"/api/songs/{s['song_id']}", json={"title": "改名"}).json()
    assert s2["title"] == "改名"
    assert [x["title"] for x in client.get("/api/songs").json()["songs"]] == ["改名"]
    assert client.get("/api/songs/../../etc").status_code in (400, 404)
    assert client.delete(f"/api/songs/{s['song_id']}").json()["ok"]
    assert client.get("/api/songs").json()["songs"] == []


def test_queue_order_cancel_timeout(client):
    a = client.post("/api/jobs", json={"kind": "demo", "lane": "gpu", "seconds": 1.2}).json()
    b = client.post("/api/jobs", json={"kind": "demo", "lane": "gpu", "seconds": 5}).json()
    c = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 0.5}).json()
    time.sleep(0.4)
    assert client.get(f"/api/jobs/{b['id']}").json()["position"] == 1  # waits for the GPU lane
    assert wait_job(client, c["id"], 10)["status"] == "succeeded"  # cpu lane runs in parallel
    assert wait_job(client, a["id"], 10)["status"] == "succeeded"
    client.post(f"/api/jobs/{b['id']}/cancel")
    assert wait_job(client, b["id"], 10)["status"] == "cancelled"
    t = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 20, "timeout_s": 1}).json()
    assert wait_job(client, t["id"], 10)["status"] == "timeout"
    f = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 0.3, "fail": True}).json()
    done = wait_job(client, f["id"], 10)
    assert done["status"] == "failed" and done["error_code"] == "demo_failure"


def test_shutdown_requires_force_when_busy(client):
    j = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 10}).json()
    r = client.post("/api/system/shutdown", json={})
    assert r.status_code == 409 and r.json()["error"] == "jobs_running"
    client.post(f"/api/jobs/{j['id']}/cancel")


def test_delete_song_removes_its_recordings(client, root):
    """Sing & record takes live in <library>/recordings; deleting the song deletes its takes too."""
    import json
    import struct
    import uuid
    from app.api_sing import video_id_for
    from app.sing_archive import RecordingArchive
    a = client.post("/api/songs", json={"title": "A"}).json()["song_id"]
    b = client.post("/api/songs", json={"title": "B"}).json()["song_id"]
    arc = RecordingArchive(root / "library" / "recordings")
    arc.ready()
    ids = {}
    for sid in (a, b):
        rid = str(uuid.uuid4())
        mix = b"RIFF" + b"\0" * 60
        meta = {"id": rid, "title": "t", "mime": "audio/wav", "created": 1, "seconds": 1, "bytes": len(mix),
                "videoId": video_id_for(sid), "complete": True}
        raw = json.dumps(meta).encode()
        bundle = root / f"{rid}.bin"
        bundle.write_bytes(struct.pack("<I", len(raw)) + raw + mix)
        arc.import_bundle(rid, bundle)
        ids[sid] = rid
    res = client.delete(f"/api/songs/{a}").json()
    assert res["ok"] and res["recordings_deleted"] == 1
    remaining = [r["id"] for r in arc.list()["records"]]
    assert remaining == [ids[b]]


def test_stored_copies_list_and_delete(client, root):
    """Library lists every separation layer / key copy with size and users; deleting one
    also deletes what was computed from it; names outside the song folder are refused."""
    import json
    sid = client.post("/api/songs", json={"title": "S"}).json()["song_id"]
    sd = next(p for p in root.rglob(sid) if p.is_dir())

    def layer(key, kind, inp, files):
        d = sd / "stems" / key
        d.mkdir(parents=True)
        for f in files:
            (d / f).write_bytes(b"x" * 100)
        (d / "info.json").write_text(json.dumps({"key": key, "kind": kind, "model": "demucs", "input": inp,
                                                 "files": files, "created_at": 1}))
    layer("aaa", "mix", "source/audio.wav", ["vocals.wav", "instrumental.wav"])
    layer("bbb", "lead", "stems/aaa/vocals.wav", ["lead.wav", "backing.wav"])
    layer("ccc", "mix", "source/audio.wav", ["vocals.wav", "instrumental.wav"])
    k = sd / "keys" / "kk_p1"
    k.mkdir(parents=True)
    (k / "lead.wav").write_bytes(b"y" * 50)
    (k / "info.json").write_text(json.dumps({"semitones": 1, "tracks": ["lead"], "sources": {"lead": "stems/bbb/lead.wav"}}))
    (sd / "keys" / "old_p2.tmp123").mkdir()
    v = sd / "cover" / "versions" / "v0123456789"
    v.mkdir(parents=True)
    (v / "version.json").write_text(json.dumps({"id": "v0123456789", "title": "#1 Me", "plan": {"vocal": {"path": "keys/kk_p1/lead.wav"},
                                                                                      "bgm": "stems/aaa/instrumental.wav"}}))
    res = client.get(f"/api/songs/{sid}/stems").json()
    by = {i["dir"]: i for i in res["items"]}
    assert set(by) == {"stems/aaa", "stems/bbb", "stems/ccc", "keys/kk_p1", "keys/old_p2.tmp123"}
    assert by["stems/bbb"]["parents"] == ["stems/aaa"] and by["keys/kk_p1"]["parents"] == ["stems/bbb"]
    assert by["keys/old_p2.tmp123"]["type"] == "incomplete"
    assert by["stems/aaa"]["bytes"] >= 200 and res["total_bytes"] >= 650
    assert [u["type"] for u in by["keys/kk_p1"]["used_by"]] == ["cover"]
    assert len(res["layers"]) == 3
    assert client.delete(f"/api/songs/{sid}/stems/%2E%2E").status_code == 404
    assert client.delete(f"/api/songs/{sid}/source/x").status_code == 404
    assert client.delete(f"/api/songs/{sid}/stems/zzz").status_code == 404
    out = client.delete(f"/api/songs/{sid}/stems/aaa").json()
    assert set(out["deleted"]) == {"stems/aaa", "stems/bbb", "keys/kk_p1"} and out["bytes"] >= 450
    left = {i["dir"] for i in client.get(f"/api/songs/{sid}/stems").json()["items"]}
    assert left == {"stems/ccc", "keys/old_p2.tmp123"}
    assert client.delete(f"/api/songs/{sid}/keys/old_p2.tmp123").json()["deleted"] == ["keys/old_p2.tmp123"]
    assert (v / "version.json").is_file()   # the cover version itself is kept


def test_storage_usage(client, root):
    """Per-song disk usage by category, library totals and free space."""
    import json
    sid = client.post("/api/songs", json={"title": "U"}).json()["song_id"]
    sd = next(p for p in root.rglob(sid) if p.is_dir())
    files = {"source/audio.wav": 1000, "stems/a/vocals.wav": 300, "keys/k_p1/x.wav": 50,
             "cover/versions/v0123456789/version.json": 10, "cover/rvc/x.wav": 70,
             "sing/c1/reference.json": 5, "mv/p1/project.json": 7, "mv/p1/frames/f.png": 40}
    for rel, n in files.items():
        (sd / rel).parent.mkdir(parents=True, exist_ok=True)
        (sd / rel).write_bytes(b"x" * n)
    r = sd / "renders" / "r1"
    r.mkdir(parents=True)
    (r / "render.json").write_text(json.dumps({"kind": "cover"}))
    (r / "audio.mp3").write_bytes(b"x" * 200)
    res = client.get(f"/api/songs/{sid}/storage").json()
    c = res["categories"]
    assert c["source"] == 1000 and c["stems"] == 350 and c["cover_cache"] == 70 and c["mv"] == 47 and c["sing"] == 5
    assert c["cover"] == 10 + 200 + len(json.dumps({"kind": "cover"}))
    assert res["counts"]["cover_versions"] == 1 and res["counts"]["mv_projects"] == 1 and res["counts"]["sing_prepared"] == 1
    assert res["total"] == sum(c.values()) and res["disk"]["free"] > 0
    lib = client.get("/api/storage").json()
    assert lib["songs"][sid] == res["total"] and lib["total"] >= res["total"]
