"""Quick MV: an audio-reactive title card made straight from a song's audio (no lyrics, no photos).

Same picture as sign_record's "製作 MV". Any of the song's audio can be used: the original,
an AI cover version or a sing & record take (both are renders of the song).
Videos live in songs/<id>/quickmv/<qid>/{video.mp4, info.json}; deleting the song deletes them.

Routes:
  GET    /api/songs/{id}/quickmv            sources, defaults and the song's quick MVs
  POST   /api/songs/{id}/quickmv            {"source": "original"|<render id>, "title", "artist"} -> job
  DELETE /api/songs/{id}/quickmv/{qid}
  GET    /api/songs/{id}/quickmv/{qid}/download   the MP4 as a download with a readable name
"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from . import renders as renders_mod
from . import settings as settings_mod
from .context import Context
from .library import LibraryError
from .util import body_json, err

QID = re.compile(r"^q[a-f0-9]{12}$")
FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/PingFang.ttc"]
HEADING = "C O V E R   S E S S I O N"
FOOTER = "AUDIO REACTIVE  /  1080p  /  30 fps"
LABEL = {"zh": "翻唱｜", "en": "Cover｜"}


def no_ai(text: str, singer: str) -> str:
    """The MV never shows "AI" (same rule as the MV workspace)."""
    cover_word = f"{singer} 翻唱" if singer else "翻唱"
    t = re.sub(r"(?i)AI\s*翻唱", cover_word, str(text or ""))
    t = re.sub(r"(?i)AI\s*Cover", cover_word, t)
    t = re.sub(r"(?i)(?<![a-zA-Z])AI(?![a-zA-Z])", singer, t)
    return re.sub(r"\s{2,}", " ", t).strip()


def clean_label(value: Any, max_len: int) -> str | None:
    v = str(value or "").strip()
    if not v or len(v) > max_len or re.search(r"[\x00-\x1f\x7f]", v):
        return None
    return v


def pick_font() -> str:
    override = os.environ.get("SIGN2MV_MV_FONT")
    for p in ([override] if override else []) + FONTS:
        if p and os.path.isfile(p):
            return p
    return ""


def quick_dir(song_dir: Path) -> Path:
    return song_dir / "quickmv"


def list_quick(song_dir: Path) -> list[dict]:
    base = quick_dir(song_dir)
    out = []
    if base.is_dir():
        for d in base.iterdir():
            if not QID.match(d.name) or not (d / "video.mp4").is_file():
                continue
            try:
                info = json.loads((d / "info.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                info = {}
            out.append({**info, "id": d.name, "path": f"quickmv/{d.name}/video.mp4"})
    out.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return out


def router(ctx: Context) -> APIRouter:
    r = APIRouter()

    def song_ctx(song_id: str):
        lib = ctx.library()
        song = lib.get(song_id)
        return song, lib.song_dir(song_id)

    def brand() -> tuple[str, str]:
        cfg = ctx.settings()
        lang = "en" if settings_mod.effective_language(cfg) == "en" else "zh"
        return (cfg.get("cover_singer_name") or "").strip(), lang

    def sources(song: dict, song_id: str) -> list[dict]:
        out = []
        src = song.get("source") or {}
        if src.get("audio"):
            out.append({"id": "original", "kind": "original", "title": song["title"], "path": src["audio"],
                        "duration": src.get("duration")})
        for rd in renders_mod.list_renders(ctx, song_id):
            if rd.get("kind") in ("cover", "sing"):
                out.append({"id": rd["id"], "kind": rd["kind"], "title": rd.get("title") or rd["id"],
                            "path": rd["path"], "duration": rd.get("duration"), "created_at": rd.get("created_at")})
        return out

    @r.get("/api/songs/{song_id}/quickmv")
    def get_quick(song_id: str):
        try:
            song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        singer, lang = brand()
        return {"sources": sources(song, song_id), "items": list_quick(sdir),
                "defaults": {"title": no_ai(song["title"], singer)[:60], "artist": singer, "label": LABEL[lang]},
                "font_ok": bool(pick_font())}

    @r.post("/api/songs/{song_id}/quickmv")
    async def make_quick(song_id: str, request: Request):
        body = await body_json(request)
        try:
            song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        singer, lang = brand()
        title = clean_label(no_ai(body.get("title"), singer), 60)
        artist = clean_label(no_ai(body.get("artist"), singer), 50)
        if not title:
            return err("quickmv_title")
        if not artist:
            return err("quickmv_artist")
        src = next((s for s in sources(song, song_id) if s["id"] == body.get("source")), None)
        if not src:
            return err("quickmv_source")
        font = pick_font()
        if not font:
            return err("quickmv_font_missing")
        qid = "q" + uuid.uuid4().hex[:12]
        info = {"source": src["id"], "source_kind": src["kind"], "source_title": src["title"], "artist": artist}
        job = ctx.submit(kind="quickmv", lane="cpu", script="mv_quick.py",
                         input={"audio": str(sdir / src["path"]), "out_dir": str(quick_dir(sdir) / qid), "font": font,
                                "title": title, "artist_line": LABEL[lang] + artist, "heading": HEADING,
                                "footer": FOOTER, "info": info},
                         title=f"quick MV: {song['title']}", song_id=song_id, timeout_s=3600,
                         dedupe=f"quickmv:{src['id']}:{title}:{artist}")
        return {"job": job, "id": qid}

    @r.delete("/api/songs/{song_id}/quickmv/{qid}")
    def delete_quick(song_id: str, qid: str):
        if not QID.match(qid or ""):
            return err("file_not_found", 404)
        try:
            _song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        d = quick_dir(sdir) / qid
        if not d.is_dir():
            return err("file_not_found", 404)
        try:
            shutil.rmtree(d)
        except OSError:
            return err("file_in_use", 409)
        return {"ok": True}

    # ---------------- all songs (sign_record's "saved MVs" panel: list, search, select, delete, clear all)
    @r.get("/api/quickmv")
    def list_all():
        lib = ctx.library()
        out = []
        for song in lib.list():
            for it in list_quick(lib.song_dir(song["song_id"])):
                out.append({**it, "song_id": song["song_id"], "song_title": song["title"]})
        out.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return {"items": out, "folder": str(lib.root / "songs"), "bytes": sum(int(i.get("bytes") or 0) for i in out)}

    @r.post("/api/quickmv/delete")
    async def delete_many(request: Request):
        """Body: {"items": [{"song_id", "id"}]} or {"all": true}. Busy songs are skipped."""
        body = await body_json(request)
        lib = ctx.library()
        if body.get("all") is True:
            targets = [(s["song_id"], it["id"]) for s in lib.list() for it in list_quick(lib.song_dir(s["song_id"]))]
        else:
            raw = body.get("items")
            if not isinstance(raw, list) or not 1 <= len(raw) <= 500:
                return err("quickmv_selection")
            targets = [(str(x.get("song_id") or ""), str(x.get("id") or "")) for x in raw if isinstance(x, dict)]
        deleted, skipped = 0, 0
        for sid, qid in targets:
            if not QID.match(qid):
                skipped += 1
                continue
            try:
                d = quick_dir(lib.song_dir(sid)) / qid
            except LibraryError:
                skipped += 1
                continue
            if not d.is_dir():   # a quick MV appears only when finished (renamed in at the end)
                skipped += 1
                continue
            try:
                shutil.rmtree(d)
                deleted += 1
            except OSError:
                skipped += 1
        return {"deleted": deleted, "skipped": skipped}

    @r.get("/api/songs/{song_id}/quickmv/{qid}/download")
    def download_quick(song_id: str, qid: str):
        if not QID.match(qid or ""):
            return err("file_not_found", 404)
        try:
            _song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        f = quick_dir(sdir) / qid / "video.mp4"
        if not f.is_file():
            return err("file_not_found", 404)
        try:
            info = json.loads((f.parent / "info.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = {}
        safe = lambda v: re.sub(r'[\\/:*?"<>|.\x00-\x1f]', "_", str(v or ""))[:65]  # noqa: E731
        name = f"MV_{safe(info.get('title'))}_{safe(info.get('artist'))}_{qid[1:9]}.mp4"
        return FileResponse(f, media_type="video/mp4", filename=name)

    return r
