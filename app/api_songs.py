"""Song library, import, separation, key versions and media files."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from . import stems as stems_mod
from .context import Context
from .library import LibraryError
from .proc import ManagedProcess
from .util import body_json, err, media_response

SEPARATION_TIMEOUT = 3600.0
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def song_recording_dirs(library_root: Path, song_id: str) -> list[Path]:
    """Sing & record keeps its takes in <library>/recordings/<id>/ (shared folder of the sign_record
    format); the folders of this song's takes."""
    from .api_sing import video_id_for
    root = Path(library_root) / "recordings"
    if not root.is_dir():
        return []
    vid = video_id_for(song_id)
    out = []
    for d in root.iterdir():
        meta = d / "metadata.json"
        if not meta.is_file():
            continue
        try:
            rec = json.loads(meta.read_text(encoding="utf-8")).get("recording") or {}
        except Exception:  # noqa: BLE001  (a damaged take is skipped)
            continue
        if rec.get("videoId") == vid:
            out.append(d)
    return out


def delete_song_recordings(library_root: Path, song_id: str) -> int:
    """Delete the takes of this song with it."""
    from .sing_archive import RecordingArchive
    root = Path(library_root) / "recordings"
    arc = RecordingArchive(root) if root.is_dir() else None
    n = 0
    for d in song_recording_dirs(library_root, song_id):
        try:
            arc.delete(d.name)
            n += 1
        except Exception:  # noqa: BLE001  (a damaged take must not block deleting the song)
            continue
    return n


# ---------------- audio shift (songs nothing has been made from yet) ----------------
SHIFT_MAX_S = 2.0
SHIFT_KEEP = {"song.json", "source"}


def _has_content(p: Path) -> bool:
    return p.is_file() or (p.is_dir() and any(_has_content(c) for c in p.iterdir()))


def audio_shift_block(ctx: Context, song_id: str, song_dir: Path, song: dict) -> str | None:
    """Why this song's audio cannot be shifted, or None. Anything made from the audio (stems, keys, sing
    references, covers, MVs, renders, recordings, ...) follows its timeline, so only a song with nothing
    but its source may be shifted. Any other folder blocks it, also ones added later."""
    src = song.get("source") or {}
    if not src.get("audio") or not src.get("video"):
        return "shift_no_video"
    if ctx.song_busy(song_id):
        return "song_busy"
    for entry in song_dir.iterdir():
        if entry.name not in SHIFT_KEEP and _has_content(entry):
            return "shift_processed"
    if song_recording_dirs(ctx.library().root, song_id):
        return "shift_processed"
    return None


def _wav_frames(path: Path) -> tuple[int, int]:
    """(sample rate, frames) of a RIFF WAV (source/audio.wav is float32; Python's wave module cannot read it)."""
    with open(path, "rb") as fh:
        head = fh.read(12)
        if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError("not a WAV file")
        rate = block = 0
        while True:
            ck = fh.read(8)
            if len(ck) < 8:
                raise ValueError("WAV without data")
            cid, size = ck[:4], int.from_bytes(ck[4:8], "little")
            if cid == b"fmt ":
                fmt = fh.read(size)
                rate, block = int.from_bytes(fmt[4:8], "little"), int.from_bytes(fmt[12:14], "little")
            elif cid == b"data":
                if not block:
                    raise ValueError("WAV data before fmt")
                return rate, size // block
            else:
                fh.seek(size + (size & 1), 1)


def shift_source(song_dir: Path, seconds: float) -> dict:
    """Shift source/audio.wav by `seconds` (+ = later: silence at the start, the end cut; - = earlier: the
    start cut, silence at the end), sample-exact and the same length; put the shifted audio into video.mp4
    (the picture is copied, not encoded again). The new source is built in source.importing and put in
    place like a re-import (the old one is deleted only once the new one is there). The original upload
    copy (source/original.*) is not carried over: it no longer matches."""
    src_dir = song_dir / "source"
    rec = json.loads((src_dir / "source.json").read_text(encoding="utf-8"))
    audio, video = src_dir / "audio.wav", song_dir / rec["video"]
    rate, frames = _wav_frames(audio)
    n = round(abs(seconds) * rate)
    if n <= 0 or n >= frames:
        raise ValueError("shift_range")
    af = (f"adelay=delays={n}S:all=1,atrim=end_sample={frames}" if seconds > 0
          else f"atrim=start_sample={n},asetpts=PTS-STARTPTS,apad=whole_len={frames}")
    work = song_dir / "source.importing"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    try:
        ff = shutil.which("ffmpeg") or "ffmpeg"
        run = lambda args: subprocess.run([ff, "-nostdin", "-y", "-v", "error", *args],  # noqa: E731
                                          capture_output=True, timeout=600, creationflags=NO_WINDOW, check=True)
        run(["-i", str(audio), "-af", af, "-c:a", "pcm_f32le", str(work / "audio.wav")])
        if _wav_frames(work / "audio.wav") != (rate, frames):
            raise RuntimeError("shifted audio has a different length")
        run(["-i", str(video), "-i", str(work / "audio.wav"), "-map", "0:v:0", "-c:v", "copy",
             "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
             str(work / Path(rec["video"]).name)])
        total = round(float(rec.get("audio_offset_s") or 0) + n / rate * (1 if seconds > 0 else -1), 4)
        base = rec.get("source_hash_base") or rec.get("source_hash") or rec.get("audio")
        rec.update({
            "source_hash_base": base,
            # a new name for the audio: caches keyed by the source (stems, covers) never take the old one
            "source_hash": f"{base}#shift{round(total * 1000):+d}ms" if round(total * 1000) else base,
            "audio_offset_s": total,
            "shifted_at": time.time(),
        })
        rec.pop("original", None)
        (work / "source.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        old = song_dir / "source.old"
        for attempt in range(8):   # Windows: a player still reading video.mp4 keeps the folder from moving
            try:
                os.replace(src_dir, old)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.5)
        try:
            os.replace(work, src_dir)
        except BaseException:
            if old.is_dir() and not src_dir.exists():
                os.replace(old, src_dir)
            raise
        shutil.rmtree(old, ignore_errors=True)
        return rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


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
        def ask() -> tuple[int, str]:
            # a whole process tree: on a timeout yt-dlp's deno helper is ended too (an outside review, R3-11)
            proc = ManagedProcess(cmd, env=child_env(ctx.paths))
            try:
                out, _ = proc.popen.communicate(timeout=45)
                return proc.popen.returncode, out.decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                proc.kill_tree()
                raise
            finally:
                proc.close()
        try:
            code, stdout = await run_in_threadpool(ask)
        except (OSError, subprocess.TimeoutExpired):
            return err("youtube_info_failed", 502)
        try:
            data = json.loads(stdout) if code == 0 else None
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

    # ---------------- audio shift ----------------
    shift_lock = threading.Lock()

    @r.get("/api/songs/{song_id}/audio-shift")
    def audio_shift_state(song_id: str):
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        block = audio_shift_block(ctx, song_id, lib.song_dir(song_id), song)
        return {"allowed": block is None, "reason": block,
                "offset": float((song.get("source") or {}).get("audio_offset_s") or 0), "max": SHIFT_MAX_S}

    @r.post("/api/songs/{song_id}/audio-shift")
    async def audio_shift_apply(song_id: str, request: Request):
        body = await body_json(request)
        try:
            seconds = round(float(body.get("seconds")), 2)
        except (TypeError, ValueError):
            return err("shift_range")
        if not (0 < abs(seconds) <= SHIFT_MAX_S):
            return err("shift_range")
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        if not shift_lock.acquire(blocking=False):
            return err("song_busy", 409)
        try:
            song_dir = lib.song_dir(song_id)
            block = audio_shift_block(ctx, song_id, song_dir, song)
            if block:
                return err(block, 409)
            try:
                rec = await run_in_threadpool(shift_source, song_dir, seconds)
            except ValueError:
                return err("shift_range")
            except (OSError, RuntimeError, subprocess.SubprocessError):
                return err("shift_failed", 500)
        finally:
            shift_lock.release()
        return {"ok": True, "offset": rec["audio_offset_s"], "source": rec}

    # ---------------- source as MP3 ----------------
    mp3_lock = threading.Lock()

    @r.get("/api/songs/{song_id}/source.mp3")
    def source_mp3(song_id: str):
        """The song's own audio as a 192 kbps MP3 download, made from the lossless source/audio.wav
        (the video's AAC is itself encoded from that WAV, so this is one lossy step, not two).
        Made for each request in tmp and removed after sending: nothing is added to the library."""
        lib, song, e = song_or_err(song_id)
        if e:
            return e
        src = (song.get("source") or {}).get("audio")
        wav = (lib.song_dir(song_id) / src) if src else None
        if not wav or not wav.is_file():
            return err("file_not_found", 404)
        if not mp3_lock.acquire(blocking=False):
            return err("mp3_busy", 409)
        out = None
        try:
            ctx.paths.tmp.mkdir(parents=True, exist_ok=True)
            out = ctx.paths.tmp / f"source_{uuid.uuid4().hex}.mp3"
            try:
                res = subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-nostdin", "-y", "-v", "error",
                                      "-i", str(wav), "-vn", "-threads", "2", "-c:a", "libmp3lame", "-b:a", "192k",
                                      str(out)], capture_output=True, timeout=180, creationflags=NO_WINDOW)
                ok = res.returncode == 0 and out.is_file() and out.stat().st_size > 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
            if not ok:
                out.unlink(missing_ok=True)
                return err("mp3_failed", 500)
        finally:
            mp3_lock.release()
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(song.get("title") or song_id)).strip(" .")[:120] or song_id
        return FileResponse(out, media_type="audio/mpeg", filename=f"{name}.mp3",
                            background=BackgroundTask(out.unlink, missing_ok=True))

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
