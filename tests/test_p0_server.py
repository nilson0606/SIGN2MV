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


def test_library_location_rules(client, root, tmp_path):
    """sign_record's rules: full path, not a drive root, not a program folder, writable."""
    bad = {"relative/lib": "library_dir_not_absolute", "/": "library_dir_root",
           str(root / "runtime" / "x"): "library_dir_reserved", "": "invalid_library_dir"}
    for value, code in bad.items():
        r = client.put("/api/settings", json={"library_dir": value})
        assert r.status_code == 400 and r.json()["error"] == code, (value, r.json())
    new = tmp_path / "newlib"
    s = client.put("/api/settings", json={"library_dir": str(new)}).json()
    assert s["library_dir"] == str(new.resolve()) and new.is_dir() and not list(new.glob(".sign2mv-write-test-*"))
    assert client.post("/api/settings/pick-library", json={}).json()["error"] == "folder_picker_windows_only"


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
    queued = client.get(f"/api/jobs/{b['id']}").json()
    assert queued["position"] == 1 and queued["waiting_for"] == (a.get("title") or "demo")  # waits for the GPU lane, says for what
    assert wait_job(client, c["id"], 10)["status"] == "succeeded"  # cpu lane runs in parallel
    assert wait_job(client, a["id"], 10)["status"] == "succeeded"
    client.post(f"/api/jobs/{b['id']}/cancel")
    assert wait_job(client, b["id"], 10)["status"] == "cancelled"
    t = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 20, "timeout_s": 1}).json()
    assert wait_job(client, t["id"], 10)["status"] == "timeout"

    # job log (the old "terminal"): start, stage changes, end; fetched incrementally
    log = client.get(f"/api/jobs/{a['id']}/log").json()
    assert log["status"] == "succeeded" and log["lines"][0].endswith("▶ " + (a.get("title") or "demo")) or "▶" in log["lines"][0]
    assert any("▶ [" in l for l in log["lines"]) and "✔ succeeded" in log["lines"][-1]
    assert client.get(f"/api/jobs/{a['id']}/log?after={log['next']}").json()["lines"] == []
    assert "timeout" in client.get(f"/api/jobs/{t['id']}/log").json()["lines"][-1]
    assert client.get("/api/jobs/nope/log").status_code == 404
    f = client.post("/api/jobs", json={"kind": "demo", "lane": "cpu", "seconds": 0.3, "fail": True}).json()
    done = wait_job(client, f["id"], 10)
    assert done["status"] == "failed" and done["error_code"] == "demo_failure"

    # every job also leaves its story in logs/jobs.log (kept after the program closes)
    from app.paths import get_paths
    events = (get_paths().logs / "jobs.log").read_text(encoding="utf-8")
    assert f"{b['id']} [demo] demo: cancel requested while running" in events and "cancelled (" in events
    assert f"{a['id']} [demo] demo: started (waited" in events and "succeeded (" in events
    assert f"{t['id']} [demo] demo: timeout" in events and "demo_failure" in events


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
    assert client.delete(f"/api/songs/{sid}/source/x").status_code in (404, 405)
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


def test_cover_versions_mvs_batch_delete_open_folder(client, root):
    """A version lists the MVs made from it; several versions are deleted at once; open-folder stays inside the song."""
    import json
    sid = client.post("/api/songs", json={"title": "V"}).json()["song_id"]
    sd = next(p for p in root.rglob(sid) if p.is_dir())
    for vid, rid in (("v0000000001", "r000000000001"), ("v0000000002", "r000000000002")):
        (sd / "cover" / "versions" / vid).mkdir(parents=True)
        (sd / "cover" / "versions" / vid / "version.json").write_text(json.dumps(
            {"id": vid, "number": int(vid[-1]), "title": f"#{vid[-1]}", "label": "M", "render_id": rid, "created_at": 1}))
        (sd / "renders" / rid).mkdir(parents=True)
        (sd / "renders" / rid / "audio.mp3").write_bytes(b"ID3" + b"x" * 500)
        (sd / "renders" / rid / "render.json").write_text(json.dumps({"id": rid, "kind": "cover", "audio": "audio.mp3", "bytes": 503}))
    q = sd / "quickmv" / "q000000000001"
    q.mkdir(parents=True)
    (q / "video.mp4").write_bytes(b"v")
    (q / "info.json").write_text(json.dumps({"source": "r000000000001", "title": "Q"}))
    m = sd / "mv" / "proj"
    (m / "output").mkdir(parents=True)
    (m / "project.json").write_text(json.dumps({"audio_file": "renders/r000000000001/audio.mp3", "output_mv": "P_MV.mp4", "title": "P"}))
    (m / "output" / "P_MV.mp4").write_bytes(b"v")
    vs = {v["id"]: v for v in client.get(f"/api/cover/songs/{sid}").json()["versions"]}
    allv = client.get("/api/cover/versions").json()
    assert sorted(x["id"] for x in allv["items"]) == ["v0000000001", "v0000000002"] and allv["bytes"] == 1006
    assert all(x["song_id"] == sid and x["song_title"] == "V" for x in allv["items"])
    one = vs["v0000000001"]
    assert one["format"] == "MP3" and one["bytes"] == 503
    assert sorted(x["kind"] for x in one["mvs"]) == ["full", "quick"] and vs["v0000000002"]["mvs"] == []
    assert one["mv_projects"] == [{"slug": f"{sid}_proj", "title": "P"}] and vs["v0000000002"]["mv_projects"] == []
    assert client.post(f"/api/open-folder", json={"song_id": sid, "rel": "../.."}).status_code == 404
    r = client.post(f"/api/open-folder", json={"song_id": sid, "rel": one["audio"]})
    assert r.json().get("error") == "open_folder_windows_only" or r.json().get("ok")
    res = client.post(f"/api/cover/songs/{sid}/versions/delete", json={"ids": ["v0000000001", "v0000000002", "vnope"]}).json()
    assert res["deleted"] == 2 and client.get(f"/api/cover/songs/{sid}").json()["versions"] == []
    assert res["freed"] >= 2 * 503                          # the versions' own audio counts in what was freed
    assert not (sd / "renders" / "r000000000001").exists()
    assert client.post(f"/api/cover/songs/{sid}/versions/delete", json={"ids": []}).status_code == 400
    # 🧹 clean-up: list first (nothing deleted), then delete; files a version still uses stay
    for rel, size in (("cover/rvc/old.wav", 300), ("cover/preview/abc_k2.mp3", 40), ("cover/rvc/used.wav", 10)):
        (sd / rel).parent.mkdir(parents=True, exist_ok=True)
        (sd / rel).write_bytes(b"x" * size)
    (sd / "cover" / "versions" / "v0000000003").mkdir(parents=True)
    (sd / "cover" / "versions" / "v0000000003" / "version.json").write_text(json.dumps(
        {"id": "v0000000003", "number": 3, "title": "#3", "plan": {"files": ["cover/rvc/used.wav"]}, "created_at": 1}))
    dry = client.get(f"/api/cover/songs/{sid}/cleanup").json()
    assert dry["kinds"] == {"rvc": {"files": 1, "bytes": 300}, "preview": {"files": 1, "bytes": 40}} and dry["total"] == 340
    assert (sd / "cover/rvc/old.wav").is_file()
    done = client.post(f"/api/cover/songs/{sid}/cleanup", json={}).json()
    assert done["freed"] == 340 and not (sd / "cover/rvc/old.wav").exists() and (sd / "cover/rvc/used.wav").is_file()
    assert client.get(f"/api/cover/songs/{sid}/cleanup").json()["total"] == 0


def test_harmless_separator_notices_stay_out_of_the_job_log():
    from app.jobs import HARMLESS_LOG_LINES, Job
    import dataclasses
    fields = {f.name for f in dataclasses.fields(Job)}
    job = Job.__new__(Job)
    job.log, job.log_total = [], 0
    job.add_log("2026-11-01 19:04:31,864 - WARNING - separator - CUDAExecutionProvider not available in "
                "ONNXruntime, so acceleration will NOT be enabled")
    job.add_log("WARNING - separator - Using soundfile for writing.")
    job.add_log("[lead] CUDA")
    assert [l[9:] for l in job.log] == ["[lead] CUDA"] and job.log_total == 1
    assert "log" in fields and len(HARMLESS_LOG_LINES) == 2


def test_recording_patch_merges_with_stored_record(root):
    """A field patch is merged with the record on disk: a newer change made meanwhile is kept, and only
    the allowed fields can be changed."""
    import json
    import struct
    import uuid
    import pytest
    from app.sing_archive import ArchiveError, RecordingArchive
    arc = RecordingArchive(root / "library" / "recordings")
    arc.ready()
    rid = str(uuid.uuid4())
    mix = b"RIFF" + b"\0" * 60
    meta = {"id": rid, "title": "t", "mime": "audio/wav", "created": 1, "seconds": 1, "bytes": len(mix),
            "complete": True, "postPending": True, "post": {"version": 1, "segments": []}}
    raw = json.dumps(meta).encode()
    bundle = root / f"{rid}.bin"
    bundle.write_bytes(struct.pack("<I", len(raw)) + raw + mix)
    arc.import_bundle(rid, bundle)
    stale = arc.get(rid)
    arc.update(rid, {**stale, "postPending": False})          # saved to post-production meanwhile
    out = arc.patch(rid, {"post.rmvpeAnalysis": {"source": "rmvpe-v1", "f0": [0, 220.5]}})
    assert out["postPending"] is False
    assert out["post"]["rmvpeAnalysis"]["f0"] == [0, 220.5] and out["post"]["segments"] == []
    for bad in ({"postPending": True}, {"bytes": 1}, {}, [], {"post.rmvpeAnalysis.x": 1}):
        with pytest.raises(ArchiveError):
            arc.patch(rid, bad)
    assert arc.get(rid)["postPending"] is False
