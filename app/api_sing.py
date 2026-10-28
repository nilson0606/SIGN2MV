"""Sing & record workspace backend.

The sing & record page is the proven sign_record front end (web/sing/). This
module provides the local-helper API that page expects, under /sr, backed by
the SIGN2MV song library, separation cache and job queue:

  /sr/session, /sr/health, /sr/busy, /sr/playback-trace
  /sr/local-media[/<videoId>]          songs of the library as playable media
  /sr/library/location                 always the SIGN2MV library
  /sr/library, /sr/library/<cacheId>[/reference|vocals|accompaniment|lead|backing|masks]
  /sr/jobs, /sr/jobs/<id>[/reference]  "prepare song" = stems + melody reference (+ key)
  /sr/recordings...                    recording archive (WAV/WebM + metadata)
  /sr/microphone/...                   native (WASAPI) capture, see native_mic.py
  /sr/diagnostics...                   optional recording diagnostics
Song ids map to sign_record media ids "local_<64 hex>" (sha256 of the song id).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import stems as stems_mod
from .context import Context

TOKEN = secrets.token_hex(32)
FEATURES = ['local-media', 'local-audio', 'library', 'stem-preview', 'library-location', 'separation-progress',
            'rebuild-song', 'lead-vocals', 'separation-models', 'score-masks', 'pitch-methods',
            'residual-separation', 'mel-roformer', 'recording-mp3', 'recording-library', 'recording-raw-mime',
            'playback-trace', 'native-microphone', 'native-speaker-output', 'song-key-versions']
SEP_MODELS = {"demucs": "demucs", "bs-roformer": "bs_roformer", "mel-roformer": "mel_roformer"}
CACHE_RE = re.compile(r"^(local_[a-f0-9]{64})_(0|15|30|60)(_lead)?(?:_(bs-roformer|mel-roformer))?(_rmvpe)?(_residual)?_v1"
                      r"(?:_key_([mp])([1-9]|1[0-2]))?$")
REC_ID = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
MAX_AUDIO = 384 * 1024 * 1024
MAX_META = 16 * 1024 * 1024


def video_id_for(song_id: str) -> str:
    return "local_" + hashlib.sha256(("sign2mv:" + song_id).encode()).hexdigest()


def cache_key(video_id: str, seconds: int, vocal_mode: str, model: str, pitch: str, method: str, shift: int = 0) -> str:
    key = (f"{video_id}_{seconds}{'_lead' if vocal_mode == 'lead' else ''}"
           f"{'_' + model if model != 'demucs' else ''}{'_rmvpe' if pitch == 'rmvpe' else ''}"
           f"{'_residual' if method == 'residual' else ''}_v1")
    if shift:
        key += f"_key_{'m' if shift < 0 else 'p'}{abs(shift)}"
    return key


def parse_cache_key(cache_id: str) -> dict[str, Any] | None:
    m = CACHE_RE.match(cache_id or "")
    if not m:
        return None
    vid, secs, lead, model, rmvpe, residual, sign, mag = m.groups()
    shift = 0 if not sign else (int(mag) * (-1 if sign == "m" else 1))
    return {"videoId": vid, "seconds": int(secs), "vocalMode": "lead" if lead else "all",
            "separationModel": model or "demucs", "pitchMethod": "rmvpe" if rmvpe else "yin",
            "separationMethod": "residual" if residual else "single", "pitchShift": shift}


def recipe_for(p: dict[str, Any]) -> dict[str, Any]:
    residual = p["separationMethod"] == "residual"
    return {"model": SEP_MODELS[p["separationModel"]], "second_pass": residual,
            "lead": p["vocalMode"] == "lead", "lead_from": "residual" if residual else "vocals"}


def stem_rel_map(tracks: dict[str, str], p: dict[str, Any]) -> dict[str, str]:
    residual = p["separationMethod"] == "residual"
    m = {"vocals": tracks["residual_vocals"] if residual else tracks["vocals"],
         "accompaniment": tracks["instrumental"]}
    if p["vocalMode"] == "lead":
        m["lead"] = tracks["lead"]
        m["backing"] = tracks["backing"]
    return m


def json_err(code: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=code)


def _rmtree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


# ===================================================================== masks
def normalize_masks(masks: Any, duration: float) -> list[dict[str, float]]:
    """Port of scoring.mjs normalizeMasks: validate (0 <= start < end <= duration, max 100),
    sort and merge overlapping/adjacent ranges."""
    if not isinstance(masks, list) or len(masks) > 100 or not (duration == duration) or duration <= 0:
        raise ValueError("遮罩資料無效，最多 100 段。")
    rows = []
    for m in masks:
        try:
            start, end = float(m.get("start")), float(m.get("end"))
        except (AttributeError, TypeError, ValueError):
            raise ValueError("遮罩需符合 0 ≤ 起點 < 終點 ≤ 歌曲基準長度。")
        if not (start == start and end == end) or start < 0 or end <= start or end > duration:
            raise ValueError("遮罩需符合 0 ≤ 起點 < 終點 ≤ 歌曲基準長度。")
        rows.append((start, min(duration, end)))
    rows.sort()
    merged: list[list[float]] = []
    for s_, e in rows:
        if merged and s_ <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s_, e])
    return [{"start": s_, "end": e} for s_, e in merged]


# ===================================================================== router
def router(ctx: Context) -> APIRouter:
    r = APIRouter()
    lock = threading.Lock()
    prep_jobs: dict[str, dict[str, Any]] = {}   # compat job id -> info
    editing_masks: set[str] = set()

    def library_root() -> Path:
        return Path(ctx.settings()["library_dir"])

    def song_index() -> dict[str, dict[str, Any]]:
        """videoId -> song (only songs with imported audio)."""
        out = {}
        try:
            for s in ctx.library().list():
                if s.get("source") and s["source"].get("audio"):
                    out[video_id_for(s["song_id"])] = s
        except OSError:
            pass
        return out

    def song_for_video(video_id: str) -> dict[str, Any] | None:
        return song_index().get(video_id)

    def sing_dir(song_id: str) -> Path:
        return ctx.library().song_dir(song_id) / "sing"

    def auth(request: Request) -> bool:
        return request.headers.get("x-karaoke-token") == TOKEN

    async def read_json_body(request: Request, limit: int = 65536) -> dict[str, Any]:
        raw = await request.body()
        if len(raw) > limit:
            raise ValueError("Request too large")
        value = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(value, dict):
            raise ValueError("invalid body")
        return value

    # ------------------------------------------------------------ session / health
    def trace_file() -> Path:
        return ctx.paths.runtime / "playback-trace.enabled"

    def trace_active() -> bool:
        # like sign_record: a flag file (runtime/playback-trace.enabled) or ?tracePlayback=1 on the page
        return trace_file().is_file() or bool(os.environ.get("SIGN2MV_PLAYBACK_TRACE"))

    @r.get("/sr/session")
    def session():
        return {"token": TOKEN, "playbackTraceActive": trace_active(), "features": FEATURES}

    health_cache: dict[str, Any] = {"t": 0.0, "value": None}

    def run_checks() -> dict[str, bool]:
        """What sign_record's helper checked, for SIGN2MV's own environments (cached 10 min)."""
        import subprocess
        from .childenv import child_env
        env = child_env(ctx.paths)
        exe = lambda name: shutil.which(name, path=env.get("PATH")) is not None  # noqa: E731
        py = ctx.python("engine")
        checks = {"python": Path(py).is_file(), "node": True, "ffmpeg": exe("ffmpeg"), "ffprobe": exe("ffprobe")}
        mods = {"ytDlp": "yt_dlp", "demucs": "demucs", "torch": "torch", "torchaudio": "torchaudio",
                "soundfile": "soundfile"}
        code = ("import importlib.util,json;print(json.dumps({k: importlib.util.find_spec(m) is not None "
                "for k, m in %r.items()}))" % mods)
        try:
            res = subprocess.run([py, "-c", code], capture_output=True, text=True, timeout=60, env=env,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            found = json.loads(res.stdout.strip().splitlines()[-1]) if res.returncode == 0 else {}
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            found = {}
        for k in mods:
            checks[k] = bool(found.get(k))
        return checks

    @r.get("/sr/health")
    def health():
        report = {}
        try:
            report = json.loads(ctx.paths.install_report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        if health_cache["value"] is None or time.time() - health_cache["t"] > 600 or not all(health_cache["value"].values()):
            health_cache.update(t=time.time(), value=run_checks())
        checks = dict(health_cache["value"])
        return {"app": "karaoke-local-helper", "version": 1, "features": FEATURES, "ready": all(checks.values()),
                "checks": checks, "audioUpload": False, "sign2mv": True, "install": report.get("completed", False)}

    @r.get("/sr/busy")
    def busy():
        active = any(ctx.jobs.get(j.get("queue_id") or "") and ctx.jobs.get(j["queue_id"])["status"] in ("queued", "running")
                     for j in prep_jobs.values() if j.get("queue_id"))
        mic = native_state["active"] is not None
        return {"preparing": active, "mv": False, "localMedia": False, "microphone": mic, "library": bool(editing_masks),
                "busy": active or mic or bool(editing_masks)}

    def busy_reasons() -> list[str]:
        out = []
        if native_state["active"] is not None:
            out.append("microphone")
        if editing_masks:
            out.append("masks")
        return out
    ctx.busy_hooks.append(busy_reasons)

    @r.post("/sr/playback-trace")
    async def playback_trace(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        if not trace_active():
            return {"saved": False}
        try:
            data = await read_json_body(request, limit=262144)
        except ValueError:
            return json_err(400, "Invalid trace")
        log_dir = ctx.paths.logs
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "playback-trace.log", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), **(data if isinstance(data, dict) else {"data": data})},
                                ensure_ascii=False) + "\n")
        return {"saved": True}

    # ------------------------------------------------------------ local media (songs)
    @r.get("/sr/local-media")
    def local_media_list(request: Request):
        rows = []
        for vid, s in song_index().items():
            rows.append({"id": vid, "title": s["title"], "kind": "video" if s["source"].get("video") else "audio",
                         "songId": s["song_id"]})
        rows.sort(key=lambda x: x["title"])
        return {"media": rows}

    @r.get("/sr/local-media/{video_id}")
    def local_media_get(video_id: str):
        s = song_for_video(video_id)
        if not s:
            return json_err(404, "找不到這首歌，請到「歌曲庫」匯入。")
        src = s["source"]
        rel = src.get("video") or src["audio"]
        return {"id": video_id, "title": s["title"], "kind": "video" if src.get("video") else "audio",
                "songId": s["song_id"], "duration": src.get("duration"),
                "playbackPath": f"/media/{s['song_id']}/{rel}"}

    # ------------------------------------------------------------ library location
    @r.get("/sr/library/location")
    def location_get():
        root = str(library_root())
        return {"configured": True, "path": root, "suggestedPath": root, "existingLibrary": True, "selectionPending": False}

    @r.post("/sr/library/location")
    @r.post("/sr/library/location/pick")
    @r.post("/sr/library/location/cancel")
    def location_set():
        return json_err(400, "歌曲庫位置請到 SIGN2MV 的「設定」修改。")

    # ------------------------------------------------------------ references
    def ref_dir(cache_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]] | None:
        p = parse_cache_key(cache_id)
        if not p:
            return None
        s = song_for_video(p["videoId"])
        if not s:
            return None
        return sing_dir(s["song_id"]) / cache_id, p, s

    def mask_file(song_id: str, video_id: str, seconds: int) -> Path:
        return sing_dir(song_id) / ".masks" / f"{video_id}_{seconds}.json"

    def shared_masks(song_id: str, p: dict[str, Any], duration: float) -> list[dict[str, float]]:
        try:
            masks = json.loads(mask_file(song_id, p["videoId"], p["seconds"]).read_text(encoding="utf-8")).get("masks", [])
            masks = normalize_masks(masks, 905)
        except (OSError, ValueError):
            masks = []
        return [{"start": m["start"], "end": min(m["end"], duration)} for m in masks if m["start"] < min(m["end"], duration)]

    def load_reference(cache_id: str) -> dict[str, Any] | None:
        found = ref_dir(cache_id)
        if not found:
            return None
        d, p, s = found
        try:
            value = json.loads((d / "reference.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        song_dir = ctx.library().song_dir(s["song_id"])
        stems = value.get("stems") or {}
        has = all((song_dir / rel).is_file() for rel in stems.values()) and bool(stems)
        value.update({"cacheId": cache_id, "hasPreview": has, "title": value.get("title") or s["title"],
                      "masks": shared_masks(s["song_id"], p, float(value.get("duration") or 905)),
                      "rangeSeconds": p["seconds"], "songId": s["song_id"]})
        return value

    @r.get("/sr/library")
    def library_list(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        rows = []
        for vid, s in song_index().items():
            base = sing_dir(s["song_id"])
            if not base.is_dir():
                continue
            for d in base.iterdir():
                if not d.is_dir() or not CACHE_RE.match(d.name):
                    continue
                ref = load_reference(d.name)
                if not ref:
                    continue
                song_dir = ctx.library().song_dir(s["song_id"])
                size = sum((song_dir / rel).stat().st_size for rel in (ref.get("stems") or {}).values()
                           if (song_dir / rel).is_file())
                rows.append({"id": d.name, "videoId": vid, "title": ref["title"], "baseTitle": ref.get("baseTitle") or ref["title"],
                             "pitchShift": ref.get("pitchShift", 0), "sourceCacheId": ref.get("sourceCacheId"),
                             "seconds": ref["rangeSeconds"], "duration": ref.get("duration"), "hasPreview": ref["hasPreview"],
                             "vocalMode": ref.get("vocalMode", "all"), "separationModel": ref.get("separationModel", "demucs"),
                             "pitchMethod": ref.get("pitchMethod", "yin"), "separationMethod": ref.get("separationMethod", "single"),
                             "savedAt": ref.get("savedAt", ""), "bytes": size})
        rows.sort(key=lambda x: x["savedAt"], reverse=True)
        return {"songs": rows}

    @r.get("/sr/library/{cache_id}/{asset}")
    def library_asset(cache_id: str, asset: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        ref = load_reference(cache_id)
        if not ref:
            return json_err(404, "本機基準已刪除，請重新準備。")
        if asset == "reference":
            ref.pop("stems", None)
            return ref
        if asset in ("vocals", "accompaniment", "lead", "backing"):
            rel = (ref.get("stems") or {}).get(asset)
            path = ctx.library().song_dir(ref["songId"]) / rel if rel else None
            if not path or not path.is_file():
                return json_err(404, "尚未保留試聽音軌，請重新準備。")
            return FileResponse(path, media_type="audio/wav", headers={"X-Content-Type-Options": "nosniff"})
        return json_err(405, "Unsupported method")

    @r.post("/sr/library/{cache_id}/masks")
    async def library_masks(cache_id: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        ref = load_reference(cache_id)
        if not ref:
            return json_err(400, "歌曲基準不存在，請重新載入歌曲。")
        p = parse_cache_key(cache_id)
        f = mask_file(ref["songId"], p["videoId"], p["seconds"])
        with lock:
            if str(f) in editing_masks:
                return json_err(409, "這筆歌曲正在處理或保存，請稍後再修改遮罩。")
            editing_masks.add(str(f))
        try:
            data = await read_json_body(request)
            masks = normalize_masks(data.get("masks"), float(ref.get("duration") or 905))
            f.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(f, json.dumps({"version": 1, "masks": masks}).encode("utf-8"))
            return {"masks": masks}
        except ValueError as exc:
            return json_err(400, str(exc))
        finally:
            editing_masks.discard(str(f))

    @r.delete("/sr/library/{cache_id}")
    def library_delete(cache_id: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        found = ref_dir(cache_id)
        if not found:
            return json_err(400, "無效的本機歌曲。")
        d, p, s = found
        if str(mask_file(s["song_id"], p["videoId"], p["seconds"])) in editing_masks:
            return json_err(409, "遮罩保存中，請稍後刪除。")
        for info in prep_jobs.values():   # a key version is being built from this one (sign_record: 409)
            j = ctx.jobs.get(info.get("queue_id") or "")
            if j and j["status"] in ("queued", "running") and info.get("cacheId") != cache_id \
                    and info["cacheId"].startswith(cache_id + "_key_"):
                return json_err(409, "此音軌正在建立另一個基準，請完成或取消後再刪除。")
        try:
            ref = json.loads((d / "reference.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ref = {}
        for info in prep_jobs.values():
            if info.get("cacheId") == cache_id and info.get("queue_id"):
                ctx.jobs.cancel(info["queue_id"])
        _rmtree(d)
        # sign_record deleted the preview tracks with the reference. Here they are the song's shared
        # stems: free the ones nothing else (AI cover versions, other prepared songs) uses any more.
        freed = 0
        if not ctx.song_busy(s["song_id"]):
            from .api_songs import stored_copies_of
            song_dir = ctx.library().song_dir(s["song_id"])
            mine = stems_mod.refs_in(ref.get("stems") or {}, set())
            for it in stored_copies_of(ctx, s["song_id"], song_dir)["items"]:
                if it["dir"] in mine and not it["used_by"]:
                    _rmtree(song_dir / it["dir"])
                    freed += it["bytes"]
        return {"deleted": True, "freedBytes": freed}

    # ------------------------------------------------------------ prepare jobs
    def summary(job_id: str) -> dict[str, Any] | None:
        info = prep_jobs.get(job_id)
        if not info:
            return None
        info["updated"] = time.time()
        base = {"id": job_id, "cacheId": info["cacheId"], "vocalMode": info["p"]["vocalMode"],
                "separationModel": info["p"]["separationModel"], "pitchMethod": info["p"]["pitchMethod"],
                "separationMethod": info["p"]["separationMethod"], "cached": info.get("cached", False),
                "networkFamily": None, "failedStage": None, "progressStage": None, "fallback": False}
        if info.get("cached"):
            ref = load_reference(info["cacheId"])
            return {**base, "stage": "ready", "message": "已從本機載入基準，不需重新分析。", "progress": 100, "ready": True,
                    "device": None, "deviceName": None, "title": ref and ref["title"], "duration": ref and ref.get("duration"),
                    "bpm": ref and ref.get("bpm"), "voicedSeconds": ref and ref.get("voicedSeconds"), "hasPreview": True,
                    "audioCleared": False}
        job = ctx.jobs.get(info["queue_id"])
        if not job:
            return {**base, "stage": "failed", "message": "工作已清除，請重新準備歌曲。", "progress": None, "ready": False}
        st = job["status"]
        device = "cuda" if (job.get("message") or "").upper() == "CUDA" else ("cpu" if (job.get("message") or "").upper() == "CPU" else None)
        if st == "queued":
            return {**base, "stage": "download", "message": f"排隊中：前面還有工作（第 {job['position']} 個）。", "progress": None,
                    "ready": False, "device": None, "deviceName": None}
        if st == "running":
            stage = job.get("stage") or "separating"
            stage = "reference" if stage == "ready" else stage
            msgs = {"separating": "人聲與伴奏", "accompaniment_separating": "第二輪伴奏中的殘留人聲", "lead_separating": "主唱與和音"}
            if stage in msgs:
                message = f"使用 {'GPU' if device == 'cuda' else 'CPU'} 在本機分離{msgs[stage]}…"
            elif stage == "transposing":
                message = "重用原調音軌，建立 Key 版本（速度不變）…"
            else:
                message = f"建立 {info['p']['pitchMethod'].upper()} 音高與節拍基準…"
            return {**base, "stage": stage, "progressStage": stage, "message": message, "progress": job.get("percent"),
                    "ready": False, "device": device, "deviceName": "NVIDIA CUDA" if device == "cuda" else ("CPU" if device else None)}
        if st == "succeeded":
            ref = load_reference(info["cacheId"])
            if not ref:
                return {**base, "stage": "failed", "message": "基準讀取失敗，請重新準備歌曲。", "progress": None, "ready": False}
            return {**base, "stage": "ready", "message": "基準與試聽音軌已保存到歌曲庫。", "progress": 100, "ready": True,
                    "device": device, "title": ref["title"], "duration": ref.get("duration"), "bpm": ref.get("bpm"),
                    "voicedSeconds": ref.get("voicedSeconds"), "hasPreview": True, "audioCleared": False}
        code = job.get("error_code") or ""
        text = {"melody_too_short": "辨識到的主旋律不足 3 秒；請換一首有清楚主唱的歌曲。",
                "model_missing": "找不到模型檔，請重新執行 install.bat。",
                "timeout": "本機處理超過時間上限，已停止。"}.get(code)
        if st == "cancelled":
            text = "已取消。"
        message = text or f"處理失敗：{(job.get('error_message') or code)[-600:]}"
        return {**base, "stage": "failed", "failedStage": "separating", "message": message, "progress": None, "ready": False}

    @r.post("/sr/jobs")
    async def create_job(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        try:
            data = await read_json_body(request)
        except ValueError:
            return json_err(400, "本機工作請求無效。")
        vid = data.get("videoId", "")
        seconds = data.get("seconds", 0)
        shift = data.get("pitchShift", 0) or 0
        if not isinstance(seconds, int) or seconds not in (0, 15, 30, 60) or not isinstance(shift, int) or not -12 <= shift <= 12:
            return json_err(400, "影片網址或片段長度無效。")
        p = {"videoId": vid, "seconds": seconds, "vocalMode": data.get("vocalMode") or "all",
             "separationModel": data.get("separationModel") or "demucs", "pitchMethod": data.get("pitchMethod") or "yin",
             "separationMethod": data.get("separationMethod") or "single", "pitchShift": shift}
        if p["vocalMode"] not in ("all", "lead") or p["separationModel"] not in SEP_MODELS or \
                p["pitchMethod"] not in ("yin", "rmvpe") or p["separationMethod"] not in ("single", "residual"):
            return json_err(400, "無效的分離設定。")
        s = song_for_video(vid)
        if not s:
            return json_err(400, "找不到這首歌，請到「歌曲庫」匯入。")
        sid = s["song_id"]
        for info in prep_jobs.values():
            if info.get("queue_id"):
                j = ctx.jobs.get(info["queue_id"])
                if j and j["status"] in ("queued", "running"):
                    return json_err(409, "已有音訊正在處理，請先取消或等待完成。")
        base_key = cache_key(vid, seconds, p["vocalMode"], p["separationModel"], p["pitchMethod"], p["separationMethod"])
        key_id = cache_key(vid, seconds, p["vocalMode"], p["separationModel"], p["pitchMethod"], p["separationMethod"], shift)
        force = bool(data.get("force"))
        job_id = uuid.uuid4().hex
        preview = data.get("preview", True) is not False
        cached_ref = load_reference(key_id)
        if not force and cached_ref and (not preview or cached_ref["hasPreview"]):
            prep_jobs[job_id] = {"cacheId": key_id, "p": p, "cached": True, "updated": time.time()}
            return JSONResponse(summary(job_id), status_code=202)
        lib = ctx.library()
        song_dir = lib.song_dir(sid)
        song = lib.get(sid)
        recipe = recipe_for(p)
        clip = None
        if seconds:
            # "Try the first 15/30/60 s": separate and analyse only a clip (fast), kept apart from the
            # whole-song stems every workspace shares; it shows as its own copy in "Saved stems".
            src = song.get("source") or {}
            if not src.get("audio"):
                return json_err(400, "這首歌沒有音訊，請到「歌曲庫」重新匯入。")
            clip_rel = f"sing/clips/clip_{seconds}s.wav"
            clip = {"src": str(song_dir / src["audio"]), "dst": str(song_dir / clip_rel), "seconds": seconds}
            song = {**song, "source": {"audio": clip_rel,
                                       "source_hash": f"{src.get('source_hash') or src['audio']}#clip{seconds}"}}
        if force:
            if ctx.song_busy(sid):
                return json_err(409, "這首歌有其他工作正在進行，請稍後。")
            _, tracks0 = stems_mod.plan(song_dir, song, recipe)
            for rel in set(stem_rel_map(tracks0, p).values()):
                layer_dir = (song_dir / rel).parent
                if layer_dir.parent.name == "stems":
                    _rmtree(layer_dir)
            if shift:
                _rmtree(sing_dir(sid) / key_id)
            else:
                _rmtree(sing_dir(sid) / base_key)
        layers, tracks = stems_mod.plan(song_dir, song, recipe)
        base_rel = stem_rel_map(tracks, p)
        pitch_rel = base_rel["lead"] if p["vocalMode"] == "lead" else base_rel["vocals"]
        meta = {"videoId": vid, "title": s["title"][:300], "vocalMode": p["vocalMode"],
                "separationModel": p["separationModel"], "pitchMethod": p["pitchMethod"],
                "separationMethod": p["separationMethod"], "rangeSeconds": seconds, "cacheId": base_key, "pitchShift": 0}
        payload: dict[str, Any] = {
            "song_dir": str(song_dir), "layers": layers, "clip": clip,
            # "keep separated tracks" off: drop the stems this job had to make once the reference is saved
            "drop_new": not preview,
            "base": {"dir": str(sing_dir(sid) / base_key), "stems_rel": base_rel,
                     "pitch_input": str(song_dir / pitch_rel), "beat_input": str(song_dir / base_rel["accompaniment"]),
                     "meta": meta},
            "force_reference": force and not shift, "key": None,
        }
        if shift:
            names = list(base_rel.keys())
            # one shared key copy per track (also used by the library page and AI cover)
            payload["key"] = {"semitones": shift, "dir": str(sing_dir(sid) / key_id),
                              "items": [stems_mod.key_item(song_dir, rel, shift) for rel in sorted(set(base_rel.values()))],
                              "stems_rel": {n: stems_mod.key_track(base_rel[n], shift)[1] for n in names},
                              "meta": {"cacheId": key_id}}
        job = ctx.submit(kind="sing_prepare", lane="gpu", script="sing_prepare.py", input=payload,
                         title=f"準備唱錄：{s['title']}", song_id=sid, timeout_s=3600 * max(1, len(layers) + 1),
                         dedupe="sing:" + key_id)
        prep_jobs[job_id] = {"cacheId": key_id, "p": p, "queue_id": job["id"], "updated": time.time()}
        return JSONResponse(summary(job_id), status_code=202)

    @r.get("/sr/jobs/{job_id}")
    def get_job(job_id: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        s = summary(job_id)
        return s if s else json_err(404, "工作已清除或不存在，請重新準備歌曲。")

    @r.get("/sr/jobs/{job_id}/reference")
    def get_job_reference(job_id: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        info = prep_jobs.get(job_id)
        if not info:
            return json_err(404, "工作已清除或不存在，請重新準備歌曲。")
        ref = load_reference(info["cacheId"])
        if not ref:
            return json_err(409, "基準尚未就緒。")
        ref.pop("stems", None)
        return ref

    @r.delete("/sr/jobs/{job_id}")
    def delete_job(job_id: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        info = prep_jobs.pop(job_id, None)
        if not info:
            return json_err(404, "工作已清除或不存在。")
        if info.get("queue_id"):
            ctx.jobs.cancel(info["queue_id"])
        return {"cleared": True}

    # ------------------------------------------------------------ recordings archive
    from .sing_archive import RecordingArchive, ArchiveError, export_mp3
    archive_lock = threading.Lock()
    mp3_lock = threading.Lock()

    def locked(fn, *args):
        with archive_lock:
            return fn(*args)

    def archive() -> RecordingArchive:
        return RecordingArchive(library_root() / "recordings")

    def check_root(request: Request, arc: RecordingArchive) -> None:
        root = request.query_params.get("root")
        if root is not None and root != str(arc.root):
            raise ArchiveError("歌曲庫位置已變更，請重新整理錄音清單。")

    @r.get("/sr/recordings")
    def rec_list(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        try:
            arc = archive()
            check_root(request, arc)
            with archive_lock:
                return arc.list()
        except ArchiveError as exc:
            return json_err(400, str(exc))

    async def body_to_file(request: Request, limit: int) -> Path:
        ctx.paths.tmp.mkdir(parents=True, exist_ok=True)
        tmp = ctx.paths.tmp / ("upload-" + uuid.uuid4().hex)
        size = 0
        try:
            with open(tmp, "wb") as fh:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > limit:
                        raise ArchiveError("錄音太大。")
                    fh.write(chunk)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return tmp

    @r.post("/sr/recordings/mp3")
    async def rec_mp3_convert(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        tmp = None
        try:
            tmp = await body_to_file(request, MAX_AUDIO)
            if not mp3_lock.acquire(blocking=False):
                return json_err(409, "另一筆錄音正在轉檔，請稍後再試。")
            cancel = threading.Event()

            async def watch() -> None:   # the page went away: stop ffmpeg (sign_record did the same)
                import asyncio
                while not cancel.is_set():
                    if await request.is_disconnected():
                        cancel.set()
                        return
                    await asyncio.sleep(0.5)
            import asyncio
            watcher = asyncio.ensure_future(watch())
            try:
                data = await run_in_threadpool(export_mp3, tmp, ctx.paths.tmp / "exports", cancel)
            finally:
                mp3_lock.release()
                if not watcher.done():
                    watcher.cancel()
        except ArchiveError as exc:
            return json_err(400, str(exc))
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)
        return Response(data, media_type="audio/mpeg", headers={"X-Content-Type-Options": "nosniff"})

    @r.api_route("/sr/recordings/{rec_id}", methods=["POST", "DELETE"])
    async def rec_item(rec_id: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        if not REC_ID.match(rec_id):
            return json_err(400, "錄音網址無效。")
        tmp = None
        try:
            arc = archive()
            check_root(request, arc)
            if request.method == "DELETE":
                await run_in_threadpool(locked, arc.delete, rec_id)
                return {"deleted": True}
            tmp = await body_to_file(request, 2 * MAX_AUDIO + MAX_META + 4)
            return await run_in_threadpool(locked, arc.import_bundle, rec_id, tmp)
        except ArchiveError as exc:
            return json_err(400, str(exc))
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)

    @r.api_route("/sr/recordings/{rec_id}/{asset}", methods=["GET", "POST"])
    async def rec_asset(rec_id: str, asset: str, request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        if not REC_ID.match(rec_id) or asset not in ("metadata", "mix", "voice", "mp3"):
            return json_err(400, "錄音網址無效。")
        tmp = None
        try:
            arc = archive()
            check_root(request, arc)
            if request.method == "POST" and asset == "metadata":
                body = await request.body()
                if len(body) > MAX_META:
                    raise ArchiveError("錄音資料太大。")
                return await run_in_threadpool(locked, arc.update, rec_id, json.loads(body.decode("utf-8")))
            if request.method == "POST" and asset == "mp3":
                tmp = await body_to_file(request, MAX_AUDIO)
                return await run_in_threadpool(locked, arc.save_mp3, rec_id, tmp)
            if request.method == "GET" and asset in ("mix", "voice", "mp3"):
                file, mime = arc.audio(rec_id, asset)
                return FileResponse(file, media_type=mime, headers={"X-Content-Type-Options": "nosniff"})
            return json_err(405, "不支援此操作。")
        except (ArchiveError, ValueError) as exc:
            return json_err(400, str(exc))
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)

    # ------------------------------------------------------------ native microphone
    from .native_mic import NativeMicrophone
    native = NativeMicrophone(ctx)
    native_state = native.state

    @r.get("/sr/microphone/devices")
    def mic_devices(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        return native.list_devices("--list")

    @r.get("/sr/microphone/outputs")
    def mic_outputs(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        return native.list_devices("--outputs")

    @r.post("/sr/microphone/stream")
    async def mic_stream(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        data = await read_json_body(request)
        return await native.stream(str(data.get("deviceId") or ""))

    @r.post("/sr/microphone/monitor")
    async def mic_monitor(request: Request):
        if not auth(request):
            return json_err(403, "Session token required")
        data = await read_json_body(request)
        # monitor() waits up to 5 s for the audio device; keep the event loop (and the PCM stream) running
        return await run_in_threadpool(native.monitor, data)

    # ------------------------------------------------------------ diagnostics
    from .sing_diagnostics import DiagnosticsStore
    diag = DiagnosticsStore(ctx.paths.runtime / "recording-diagnostics")

    @r.get("/sr/diagnostics/session")
    def diag_session():
        return {"token": diag.token, "version": 1}

    @r.api_route("/sr/diagnostics", methods=["GET", "DELETE"])
    def diag_root(request: Request):
        if request.headers.get("x-diagnostic-token") != diag.token:
            return json_err(403, "Token required")
        try:
            return diag.inventory_summary() if request.method == "GET" else diag.clear()
        except ValueError as exc:
            return json_err(400, str(exc))

    @r.post("/sr/diagnostics/{diag_id}")
    @r.post("/sr/diagnostics/{diag_id}/{action}")
    async def diag_post(diag_id: str, request: Request, action: str | None = None):
        if request.headers.get("x-diagnostic-token") != diag.token:
            return json_err(403, "Token required")
        try:
            body = await request.body()
            if len(body) > 8 * 1024 * 1024:
                raise ValueError("診斷單筆資料過大")
            return diag.post(diag_id, action, json.loads(body.decode("utf-8") or "{}"))
        except ValueError as exc:
            return json_err(400, str(exc))

    # ------------------------------------------------------------ renders (send to MV)
    @r.post("/sr/renders")
    async def send_render(request: Request):
        """Save a finished recording as a 'render' of its song (used by the MV workspace)."""
        if not auth(request):
            return json_err(403, "Session token required")
        vid = request.query_params.get("videoId", "")
        title = request.query_params.get("title", "")[:200]
        s = song_for_video(vid)
        if not s:
            return json_err(400, "找不到這首歌。")
        from .renders import save_render_file
        try:
            tmp = await body_to_file(request, MAX_AUDIO)
        except ArchiveError:
            return json_err(400, "音檔太大。")
        try:
            if not tmp.stat().st_size:
                return json_err(400, "音檔為空。")
            rec_id = request.query_params.get("recordingId", "")[:64]
            digest = hashlib.sha1(tmp.read_bytes()).hexdigest()
            if rec_id:   # the same saved take sent again (quick MV, then full MV): reuse its render
                from .renders import list_renders
                song_dir = ctx.library().song_dir(s["song_id"])
                for rd in list_renders(ctx, s["song_id"]):
                    if rd.get("kind") != "sing" or rd.get("recording_id") != rec_id:
                        continue
                    old = rd.get("sha1")
                    if not old:
                        try:
                            old = hashlib.sha1((song_dir / rd["path"]).read_bytes()).hexdigest()
                        except OSError:
                            continue
                    if old == digest:
                        return {**rd, "reused": True}
            return save_render_file(ctx, s["song_id"], tmp, title=title or s["title"], kind="sing",
                                    extra={"recording_id": rec_id, "sha1": digest})
        except ValueError:
            return json_err(400, "不支援的音檔格式。")
        finally:
            tmp.unlink(missing_ok=True)

    def cleanup_loop() -> None:
        while True:
            time.sleep(60)
            cutoff = time.time() - 15 * 60
            for jid, info in list(prep_jobs.items()):
                if info.get("updated", 0) < cutoff:
                    j = ctx.jobs.get(info.get("queue_id") or "")
                    if not j or j["status"] not in ("queued", "running"):
                        prep_jobs.pop(jid, None)

    threading.Thread(target=cleanup_loop, daemon=True).start()
    return r
