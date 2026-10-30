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
    assert len(calls) == 1 and calls[0]["audio"] == "samples" and abs(calls[0]["seconds"] - 20) < 0.5
    w = json.loads((pdir / "whisper.json").read_text(encoding="utf-8"))
    assert w["transcribed_from"] in ("vocals", "lead")   # transcribed the separated vocals
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
    # old JSONs carry full paths: photos, Whisper result, finished MV and outside audio are copied in
    ext = tmp_path / "old_project"
    (ext / "illust").mkdir(parents=True)
    Image.new("RGB", (64, 64), (200, 30, 30)).save(ext / "illust" / "p1.png")
    (ext / "illust" / "notes.txt").write_text("x")
    (ext / "whisper.json").write_text('{"segments": []}', encoding="utf-8")
    import shutil as _sh
    _sh.copy2(root / "library" / "songs" / sid / "source" / "audio.wav", ext / "cover.wav")
    old_full = dict(old_style, slug="old_full", illust_dir=str(ext / "illust"), whisper_json=str(ext / "whisper.json"),
                    output_mv=str(mp4), audio_file=str(ext / "cover.wav"))
    imp2 = client.post("/api/mv/project/import", json={"song_id": sid, "project": old_full}).json()
    assert imp2["copied"] == {"photos": 1, "whisper": True, "mv": True, "audio": True}
    p2 = Path(client.get(f"/api/mv/project/{imp2['project']['slug']}").json()["project"]["audio_file"])
    assert p2.is_file() and ext not in p2.parents                       # served from the project, not the old path
    assert client.get("/api/mv/media", params={"path": str(p2)}, headers={"Range": "bytes=0-9"}).status_code == 206
    # same name again: the page is asked first; replace keeps the slug, "no" makes a copy
    again = client.post("/api/mv/project/import", json={"song_id": sid, "project": old_full})
    assert again.status_code == 409 and again.json()["status"] == "exists"
    rep = client.post("/api/mv/project/import", json={"song_id": sid, "project": old_full, "replace": True}).json()
    assert rep["project"]["slug"] == imp2["project"]["slug"]
    cp = client.post("/api/mv/project/import", json={"song_id": sid, "project": old_full, "replace": False}).json()
    assert cp["project"]["slug"] == f"{sid}_old_full_2"

    # any audio format can be dropped in (old MV Studio); ones the browser cannot play become FLAC
    aif = tmp_path / "take.aiff"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(aif)], check=True)
    with open(aif, "rb") as fh:
        up = client.post("/api/mv/upload_audio", data={"slug": cp["project"]["slug"]}, files={"file": ("take.aiff", fh)}).json()
    assert up["status"] == "ok" and up["filename"].endswith("_master.flac") and up["probe"]["exists"]
    assert not [f for f in Path(up["audio_file"]).parent.iterdir() if f.name.startswith("upload_") or ".part" in f.name]
    bad = client.post("/api/mv/upload_audio", data={"slug": cp["project"]["slug"]}, files={"file": ("x.aiff", b"not audio")})
    assert bad.status_code == 400
    gone = [slug, imp["project"]["slug"], imp2["project"]["slug"], cp["project"]["slug"]]
    d = client.post("/api/mv/projects/delete", json={"slugs": gone}).json()
    assert sorted(d["deleted"]) == sorted(gone) and not pdir.exists()
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

    # the old AI cover look ("studio": subtitle, badge, credits line, 60 fps) and the 720p size
    assert info["sources"][0]["studio"] == {"subtitle": "原曲", "badge": "原曲", "credits": ""}
    assert client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "t", "artist": "x",
                                                          "style": "fancy"}).status_code == 400
    assert client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "t", "artist": "x",
                                                          "resolution": "4k"}).status_code == 400
    assert client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "t", "artist": "x", "style": "studio",
                                                          "credits": "x" * 121}).status_code == 400
    j = client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "錄音室", "artist": "Nilson",
                                                       "style": "studio", "resolution": "720p", "subtitle": "AI Cover · 測試",
                                                       "badge": "🎸 吉他版", "credits": "Model: X | Pitch: +2"}).json()
    done = wait_job(client, j["job"]["id"], 600)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    st = client.get(f"/api/songs/{sid}/quickmv").json()["items"][0]
    assert st["style"] == "studio" and st["resolution"] == "720p" and st["fps"] == 60
    assert st["subtitle"] == "Nilson 翻唱 · 測試" and st["badge"] == "🎸 吉他版"     # never shows "AI"
    video = sdir / st["path"]
    v = next(s for s in probe(video)["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["r_frame_rate"]) == (1280, 720, "60/1")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "5", "-i", str(video), "-frames:v", "1", str(frame)], check=True)
    img = Image.open(frame).convert("RGB")
    assert max(img.crop((80, 60, 600, 130)).convert("L").getdata()) > 230      # white title
    r, g, b = img.getpixel((675, 380))                                          # vinyl label (green)
    assert g > 120 and g > r and g > b
    sub = img.crop((83, 133, 600, 160))
    assert any(px[1] > 150 and px[0] < 120 for px in sub.getdata())             # green subtitle
    j2 = client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "card720", "artist": "Nilson",
                                                        "resolution": "720p"}).json()
    assert wait_job(client, j2["job"]["id"], 600)["status"] == "succeeded"
    c720 = next(i for i in client.get(f"/api/songs/{sid}/quickmv").json()["items"] if i["title"] == "card720")
    v = next(s for s in probe(sdir / c720["path"])["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["r_frame_rate"]) == (1280, 720, "30/1") and c720["style"] == "card"


def test_quick_mv_lyrics(client, root, tmp_path, monkeypatch, fake_whisper):
    """Studio look with lyric subtitles: LRC, Whisper timing (once per song), save/load, burnt into the video."""
    fonts = sorted(Path("/usr/share/fonts/opentype/noto").glob("NotoSansCJK-Regular.ttc"))
    if not fonts:
        pytest.skip("no CJK font in this environment")
    monkeypatch.setenv("SIGN2MV_MV_FONT", str(fonts[0]))
    song = import_file(client, tmp_path, video=False, secs=12)
    sid = song["song_id"]
    client.put("/api/settings", json={"cover_singer_name": "Nilson", "language": "zh-TW"})
    base = f"/api/songs/{sid}/quickmv/lyrics"

    lrc = client.post(f"{base}/align", json={"text": "[00:01.00]第一句\n[00:04.50]第二句\n[00:07.00]第三句"}).json()
    assert lrc["mode"] == "lrc" and [x["start"] for x in lrc["lines"]] == [1.0, 4.5, 7.0]
    assert lrc["lines"][0]["end"] == 4.5 and 7.3 <= lrc["lines"][2]["end"] <= 12.1     # last line: 6 s or the song end
    assert client.post(f"{base}/align", json={"text": "  "}).status_code == 400
    even = client.post(f"{base}/align", json={"text": "一\n二", "even": True}).json()
    assert even["mode"] == "even" and len(even["lines"]) == 2

    # plain lines: Whisper runs once on the song's separated vocals, then the lines are matched
    first = client.post(f"{base}/align", json={"text": "一二三\n四五六"}).json()
    assert "job" in first
    assert wait_job(client, first["job"]["id"], 900)["status"] == "succeeded"
    timed = client.post(f"{base}/align", json={"text": "一二三\n四五六"}).json()
    assert timed["mode"] in ("whisper", "even") and len(timed["lines"]) == 2
    assert (root / "library" / "songs" / sid / "quickmv" / "lyrics" / "whisper.json").is_file()

    # save / load per audio; bad lines refused
    assert client.put(base, json={"source": "original", "text": "x", "lines": [{"start": 2, "end": 1, "text": "x"}]}).json()["lines"] == []
    assert client.put(base, json={"source": "../x", "lines": []}).status_code == 400
    saved = client.put(base, json={"source": "original", "text": "第一句", "lines": [{"start": 1, "end": 6, "text": "第一句測試"}]}).json()
    assert saved["lines"] == [{"start": 1.0, "end": 6.0, "text": "第一句測試"}]
    got = client.get(base, params={"source": "original"}).json()
    assert got["text"] == "第一句" and got["lines"] == saved["lines"] and got["whisper_ready"]

    j = client.post(f"/api/songs/{sid}/quickmv", json={"source": "original", "title": "字幕", "artist": "Nilson",
                                                       "style": "studio", "lyrics": saved["lines"]}).json()
    done = wait_job(client, j["job"]["id"], 600)
    assert done["status"] == "succeeded", (done["error_code"], done["error_message"])
    it = client.get(f"/api/songs/{sid}/quickmv").json()["items"][0]
    assert it["lyric_lines"] == 1
    video = root / "library" / "songs" / sid / it["path"]
    frame = tmp_path / "lyr.png"
    for at, expect in ((3, True), (8, False)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", str(video), "-frames:v", "1", str(frame)], check=True)
        band = Image.open(frame).convert("L").crop((500, 700, 1420, 775))
        assert (max(band.getdata()) > 240) == expect, at                # white lyric only while the line is on


def test_mv_scene_move_and_99_slots(client, root, tmp_path):
    """Drag a photo to another card (the photos in between shift by one, lyrics stay), and insert
    slots past the old 36-photo limit up to 99."""
    song = import_file(client, tmp_path, secs=6)
    sid = song["song_id"]
    slug = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "drag", "scene_count": 4}).json()["project"]["slug"]
    sdir = root / "library" / "songs" / sid / "mv" / "drag" / "scenes"
    colors = ["red", "green", "blue", "yellow"]
    files = [("files", (f"p{i}.png", png(c), "image/png")) for i, c in enumerate(colors, 1)]
    assert client.post("/api/mv/upload_scenes_batch", data={"slug": slug, "start_scene": "1", "fill_empty": "1"},
                       files=files).json()["count"] == 4

    def order():
        out = []
        for n in range(1, 5):
            r, g, b = Image.open(sdir / f"scene_{n:02d}.png").convert("RGB").getpixel((960, 540))
            out.append({(255, 0, 0): "red", (0, 128, 0): "green", (0, 0, 255): "blue", (255, 255, 0): "yellow"}.get((r, g, b), (r, g, b)))
        return out

    timeline = [{"scene": n, "start": n - 1.0, "end": float(n), "text": f"第{n}句", "type": "lyric"} for n in range(1, 5)]
    proj = client.get(f"/api/mv/project/{slug}").json()["project"]
    proj["timeline"] = timeline
    assert client.post("/api/mv/project/save", json=proj).status_code == 200

    res = client.post("/api/mv/scenes/move", json={"slug": slug, "a": 1, "b": 3}).json()
    assert res["status"] == "ok" and order() == ["green", "blue", "red", "yellow"]
    res = client.post("/api/mv/scenes/move", json={"slug": slug, "a": 4, "b": 1}).json()
    assert order() == ["yellow", "green", "blue", "red"]
    # the lyrics stay with their positions
    assert [s["text"] for s in res["project"]["timeline"]] == ["第1句", "第2句", "第3句", "第4句"]
    assert [s["scene"] for s in res["project"]["timeline"]] == [1, 2, 3, 4]
    assert client.post("/api/mv/scenes/move", json={"slug": slug, "a": 2, "b": 2}).status_code == 400

    # insert empty slots in front of card 1 until the limit: 99 photos (was 36)
    n = 4
    while True:
        r = client.post("/api/mv/scenes/insert_slot", json={"slug": slug, "before": 1})
        if r.status_code != 200:
            assert r.status_code == 409
            break
        n += 1
    assert n == 99
    assert (sdir / "scene_99.png").is_file() and (sdir / "scene_96.png").is_file()   # the four photos moved to the end


def test_mv_insert_photos_before(client, root, tmp_path):
    """「＋ 插入照片」: N chosen photos become N new cards in front of a card; the cards after them move
    back N places with their lyrics."""
    song = import_file(client, tmp_path, secs=6)
    sid = song["song_id"]
    slug = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "ins", "scene_count": 3}).json()["project"]["slug"]
    sdir = root / "library" / "songs" / sid / "mv" / "ins" / "scenes"
    files = [("files", (f"p{i}.png", png(c), "image/png")) for i, c in enumerate(["red", "green", "blue"], 1)]
    client.post("/api/mv/upload_scenes_batch", data={"slug": slug, "start_scene": "1", "fill_empty": "1"}, files=files)
    proj = client.get(f"/api/mv/project/{slug}").json()["project"]
    proj["timeline"] = [{"scene": n, "start": n - 1.0, "end": float(n), "text": f"第{n}句", "type": "lyric"} for n in range(1, 4)]
    proj["title"] = "改過還沒存的標題"   # the page's unsaved edits are kept
    new = [("files", (f"new{i}.jpg", png(c), "image/png")) for i, c in ((2, "yellow"), (1, "white"))]   # name order: new1, new2
    res = client.post("/api/mv/scenes/insert_photos", data={"slug": slug, "before": "2", "project": json.dumps(proj)}, files=new).json()
    assert res["status"] == "ok" and (res["first"], res["last"]) == (2, 3)

    def color(n):
        return Image.open(sdir / f"scene_{n:02d}.png").convert("RGB").getpixel((960, 540))
    assert [color(n) for n in range(1, 6)] == [(255, 0, 0), (255, 255, 255), (255, 255, 0), (0, 128, 0), (0, 0, 255)]
    p = res["project"]
    assert [(s["scene"], s["text"]) for s in p["timeline"]] == [(1, "第1句"), (4, "第2句"), (5, "第3句")]
    assert p["scene_count"] == 5 and p["title"] == "改過還沒存的標題"
    # after the last card (outro at the end): before = count + 1
    res = client.post("/api/mv/scenes/insert_photos", data={"slug": slug, "before": "6"},
                      files=[("files", ("x.png", png("black"), "image/png"))]).json()
    assert res["status"] == "ok" and color(6) == (0, 0, 0)
    # a file that is not a picture: nothing moves
    bad = client.post("/api/mv/scenes/insert_photos", data={"slug": slug, "before": "1"},
                      files=[("files", ("a.png", png("red"), "image/png")), ("files", ("b.png", b"not a picture", "image/png"))])
    assert bad.status_code == 400 and color(1) == (255, 0, 0) and not (sdir / "scene_07.png").exists()
    # the limit is checked before anything moves
    many = [("files", (f"m{i}.png", png("red"), "image/png")) for i in range(94)]
    r = client.post("/api/mv/scenes/insert_photos", data={"slug": slug, "before": "1"}, files=many)
    assert r.status_code == 409 and color(1) == (255, 0, 0)
