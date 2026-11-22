"""[2026-11-22] The MV page's 「這首歌的音檔」 menu also lists the song's saved takes of the sing page (the list of its
「錄音後處理」: whole takes, segment mixes, versions saved from post-production). Picking one uses the song's copy
of it (made once, the same copy the sing page's 「完整 MV」 makes), so the MV keeps its sound if the take is deleted."""
import io
import json
import threading
import time
import uuid
import wave
from pathlib import Path

from app.api_sing import video_id_for
from app.mvstudio import core
from test_mv_photos import project


def _wav(seconds=1.0, rate=16000, tone=1):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes([tone % 256, 0]) * int(seconds * rate))
    return buf.getvalue()


def _take(rec_root: Path, video_id: str, title: str, created_s: float, tone: int, **fields) -> tuple[str, Path]:
    """A take written as the sing page stores it: <library>/recordings/<id>/{metadata.json, mix.wav}."""
    rec_id = str(uuid.uuid4())
    d = rec_root / rec_id
    d.mkdir(parents=True)
    mix = _wav(tone=tone)
    (d / "mix.wav").write_bytes(mix)
    meta = {"id": rec_id, "title": title, "videoId": video_id, "mime": "audio/wav", "created": created_s * 1000,
            "seconds": 1.0, "bytes": len(mix), "complete": True, "mode": "mix", **fields}
    (d / "metadata.json").write_text(json.dumps({"format": "karaoke-recording-v1", "recording": meta}, ensure_ascii=False),
                                     encoding="utf-8")
    return rec_id, d / "mix.wav"


def _menu(client, sid):
    return [a for a in client.get("/api/mv/projects").json()["available_audios"] if a["song_id"] == sid]


def _renders(song_dir: Path):
    return sorted(p.parent.name for p in (song_dir / "renders").glob("r*/render.json"))


def test_saved_takes_are_in_the_menu_and_picking_one_uses_one_copy(client, root):
    sid, slug, pdir = project(client, root, 12)
    song_dir = pdir.parent.parent
    title = client.get(f"/api/songs/{sid}").json()["title"]
    rec_root = core.LIBRARY_ROOT / "recordings"
    vid = video_id_for(sid)
    t0 = time.time() - 3600
    a_id, a_mix = _take(rec_root, vid, f"{title} · 降 1 Key · 分段合成", t0, 1)
    b_id, b_mix = _take(rec_root, vid, f"{title} · 降 1 Key · 分段合成", t0 + 60, 2, parentId=a_id)   # saved from post
    c_id, _ = _take(rec_root, vid, title, t0 + 120, 3, mode="voice")                                 # voice only
    _take(rec_root, vid, f"{title} · 第 1 段", t0 + 180, 4, segmentTake={"version": 1})               # a segment
    _take(rec_root, vid, f"{title} · 待確認", t0 + 240, 5, postPending=True)                           # in review
    _take(rec_root, vid, f"{title} · 中斷", t0 + 300, 6, complete=False)                               # incomplete
    gone, _ = _take(rec_root, vid, f"{title} · 刪掉的", t0 + 360, 7)
    (rec_root / ".deleted.json").write_text(json.dumps([gone]), encoding="utf-8")
    other_id, other_mix = _take(rec_root, video_id_for("someothersong"), "別首", t0 + 420, 8)       # no such song

    menu = _menu(client, sid)
    takes = [a for a in menu if a["kind"] == "take"]
    stamp = lambda s: time.strftime("%m-%d %H:%M", time.localtime(s))
    whole, voice = ("whole song", "vocals only") if core.BRAND["lang"] == "en" else ("整首", "純人聲")
    assert [a["name"] for a in takes] == [f"後處理：{stamp(t0 + 120)} · {whole} · {voice}",      # newest first
                                          f"後處理：{stamp(t0 + 60)} · 降 1 Key · 分段合成",
                                          f"後處理：{stamp(t0)} · 降 1 Key · 分段合成"]
    assert [a["recording_id"] for a in takes] == [c_id, b_id, a_id]
    assert takes[2]["path"] == str(a_mix) and takes[2]["render_id"] == ""
    assert menu[0]["kind"] == "mix"                                         # the original stays first
    assert not any(a["path"] == str(other_mix) for a in client.get("/api/mv/projects").json()["available_audios"])

    # picking a take: the song gets a copy of it, the project uses the copy, the menu shows the take once
    r = client.post("/api/mv/select_audio", json={"slug": slug, "audio_file": str(a_mix)}).json()
    assert r["status"] == "ok" and r["audio_probe"]["exists"]
    used = Path(r["project"]["audio_file"])
    assert used.parent.parent == song_dir / "renders" and used.read_bytes() == a_mix.read_bytes()
    info = json.loads((used.parent / "render.json").read_text(encoding="utf-8"))
    assert info["kind"] == "sing" and info["recording_id"] == a_id and info["title"] == f"{title} · 降 1 Key · 分段合成"
    assert _renders(song_dir) == [used.parent.name]
    menu = _menu(client, sid)
    a_row = next(a for a in menu if a.get("recording_id") == a_id)
    assert a_row["path"] == str(used) and a_row["render_id"] == used.parent.name
    assert a_row["name"] == f"後處理：{stamp(t0)} · 降 1 Key · 分段合成"
    assert not [a for a in menu if a["kind"] == "sing"]                    # not listed a second time as 唱錄

    # picking it again (from the take's file or from the menu's copy) makes no second copy
    for path in (a_mix, used, a_mix):
        r = client.post("/api/mv/select_audio", json={"slug": slug, "audio_file": str(path)}).json()
        assert r["status"] == "ok" and r["project"]["audio_file"] == str(used)
    assert _renders(song_dir) == [used.parent.name]

    # deleting the take on the sing page leaves the MV's sound; the copy is then listed as a 唱錄 of the song
    (rec_root / ".deleted.json").write_text(json.dumps([gone, a_id]), encoding="utf-8")
    menu = _menu(client, sid)
    assert not any(a.get("recording_id") == a_id for a in menu)
    assert any(a["kind"] == "sing" and a["path"] == str(used) for a in menu)
    assert used.is_file()

    # a take of another song chosen by hand is copied into the project, as any file from elsewhere
    r = client.post("/api/mv/select_audio", json={"slug": slug, "audio_file": str(other_mix)}).json()
    assert r["status"] == "ok" and Path(r["project"]["audio_file"]).parent == pdir / "audio"
    assert _renders(song_dir) == [used.parent.name]


def test_a_take_sent_by_the_sing_page_is_the_same_copy(client, root):
    """「完整 MV」 on the sing page copies the take first; picking the take here then uses that copy."""
    sid, slug, pdir = project(client, root, 12)
    song_dir = pdir.parent.parent
    rec_root = core.LIBRARY_ROOT / "recordings"
    rec_id, mix = _take(rec_root, video_id_for(sid), "take", time.time(), 9)
    token = client.get("/sr/session").json()["token"]
    sent = client.post(f"/sr/renders?videoId={video_id_for(sid)}&title=take&recordingId={rec_id}",
                       headers={"X-Karaoke-Token": token}, content=mix.read_bytes()).json()
    assert sent["kind"] == "sing" and sent["recording_id"] == rec_id
    menu = _menu(client, sid)
    row = next(a for a in menu if a.get("recording_id") == rec_id)
    assert row["render_id"] == sent["id"] and row["path"] == str(song_dir / sent["path"])
    assert not [a for a in menu if a["kind"] == "sing"]
    r = client.post("/api/mv/select_audio", json={"slug": slug, "audio_file": str(mix)}).json()
    assert r["project"]["audio_file"] == str(song_dir / sent["path"])
    assert _renders(song_dir) == [sent["id"]]


def test_two_quick_picks_make_one_copy(client, root):
    sid, slug, pdir = project(client, root, 12)
    song_dir = pdir.parent.parent
    rec_id, mix = _take(core.LIBRARY_ROOT / "recordings", video_id_for(sid), "take", time.time(), 10)
    results = []

    def pick():
        results.append(client.post("/api/mv/select_audio", json={"slug": slug, "audio_file": str(mix)}).json())

    threads = [threading.Thread(target=pick) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 3 and all(r["status"] == "ok" for r in results)
    assert len({r["project"]["audio_file"] for r in results}) == 1
    assert len(_renders(song_dir)) == 1
