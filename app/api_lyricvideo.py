"""Lyric picture of a library song: the pasted lyrics as subtitles, used as the song's picture.

For a song whose picture has no lyrics, or that has no picture (an audio file): sing & record then shows
the words. The lyrics and their times are the quick MV's (songs/<id>/quickmv/lyrics/original.json and its
align route); this module only makes the picture and switches the song between it and the original.
The audio is never touched, so stems, key versions, covers and takes stay valid.

On disk: songs/<id>/lyricvideo/{v_<id>.mp4, info.json}. source/source.json:
  "video"           the picture in use ("lyricvideo/v_<id>.mp4" while the lyric picture is on)
  "video_original"  {"video", "video_size"} of the imported picture (only while the lyric picture is on)
  "lyric_video"     {"file", "style", "lead", "lines", "made_at"} (only while the lyric picture is on)

Routes:
  GET  /api/songs/{id}/lyric-video        {"active", "made", "has_picture", "styles", "lead_default"}
  POST /api/songs/{id}/lyric-video        {"lines": [{"start", "end", "text"}], "style": "plain"|"overlay",
                                           "lead": 0..3} -> job; when it is done the song uses the new picture
  POST /api/songs/{id}/lyric-video/use    {"on": false} back to the original picture (the lyric picture is
                                           kept), {"on": true} the lyric picture again
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Request

from . import quick_lyrics
from .api_quickmv import pick_font
from .context import Context
from .library import LibraryError, lost_lyric_picture
from .util import body_json, err

LEAD_DEFAULT = 0.7    # the MV workspace's early_lead
LEAD_MAX = 3.0


def _made(sdir: Path, src: dict) -> dict | None:
    """The lyric picture made for the song's current audio, or None."""
    try:
        info = json.loads((sdir / "lyricvideo" / "info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or info.get("source_hash") != src.get("source_hash"):
        return None
    rel = str(info.get("file") or "")
    if not rel.startswith("lyricvideo/v_") or not (sdir / rel).is_file():
        return None
    return info


def state(sdir: Path, song: dict) -> dict:
    src = song.get("source") or {}
    active = isinstance(src.get("lyric_video"), dict)
    original = ((src.get("video_original") or {}) if active else src).get("video")
    has_picture = bool(original) and (sdir / str(original)).is_file()
    made = _made(sdir, src)
    return {"active": active, "made": made, "current": src.get("lyric_video") if active else None,
            "has_picture": has_picture, "styles": ["plain"] + (["overlay"] if has_picture else []),
            "lead_default": LEAD_DEFAULT, "lead_max": LEAD_MAX}


def _write_source(sdir: Path, rec: dict) -> None:
    path = sdir / "source" / "source.json"
    tmp = path.with_name("source.json.tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def router(ctx: Context) -> APIRouter:
    r = APIRouter()

    def song_ctx(song_id: str):
        lib = ctx.library()
        return lib.get(song_id), lib.song_dir(song_id)

    @r.get("/api/songs/{song_id}/lyric-video")
    def get_state(song_id: str):
        try:
            song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        if not (song.get("source") or {}).get("audio"):
            return err("song_has_no_audio")
        return state(sdir, song)

    @r.post("/api/songs/{song_id}/lyric-video")
    async def make(song_id: str, request: Request):
        body = await body_json(request)
        try:
            song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        src = song.get("source") or {}
        if not src.get("audio"):
            return err("song_has_no_audio")
        if ctx.song_busy(song_id):
            return err("song_busy", 409)
        lines = quick_lyrics.clean_lines(body.get("lines"), float(src.get("duration") or 0) or None)
        if not lines:
            return err("lyricvideo_lines")
        style = body.get("style", "plain")
        if style not in state(sdir, song)["styles"]:
            return err("lyricvideo_no_picture" if style == "overlay" else "lyricvideo_style")
        raw = body.get("lead", LEAD_DEFAULT)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not 0 <= raw <= LEAD_MAX:
            return err("lyricvideo_lead")
        font = pick_font()
        if not font:
            return err("quickmv_font_missing")
        job = ctx.submit(kind="lyricvideo", lane="cpu", script="lyric_video.py",
                         input={"song_dir": str(sdir), "style": style, "lines": lines, "lead": float(raw),
                                "font": font, "title": song["title"]},
                         title=f"lyric picture: {song['title']}", song_id=song_id, timeout_s=3600,
                         dedupe="lyricvideo")
        return {"job": job}

    @r.post("/api/songs/{song_id}/lyric-video/use")
    async def use(song_id: str, request: Request):
        body = await body_json(request)
        if not isinstance(body.get("on"), bool):
            return err("lyricvideo_use")
        try:
            song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        if ctx.song_busy(song_id):
            return err("song_busy", 409)
        src = song.get("source") or {}
        if not src.get("audio"):
            return err("song_has_no_audio")
        try:
            rec = json.loads((sdir / "source" / "source.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return err("song_unreadable", 500)
        healed = lost_lyric_picture(sdir, rec)   # the record on disk still named a lyric picture that is gone
        active = isinstance(rec.get("lyric_video"), dict)
        if body["on"] and not active:
            made = _made(sdir, rec)
            if not made:
                if healed:
                    _write_source(sdir, rec)
                return err("lyricvideo_none", 404)
            rec["video_original"] = {"video": rec.get("video"), "video_size": rec.get("video_size")}
            rec["video"], rec["video_size"] = made["file"], made.get("video_size")
            rec["lyric_video"] = {k: made.get(k) for k in ("file", "style", "lead", "lines", "made_at")}
            _write_source(sdir, rec)
        elif not body["on"] and active:
            orig = rec.pop("video_original", None) or {}
            rec.pop("lyric_video", None)
            rec["video"], rec["video_size"] = orig.get("video"), orig.get("video_size")
            if not rec["video_size"]:
                rec.pop("video_size")
            _write_source(sdir, rec)
        elif healed:
            _write_source(sdir, rec)
        song, sdir = song_ctx(song_id)
        return state(sdir, song)

    return r
