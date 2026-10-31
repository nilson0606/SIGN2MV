"""The finished-outputs folder (<library>/Finished): names, duplicates, renames, deletes, user files."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app import finished


def _song(lib: Path, sid: str, title: str, created: float) -> Path:
    d = lib / "songs" / sid
    d.mkdir(parents=True)
    (d / "song.json").write_text(json.dumps({"song_id": sid, "title": title, "created_at": created}), encoding="utf-8")
    return d


def _cover(sd: Path, vid: str, rid: str, number: int, label: str, created: float) -> Path:
    r = sd / "renders" / rid
    r.mkdir(parents=True)
    (r / "audio.mp3").write_bytes(b"x")
    (r / "render.json").write_text(json.dumps({"id": rid, "kind": "cover", "title": f"#{number} {label}",
                                               "audio": "audio.mp3", "created_at": created, "cover_version": vid}))
    v = sd / "cover" / "versions" / vid
    v.mkdir(parents=True)
    (v / "version.json").write_text(json.dumps({"id": vid, "number": number, "title": f"#{number} {label}",
                                                "render_id": rid, "created_at": created}))
    return r / "audio.mp3"


def _sing(sd: Path, rid: str, created: float) -> Path:
    r = sd / "renders" / rid
    r.mkdir(parents=True)
    (r / "audio.wav").write_bytes(b"x")
    (r / "render.json").write_text(json.dumps({"id": rid, "kind": "sing", "title": "x", "audio": "audio.wav",
                                               "created_at": created}))
    return r / "audio.wav"


def _quick(sd: Path, qid: str, created: float, **info) -> Path:
    q = sd / "quickmv" / qid
    q.mkdir(parents=True)
    (q / "video.mp4").write_bytes(b"x")
    (q / "info.json").write_text(json.dumps({"created_at": created, **info}, ensure_ascii=False), encoding="utf-8")
    return q / "video.mp4"


def _mv(sd: Path, name: str, title: str) -> Path:
    p = sd / "mv" / name
    (p / "output").mkdir(parents=True)
    (p / "project.json").write_text(json.dumps({"title": title, "output_mv": f"{title}_MV.mp4"}, ensure_ascii=False),
                                    encoding="utf-8")
    (p / "output" / f"{title}_MV.mp4").write_bytes(b"x")
    return p / "output" / f"{title}_MV.mp4"


def _ts(month_day_hm: str) -> float:
    return time.mktime(time.strptime("2026-" + month_day_hm, "%Y-%m-%d %H:%M"))


def _links(folder: Path) -> dict[str, str]:
    return {p.name: os.readlink(p) for p in folder.iterdir() if p.is_symlink()}


def test_names_duplicates_rename_and_delete(tmp_path):
    lib = tmp_path / "lib"
    tmp = tmp_path / "tmp"
    a = _song(lib, "s000000000a", "童話", _ts("10-29 10:00"))
    cover = _cover(a, "v0000000001", "r000000000001", 1, "My_Voice_Ver8 -12 · Key -2", _ts("10-30 08:00"))
    sing = _sing(a, "r000000000002", _ts("10-31 09:05"))
    quick = _quick(a, "q000000000001", _ts("10-31 09:20"), style="studio", resolution="1080p",
                   source_kind="cover", source_title="#1 My_Voice_Ver8 -12 · Key -2")
    mv = _mv(a, "main", "童話")
    res = finished.sync(lib, "zh-TW", tmp)
    assert res["created"] == 4 and not res["errors"]
    links = _links(lib / "Finished" / "童話")
    assert links == {"翻唱 #1 My_Voice_Ver8 -12 · Key -2": str(cover), "唱錄 10-31 09：05": str(sing),
                     "快速MV 錄音室 1080p · 翻唱 #1 · 10-31 09：20": str(quick), "MV 童話": str(mv)}
    # nothing changed: nothing is made again
    assert finished.sync(lib, "zh-TW", tmp)["created"] == 0

    # a second 童話 imported on another day: both folders get the import date
    b = _song(lib, "s000000000b", "童話", _ts("10-31 19:05"))
    _sing(b, "r000000000003", _ts("10-31 19:30"))
    (lib / "Finished" / "童話" / "my notes.txt").write_text("mine")   # the user's own file
    finished.sync(lib, "zh-TW", tmp)
    names = sorted(p.name for p in (lib / "Finished").iterdir())
    assert names == ["童話（10-29 匯入）", "童話（10-31 匯入）"]
    assert (lib / "Finished" / "童話（10-29 匯入）" / "my notes.txt").read_text() == "mine"   # moved with the folder
    assert len(_links(lib / "Finished" / "童話（10-29 匯入）")) == 4

    # rename the first song: its folder follows
    meta = json.loads((a / "song.json").read_text(encoding="utf-8"))
    meta["title"] = "童話 (live)"
    (a / "song.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    finished.sync(lib, "zh-TW", tmp)
    assert sorted(p.name for p in (lib / "Finished").iterdir()) == ["童話", "童話 (live)"]

    # delete a version: its shortcut goes, the others stay
    import shutil
    shutil.rmtree(a / "renders" / "r000000000001")
    shutil.rmtree(a / "cover" / "versions" / "v0000000001")
    finished.sync(lib, "zh-TW", tmp)
    assert "翻唱 #1 My_Voice_Ver8 -12 · Key -2" not in _links(lib / "Finished" / "童話 (live)")
    assert len(_links(lib / "Finished" / "童話 (live)")) == 3

    # delete the songs: shortcuts go; a folder with the user's file stays, an empty one goes
    shutil.rmtree(a)
    shutil.rmtree(b)
    finished.sync(lib, "zh-TW", tmp)
    assert sorted(p.name for p in (lib / "Finished").iterdir()) == ["童話 (live)"]
    assert [p.name for p in (lib / "Finished" / "童話 (live)").iterdir()] == ["my notes.txt"]


def test_same_day_gets_the_time_and_user_files_are_never_claimed(tmp_path):
    lib = tmp_path / "lib"
    a = _song(lib, "s000000000a", "A/B?", _ts("10-31 09:00"))
    b = _song(lib, "s000000000b", "A/B?", _ts("10-31 19:05"))
    _sing(a, "r000000000001", _ts("10-31 10:00"))
    _sing(b, "r000000000002", _ts("10-31 20:00"))
    # a user's file already has the shortcut's name: left alone and never deleted later
    user = lib / "Finished" / "A_B_（10-31 09：00 匯入）"
    user.mkdir(parents=True)
    (user / "唱錄 10-31 10：00").write_text("mine")
    finished.sync(lib, "zh-TW", tmp_path / "tmp")
    assert sorted(p.name for p in (lib / "Finished").iterdir()) == ["A_B_（10-31 09：00 匯入）", "A_B_（10-31 19：05 匯入）"]
    assert (user / "唱錄 10-31 10：00").read_text() == "mine"
    import shutil
    shutil.rmtree(a)
    finished.sync(lib, "zh-TW", tmp_path / "tmp")
    assert (user / "唱錄 10-31 10：00").read_text() == "mine"


def test_english_names_and_language_switch(tmp_path):
    lib = tmp_path / "lib"
    a = _song(lib, "s000000000a", "Song", _ts("10-29 10:00"))
    _quick(a, "q000000000001", _ts("10-31 09:20"), style="card", resolution="720p", source_kind="original",
           source_title="Song")
    finished.sync(lib, "zh-TW", tmp_path / "tmp")
    assert list(_links(lib / "Finished" / "Song")) == ["快速MV 卡片 720p · 原曲 · 10-31 09：20"]
    finished.sync(lib, "en", tmp_path / "tmp")
    assert list(_links(lib / "Finished" / "Song")) == ["Quick MV Card 720p · Original · 10-31 09.20"]


def test_server_keeps_the_folder_in_step(client, root):
    # the app syncs in the background after changes; run it directly here
    from app.server import create_app  # noqa: F401  (client fixture already built the app)
    song = client.post("/api/songs", json={"title": "測試歌"}).json()
    app = client.app
    res = app.state.ctx.finished.run_now()
    assert not res.get("errors")
    info = client.get("/api/finished").json()
    assert info["path"].endswith("Finished")
    assert song["song_id"] not in info["songs"]   # nothing finished yet: no folder


def test_old_chinese_folder_is_moved(tmp_path):
    lib = tmp_path / "lib"
    a = _song(lib, "s000000000a", "Song", _ts("10-29 10:00"))
    _sing(a, "r000000000001", _ts("10-31 10:00"))
    finished.sync(lib, "zh-TW", tmp_path / "tmp")
    # a library made by 9923aec: the folder was 成品
    os.replace(lib / "Finished", lib / "成品")
    man = json.loads((lib / finished.MANIFEST).read_text(encoding="utf-8"))
    man["root"] = "成品"
    (lib / finished.MANIFEST).write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    (lib / "成品" / "Song" / "mine.txt").write_text("x")
    finished.sync(lib, "zh-TW", tmp_path / "tmp")
    assert not (lib / "成品").exists()
    assert sorted(p.name for p in (lib / "Finished" / "Song").iterdir()) == ["mine.txt", "唱錄 10-31 10：00"]
