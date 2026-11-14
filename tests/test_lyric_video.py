"""Library: a picture with the pasted lyrics as subtitles, used as the song's picture (api_lyricvideo)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from conftest import REPO, wait_job

sys.path.insert(0, str(REPO / "workers"))

FF = ["ffmpeg", "-y", "-v", "error"]
# made-up lines; the second is long enough to need several rows
LINES = [{"start": 2.0, "end": 4.0, "text": "風吹過了小河"},
         {"start": 4.2, "end": 6.5, "text": "河水帶著落葉慢慢流向遠方的大海 岸邊的燈一盞一盞亮了起來"},
         {"start": 7.0, "end": 9.0, "text": "Paper boats are drifting slowly down the quiet river tonight"}]


def _song(client, root: Path, video: str | None = "320x180", dur: int = 11) -> tuple[str, Path]:
    sid = client.post("/api/songs", json={"title": "河邊 Riverside"}).json()["song_id"]
    sd = next(p for p in root.rglob(sid) if (p / "song.json").is_file())
    src = sd / "source"
    src.mkdir()
    subprocess.run(FF + ["-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}:sample_rate=44100", "-ac", "2",
                         "-c:a", "pcm_f32le", str(src / "audio.wav")], check=True)
    rec = {"type": "audio", "audio": "source/audio.wav", "video": None, "duration": float(dur),
           "source_hash": "sha256:abc", "imported_at": 1.0}
    if video:
        # a dark picture, so that white subtitle pixels can be told from it
        subprocess.run(FF + ["-f", "lavfi", "-i", f"color=c=0x203040:size={video}:rate=25:duration={dur}",
                             "-i", str(src / "audio.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                             "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                             str(src / "video.mp4")], check=True)
        w, h = video.split("x")
        rec.update(type="video", video="source/video.mp4", video_size=[int(w), int(h)])
    (src / "source.json").write_text(json.dumps(rec), encoding="utf-8")
    return sid, sd


def _rec(sd: Path) -> dict:
    return json.loads((sd / "source" / "source.json").read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stream_hash(path: Path, stream: str) -> str:
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", f"0:{stream}:0", "-c", "copy", "-f", "hash", "-"],
                          capture_output=True, text=True, check=True).stdout


def _white(path: Path, at: float, tmp: Path, box: tuple[float, float, float, float]) -> int:
    """Near-white pixels of the frame at `at` inside box (fractions: left, top, right, bottom)."""
    png = tmp / f"f_{path.stem}_{at}.png"
    subprocess.run(FF + ["-ss", str(at), "-i", str(path), "-frames:v", "1", str(png)], check=True)
    img = Image.open(png).convert("L")
    w, h = img.size
    crop = img.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    return sum(1 for v in crop.getdata() if v > 225)


def _make(client, sid: str, **body) -> dict:
    r = client.post(f"/api/songs/{sid}/lyric-video", json={"lines": LINES, "style": "plain", "lead": 0.7, **body})
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json()["job"]["id"])
    assert job["status"] == "succeeded", job
    return job


MIDDLE, BOTTOM, TOP = (0.05, 0.3, 0.95, 0.7), (0.0, 0.7, 1.0, 1.0), (0.0, 0.0, 1.0, 0.6)


def test_audio_only_song_gets_a_picture_and_can_drop_it_again(client, root, tmp_path):
    sid, sd = _song(client, root, video=None)
    audio_before = _sha(sd / "source" / "audio.wav")
    st = client.get(f"/api/songs/{sid}/lyric-video").json()
    assert st["active"] is False and st["made"] is None and st["has_picture"] is False and st["styles"] == ["plain"]
    assert st["lead_default"] == 0.7
    media_id = next(m["id"] for m in client.get("/sr/local-media").json()["media"] if m["songId"] == sid)
    assert client.get(f"/sr/local-media/{media_id}").json()["kind"] == "audio"
    # what cannot be made
    post = lambda **b: client.post(f"/api/songs/{sid}/lyric-video", json={"lines": LINES, "style": "plain", "lead": 0.7, **b})  # noqa: E731
    assert post(style="overlay").json()["error"] == "lyricvideo_no_picture"
    assert post(style="fancy").json()["error"] == "lyricvideo_style"
    assert post(lines=[]).json()["error"] == "lyricvideo_lines"
    assert post(lines=[{"start": 5, "end": 4, "text": "x"}]).json()["error"] == "lyricvideo_lines"
    for bad in (-0.1, 3.5, "1", True, None):
        assert post(lead=bad).json()["error"] == "lyricvideo_lead"
    assert client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": True}).json()["error"] == "lyricvideo_none"
    assert client.post(f"/api/songs/{sid}/lyric-video/use", json={}).json()["error"] == "lyricvideo_use"
    assert _rec(sd)["video"] is None and not (sd / "lyricvideo").exists()
    other_before = client.get(f"/api/songs/{sid}/storage").json()["categories"]["other"]

    _make(client, sid)
    rec = _rec(sd)
    video = sd / rec["video"]
    assert rec["video"].startswith("lyricvideo/v_") and video.is_file() and rec["video_size"] == [1920, 1080]
    assert rec["video_original"] == {"video": None, "video_size": None}
    assert rec["lyric_video"]["style"] == "plain" and rec["lyric_video"]["lines"] == 3 and rec["lyric_video"]["lead"] == 0.7
    assert _sha(sd / "source" / "audio.wav") == audio_before            # the audio is not touched
    assert not list((sd / "lyricvideo").glob("work*"))                   # scratch removed
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                                       "-of", "json", str(video)], capture_output=True, text=True, check=True).stdout)
    assert sorted(s["codec_type"] for s in probe["streams"]) == ["audio", "video"]
    assert abs(float(probe["format"]["duration"]) - 11.0) < 0.2
    # one line at a time, 0.7 s before it is sung (line 1 is sung 2.0-4.0)
    assert _white(video, 1.0, tmp_path, MIDDLE) == 0
    assert _white(video, 1.6, tmp_path, MIDDLE) > 500
    assert _white(video, 3.8, tmp_path, MIDDLE) > 500      # line 2 comes at 3.5: line 1 has made room for it
    assert _white(video, 6.8, tmp_path, MIDDLE) > 500      # line 3 (sung at 7.0) is already there
    assert _white(video, 10.0, tmp_path, MIDDLE) == 0
    # sing & record now plays a picture
    info = client.get(f"/sr/local-media/{media_id}").json()
    assert info["kind"] == "video" and info["playbackPath"] == f"/media/{sid}/{rec['video']}"
    assert client.get(info["playbackPath"], headers={"Range": "bytes=0-99"}).status_code in (200, 206)
    st = client.get(f"/api/songs/{sid}/lyric-video").json()
    assert st["active"] is True and st["current"]["style"] == "plain" and st["made"]["file"] == rec["video"]
    cats = client.get(f"/api/songs/{sid}/storage").json()["categories"]
    assert cats["other"] == other_before and cats["source"] > video.stat().st_size   # counted with the song's source

    # drop it (kept on disk), use it again
    st = client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": False}).json()
    assert st["active"] is False and st["made"]["file"] == rec["video"]
    off = _rec(sd)
    assert off["video"] is None and "lyric_video" not in off and "video_original" not in off and "video_size" not in off
    assert video.is_file() and client.get(f"/sr/local-media/{media_id}").json()["kind"] == "audio"
    assert client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": False}).json()["active"] is False   # twice is fine
    st = client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": True}).json()
    assert st["active"] is True and _rec(sd)["video"] == rec["video"] and _rec(sd)["video_size"] == [1920, 1080]
    assert _rec(sd)["video_original"] == {"video": None, "video_size": None}

    # deleting the song takes the lyric picture along
    assert client.delete(f"/api/songs/{sid}").status_code == 200
    assert not sd.exists()


def test_subtitles_over_the_original_picture_keep_picture_size_and_sound(client, root, tmp_path):
    sid, sd = _song(client, root, video="640x360")
    original = sd / "source" / "video.mp4"
    before, sound = _sha(original), _stream_hash(original, "a")
    assert client.get(f"/api/songs/{sid}/lyric-video").json()["styles"] == ["plain", "overlay"]
    assert client.get(f"/api/songs/{sid}/audio-shift").json()["allowed"] is True

    _make(client, sid, style="overlay", lead=0)
    rec = _rec(sd)
    video = sd / rec["video"]
    assert rec["video_size"] == [640, 360] and rec["video_original"] == {"video": "source/video.mp4", "video_size": [640, 360]}
    assert _sha(original) == before                          # the imported picture is not changed
    assert _stream_hash(video, "a") == sound                 # the same sound, copied
    assert _white(video, 1.9, tmp_path, BOTTOM) == 0         # lead 0: nothing before 2.0
    assert _white(video, 2.3, tmp_path, BOTTOM) > 100
    assert _white(video, 2.3, tmp_path, TOP) == 0            # along the bottom only
    assert _white(video, 5.0, tmp_path, BOTTOM) > _white(video, 2.3, tmp_path, BOTTOM)   # the long line, in rows
    # the audio cannot be shifted against a picture whose lines follow the audio
    shift = client.get(f"/api/songs/{sid}/audio-shift").json()
    assert shift["allowed"] is False and shift["reason"] == "shift_lyric_picture"
    assert client.post(f"/api/songs/{sid}/audio-shift", json={"target": 0.5}).status_code != 200

    # made again as lyrics only: one lyric picture is kept, the original is still the imported one
    _make(client, sid, style="plain")
    rec2 = _rec(sd)
    assert rec2["video"] != rec["video"] and not video.exists() and rec2["video_size"] == [1920, 1080]
    assert rec2["video_original"] == {"video": "source/video.mp4", "video_size": [640, 360]}
    assert len(list((sd / "lyricvideo").glob("v_*.mp4"))) == 1
    # and over the picture again: over the imported one, not over the lyric picture
    _make(client, sid, style="overlay")
    rec3 = _rec(sd)
    assert rec3["video_size"] == [640, 360] and _white(sd / rec3["video"], 1.6, tmp_path, MIDDLE) == 0
    assert _white(sd / rec3["video"], 1.6, tmp_path, BOTTOM) > 100

    # back to the original picture
    st = client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": False}).json()
    assert st["active"] is False and st["has_picture"] is True
    back = _rec(sd)
    assert back["video"] == "source/video.mp4" and back["video_size"] == [640, 360] and "lyric_video" not in back
    assert _sha(original) == before
    # something was made from this song's timing by now: still no shifting
    assert client.get(f"/api/songs/{sid}/audio-shift").json()["allowed"] is False


def test_upright_picture_keeps_the_lines_inside(client, root, tmp_path):
    sid, sd = _song(client, root, video="360x640")
    _make(client, sid, style="overlay")
    rec = _rec(sd)
    video = sd / rec["video"]
    assert rec["video_size"] == [360, 640]
    assert _white(video, 5.0, tmp_path, BOTTOM) > 100
    # nothing runs off the sides: the outermost columns stay dark
    assert _white(video, 5.0, tmp_path, (0.0, 0.0, 0.02, 1.0)) == 0 and _white(video, 5.0, tmp_path, (0.98, 0.0, 1.0, 1.0)) == 0
    assert _white(video, 8.0, tmp_path, (0.0, 0.0, 0.02, 1.0)) == 0 and _white(video, 8.0, tmp_path, (0.98, 0.0, 1.0, 1.0)) == 0


def test_lost_or_outdated_lyric_picture_does_not_break_the_song(client, root):
    sid, sd = _song(client, root, video="320x180")
    _make(client, sid)
    rec = _rec(sd)
    # the file is gone (removed by hand): the song shows its imported picture again
    (sd / rec["video"]).unlink()
    song = next(s for s in client.get("/api/songs").json()["songs"] if s["song_id"] == sid)
    assert song["source"]["video"] == "source/video.mp4" and "lyric_video" not in song["source"]
    st = client.get(f"/api/songs/{sid}/lyric-video").json()
    assert st["active"] is False and st["made"] is None and st["has_picture"] is True
    assert client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": True}).json()["error"] == "lyricvideo_none"
    assert _rec(sd)["video"] == "source/video.mp4" and "lyric_video" not in _rec(sd)    # the record on disk too
    assert client.get(f"/api/songs/{sid}/audio-shift").json()["reason"] == "shift_processed"
    # made again, then the song's audio is replaced (imported again): the old lyric picture no longer fits
    _make(client, sid)
    new = {"type": "video", "audio": "source/audio.wav", "video": "source/video.mp4", "video_size": [320, 180],
           "duration": 11.0, "source_hash": "sha256:other", "imported_at": 2.0}
    (sd / "source" / "source.json").write_text(json.dumps(new), encoding="utf-8")
    st = client.get(f"/api/songs/{sid}/lyric-video").json()
    assert st["active"] is False and st["made"] is None
    assert client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": True}).json()["error"] == "lyricvideo_none"
    _make(client, sid)
    assert _rec(sd)["video_original"]["video"] == "source/video.mp4"


def test_one_job_at_a_time(client, root):
    sid, sd = _song(client, root, video=None, dur=40)
    first = client.post(f"/api/songs/{sid}/lyric-video", json={"lines": LINES, "style": "plain", "lead": 0.7}).json()["job"]
    again = client.post(f"/api/songs/{sid}/lyric-video", json={"lines": LINES, "style": "plain", "lead": 1.0})
    assert again.status_code == 409 and again.json()["error"] == "song_busy"
    assert client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": False}).status_code == 409
    assert wait_job(client, first["id"])["status"] == "succeeded"
    assert len(list((sd / "lyricvideo").glob("v_*.mp4"))) == 1


def test_missing_song_and_song_without_audio(client):
    assert client.get("/api/songs/nope/lyric-video").status_code in (400, 404)
    sid = client.post("/api/songs", json={"title": "empty"}).json()["song_id"]
    assert client.get(f"/api/songs/{sid}/lyric-video").json()["error"] == "song_has_no_audio"
    assert client.post(f"/api/songs/{sid}/lyric-video", json={"lines": LINES}).json()["error"] == "song_has_no_audio"
    assert client.post(f"/api/songs/{sid}/lyric-video/use", json={"on": True}).json()["error"] == "song_has_no_audio"


def test_lines_come_early_and_never_overlap():
    import lyric_video
    rows = lyric_video.shown_lines([{"start": 5.0, "end": 8.0, "text": "b"}, {"start": 0.3, "end": 4.9, "text": "a"},
                                    {"start": 8.2, "end": 9.0, "text": " "}, {"start": 20.0, "end": 22.0, "text": "c"}], 0.7)
    assert rows == [(0.0, 4.3, "a"), (4.3, 8.0, "b"), (19.3, 22.0, "c")]
    assert lyric_video.shown_lines([{"start": 1.0, "end": 2.0, "text": "a"}], 0) == [(1.0, 2.0, "a")]
    # two lines at the same moment: the first still shows for a moment
    both = lyric_video.shown_lines([{"start": 3.0, "end": 5.0, "text": "a"}, {"start": 3.0, "end": 5.0, "text": "b"}], 0.5)
    assert both[0][1] - both[0][0] == pytest.approx(lyric_video.MIN_SHOW_S)


def test_long_lines_are_wrapped_in_even_rows():
    import lyric_video
    from PIL import ImageFont
    font = next((p for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "C:/Windows/Fonts/msjh.ttc",
                             "C:/Windows/Fonts/msyh.ttc") if Path(p).is_file()), None)
    if not font:
        pytest.skip("no CJK font on this machine")
    width = lambda rows, em: [ImageFont.truetype(font, em).getlength(r) * 1.06 for r in rows]  # noqa: E731
    rows, em = lyric_video.wrap("短短一句", font, 60, 800)
    assert rows == ["短短一句"] and em == 60
    text = "河水帶著落葉慢慢流向遠方的大海岸邊的燈一盞一盞亮了起來"          # no spaces at all
    rows, em = lyric_video.wrap(text, font, 60, 800)
    assert "".join(rows) == text and len(rows) == 3 and em == 60 and max(width(rows, em)) <= 800
    assert min(len(r) for r in rows) >= 7                                # no last row of one or two characters
    rows, em = lyric_video.wrap("Paper boats are drifting slowly down the quiet river tonight", font, 60, 800)
    assert " ".join(rows) == "Paper boats are drifting slowly down the quiet river tonight" and max(width(rows, em)) <= 800
    rows, em = lyric_video.wrap(text * 4, font, 60, 800)                 # far too long: smaller, never more rows than fit
    assert "".join(rows) == text * 4 and em < 60
    assert lyric_video.line_ratio(font) >= 1.0
