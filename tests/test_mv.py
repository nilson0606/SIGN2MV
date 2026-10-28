"""MV workspace (/api/mv) with the real engine (CPU): projects, photos, Whisper alignment
(faster-whisper replaced by tests/fakes), karaoke timing, render and verification."""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from conftest import REPO, engine_available, wait_job
from test_p1_engine import import_file

pytestmark = pytest.mark.skipif(not engine_available(), reason="engine environment not configured")


@pytest.fixture()
def fake_whisper(root, monkeypatch, tmp_path):
    wdir = root / "models_whisper"
    for size in ("medium", "small"):
        (wdir / size).mkdir(parents=True)
        (wdir / size / "model.bin").write_bytes(b"x")
    log = tmp_path / "whisper_calls.jsonl"
    monkeypatch.setenv("SIGN2MV_WHISPER_DIR", str(wdir))
    monkeypatch.setenv("PYTHONPATH", str(REPO / "tests" / "fakes"))
    monkeypatch.setenv("FAKE_WHISPER_LOG", str(log))
    return log


def png(color):
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), color).save(buf, "PNG")
    return buf.getvalue()


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_mv_project_whisper_render(client, root, tmp_path, fake_whisper):
    song = import_file(client, tmp_path, video=True, secs=20)
    sid = song["song_id"]
    client.put("/api/settings", json={"cover_singer_name": "Tester", "studio_name": "Test Studio"})

    lst = client.get("/api/mv/projects").json()
    assert lst["projects"] == [] and any(s["song_id"] == sid for s in lst["songs"])
    mix = next(a for a in lst["available_audios"] if a["song_id"] == sid and a["kind"] == "mix")
    assert lst["brand"]["singer"] == "Tester"

    # create: the song's mix is the default audio; names come from the settings
    created = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "demo", "title": "測試歌",
                                                          "scene_count": 3, "original_singer": "原唱人"}).json()
    proj = created["project"]
    slug = proj["slug"]
    assert slug == f"{sid}_demo" and proj["audio_file"] == mix["path"]
    assert proj["cover_singer"] == "Tester" and proj["studio"] == "Test Studio" and "AI" not in proj["badge"]
    assert client.post("/api/mv/project/create", json={"song_id": sid, "slug": "demo"}).status_code == 409
    pdir = root / "library" / "songs" / sid / "mv" / "demo"
    stored = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    assert stored["audio_file"] == "source/audio.wav"   # stored relative to the song

    # photos: batch upload fills slots 1..3
    files = [("files", (f"p{i}.png", png(c), "image/png")) for i, c in enumerate(["red", "green", "blue"], 1)]
    up = client.post("/api/mv/upload_scenes_batch", data={"slug": slug, "start_scene": "1", "fill_empty": "1"}, files=files).json()
    assert up["count"] == 3 and (pdir / "scenes" / "scene_03.png").is_file()
    assert Image.open(pdir / "scenes" / "scene_01.png").size == (1920, 1080)

    # Whisper alignment: separation (real Demucs) + transcription (fake) + DP alignment
    lyrics = "[Scene 01] ～ 前奏 ～\n一二三四\n五六七八\n九十一二\n[Scene 03] ～ 尾奏 ～"
    res = client.post("/api/mv/paste_lyrics", json={"slug": slug, "lyrics_text": lyrics, "mode": "whisper_align"}, timeout=900)
    data = res.json()
    assert res.status_code == 200, data
    assert data["fallback_used"] is False, data.get("warning")
    tl = data["project"]["timeline"]
    lyric = [s for s in tl if s["type"] == "lyric"]
    assert [s["text"] for s in lyric] == ["一二三四", "五六七八", "九十一二"]
    assert abs(tl[-1]["end"] - 20) < 0.3 and tl[0]["start"] == 0
    calls = [json.loads(x) for x in fake_whisper.read_text().splitlines()]
    assert len(calls) == 1 and calls[0]["audio"].endswith("vocals.wav")   # transcribed the separated vocals
    w = json.loads((pdir / "whisper.json").read_text(encoding="utf-8"))
    assert w["pipeline"] == "vocals_v1" and w["refine"]["vad_refined"] and w["segments"]
    # the vocals came from the song's stem cache (shared with sing & record / cover)
    assert any((root / "library" / "songs" / sid / "stems").glob("*/vocals.wav"))
    # second alignment uses the cached transcript
    res2 = client.post("/api/mv/paste_lyrics", json={"slug": slug, "lyrics_text": lyrics, "mode": "whisper_align"}).json()
    assert res2["whisper_source"] == "cache" and len(fake_whisper.read_text().splitlines()) == 1

    kara = client.post("/api/mv/karaoke_times", json={"slug": slug}).json()
    assert kara["has_whisper"]
    seg = next(x for x in kara["segments"] if x)
    assert all(t is not None for t in seg["times"]) and seg["times"] == sorted(seg["times"])

    det = client.post("/api/mv/interlude/detect", json={"slug": slug, "min_gap": 2}).json()
    assert det["status"] == "ok"

    prev = client.post("/api/mv/preview_frame", json={"slug": slug, "seg_idx": 1}).json()
    img = client.get("/api/mv/media", params={"path": prev["preview_path"]})
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert client.get("/api/mv/media", params={"path": str(REPO / "app" / "server.py")}).status_code == 403

    # render (GPU lane job; libx264 here) -> 1080p 60 fps MP4 with audio, check frames
    r = client.post("/api/mv/render", json={"slug": slug}, timeout=1800)
    out = r.json()
    assert r.status_code == 200, out
    mp4 = Path(out["output_mv"])
    assert mp4.is_file() and mp4.parent == pdir / "output"
    info = probe(mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["r_frame_rate"]) == (1920, 1080, "60/1")
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert abs(float(info["format"]["duration"]) - 20) < 0.6
    assert out["verification"]["frames"] and not list((pdir / "output").glob("*.rendering.mp4"))
    jobs = client.get("/api/jobs").json()["jobs"]
    assert any(j["kind"] == "mv_render" and j["status"] == "succeeded" for j in jobs)
    rng = client.get("/api/mv/media", params={"path": str(mp4)}, headers={"Range": "bytes=0-99"})
    assert rng.status_code == 206 and len(rng.content) == 100

    full = client.get(f"/api/mv/project/{slug}").json()
    assert full["mv_probe"]["exists"] and full["verification"]["frames"]

    # import an exported project JSON as a new project of the same song
    old_style = {k: v for k, v in full["project"].items() if k not in ("name", "song_id")}   # like an old MV Studio JSON
    imp = client.post("/api/mv/project/import", json={"song_id": sid, "project": dict(old_style, slug="old_slug")}).json()
    assert imp["project"]["slug"] == f"{sid}_old_slug" and imp["project"]["timeline"] == full["project"]["timeline"]

    d = client.post("/api/mv/projects/delete", json={"slugs": [slug, imp["project"]["slug"]]}).json()
    assert sorted(d["deleted"]) == sorted([slug, imp["project"]["slug"]]) and not pdir.exists()
    assert (root / "library" / "songs" / sid / "source" / "audio.wav").is_file()   # song audio untouched


def test_mv_no_ai_text(client, root, tmp_path):
    from app.mvstudio import core
    core.configure(root / "library", "Ann", "Ann Studio", "zh")
    assert core.sanitize_no_ai("AI 翻唱 版") == "Ann 翻唱 版"
    assert core.sanitize_no_ai("AI Cover") == "Ann 翻唱"
    core.configure(root / "library", "", "", "zh")
    assert "AI" not in core.sanitize_no_ai("AI 翻唱 by AI")
    assert core.default_badge() == "翻唱" and core.default_badge("en") == "Cover"


def test_quick_mv(client, root, tmp_path, monkeypatch):
    """Quick MV: audio-reactive title card from the song's audio (sing_record's picture)."""
    fonts = sorted(Path("/usr/share/fonts/opentype/noto").glob("NotoSansCJK-Regular.ttc"))
    if not fonts:
        pytest.skip("no CJK font in this environment")
    monkeypatch.setenv("SIGN2MV_MV_FONT", str(fonts[0]))
    song = import_file(client, tmp_path, video=False, secs=12)
    sid = song["song_id"]
    client.put("/api/settings", json={"cover_singer_name": "Nilson", "language": "zh-TW"})

    info = client.get(f"/api/songs/{sid}/quickmv").json()
    assert info["font_ok"] and info["items"] == []
    assert info["sources"][0]["id"] == "original" and info["defaults"]["artist"] == "Nilson"
    title = info["defaults"]["title"]

    # bad input is refused before a job starts
    assert client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "", "artist": "x"}).status_code == 400
    assert client.post(f"/api/songs/{sid}/quickmv", json={"source": "nope", "title": "t", "artist": "x"}).status_code == 400
    assert client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "a\nb", "artist": "x"}).status_code == 400

    res = client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "AI 翻唱 測試", "artist": "Nilson"}).json()
    done = wait_job(client, res["job"]["id"], 600)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    items = client.get(f"/api/songs/{sid}/quickmv").json()["items"]
    assert len(items) == 1
    it = items[0]
    assert it["title"] == "Nilson 翻唱 測試"           # never shows "AI"
    assert it["artist_line"] == "翻唱｜Nilson" and it["source"] == "original"
    sdir = root / "library" / "songs" / sid
    video = sdir / it["path"]
    pr = probe(video)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["r_frame_rate"]) == (1920, 1080, "30/1")
    assert any(s["codec_type"] == "audio" for s in pr["streams"])
    assert abs(float(pr["format"]["duration"]) - 12) < 0.3
    assert not list((sdir / "quickmv").glob("*.tmp*"))        # scratch removed
    assert sorted(p.name for p in video.parent.iterdir()) == ["info.json", "video.mp4"]

    # the picture: dark card, teal accent bar, white title pixels, bars at the bottom
    frame = tmp_path / "f.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "5", "-i", str(video), "-frames:v", "1", str(frame)], check=True)
    img = Image.open(frame).convert("RGB")
    assert img.getpixel((40, 40))[2] > img.getpixel((40, 40))[0]               # navy background
    r, g, b = img.getpixel((200, 152))
    assert g > 150 and b > 150 and r < 160                                      # teal accent bar
    title_band = img.crop((160, 300, 1760, 400)).convert("L")
    assert max(title_band.getdata()) > 230                                      # white title text

    dl = client.get(f"/api/songs/{sid}/quickmv/{it['id']}/download")
    assert dl.status_code == 200 and "MV_" in dl.headers["content-disposition"]
    usage = client.get(f"/api/songs/{sid}/storage").json()
    assert usage["counts"]["quick_mvs"] == 1 and usage["categories"]["mv"] >= video.stat().st_size

    resp = client.delete(f"/api/songs/{sid}/quickmv/{it['id']}").json()
    assert resp.get("ok"), resp
    assert client.get(f"/api/songs/{sid}/quickmv").json()["items"] == []

    # every song's quick MVs: list, delete selected, delete all (sign_record's saved-MV panel)
    for name in ("one", "two"):
        j = client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": name, "artist": "Nilson"}).json()
        assert wait_job(client, j["job"]["id"], 600)["status"] == "succeeded"
    allq = client.get("/api/quickmv").json()
    assert sorted(i["title"] for i in allq["items"]) == ["one", "two"] and allq["bytes"] > 0
    assert all(i["song_id"] == sid and i["song_title"] for i in allq["items"])
    first = allq["items"][0]
    assert client.post("/api/quickmv/delete", json={"items": [{"song_id": sid, "id": first["id"]},
                                                               {"song_id": sid, "id": "qbad"}]}).json() == {"deleted": 1, "skipped": 1}
    assert client.post("/api/quickmv/delete", json={"items": []}).status_code == 400
    assert client.post("/api/quickmv/delete", json={"all": True}).json()["deleted"] == 1
    assert client.get("/api/quickmv").json()["items"] == []
    assert client.delete(f"/api/songs/{sid}/quickmv/qzzzzzzzzzzzz").status_code == 404
