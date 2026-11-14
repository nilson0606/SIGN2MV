"""MV workspace: a project shows only the photos the user put in through the page.

A file that some other program writes into the project's scenes folder (even under the right name) is never
shown, counted or rendered; it is kept in <project>/not_imported/ and the page is told how many there are.
"""
import io
import json

from PIL import Image

from app.mvstudio import core
from test_lyric_align import CHORUS, VERSE, _song_with_audio, sing


def png(color, size=(1920, 1080)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def project(client, root, secs=30):
    sid, song_dir = _song_with_audio(client, root, secs)
    slug = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "demo", "title": "t", "scene_count": 3}).json()["project"]["slug"]
    return sid, slug, song_dir / "mv" / "demo"


def state(client, slug):
    data = client.get(f"/api/mv/project/{slug}").json()
    return data, sorted(s["scene_id"] for s in data["scenes"] if s.get("exists"))


def test_files_written_by_something_else_are_not_used(client, root):
    sid, slug, pdir = project(client, root)
    scenes = pdir / "scenes"
    assert json.loads((pdir / "photos.json").read_text())["photos"] == []
    # another program drops pictures in, with exactly the names the app uses
    (scenes / "scene_01.png").write_bytes(png("red"))
    (scenes / "scene_02.png").write_bytes(png("green"))
    (scenes / "inst_intro.png").write_bytes(png("blue"))
    data, shown = state(client, slug)
    assert shown == [] and data["instrument_photos"] == {}
    assert data["not_imported"]["waiting"] == 3
    hold = pdir / "not_imported"
    assert sorted(p.name for p in hold.iterdir()) == ["inst_intro.png", "scene_01.png", "scene_02.png"]
    assert (hold / "scene_01.png").read_bytes() == png("red")            # kept as it was, only out of the way
    assert not list(scenes.glob("*.png"))
    assert core.count_existing_scene_images(str(scenes)) == 0
    assert core.seg_photo_path({"illust_dir": str(scenes)}, {"type": "intro", "scene": 1}) == ""
    # the same name again later: kept next to the first one, nothing overwritten
    (scenes / "scene_01.png").write_bytes(png("white"))
    data, shown = state(client, slug)
    assert shown == [] and data["not_imported"]["waiting"] == 4 and (hold / "scene_01 (2).png").read_bytes() == png("white")

    # aligning lyrics does not bring pictures in either, and their number does not count as photos
    lines, starts, words = sing([VERSE, CHORUS], t0=3.0, between=2.0)
    (pdir / "whisper.json").write_text(json.dumps({
        "pipeline": "vocals_v1", "duration": 30.0, "lead_requested": False,
        "audio_file": str(pdir.parent.parent / "source" / "audio.wav"),
        "segments": [{"start": words[0]["start"], "end": words[-1]["end"], "text": "x", "words": words}]}), encoding="utf-8")
    (scenes / "scene_40.png").write_bytes(png("black"))
    res = client.post("/api/mv/paste_lyrics", json={"slug": slug, "lyrics_text": "\n".join(lines), "mode": "whisper_align"}).json()
    assert res["status"] == "ok" and res["project"]["scene_count"] == 8           # the 8 lines; 40 would mean the file counted
    data, shown = state(client, slug)
    assert shown == [] and data["not_imported"]["waiting"] == 5


def test_photos_from_the_page_stay_through_every_move(client, root):
    sid, slug, pdir = project(client, root)
    scenes = pdir / "scenes"
    up = client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": "1"}, files={"file": ("a.jpg", png("red", (800, 600)), "image/png")}).json()
    assert up["status"] == "ok"
    files = [("files", (f"p{i}.png", png(c, (640, 480)), "image/png")) for i, c in enumerate(["green", "blue"], 1)]
    batch = client.post("/api/mv/upload_scenes_batch", data={"slug": slug, "start_scene": "1", "fill_empty": "1"}, files=files).json()
    assert batch["count"] == 2 and [s["scene_id"] for s in batch["scenes"]] == [2, 3]
    inst = client.post("/api/mv/instrumental/upload_photo", data={"slug": slug, "key": "intro"},
                       files={"file": ("i.png", png("yellow"), "image/png")}).json()
    assert inst["status"] == "ok"
    data, shown = state(client, slug)
    assert shown == [1, 2, 3] and data["not_imported"]["waiting"] == 0
    intro = core.seg_photo_path({"illust_dir": str(scenes)}, {"type": "intro", "scene": 1})
    assert intro.endswith("inst_intro.png") and core.list_instrumental_photos(str(scenes), [{"type": "intro", "scene": 1}])
    assert len(json.loads((pdir / "photos.json").read_text())["photos"]) == 4 and not list(scenes.glob("*.part"))

    def colors():
        out = {}
        for p in sorted(scenes.glob("scene_*.png")):
            with Image.open(p) as im:
                out[int(p.stem[-2:])] = im.getpixel((5, 5))
        return out

    assert colors() == {1: (255, 0, 0), 2: (0, 128, 0), 3: (0, 0, 255)}
    assert client.post("/api/mv/scenes/swap", json={"slug": slug, "a": 1, "b": 3}).json()["status"] == "ok"
    assert state(client, slug)[1] == [1, 2, 3] and colors() == {1: (0, 0, 255), 2: (0, 128, 0), 3: (255, 0, 0)}
    ins = client.post("/api/mv/scenes/insert_photos", data={"slug": slug, "before": "2"},
                      files=[("files", ("n.png", png("white"), "image/png"))]).json()
    assert ins["status"] == "ok", ins
    data, shown = state(client, slug)
    assert shown == [1, 2, 3, 4] and colors()[2] == (255, 255, 255) and data["not_imported"]["waiting"] == 0
    assert not (scenes / "__insert_tmp").exists()

    # something overwrites one of the user's photos: that slot is empty now, the foreign content is not shown
    (scenes / "scene_03.png").write_bytes(png("black"))
    data, shown = state(client, slug)
    assert shown == [1, 2, 4] and data["not_imported"]["waiting"] == 1


def test_project_from_before_the_list_keeps_its_photos(client, root):
    sid, slug, pdir = project(client, root)
    scenes = pdir / "scenes"
    (pdir / "photos.json").unlink()                 # a project made by an earlier version: photos, no list
    (scenes / "scene_01.png").write_bytes(png("red"))
    (scenes / "scene_02_old.jpg").write_bytes(png("green"))
    data, shown = state(client, slug)
    assert shown == [1, 2] and data["not_imported"]["waiting"] == 0
    assert len(json.loads((pdir / "photos.json").read_text())["photos"]) == 2
    (scenes / "scene_03.png").write_bytes(png("blue"))      # from now on only the page adds photos
    data, shown = state(client, slug)
    assert shown == [1, 2] and data["not_imported"]["waiting"] == 1


def test_importing_a_project_brings_its_photos(client, root, tmp_path):
    sid, slug, pdir = project(client, root)
    old = tmp_path / "old_scenes"
    old.mkdir()
    (old / "scene_01.png").write_bytes(png("red"))
    (old / "scene_02.png").write_bytes(png("green"))
    res = client.post("/api/mv/project/import", json={"song_id": sid, "project": {"name": "brought", "title": "t",
                      "illust_dir": str(old), "timeline": []}}).json()
    assert res["status"] == "ok" and res["copied"]["photos"] == 2
    data, shown = state(client, res["project"]["slug"])
    assert shown == [1, 2] and data["not_imported"]["waiting"] == 0
