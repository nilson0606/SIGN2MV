"""AI cover workspace (/api/cover): parameters, plan, voice models, conversion, remix, sections, training.

Conversion tests need the engine (separation, mixing) and Applio with one voice
model: SIGN2MV_TEST_APPLIO_PYTHON, SIGN2MV_TEST_APPLIO_DIR, SIGN2MV_TEST_VOICE.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest import ENGINE_PY, VOICE_DIR, applio_available, wait_job
from test_p1_engine import import_file


def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


# ------------------------------------------------------------------ pure parts
def test_params_and_plan(tmp_path):
    from app import cover
    p = cover.clean_params({})
    assert p["rvc"]["envelope"] == 0.0 and p["vocal_mode"] == "lead_keep_backing" and p["backing_on"] is True
    assert p["mix"] == {"vocal_vol": 0.95, "bgm_vol": 0.85, "inst_vol": 0.0, "instrument": "none",
                        "octave_shift": 99, "reverb_wet": 0.1}
    with pytest.raises(cover.CoverError):
        cover.validate(p)                                      # no model
    p = cover.clean_params({"model": "Voice_A", "pitch": 40, "key": -20, "rvc": {"protect": 2, "f0": "bad"},
                            "masks": [{"start": 5, "end": 2}, {"start": 1, "end": 2, "mode": "rvc"},
                                      {"start": 3, "end": 4, "mode": "file", "file": "../x.wav"},
                                      {"start": 6, "end": 7, "mode": "original"}],
                            "vol_segments": [{"track": "backing", "start": 1, "end": 3, "gain": 1.5},
                                             {"track": "vocal", "start": 1, "end": 3, "gain": 1.0}]})
    assert (p["pitch"], p["key"], p["rvc"]["protect"], p["rvc"]["f0"]) == (12, -8, 0.5, "rmvpe")   # old ±12
    assert [m["mode"] for m in p["masks"]] == ["rvc", "original"]
    assert p["masks"][0]["rvc"]["model"] == "Voice_A" and p["masks"][0]["rvc"]["pitch"] == 12
    sec = cover.clean_params({"model": "A", "masks": [{"start": 1, "end": 2, "mode": "rvc", "rvc": {"pitch": -20}}]})
    assert sec["masks"][0]["rvc"]["pitch"] == -20                 # re-converted sections keep ±24 (as the old page)
    assert p["vol_segments"] == [{"track": "backing", "start": 1.0, "end": 3.0, "gain": 1.5}]
    assert cover.clean_model_name("bad name") == "" and cover.clean_model_name("Ok_1__e20") == "Ok_1__e20"

    song_dir = tmp_path / "song"
    (song_dir / "source").mkdir(parents=True)
    song = {"source": {"audio": "source/audio.wav", "source_hash": "abc"}}
    resolve = lambda name: {"pth": f"/m/{name}.pth", "index": "", "sig": name}  # noqa: E731
    p = cover.clean_params({"model": "A", "pitch": 2, "key": 3, "masks": [
        {"start": 1, "end": 2, "mode": "original"}, {"start": 3, "end": 4, "mode": "rvc", "rvc": {"model": "B"}},
        {"start": 5, "end": 6, "mode": "rvc", "sep": {"sep_model": "bs_roformer", "vocal_mode": "lead_keep_backing"}}]})
    pl = cover.plan(song_dir, song, p, resolve)
    assert pl["need_gpu"] and [l["kind"] for l in pl["layers"]] == ["mix", "lead"]
    main = next(t for t in pl["rvc_tasks"] if t["label"] == "main")
    assert main["pitch"] == 5 and main["input"] == pl["tracks"]["lead"]           # pitch + key, lead converted
    assert pl["bgm"].startswith("keys/") and pl["backings"][0].startswith("keys/")  # accompaniment shifted
    assert pl["orig_vocal"].startswith("keys/")                                    # 'original' sections in key
    from app import stems as stems_mod                                             # key copies shared per track
    assert pl["bgm"] == stems_mod.key_track(pl["tracks"]["instrumental"], 3)[1]
    assert len(pl["rvc_tasks"]) == 3 and len(pl["cut_jobs"]) == 1 and len(pl["seg_jobs"]) == 1
    assert [m["target"] for m in pl["masks"] if m["mode"] == "replace"] == ["vocal", "vocal", "bgm"]
    # same settings -> same cache names; another model -> another converted vocal
    assert cover.plan(song_dir, song, p, resolve)["vocal"] == pl["vocal"]
    p2 = cover.clean_params(dict(p, model="C"))
    assert cover.plan(song_dir, song, p2, resolve)["vocal"] != pl["vocal"]
    # x2 lead and male/female recipes
    px = cover.clean_params({"model": "A", "vocal_mode": "lead_keep_backing_x2"})
    plx = cover.plan(song_dir, song, px, resolve)
    assert [l["kind"] for l in plx["layers"]] == ["mix", "lead", "lead"] and len(plx["backings"]) == 2
    # becruily lead split (old 卡拉OK模型): own cache keys; aufr33 keeps the old keys and is not stored
    assert "karaoke_model" not in cover.clean_params({"model": "A", "karaoke_model": "aufr33"})
    pb = cover.clean_params({"model": "A", "karaoke_model": "becruily"})
    plb = cover.plan(song_dir, song, pb, resolve)
    pla = cover.plan(song_dir, song, cover.clean_params({"model": "A"}), resolve)
    assert [l["model"] for l in plb["layers"] if l["kind"] == "lead"] == ["karaoke_becruily"]
    assert plb["tracks"]["lead"] != pla["tracks"]["lead"] and plb["tracks"]["vocals"] == pla["tracks"]["vocals"]
    assert stems_mod.normalize({"lead": True, "karaoke": "aufr33"}) == stems_mod.normalize({"lead": True})
    with pytest.raises(stems_mod.RecipeError):
        stems_mod.normalize({"lead": True, "karaoke": "nope"})
    assert cover.clean_sep({"vocal_mode": "lead_keep_backing", "karaoke_model": "becruily"})["karaoke_model"] == "becruily"
    assert "karaoke_model" not in cover.clean_sep({"vocal_mode": "full", "karaoke_model": "becruily"})
    pm = cover.clean_params({"model": "A", "mf": {"sep_model": "aufr33", "male": {"keep": True},
                                                  "female": {"model": "B", "pitch": 3, "vol": 1.2}}})
    plm = cover.plan(song_dir, song, pm, resolve)
    assert [l["kind"] for l in plm["layers"]] == ["mix", "male_female"] and plm["backings"] == []
    assert plm["vocal"]["combine"]["male"] == plm["tracks"]["male"] and len(plm["rvc_tasks"]) == 1
    assert cover.version_label(pm) == "Original + B +3"
    # remix reuses the version's converted vocal: no model needed, file stays referenced
    (song_dir / "cover" / "rvc").mkdir(parents=True)
    (song_dir / "cover" / "rvc" / "old.wav").write_bytes(b"x")
    def no_model(name):
        raise AssertionError("model resolved")
    plr = cover.plan(song_dir, song, cover.clean_params({"model": "Gone"}), no_model, reuse={"path": "cover/rvc/old.wav"})
    assert plr["vocal"]["path"] == "cover/rvc/old.wav" and plr["rvc_tasks"] == [] and "cover/rvc/old.wav" in plr["files"]
    # backing vocals converted too (off by default): same model and pitch + key, both x2 backings
    assert cover.clean_params({})["backing_rvc"] is False
    pbv = cover.clean_params({"model": "A", "pitch": 2, "key": 3, "backing_rvc": True})
    plv = cover.plan(song_dir, song, pbv, resolve)
    bt = [t for t in plv["rvc_tasks"] if t["label"] == "backing"]
    assert len(bt) == 1 and bt[0]["pitch"] == 5 and bt[0]["input"] == plv["tracks"]["backing"]
    assert plv["backings"] == [bt[0]["output"]] and bt[0]["output"] in plv["files"]
    assert cover.version_label(pbv) == "A +2 · Key +3 · Backing VC"
    plv2 = cover.plan(song_dir, song, cover.clean_params({"model": "A", "vocal_mode": "lead_keep_backing_x2",
                                                        "backing_rvc": True}), resolve)
    assert sorted(t["label"] for t in plv2["rvc_tasks"]) == ["backing", "backing2", "main"]
    # no effect without the backing in the mix, or without the lead split
    off = cover.clean_params({"model": "A", "backing_rvc": True, "backing_on": False})
    assert cover.plan(song_dir, song, off, resolve)["backings"] == [] and "Backing" not in cover.version_label(off)
    full = cover.clean_params({"model": "A", "backing_rvc": True, "vocal_mode": "full"})
    assert len(cover.plan(song_dir, song, full, resolve)["rvc_tasks"]) == 1
    # a remix reuses the version's converted backing: no model needed
    (song_dir / "cover" / "rvc" / "bv.wav").write_bytes(b"x")
    plrb = cover.plan(song_dir, song, cover.clean_params({"model": "Gone", "backing_rvc": True}), no_model,
                      reuse={"path": "cover/rvc/old.wav"}, reuse_backings=["cover/rvc/bv.wav"])
    assert plrb["backings"] == ["cover/rvc/bv.wav"] and plrb["rvc_tasks"] == []


def fake_model(folder: Path, name: str, epochs=(10, 20)) -> Path:
    d = folder / name
    (d / "epochs").mkdir(parents=True)
    (d / f"{name}_30e.pth").write_bytes(b"pth" * 100)
    (d / f"{name}.index").write_bytes(b"idx")
    (d / "模型說明.txt").write_text("說明", encoding="utf-8")
    for e in epochs:
        (d / "epochs" / f"{name}_{e}e_{e * 7}s.pth").write_bytes(b"e" * e)
    (d / "epochs" / "loss.json").write_text(json.dumps({"epoch": [1, 2], "mel": [30.0, 25.0], "final_epoch": 30}))
    return d


def test_voice_models(client, root, tmp_path):
    from app import cover
    d = tmp_path / "logs_like"
    d.mkdir()
    (d / "G_2333333.pth").write_bytes(b"g")
    (d / "Alice_100e_700s.pth").write_bytes(b"a")
    assert cover.model_files(d)[0].name == "Alice_100e_700s.pth"
    single = client.post("/api/cover/models/import", json={"path": str(d / "Alice_100e_700s.pth")}).json()
    assert single["imported"] == ["Alice"]
    old = tmp_path / "old_models"
    fake_model(old, "Voice_A")
    fake_model(old, "Voice_B")
    (old / "中文模型").mkdir()
    (old / "中文模型" / "x.pth").write_bytes(b"x")
    st = client.get("/api/cover/status").json()
    assert [m["name"] for m in st["models"]] == ["Alice"]
    assert st["separators"]["becruily"] is False and st["becruily"]["path"].endswith("mel_band_roformer_karaoke_becruily.ckpt")
    assert st["becruily"]["url"].startswith("https://")
    assert client.delete("/api/cover/models/Alice").status_code == 200
    res = client.post("/api/cover/models/import", json={"path": str(old)}).json()
    assert sorted(res["imported"]) == ["Voice_A", "Voice_B"]
    assert res["skipped"] == [{"source": "中文模型", "reason": "invalid_model_name"}]
    again = client.post("/api/cover/models/import", json={"path": str(old / "Voice_A")}).json()
    assert again["imported"] == [] and again["skipped"][0]["reason"] == "model_exists"
    named = client.post("/api/cover/models/import", json={"path": str(old / "中文模型"), "name": "Chinese_1"}).json()
    assert named["imported"] == ["Chinese_1"]
    models = {m["name"]: m for m in client.get("/api/cover/models").json()["models"]}
    a = models["Voice_A"]
    assert a["pth"] == "Voice_A_30e.pth" and a["index"] == "Voice_A.index" and [e["epoch"] for e in a["epochs"]] == [10, 20]
    assert a["has_loss"] and "說明" in a["description"]
    loss = client.get("/api/cover/models/Voice_A/loss").json()
    assert loss["source"] == "saved" and loss["kept_epochs"] == [10, 20, 30]
    assert client.delete("/api/cover/models/Voice_A/epochs/10").json()["freed"] == 10
    assert client.delete("/api/cover/models/Voice_A/epochs/10").status_code == 404
    # default model = the newest when nothing was used yet
    assert client.get("/api/cover/status").json()["defaults"]["model"] in models
    # upload
    up = client.post("/api/cover/models/upload", data={"name": "Up 1"},
                     files={"pth": ("w.pth", b"w" * 50), "index": ("w.index", b"i")}).json()
    assert up["name"] == "Up_1" and (root / "models" / "voices" / "Up_1" / "w.index").is_file()
    assert client.post("/api/cover/models/upload", data={"name": "Up_1"}, files={"pth": ("w.pth", b"w")}).status_code == 409
    assert client.delete("/api/cover/models/Up_1").status_code == 200
    assert not (root / "models" / "voices" / "Up_1").exists()
    assert client.delete("/api/cover/models/../x").status_code in (404, 405)
    # training needs Applio + a valid English name
    assert client.post("/api/cover/train", json={"name": "我的"}).json()["error"] == "invalid_model_name"


def test_cover_needs_song_and_model(client, root):
    song = client.post("/api/songs", json={"title": "x"}).json()
    sid = song["song_id"]
    assert client.post(f"/api/cover/songs/{sid}/run", json={"params": {"model": "A"}}).json()["error"] == "song_has_no_audio"
    st = client.get(f"/api/cover/songs/{sid}").json()
    assert st["versions"] == [] and st["settings"]["vocal_mode"] == "lead_keep_backing"
    saved = client.put(f"/api/cover/songs/{sid}/settings", json={"params": {"model": "A", "key": 3}}).json()
    assert saved["settings"]["key"] == 3
    assert client.get(f"/api/cover/songs/{sid}").json()["settings"]["key"] == 3
    # audio is served from memory (no file handle kept open), with ranges
    f = root / "library" / "songs" / sid / "renders" / "rtest" / "audio.mp3"
    f.parent.mkdir(parents=True)
    f.write_bytes(bytes(range(256)) * 4)
    full = client.get(f"/media/{sid}/renders/rtest/audio.mp3")
    assert full.status_code == 200 and len(full.content) == 1024 and full.headers["accept-ranges"] == "bytes"
    part = client.get(f"/media/{sid}/renders/rtest/audio.mp3", headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and part.content == bytes(range(10, 20))
    assert part.headers["content-range"] == "bytes 10-19/1024"
    tail = client.get(f"/media/{sid}/renders/rtest/audio.mp3", headers={"Range": "bytes=-4"})
    assert tail.content == bytes(range(252, 256))
    f.unlink()   # nothing holds it
    # finished jobs can be cleared from the list
    assert client.post("/api/jobs/clear-finished").json()["cleared"] >= 0


# ------------------------------------------------------------------ conversion (engine + Applio)
need_applio = pytest.mark.skipif(not applio_available(), reason="Applio test environment not configured")


def import_voice(client) -> str:
    res = client.post("/api/cover/models/import", json={"path": VOICE_DIR}).json()
    return res["imported"][0]


def run_job(client, resp, timeout=1800):
    data = resp.json()
    assert resp.status_code == 200, data
    job = wait_job(client, data["job"]["id"], timeout)
    assert job["status"] == "succeeded", (job["error_code"], job["error_message"])
    return data, job


@need_applio
def test_cover_full_flow(client, root, tmp_path):
    voice = import_voice(client)
    song = import_file(client, tmp_path, video=False, secs=20)
    sid = song["song_id"]
    sdir = root / "library" / "songs" / sid
    params = {"model": voice}    # defaults: lead split, keep backing, envelope 0

    data, job = run_job(client, client.post(f"/api/cover/songs/{sid}/run", json={"params": params}))
    assert job["lane"] == "gpu"
    st = client.get(f"/api/cover/songs/{sid}").json()
    assert len(st["versions"]) == 1
    v1 = st["versions"][0]
    assert v1["number"] == 1 and v1["audio"].endswith("audio.mp3") and v1["label"] == voice
    st1 = v1["stats"]   # timing shown on the version: start-up vs conversion, mix steps
    assert st1["rvc_load_s"] > 0 and st1["rvc_convert_s"] > 0 and st1["rvc_device"]
    assert st1["rvc_load_s"] + st1["rvc_convert_s"] <= st1["rvc_s"] + 1
    assert "mix_master" in st1["mix_steps"]
    mp3 = sdir / v1["audio"]
    assert abs(probe_duration(mp3) - 20) < 0.5
    rj = json.loads((sdir / "renders" / v1["render_id"] / "render.json").read_text(encoding="utf-8"))
    assert rj["kind"] == "cover" and rj["cover_version"] == v1["id"] and "AI" not in rj["title"]
    # the MV workspace offers the cover as MV audio
    audios = client.get("/api/mv/projects").json()["available_audios"]
    assert any(a.get("render_id") == v1["render_id"] and a["kind"] == "cover" for a in audios)
    # the last settings become the defaults
    assert client.get("/api/cover/status").json()["defaults"]["model"] == voice
    tracks = {t["key"] for t in client.get(f"/api/cover/songs/{sid}/versions/{v1['id']}/tracks").json()["tracks"]}
    assert {"mix", "vocals", "instrumental", "lead", "backing", "ai_vocal"} <= tracks

    # quick remix of volumes only: CPU lane, same render replaced in place
    before = mp3.stat().st_mtime
    d2, job2 = run_job(client, client.post(f"/api/cover/songs/{sid}/versions/{v1['id']}/remix",
                                           json={"mix": {"vocal_vol": 0.5, "bgm_vol": 1.0},
                                                 "vol_segments": [{"track": "backing", "start": 2, "end": 6, "gain": 0}]}))
    assert job2["lane"] == "cpu" and d2["version_id"] == v1["id"]
    assert mp3.stat().st_mtime > before and len(client.get(f"/api/cover/songs/{sid}").json()["versions"]) == 1

    # sections: upload a clip, mute / original / re-convert / external clip converted, instrument; as a new version
    clip = tmp_path / "clip.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=3",
                    str(clip)], check=True)
    patch = client.post(f"/api/cover/songs/{sid}/patches", files={"file": ("我的片段.wav", clip.read_bytes())}).json()
    assert patch["file"].startswith("up_") and abs(patch["duration"] - 3) < 0.1
    masks = [{"start": 1, "end": 2, "mode": "mute"}, {"start": 3, "end": 4, "mode": "original"},
             {"start": 6, "end": 8, "mode": "rvc", "rvc": {"model": voice, "pitch": 2}},
             {"start": 10, "end": 12, "mode": "file", "file": patch["file"], "to_ai": True, "rvc": {"model": voice}}]
    d3, job3 = run_job(client, client.post(f"/api/cover/songs/{sid}/versions/{v1['id']}/remix", json={
        "save_as_new": True, "masks": masks, "mix": {"instrument": "steel_guitar", "inst_vol": 0.6}}))
    assert job3["lane"] == "gpu" and d3["version_id"] != v1["id"]
    vers = {v["id"]: v for v in client.get(f"/api/cover/songs/{sid}").json()["versions"]}
    v2 = vers[d3["version_id"]]
    assert v2["number"] == 2 and v2["source_version"] == v1["id"] and v2["instrument_used"] is True
    assert v2["render_id"] != v1["render_id"]
    assert list((sdir / "cover" / "midi").glob("*.mid"))
    assert len(list((sdir / "cover" / "rvc").glob("*.wav"))) == 3    # main + section + external clip

    # key +2: new conversion, accompaniment shifted
    d4, job4 = run_job(client, client.post(f"/api/cover/songs/{sid}/run", json={"params": dict(params, key=2)}))
    v4 = next(v for v in client.get(f"/api/cover/songs/{sid}").json()["versions"] if v["id"] == d4["version_id"])
    assert v4["label"] == f"{voice} · Key +2" and list((sdir / "keys").glob("*_p2/instrumental.wav"))

    # rename and delete: renders go too, unused cache files are collected
    assert client.patch(f"/api/cover/songs/{sid}/versions/{v4['id']}", json={"title": "升 Key 版"}).json()["title"] == "升 Key 版"
    n_rvc = len(list((sdir / "cover" / "rvc").glob("*.wav")))
    assert client.delete(f"/api/cover/songs/{sid}/versions/{v4['id']}").status_code == 200
    assert not (sdir / "renders" / v4["render_id"]).exists()
    assert len(list((sdir / "cover" / "rvc").glob("*.wav"))) == n_rvc - 1
    # key preview of the original
    kp = client.post(f"/api/cover/songs/{sid}/key_preview", json={"key": -3}).json()
    assert kp["path"].endswith("_k-3.mp3") and (sdir / kp["path"]).is_file()
    # the voice model is deleted: a volume remix still works from the version's converted vocal
    assert client.delete(f"/api/cover/models/{voice}").status_code == 200
    d5, job5 = run_job(client, client.post(f"/api/cover/songs/{sid}/versions/{v1['id']}/remix",
                                           json={"mix": {"vocal_vol": 0.8}}))
    assert job5["lane"] == "cpu"
    assert client.post(f"/api/cover/songs/{sid}/run", json={"params": params}).json()["error"] == "model_not_found"


@need_applio
def test_cover_male_female(client, root, tmp_path):
    """Duet mode with a prepared male/female layer (the separation model itself is covered by P1 tests)."""
    from app import cover
    import soundfile as sf
    voice = import_voice(client)
    song = import_file(client, tmp_path, video=False, secs=12)
    sid = song["song_id"]
    sdir = root / "library" / "songs" / sid
    p = cover.clean_params({"model": voice, "mf": {"sep_model": "aufr33", "male": {"keep": True, "vol": 0.8},
                                                   "female": {"model": voice, "pitch": 5}}})
    layers, tracks = cover.stems_mod.plan(sdir, song, cover.recipe_for(p))
    # run the vocals layer for real, then fake the male/female split from it
    first = run_job(client, client.post(f"/api/songs/{sid}/stems", json={"recipe": {"model": "demucs"}}))
    mf_layer = next(l for l in layers if l["kind"] == "male_female")
    d = sdir / "stems" / mf_layer["key"]
    d.mkdir(parents=True)
    x, sr = sf.read(str(sdir / tracks["vocals"]), dtype="float32")
    sf.write(str(d / "male.wav"), x * 0.5, sr, subtype="FLOAT")
    sf.write(str(d / "female.wav"), x * 0.5, sr, subtype="FLOAT")
    (d / "info.json").write_text(json.dumps({"key": mf_layer["key"], "kind": "male_female"}))
    del first
    data, job = run_job(client, client.post(f"/api/cover/songs/{sid}/run", json={"params": p}))
    v = client.get(f"/api/cover/songs/{sid}").json()["versions"][0]
    assert v["label"] == f"Original + {voice} +5"
    tracks_out = {t["key"] for t in client.get(f"/api/cover/songs/{sid}/versions/{v['id']}/tracks").json()["tracks"]}
    assert {"male", "female", "ai_male", "ai_female", "ai_vocal"} <= tracks_out
    assert (sdir / v["audio"]).stat().st_size > 100_000
    # change only the male/female volumes: remix without converting again
    d2, job2 = run_job(client, client.post(f"/api/cover/songs/{sid}/versions/{v['id']}/remix",
                                           json={"mf_vols": {"male": 1.5, "female": 0.5}}))
    assert job2["lane"] == "cpu"
    assert client.post(f"/api/cover/songs/{sid}/run", json={"params": {
        "model": voice, "mf": {"male": {"keep": True}, "female": {"keep": True}}}}).json()["error"] == "mf_both_original"


@pytest.mark.skipif(not applio_available() or not ENGINE_PY, reason="Applio test environment not configured")
def test_train_smoke(client, root, tmp_path):
    """Two CPU epochs on a short synthetic voice: the whole 6-step pipeline and the install."""
    wav = tmp_path / "voice.wav"
    subprocess.run([ENGINE_PY, str(Path(__file__).parent / "synth_song.py"), str(wav), "40", "--voice-only"],
                   check=True)
    up = client.post("/api/cover/train/files", files=[("files", ("我的聲音.wav", wav.read_bytes()))]).json()
    assert len(up["files"]) == 1
    res = client.post("/api/cover/train", json={"name": "Smoke_1", "token": up["token"], "epochs": 2,
                                                "save_every": 1, "batch_size": 1})
    data = res.json()
    assert res.status_code == 200, data
    job = wait_job(client, data["job"]["id"], 3600)
    assert job["status"] == "succeeded", (job["error_code"], job["error_message"])
    m = next(m for m in client.get("/api/cover/models").json()["models"] if m["name"] == "Smoke_1")
    assert m["pth"] == "Smoke_1_2e.pth" and m["index"] and [e["epoch"] for e in m["epochs"]] == [1]
    if m["has_loss"]:   # TensorBoard flushes lazily: a 2-epoch run may end before anything was written
        loss = client.get("/api/cover/models/Smoke_1/loss").json()
        assert loss["source"] == "saved" and loss["final_epoch"] == 2
    assert not (root / "runtime" / "applio-logs" / "Smoke_1").exists()        # scratch cleaned
    assert client.post("/api/cover/train", json={"name": "Smoke_1", "token": up["token"]}).json()["error"] in (
        "model_exists", "train_no_audio")


def test_new_song_takes_only_the_voice_model(client, root):
    """A song without cover settings starts from the defaults, keeping only the last cover's voice model;
    pitch, accompaniment key, separation and mix of the last song stay with it."""
    vdir = root / "models" / "voices" / "Last_Voice"
    vdir.mkdir(parents=True)
    (vdir / "Last_Voice.pth").write_bytes(b"x" * 1024)
    last = {"model": "Last_Voice", "pitch": 5, "key": -4, "sep_model": "bs_roformer", "vocal_mode": "all",
            "mix": {"vocal_vol": 1.5, "bgm_vol": 0.4}}
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "cover_defaults.json").write_text(json.dumps(last), encoding="utf-8")
    d = client.get("/api/cover/status").json()["defaults"]
    assert d["model"] == "Last_Voice" and d["pitch"] == 0
    assert d["key"] == 0 and d["sep_model"] == "demucs" and d["vocal_mode"] == "lead_keep_backing"
    assert d["mix"]["vocal_vol"] != 1.5 and d["masks"] == [] and d["vol_segments"] == []
