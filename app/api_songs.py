"""Song library, import, separation, key versions and media files."""
from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse

from . import stems as stems_mod
from .context import Context
from .library import LibraryError
from .util import body_json, err

SEPARATION_TIMEOUT = 3600.0


def router(ctx: Context) -> APIRouter:
    r = APIRouter()

    def song_or_err(song_id: str):
        try:
            lib = ctx.library()
            return lib, lib.get(song_id), None
        except LibraryError as exc:
            return None, None, err(exc.code, exc.status)

    # ---------------- library ----------------
    @r.get("/api/songs")
    def list_songs():
        try:
            songs = ctx.library().list()
        except OSError:
            return err("library_unavailable", 500)
        for s in songs:
            s["busy"] = ctx.song_busy(s["song_id"])
        return {"songs": songs}

    @r.post("/api/songs")
    async def create_song(request: Request):
        body = await body_json(request)
        try:
            return ctx.library().create(body.get("title"), auto_title=body.get("auto_title"))
        except LibraryError as exc:
            return err(exc.code, exc.status)
        except OSError:
            return err("library_unavailable", 500)

    @r.get("/api/songs/{song_id}")
    def get_song(song_id: str):
        _, song, e = song_or_err(song_id)
        if e:
            return e
        song["busy"] = ctx.song_busy(song_id)
        return song

    @r.patch("/api/songs/{song_id}")
    async def rename_song(song_id: str, request: Request):
        body = await body_json(request)
        try:
            return ctx.library().rename(song_id, body.get("title"))
        except LibraryError as exc:
            return err(exc.code, exc.status)

    @r.delete("/api/songs/{song_id}")
    def delete_song(song_id: str):
        if ctx.song_busy(song_id):
            return err("song_busy", 409)
        try:
            ctx.library().delete(song_id)
            return {"ok": True}
        except LibraryError as exc:
            return err(exc.code, exc.status)
        except OSError:
            return err("delete_failed", 500)

    # ---------------- import ----------------
    @r.post("/api/songs/{song_id}/import/youtube")
    async def import_youtube(song_id: str, request: Request):
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        if ctx.song_busy(song_id):
            return err("song_busy", 409)
        body = await body_json(request)
        url = str(body.get("url") or "").strip()
        if not re.match(r"^https?://", url):
            return err("invalid_url")
        return ctx.submit(kind="import", lane="cpu", script="import_media.py",
                          input={"song_dir": str(lib.song_dir(song_id)), "mode": "youtube", "url": url},
                          title=f"import: {song['title']}", song_id=song_id, timeout_s=3600,
                          dedupe="import")

    @r.post("/api/songs/{song_id}/import/file")
    async def import_file(song_id: str, file: UploadFile = File(...)):
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        if ctx.song_busy(song_id):
            return err("song_busy", 409)
        name = os.path.basename(file.filename or "upload")
        ctx.paths.tmp.mkdir(parents=True, exist_ok=True)
        dest = ctx.paths.tmp / f"upload_{uuid.uuid4().hex}{Path(name).suffix[:6].lower()}"
        size = 0
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                if size > 2 * 1024 ** 3:
                    out.close()
                    dest.unlink(missing_ok=True)
                    return err("file_too_large", 413)
                out.write(chunk)
        return ctx.submit(kind="import", lane="cpu", script="import_media.py",
                          input={"song_dir": str(lib.song_dir(song_id)), "mode": "file", "path": str(dest),
                                 "original_name": name},
                          title=f"import: {song['title']}", song_id=song_id, timeout_s=3600, dedupe="import")

    # ---------------- separation ----------------
    @r.post("/api/songs/{song_id}/stems")
    async def request_stems(song_id: str, request: Request):
        """Body: {"recipe": {...}}. Returns tracks and, if work is needed, the job."""
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        body = await body_json(request)
        try:
            layers, tracks = stems_mod.plan(lib.song_dir(song_id), song, body.get("recipe") or {})
        except stems_mod.RecipeError as exc:
            return err(exc.code)
        result: dict[str, Any] = {"tracks": tracks, "ready": not layers, "job": None}
        if layers:
            dedupe = "stems:" + ",".join(l["key"] for l in layers)
            result["job"] = ctx.submit(kind="separate", lane="gpu", script="separate.py",
                                       input={"song_dir": str(lib.song_dir(song_id)), "layers": layers},
                                       title=f"separate: {song['title']}", song_id=song_id,
                                       timeout_s=SEPARATION_TIMEOUT * len(layers), dedupe=dedupe)
        return result

    @r.post("/api/songs/{song_id}/key")
    async def request_key(song_id: str, request: Request):
        """Body: {"recipe": {...}, "semitones": n, "tracks": ["instrumental", ...]}"""
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        body = await body_json(request)
        try:
            semis = int(body.get("semitones", 0))
        except (TypeError, ValueError):
            return err("invalid_key")
        if not -12 <= semis <= 12:
            return err("invalid_key")
        try:
            layers, tracks = stems_mod.plan(lib.song_dir(song_id), song, body.get("recipe") or {})
        except stems_mod.RecipeError as exc:
            return err(exc.code)
        if layers:
            return err("stems_not_ready", 409)
        names = [n for n in (body.get("tracks") or ["instrumental", "vocals"]) if n in tracks]
        if not names:
            return err("invalid_tracks")
        if semis == 0:
            return {"ready": True, "tracks": {n: tracks[n] for n in names}, "job": None}
        dir_name = stems_mod.key_dir_name(tracks, names, semis)
        song_dir = lib.song_dir(song_id)
        out_dir = song_dir / "keys" / dir_name
        mapped = {n: f"keys/{dir_name}/{n}.wav" for n in names}
        if (out_dir / "info.json").is_file():
            return {"ready": True, "tracks": mapped, "job": None}
        job = ctx.submit(kind="key", lane="cpu", script="key_shift.py",
                         input={"semitones": semis, "out_dir": str(out_dir),
                                "files": [{"src": str(song_dir / tracks[n]), "dst": str(out_dir / f"{n}.wav")} for n in names],
                                "info": {"tracks": names}},
                         title=f"key {semis:+d}: {song['title']}", song_id=song_id, timeout_s=3600,
                         dedupe="key:" + dir_name)
        return {"ready": False, "tracks": mapped, "job": job}

    @r.get("/api/songs/{song_id}/stems")
    def list_stems(song_id: str):
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        base = lib.song_dir(song_id) / "stems"
        out = []
        if base.is_dir():
            for d in sorted(base.iterdir()):
                info = d / "info.json"
                if info.is_file():
                    try:
                        import json
                        out.append(json.loads(info.read_text(encoding="utf-8")))
                    except (OSError, ValueError):
                        pass
        return {"layers": out}

    # ---------------- media ----------------
    @r.get("/media/{song_id}/{rel:path}")
    def media(song_id: str, rel: str):
        try:
            lib = ctx.library()
            song_dir = lib.song_dir(song_id).resolve()
        except LibraryError as exc:
            return err(exc.code, exc.status)
        target = (song_dir / rel).resolve()
        if song_dir not in target.parents or not target.is_file():
            return err("file_not_found", 404)
        return FileResponse(target)

    return r
