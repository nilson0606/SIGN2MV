"""Song library, import, separation, key versions and media files."""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Request, UploadFile

from . import stems as stems_mod
from .context import Context
from .library import LibraryError
from .util import body_json, err, media_response

SEPARATION_TIMEOUT = 3600.0


def delete_song_recordings(library_root: Path, song_id: str) -> int:
    """Sing & record keeps its takes in <library>/recordings/<id>/ (shared folder of the
    sign_record format); delete the takes of this song with it."""
    from .api_sing import video_id_for
    from .sing_archive import RecordingArchive
    root = Path(library_root) / "recordings"
    if not root.is_dir():
        return 0
    vid = video_id_for(song_id)
    arc = RecordingArchive(root)
    n = 0
    for d in root.iterdir():
        meta = d / "metadata.json"
        if not meta.is_file():
            continue
        try:
            rec = json.loads(meta.read_text(encoding="utf-8")).get("recording") or {}
            if rec.get("videoId") == vid:
                arc.delete(d.name)
                n += 1
        except Exception:  # noqa: BLE001  (a damaged take must not block deleting the song)
            continue
    return n


def stored_copies_of(ctx: Context, song_id: str, song_dir: Path) -> dict[str, Any]:
    """Separation layers and key copies of a song, who uses them and how big they are."""
    from . import cover as cover_mod
    items = stems_mod.inventory(song_dir)
    users: dict[str, list[dict]] = {}
    inferred: dict[str, set[str]] = {}

    def use(ref: str, entry: dict) -> None:
        lst = users.setdefault(ref, [])
        if entry not in lst:
            lst.append(entry)

    for v in cover_mod.list_versions(song_dir):
        entry = {"type": "cover", "label": v.get("title") or v.get("label") or v.get("id")}
        for ref in stems_mod.refs_in(v, set()):
            use(ref, entry)
        for j in ((v.get("plan") or {}).get("key_jobs") or []):
            kd, src = j.get("dir"), stems_mod._parent(j.get("src"))
            if kd and src:
                inferred.setdefault(kd, set()).add(src)
    sing_refs: dict[str, dict] = {}
    sdir = song_dir / "sing"
    if sdir.is_dir():
        for d in sdir.iterdir():
            ref = stems_mod._read(d / "reference.json") if d.is_dir() else None
            if ref:
                sing_refs[d.name] = ref
    for ref in sing_refs.values():
        entry = {"type": "sing", "label": ref.get("title") or ""}
        mine = stems_mod.refs_in(ref.get("stems") or {}, set())
        for r_ in mine:
            use(r_, entry)
        base = sing_refs.get(ref.get("sourceCacheId") or "")
        if base and ref.get("pitchShift"):
            parents = stems_mod.refs_in(base.get("stems") or {}, set())
            for r_ in mine:
                if r_.startswith("keys/"):
                    inferred.setdefault(r_, set()).update(parents)
    for it in items:
        it["used_by"] = users.get(it["dir"], [])
        if it["type"] == "key" and not it["parents"]:
            it["parents"] = sorted(inferred.get(it["dir"], set()))
    return {"items": items, "total_bytes": sum(i["bytes"] for i in items), "busy": ctx.song_busy(song_id)}


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
            lib = ctx.library()
            lib.delete(song_id)
            removed = delete_song_recordings(lib.root, song_id)
            return {"ok": True, "recordings_deleted": removed}
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

    info_cache: dict[str, dict] = {}

    @r.get("/api/youtube/info")
    async def youtube_info(url: str = ""):
        """Title, length and thumbnail before importing (old /api/yt_info preview card). Read only, nothing downloaded."""
        from starlette.concurrency import run_in_threadpool
        import subprocess
        url = url.strip()
        if not re.match(r"^https?://\S+$", url) or len(url) > 500:
            return err("invalid_url")
        if url in info_cache:
            return info_cache[url]
        from .childenv import child_env
        cmd = [ctx.python("engine"), "-m", "yt_dlp", "--ignore-config", "--no-playlist", "--no-cache-dir",
               "--js-runtimes", "deno", "--socket-timeout", "15", "--skip-download", "-J", url]
        try:
            res = await run_in_threadpool(subprocess.run, cmd, capture_output=True, text=True, encoding="utf-8",
                                          errors="replace", timeout=45, env=child_env(ctx.paths),
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            return err("youtube_info_failed", 502)
        try:
            data = json.loads(res.stdout) if res.returncode == 0 else None
        except ValueError:
            data = None
        if not isinstance(data, dict):
            return err("youtube_info_failed", 502)
        out = {"id": data.get("id") or "", "title": data.get("title") or "", "duration": data.get("duration"),
               "uploader": data.get("uploader") or data.get("channel") or "", "thumbnail": data.get("thumbnail") or "",
               "url": data.get("webpage_url") or url, "site": data.get("extractor_key") or ""}
        if len(info_cache) > 200:
            info_cache.clear()
        info_cache[url] = out
        return out

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
        song_dir = lib.song_dir(song_id)
        mapped = {n: stems_mod.key_track(tracks[n], semis)[1] for n in names}
        items = [stems_mod.key_item(song_dir, tracks[n], semis) for n in names]
        items = [it for it in items if not (Path(it["out_dir"]) / "info.json").is_file()]
        if not items:
            return {"ready": True, "tracks": mapped, "job": None}
        job = ctx.submit(kind="key", lane="cpu", script="key_shift.py",
                         input={"semitones": semis, "items": items},
                         title=f"key {semis:+d}: {song['title']}", song_id=song_id, timeout_s=1800 * len(items),
                         dedupe="key:" + ",".join(sorted(Path(it["out_dir"]).name for it in items)))
        return {"ready": False, "tracks": mapped, "job": job}

    def stored_copies(song_id: str, song_dir: Path) -> dict[str, Any]:
        return stored_copies_of(ctx, song_id, song_dir)

    @r.get("/api/songs/{song_id}/storage")
    def song_storage(song_id: str):
        """Disk usage of one song by category (source, stems, covers, sing, MV ...)."""
        from . import storage
        from .api_sing import video_id_for
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        recs = storage.recordings_index(lib.root).get(video_id_for(song_id), [])
        return {**storage.song_usage(lib.song_dir(song_id), recs), "disk": storage.disk(lib.root)}

    @r.get("/api/storage")
    def library_storage():
        """Size of every song (for the library list) and free disk space."""
        from . import storage
        from .api_sing import video_id_for
        try:
            lib = ctx.library()
            songs = lib.list()
        except LibraryError as exc:
            return err(exc.code, exc.status)
        recs = storage.recordings_index(lib.root)
        sizes = {}
        for s in songs:
            sid = s["song_id"]
            sizes[sid] = storage.song_usage(lib.song_dir(sid), recs.get(video_id_for(sid), []))["total"]
        return {"songs": sizes, "total": sum(sizes.values()), "disk": storage.disk(lib.root)}

    @r.get("/api/songs/{song_id}/stems")
    def list_stems(song_id: str):
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        song_dir = lib.song_dir(song_id)
        out = stored_copies(song_id, song_dir)
        out["layers"] = [i for i in out["items"] if i["type"] == "layer"]
        return out

    @r.delete("/api/songs/{song_id}/stems/{name}")
    def delete_stem_copy(song_id: str, name: str):
        return delete_stored_copy(song_id, "stems", name)

    @r.delete("/api/songs/{song_id}/keys/{name}")
    def delete_key_copy(song_id: str, name: str):
        return delete_stored_copy(song_id, "keys", name)

    def delete_stored_copy(song_id: str, top: str, name: str):
        """Delete one separation layer or key copy and everything computed from it."""
        if top not in ("stems", "keys") or not stems_mod.DIR_NAME.match(name) or name in (".", ".."):
            return err("file_not_found", 404)
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        if ctx.song_busy(song_id):
            return err("song_busy", 409)
        song_dir = lib.song_dir(song_id)
        target = f"{top}/{name}"
        items = stored_copies(song_id, song_dir)["items"]
        if not any(i["dir"] == target for i in items):
            return err("file_not_found", 404)
        gone = stems_mod.dependents(items, target)
        import shutil
        freed = 0
        for rel in reversed(gone):
            d = song_dir / rel
            size = next((i["bytes"] for i in items if i["dir"] == rel), 0)
            try:
                shutil.rmtree(d)
            except FileNotFoundError:
                pass
            except OSError:
                return err("file_in_use", 409)
            freed += size
        return {"deleted": gone, "bytes": freed}

    @r.post("/api/open-folder")
    async def open_folder(request: Request):
        """Show a song file (or the song folder) in Windows Explorer (old 「📂 開啟電腦資料夾」).
        Body: {"song_id", "rel"?}. Only files inside that song's folder."""
        import subprocess
        body = await body_json(request)
        try:
            lib = ctx.library()
            song_dir = lib.song_dir(str(body.get("song_id") or "")).resolve()
        except LibraryError as exc:
            return err(exc.code, exc.status)
        target = (song_dir / str(body.get("rel") or "")).resolve()
        if target != song_dir and song_dir not in target.parents:
            return err("file_not_found", 404)
        if not target.exists():
            return err("file_not_found", 404)
        if os.name != "nt":
            return err("open_folder_windows_only")
        args = ["explorer", f"/select,{target}"] if target.is_file() else ["explorer", str(target)]
        subprocess.Popen(args)
        return {"ok": True, "path": str(target)}

    # ---------------- media ----------------
    @r.get("/media/{song_id}/{rel:path}")
    def media(song_id: str, rel: str, request: Request):
        try:
            lib = ctx.library()
            song_dir = lib.song_dir(song_id).resolve()
        except LibraryError as exc:
            return err(exc.code, exc.status)
        target = (song_dir / rel).resolve()
        if song_dir not in target.parents or not target.is_file():
            return err("file_not_found", 404)
        return media_response(target, request)

    return r
