"""MV workspace API (/api/mv/*), used by the MV page (web/mv/index.html).

Port of the MV Studio server of AI_COVER_MV (mv_studio_server.py, 2026-10-27).
The routes, request and response shapes are the ones the MV page already uses.
Differences for SIGN2MV:
  * projects belong to songs of the library ("<song id>_<name>", see core.py);
  * the MV audio is the song's original audio, a sing & record take or a cover
    result of that song (renders), or a file uploaded into the project;
  * Whisper and the render run as queue jobs on the GPU lane (one GPU job at a
    time across SIGN2MV); /api/mv/progress reports the running MV job;
  * Whisper listens to vocals from the song's stem cache (app/stems.py);
  * "reset everything" is not offered (it would delete every MV project).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from . import settings as settings_mod
from . import stems as stems_mod
from .context import Context
from .library import LibraryError
from .mvstudio import align, core
from .mvstudio.align import (align_timeline_with_anchors_and_whisper, apply_anchor_locks,
                             auto_generate_timeline_from_whisper_only, build_guaranteed_fallback_timeline,
                             enforce_anchor_invariants, WHISPER_PIPELINE)
from .mvstudio.core import (Image, KARAOKE_TIMING_MODES, MAX_SCENES, FRAME_W, FRAME_H, INST_KEY_RE,
                            ProjectNotFound, _is_plain_lyric, count_existing_scene_images, detect_interlude_candidates,
                            instrumental_photo_path, is_kept_instrumental_line, is_user_interlude, karaoke_advance,
                            karaoke_char_times, karaoke_enabled_for, list_instrumental_photos, list_scene_images,
                            load_project_dict, load_whisper_words, normalize_instrumental_fields, normalize_tilde,
                            probe_media_file, render_single_styled_frame, renumber_scene_files, resolve_scene_image_path,
                            restore_instrumentals, sanitize_no_ai, save_project_dict, splice_interlude, _scene_files,
                            _scene_payload, TRANSITION_STYLES, BLINDS_N, BLUR_MAX_PX, execute_mv_verification)
from .renders import list_renders
from .util import media_response

AUDIO_EXT = (".wav", ".mp3", ".m4a", ".flac", ".webm", ".ogg", ".aac")
MEDIA_TYPES = {".mp4": "video/mp4", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
               ".webm": "audio/webm", ".flac": "audio/flac", ".ogg": "audio/ogg", ".png": "image/png",
               ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
MAX_UPLOAD = 2 * 1024 ** 3


def jerr(status: int, detail: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status, content={"status": "error", "detail": detail, **extra})


def router(ctx: Context) -> APIRouter:
    r = APIRouter()
    local_progress: Dict[str, Any] = {"active": False, "task_type": "idle", "percent": 0, "stage": "待命中",
                                      "detail": "", "started_at": 0.0, "elapsed_sec": 0.0}
    current: Dict[str, Any] = {"job": None, "kind": "idle", "started": 0.0}

    def local_update(active: bool, task_type: str, percent: int, stage: str, detail: str = ""):
        now = time.time()
        if active and not local_progress["active"]:
            local_progress["started_at"] = now
        local_progress.update({"active": active, "task_type": task_type, "percent": max(0, min(100, int(percent))),
                               "stage": stage, "detail": detail})
        if local_progress["started_at"] > 0:
            local_progress["elapsed_sec"] = round(now - local_progress["started_at"], 1)
        if not active:
            local_progress["started_at"] = now

    def configure() -> Dict[str, Any]:
        cfg = ctx.settings()
        lang = "en" if settings_mod.effective_language(cfg) == "en" else "zh"
        core.configure(cfg["library_dir"], cfg.get("cover_singer_name") or "", cfg.get("studio_name") or "", lang,
                       progress=local_update)
        return cfg

    def brand() -> Dict[str, str]:
        return {"singer": core.BRAND["singer"], "studio": core.BRAND["studio"], "lang": core.BRAND["lang"],
                "badge": core.default_badge(), "outro": core.default_outro(), "intro": core.default_intro()}

    def songs_root() -> Path:
        return core.LIBRARY_ROOT / "songs"

    def client_project(body: Dict[str, Any], slug: str) -> Dict[str, Any]:
        """A project sent back by the page: keep the edits, but paths always come from the slug."""
        if isinstance(body.get("project"), dict):
            proj = dict(body["project"])
            proj["slug"] = slug or str(proj.get("slug", ""))
            core.parse_slug(proj["slug"])
            audio = str(proj.get("audio_file") or "")
            return core._resolve(dict(proj, audio_file=core._rel_audio(core.parse_slug(proj["slug"])[0], audio)))
        return load_project_dict(slug)

    # ------------------------------------------------------------------ jobs
    def job_state() -> Optional[Dict[str, Any]]:
        jid = current["job"]
        if not jid:
            return None
        job = ctx.jobs.get(jid)
        if not job or job["status"] not in ("queued", "running"):
            return None
        return job

    async def wait_job(job_id: str) -> Dict[str, Any]:
        while True:
            job = ctx.jobs.get(job_id)
            if not job or job["status"] not in ("queued", "running"):
                return job or {"status": "failed", "error_code": "job_not_found", "error_message": ""}
            await asyncio.sleep(0.4)

    def start_job(kind: str, script: str, payload: Dict[str, Any], title: str, song_id: str, timeout: float) -> str:
        job = ctx.submit(kind=kind, lane="gpu", script=script, input=payload, title=title, song_id=song_id,
                         timeout_s=timeout, dedupe=f"{kind}:{payload.get('slug') or payload.get('w_json')}")
        current.update({"job": job["id"], "kind": "render" if kind == "mv_render" else "whisper",
                        "started": time.time()})
        return job["id"]

    def whisper_payload(proj: Dict[str, Any], lead_only: bool) -> Dict[str, Any]:
        sid = proj["song_id"]
        lib = ctx.library()
        song = lib.get(sid)
        sdir = lib.song_dir(sid)
        audio = Path(proj["audio_file"])
        src = song.get("source") or {}
        convert = None
        if src.get("audio") and audio.resolve() == (sdir / src["audio"]).resolve():
            pseudo = song
        else:
            st = audio.stat()
            h = hashlib.sha1(f"{audio.resolve()}|{int(st.st_mtime)}|{st.st_size}".encode("utf-8")).hexdigest()[:16]
            rel = f"mv/_audio_cache/{h}.wav"
            convert = {"src": str(audio), "dst": str(sdir / rel)}
            pseudo = {"source": {"audio": rel, "source_hash": "file:" + h}}
        layers, tracks = stems_mod.plan(sdir, pseudo, {"model": "demucs", "lead": bool(lead_only)})
        return {"song_dir": str(sdir), "layers": layers, "convert": convert,
                "voice": str(sdir / tracks["voice"]), "vocals": str(sdir / tracks["vocals"]),
                "used": "lead" if lead_only else "vocals", "audio_file": str(audio), "w_json": proj["whisper_json"],
                "prompt": str(proj.get("title", ""))[:220], "lead_requested": bool(lead_only)}

    async def run_whisper(proj: Dict[str, Any], force: bool) -> tuple:
        audio = proj.get("audio_file", "")
        lead_only = bool(proj.get("whisper_lead_only", False))
        w_json = proj["whisper_json"]
        if not force and align.is_whisper_cache_valid(w_json, audio, lead_only):
            local_update(True, "whisper", 60, "🎙️ 已載入 Whisper 逐字聲學定位快取", os.path.basename(w_json))
            with open(w_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            return (data.get("segments", data) if isinstance(data, dict) else data), "cache"
        payload = whisper_payload(proj, lead_only)
        jid = start_job("mv_whisper", "mv_whisper.py", payload, f"Whisper：{proj.get('title') or proj['name']}",
                        proj["song_id"], 3600)
        job = await wait_job(jid)
        if job["status"] == "cancelled":
            raise RuntimeError("已由使用者取消 Whisper 語音辨識")
        if job["status"] == "timeout":
            raise RuntimeError("Whisper 語音辨識逾時")
        if job["status"] != "succeeded":
            code = job.get("error_code") or ""
            if code == "model_missing":
                raise RuntimeError("找不到 Whisper 模型，請重新執行 install.bat")
            raise RuntimeError(job.get("error_message") or code or "Whisper 子程序異常結束")
        with open(w_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("segments", []), (job.get("result") or {}).get("source", "faster-whisper")

    # ------------------------------------------------------------------ progress / cancel / busy
    @r.get("/api/mv/transitions")
    def api_list_transitions():
        return {"styles": [{"key": k, "label": lab} for k, lab in TRANSITION_STYLES], "blinds": BLINDS_N,
                "blur_max_px": BLUR_MAX_PX}

    @r.get("/api/mv/progress")
    def api_get_progress():
        job = job_state()
        if job:
            started = job.get("started_at") or job.get("created_at") or current["started"]
            if job["status"] == "queued":
                stage = f"⏳ 排隊中：GPU 正在處理其他工作（第 {job.get('position') or 1} 個）"
                return {"active": True, "task_type": current["kind"], "percent": 0, "stage": stage,
                        "detail": "可以到「工作佇列」查看", "started_at": started,
                        "elapsed_sec": round(time.time() - current["started"], 1)}
            return {"active": True, "task_type": current["kind"], "percent": int(job.get("percent") or 0),
                    "stage": job.get("stage") or "處理中…", "detail": job.get("message") or "",
                    "started_at": started, "elapsed_sec": round(time.time() - started, 1)}
        if local_progress["active"] and local_progress["started_at"] > 0:
            local_progress["elapsed_sec"] = round(time.time() - local_progress["started_at"], 1)
        return local_progress

    @r.post("/api/mv/cancel_task")
    def api_cancel_task():
        job = job_state()
        if job:
            ctx.jobs.cancel(job["id"])
        local_update(False, "idle", 0, "⏹️ 已由使用者手動終止", "")
        return {"status": "ok"}

    @r.get("/api/mv/busy")
    def api_mv_busy():
        job = job_state()
        tasks = [current["kind"]] if job else []
        return {"busy": bool(tasks), "tasks": tasks}

    @r.post("/api/mv/reset_clean")
    def api_reset_clean():
        return jerr(410, "SIGN2MV 不提供「清空全部專案」；請勾選要刪除的專案再刪除。")

    # ------------------------------------------------------------------ projects
    def available_audios(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = []
        try:
            songs = ctx.library().list()
        except OSError:
            return out
        for s in songs:
            src = s.get("source") or {}
            sid = s["song_id"]
            sdir = ctx.library().song_dir(sid)
            if src.get("audio") and (sdir / src["audio"]).is_file():
                p = sdir / src["audio"]
                out.append({"name": "原曲音訊", "folder": s["title"], "path": str(p), "song_id": sid, "kind": "mix",
                            "size_mb": round(p.stat().st_size / 1048576, 2)})
            for rd in list_renders(ctx, sid):
                p = sdir / rd["path"]
                label = {"sing": "唱錄", "cover": "翻唱"}.get(rd["kind"], rd["kind"])
                out.append({"name": f"{label}：{rd['title']}", "folder": s["title"], "path": str(p), "song_id": sid,
                            "kind": rd["kind"], "render_id": rd["id"], "size_mb": round(p.stat().st_size / 1048576, 2)})
            mvd = sdir / "mv"
            if mvd.is_dir():
                for pd in sorted(mvd.iterdir()):
                    ad = pd / "audio"
                    if core.NAME_RE.match(pd.name) and ad.is_dir():
                        for f in sorted(ad.iterdir()):
                            if f.suffix.lower() in AUDIO_EXT and f.is_file():
                                out.append({"name": f"上傳：{f.name}", "folder": s["title"], "path": str(f),
                                            "song_id": sid, "kind": "upload",
                                            "size_mb": round(f.stat().st_size / 1048576, 2)})
        return out

    @r.get("/api/mv/projects")
    def api_list_projects():
        cfg = configure()
        titles = {}
        try:
            titles = {s["song_id"]: s["title"] for s in ctx.library().list()}
        except OSError:
            pass
        projects = []
        for slug in core.list_project_slugs():
            try:
                p = load_project_dict(slug)
            except Exception:  # noqa: BLE001
                continue
            projects.append({"slug": slug, "title": p.get("title") or "（全新空白專案）",
                             "original_singer": p.get("original_singer", ""), "cover_singer": p.get("cover_singer", ""),
                             "timeline_count": len(p.get("timeline", [])), "audio_exists": os.path.exists(p.get("audio_file", "")),
                             "mv_exists": os.path.exists(p.get("output_mv", "")), "song_id": p["song_id"],
                             "song_title": titles.get(p["song_id"], ""),
                             "mtime": os.path.getmtime(Path(core.project_dir(slug)) / "project.json")})
        songs = [{"song_id": sid, "title": t} for sid, t in titles.items()]
        return {"projects": projects, "available_audios": available_audios(cfg), "songs": songs, "brand": brand()}

    @r.get("/api/mv/project/{slug}")
    def api_get_project(slug: str):
        configure()
        try:
            proj = load_project_dict(slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        audio_probe = probe_media_file(proj.get("audio_file", ""))
        mv_probe = probe_media_file(proj.get("output_mv", ""))
        existing_img_max = count_existing_scene_images(proj.get("illust_dir", ""))
        tl_max = max([int(s.get("scene", 1)) for s in proj.get("timeline", [])] + [0])
        saved_sc_count = int(proj.get("scene_count", 12) or 12)
        max_sc = max(tl_max, existing_img_max, saved_sc_count, 12)
        scenes = list_scene_images(proj.get("illust_dir", ""), max_scene=max_sc)
        whisper_segments = []
        w_path = proj.get("whisper_json", "")
        if w_path and os.path.exists(w_path):
            try:
                with open(w_path, "r", encoding="utf-8") as f:
                    w_raw = json.load(f)
                if isinstance(w_raw, dict) and "segments" in w_raw:
                    whisper_segments = w_raw["segments"]
                elif isinstance(w_raw, list):
                    whisper_segments = w_raw
            except Exception:  # noqa: BLE001
                pass
        verify_info = {"exists": False, "frames": []}
        if mv_probe.get("exists"):
            report_json = os.path.join(core.project_dir(slug), "verify", "verify_report.json")
            if os.path.exists(report_json):
                try:
                    with open(report_json, "r", encoding="utf-8") as f:
                        verify_info = json.load(f)
                except Exception:  # noqa: BLE001
                    pass
        if normalize_instrumental_fields(proj.get("timeline", [])):
            proj = save_project_dict(proj)
        return {"project": proj, "instrument_photos": list_instrumental_photos(proj.get("illust_dir", ""), proj.get("timeline", [])),
                "audio_probe": audio_probe, "mv_probe": mv_probe, "scenes": scenes, "whisper_segments": whisper_segments,
                "verification": verify_info, "brand": brand()}

    @r.post("/api/mv/project/save")
    async def api_save_project(request: Request):
        configure()
        body = await request.json()
        try:
            proj = client_project({"project": body}, str(body.get("slug", "")))
            if not (Path(core.project_dir(proj["slug"])) / "project.json").is_file():
                return jerr(404, "找不到這個專案，請重新整理")
            return {"status": "ok", "project": save_project_dict(proj)}
        except ProjectNotFound as exc:
            return jerr(404, str(exc))

    @r.post("/api/mv/projects/delete")
    async def api_delete_projects(request: Request):
        configure()
        body = await request.json()
        deleted = []
        for s in body.get("slugs", []):
            try:
                sid, name = core.parse_slug(str(s))
            except ProjectNotFound:
                continue
            if job_state() and ctx.song_busy(sid):
                continue
            pdir = Path(core.project_dir(str(s)))
            if pdir.is_dir() and pdir.parent == core.song_dir(sid) / "mv" and core.NAME_RE.match(pdir.name):
                shutil.rmtree(pdir, ignore_errors=True)
                deleted.append(str(s))
        return {"status": "ok", "deleted": deleted, "remaining": core.list_project_slugs()}

    @r.post("/api/mv/project/create")
    async def api_create_project(request: Request):
        cfg = configure()
        body = await request.json()
        sid = str(body.get("song_id", ""))
        try:
            song = ctx.library().get(sid)
        except LibraryError:
            return jerr(400, "請先選擇這個 MV 用的歌曲")
        name = re.sub(r"[^a-z0-9_-]", "_", str(body.get("slug", "")).lower()).strip("_-")[:40]
        if not name or not core.NAME_RE.match(name):
            name = f"mv_{int(time.time())}"
        slug = f"{sid}_{name}"
        if (Path(core.project_dir(slug)) / "project.json").exists():
            return jerr(409, f"這首歌已經有叫「{name}」的專案，請換一個代碼")
        title = sanitize_no_ai(body.get("title") or song["title"], song["title"])[:120]
        audio_file = str(body.get("audio_file", "")).strip()
        if not audio_file:
            src = song.get("source") or {}
            audio_file = str(ctx.library().song_dir(sid) / src["audio"]) if src.get("audio") else ""
        if audio_file and not os.path.exists(audio_file):
            audio_file = ""
        probe = probe_media_file(audio_file)
        scene_count = max(1, min(MAX_SCENES, int(body.get("scene_count", 12) or 12)))
        lang = "en" if settings_mod.effective_language(cfg) == "en" else "zh"
        proj = {"slug": slug, "title": title, "title_spaced": "  ".join(list(title)), "badge": core.default_badge(lang),
                "lyricist": sanitize_no_ai(body.get("lyricist", ""), ""), "composer": sanitize_no_ai(body.get("composer", ""), ""),
                "original_singer": sanitize_no_ai(body.get("original_singer", ""), ""),
                "cover_singer": core.BRAND["singer"], "studio": core.BRAND["studio"], "credit_lang": lang,
                "intro_desc": core.default_intro(lang), "outro_desc": "",
                "style_theme": body.get("style_theme", ""), "audio_file": audio_file,
                "output_mv": f"{core.safe_file_title(title, name)}_MV.mp4", "scene_count": scene_count,
                "early_lead_sec": -0.70, "tail_extend_sec": 2.50, "timeline": []}
        proj["outro_desc"] = core.default_outro(proj)
        (Path(core.project_dir(slug)) / "scenes").mkdir(parents=True, exist_ok=True)
        saved = save_project_dict(proj)
        return {"status": "ok", "project": saved, "audio_probe": probe}

    @r.post("/api/mv/project/import")
    async def api_import_project(request: Request):
        """A project JSON (exported here or by the old MV Studio) becomes a new project of a song.
        Timeline, texts and settings are kept; photos are not part of the JSON."""
        configure()
        body = await request.json()
        sid = str(body.get("song_id", ""))
        src = body.get("project")
        if not isinstance(src, dict):
            return jerr(400, "JSON 格式無效")
        try:
            song = ctx.library().get(sid)
        except LibraryError:
            return jerr(400, "請先選一個專案（決定要匯入到哪一首歌），再匯入")
        base = re.sub(r"[^a-z0-9_-]", "_", str(src.get("name") or src.get("slug") or "imported").lower()).strip("_-")[:30] or "imported"
        if base.startswith(sid + "_"):
            base = base[len(sid) + 1:] or "imported"
        name, n = base, 2
        while (Path(core.project_dir(f"{sid}_{name}")) / "project.json").exists():
            name, n = f"{base}_{n}", n + 1
        proj = {k: v for k, v in src.items() if k not in ("slug", "song_id", "name", "illust_dir", "whisper_json", "output_mv")}
        proj["slug"] = f"{sid}_{name}"
        audio = str(src.get("audio_file") or "")
        if not audio or not os.path.isfile(audio):
            s_src = song.get("source") or {}
            audio = str(ctx.library().song_dir(sid) / s_src["audio"]) if s_src.get("audio") else ""
        proj["audio_file"] = audio
        proj["output_mv"] = f"{core.safe_file_title(proj.get('title', ''), name)}_MV.mp4"
        (Path(core.project_dir(proj["slug"])) / "scenes").mkdir(parents=True, exist_ok=True)
        return {"status": "ok", "project": save_project_dict(proj)}

    def _fit_timeline_to_audio(proj: Dict[str, Any], probe: Dict[str, Any], min_dur: float) -> None:
        if probe.get("exists") and probe.get("duration", 0) > min_dur and proj.get("timeline"):
            dur = round(float(probe["duration"]), 2)
            tl = proj["timeline"]
            if len(tl) == 3 and "請貼入歌詞" in str(tl[1].get("text", "")):
                intro_e = min(18.0, round(dur * 0.1, 2))
                outro_s = max(intro_e + 10.0, round(dur - min(18.0, dur * 0.1), 2))
                tl[0]["start"], tl[0]["end"] = 0.0, intro_e
                tl[1]["start"], tl[1]["end"] = intro_e, outro_s
                tl[2]["start"], tl[2]["end"] = outro_s, dur
            else:
                tl[-1]["end"] = dur
                if float(tl[-1].get("start", 0)) >= dur:
                    tl[-1]["start"] = max(0.0, round(dur - 12.0, 2))
                    if len(tl) >= 2:
                        tl[-2]["end"] = tl[-1]["start"]

    def _drop_whisper_if_audio_changed(proj: Dict[str, Any], old_audio: str, new_audio: str) -> None:
        if old_audio and new_audio and os.path.abspath(old_audio) != os.path.abspath(new_audio):
            w_p = proj.get("whisper_json", "")
            if w_p and os.path.exists(w_p):
                try:
                    os.remove(w_p)
                except OSError:
                    pass

    @r.post("/api/mv/select_audio")
    async def api_select_audio(request: Request):
        configure()
        body = await request.json()
        slug = str(body.get("slug", ""))
        try:
            proj = client_project(body, slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        audio_file = str(body.get("audio_file", "")).strip()
        old_audio = proj.get("audio_file", "")
        sdir = core.song_dir(proj["song_id"]).resolve()
        if audio_file and os.path.isfile(audio_file):
            inside = True
            try:
                Path(audio_file).resolve().relative_to(sdir)
            except ValueError:
                inside = False
            if not inside:   # a file outside this song: keep a copy in the project (the old MV Studio did the same)
                ext = os.path.splitext(audio_file)[1].lower() or ".wav"
                if ext not in AUDIO_EXT:
                    return jerr(400, "這不是支援的音檔格式")
                target_dir = Path(core.project_dir(slug)) / "audio"
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / f"{core.safe_file_title(proj.get('title', ''), proj['name'])}_master{ext}"
                shutil.copy2(audio_file, target)
                audio_file = str(target)
        elif audio_file:
            return jerr(400, f"找不到音檔：{audio_file}")
        proj["audio_file"] = audio_file
        probe = probe_media_file(audio_file)
        _fit_timeline_to_audio(proj, probe, 5)
        _drop_whisper_if_audio_changed(proj, old_audio, audio_file)
        saved = save_project_dict(proj)
        return {"status": "ok", "project": saved, "audio_probe": probe}

    @r.post("/api/mv/add_scene_slot")
    async def api_add_scene_slot(request: Request):
        configure()
        body = await request.json()
        try:
            proj = client_project(body, str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        existing_img_max = count_existing_scene_images(proj.get("illust_dir", ""))
        tl_max = max([int(s.get("scene", 1)) for s in proj.get("timeline", [])] + [0])
        cur_sc = max(tl_max, existing_img_max, int(proj.get("scene_count", 12) or 12), int(body.get("current_count", 12) or 12))
        new_sc = min(MAX_SCENES, cur_sc + 1)
        proj["scene_count"] = new_sc
        saved = save_project_dict(proj)
        scenes = list_scene_images(saved.get("illust_dir", ""), max_scene=new_sc)
        return {"status": "ok", "new_scene_id": new_sc, "scenes": scenes, "project": saved}

    # ------------------------------------------------------------------ lyrics / alignment
    @r.post("/api/mv/paste_lyrics")
    async def api_paste_lyrics(request: Request):
        configure()
        body = await request.json()
        slug = str(body.get("slug", ""))
        raw_text = str(body.get("lyrics_text", "")).strip()
        mode = body.get("mode", "whisper_align")
        early_lead = float(body.get("early_lead", -0.70))
        tail_ext = float(body.get("tail_extend", 2.50))
        apply_lead_lrc = bool(body.get("apply_lead_lrc", True))
        force_whisper = bool(body.get("force_whisper", False))
        warning_notes: List[str] = []
        try:
            proj = load_project_dict(slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        if isinstance(body.get("project"), dict):
            inc = body["project"]
            for k in ("title", "title_spaced", "badge", "lyricist", "composer", "original_singer", "cover_singer", "studio",
                      "style_theme", "intro_desc", "outro_desc", "trans_duration", "scene_count", "transition_mode",
                      "transition_style", "transition_seed", "spectrum_enabled", "karaoke_enabled", "spectrum_color",
                      "whisper_lead_only", "karaoke_timing", "karaoke_advance", "credit_lang"):
                if inc.get(k) is not None and str(inc.get(k)) != "":
                    proj[k] = inc[k]
            if inc.get("audio_file"):
                proj["audio_file"] = core._abs_audio(proj["song_id"], core._rel_audio(proj["song_id"], str(inc["audio_file"])))

        audio_file_path = str(proj.get("audio_file", "")).strip()
        probe = probe_media_file(audio_file_path)
        total_dur = probe.get("duration", 240.0) if probe.get("exists") else 240.0
        raw_lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        scene_tag_re = re.compile(r"^\[Scene\s*(\d+)\]\s*(.*)$", re.IGNORECASE)

        def extract_scene_tag(line_str: str, default_sc: int):
            m_sc = scene_tag_re.match(line_str.strip())
            if m_sc:
                return int(m_sc.group(1)), normalize_tilde(m_sc.group(2).strip())
            return default_sc, normalize_tilde(line_str.strip())

        lrc_pattern = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$")
        parsed_lrc = []
        for i, ln in enumerate(raw_lines):
            m = lrc_pattern.match(ln)
            if m:
                sec = round(int(m.group(1)) * 60 + float(m.group(2)), 2)
                sc_num, rem_txt = extract_scene_tag(m.group(3).strip(), min(MAX_SCENES, i + 1))
                txt = sanitize_no_ai(rem_txt, rem_txt)
                if txt:
                    parsed_lrc.append((sec, sc_num, txt))

        if parsed_lrc and mode in ("lrc_or_even", "whisper_align"):
            new_tl = []
            first_st = parsed_lrc[0][0]
            if first_st > 3.0:
                new_tl.append({"scene": 1, "start": 0.00, "end": first_st, "text": f"～ 前奏 · {proj.get('title', '')} ～",
                               "type": "intro", "note": "開場名牌卡"})
            for i, (st, sc_num, txt) in enumerate(parsed_lrc):
                tp = "interlude" if txt.startswith("～") and "間奏" in txt else ("outro" if txt.startswith("～") and "尾奏" in txt else ("intro" if i == 0 and txt.startswith("～") else "lyric"))
                adj_st = max(0.0, round(st + early_lead, 2)) if (apply_lead_lrc and tp == "lyric") else st
                if new_tl:
                    new_tl[-1]["end"] = adj_st
                nxt_raw = parsed_lrc[i + 1][0] if i + 1 < len(parsed_lrc) else max(adj_st + 6.0, total_dur - 15.0)
                et = max(adj_st + 0.5, round(nxt_raw + (early_lead if apply_lead_lrc else 0.0), 2))
                new_tl.append({"scene": sc_num, "start": adj_st, "end": et, "text": txt, "type": tp,
                               "note": f"LRC 匯入 (已套用 {early_lead}s 提前進字)" if (apply_lead_lrc and tp == "lyric") else "LRC 時間碼匯入"})
            if new_tl[-1]["type"] != "outro" and new_tl[-1]["end"] < total_dur:
                new_tl.append({"scene": min(MAX_SCENES, new_tl[-1]["scene"]), "start": new_tl[-1]["end"], "end": total_dur,
                               "text": f"～ 尾奏 · {proj.get('title', '')} 感謝聆聽 ～", "type": "outro", "note": "片尾名牌卡"})
            existing_full = (body.get("project", {}).get("timeline") if isinstance(body.get("project"), dict) else None) or proj.get("timeline", [])
            user_ivs = [s for s in existing_full if is_user_interlude(s)]
            existing_tl = [s for s in existing_full if not is_user_interlude(s)]
            if existing_tl:
                new_tl = apply_anchor_locks(new_tl, existing_tl, total_dur)
                locked_cnt = sum(1 for s in new_tl if s.get("locked"))
                if locked_cnt > 0:
                    warning_notes.append(f"🔒 定錨保護生效：已為您精準凍結 {locked_cnt} 個定錨段落（時間 100% 不變），其餘段落已完成 Whisper 重新對齊！")
            new_tl, iv_notes = restore_instrumentals(new_tl, existing_full, user_ivs, total_dur)
            warning_notes.extend(iv_notes)
            proj["timeline"] = new_tl
            proj["early_lead_applied"] = early_lead if apply_lead_lrc else 0.0
            saved = save_project_dict(proj)
            return {"status": "ok", "mode_used": "lrc", "count": len(new_tl), "project": saved,
                    "warning": " ".join(warning_notes) if warning_notes else ""}

        filtered_pairs = []
        role_scene: Dict[str, int] = {}
        line_pos: List[int] = []
        pos = 0
        for ln in raw_lines:
            sc_t, rem_t = extract_scene_tag(ln, -1)
            if not rem_t or "請貼入歌詞或執行 Whisper" in rem_t:
                continue
            pos += 1
            if rem_t.startswith("～") and ("前奏" in rem_t or "尾奏" in rem_t or "感謝聆聽" in rem_t):
                role_scene["intro" if "前奏" in rem_t else "outro"] = sc_t if sc_t > 0 else min(MAX_SCENES, pos)
                continue
            filtered_pairs.append((sc_t, sanitize_no_ai(rem_t, rem_t)))
            line_pos.append(min(MAX_SCENES, pos))

        existing_sc_count = count_existing_scene_images(proj.get("illust_dir", "")) or int(proj.get("scene_count", 12) or 12)

        if mode == "replace_text_only":
            if not filtered_pairs:
                return JSONResponse(status_code=400, content={"status": "error", "detail": "貼上的字幕內容不能為空！請先在字幕框輸入或貼上歌詞。"})
            tl = proj.get("timeline", [])
            lyric_indices = [i for i, s in enumerate(tl) if s.get("type", "lyric") == "lyric" and not str(s.get("text", "")).startswith("～")]
            if not lyric_indices:
                line_pairs = [(p[0] if p[0] > 0 else line_pos[idx], p[1]) for idx, p in enumerate(filtered_pairs)]
                target_sc_max = max(existing_sc_count, len(line_pairs))
                proj["scene_count"] = target_sc_max
                proj["timeline"] = build_guaranteed_fallback_timeline(line_pairs=line_pairs, total_dur=total_dur, early_lead=early_lead,
                                                                      title=proj.get("title", ""), target_scene_count=target_sc_max)
                proj["early_lead_applied"] = early_lead
                saved = save_project_dict(proj)
                return {"status": "ok", "mode_used": "replace_text_only_init", "count": len(proj["timeline"]),
                        "lyric_count": len(line_pairs),
                        "warning": "💡 提醒：因原本尚未建立時間軸，系統已自動為您貼上的歌詞配置連續時間軸並填入左側照片卡片！",
                        "project": saved}
            replaced = 0
            for idx_pos, (sc_num, line_txt) in zip(lyric_indices, filtered_pairs):
                tl[idx_pos]["text"] = line_txt
                if sc_num > 0:
                    tl[idx_pos]["scene"] = sc_num
                replaced += 1
            saved = save_project_dict(proj)
            return {"status": "ok", "mode_used": "replace_text_only", "count": replaced, "lyric_count": replaced, "project": saved}

        clean_lines = [p[1] for p in filtered_pairs]
        scene_nums = [p[0] if p[0] > 0 else line_pos[idx] for idx, p in enumerate(filtered_pairs)]
        line_pairs = list(zip(scene_nums, clean_lines))
        target_sc_max = max([existing_sc_count, len(line_pairs) or 12] + scene_nums + list(role_scene.values()))
        proj["scene_count"] = target_sc_max

        existing_full = (body.get("project", {}).get("timeline") if isinstance(body.get("project"), dict) else None) or proj.get("timeline", [])
        user_ivs = [s for s in existing_full if is_user_interlude(s)]
        existing_tl = [s for s in existing_full if not is_user_interlude(s)]
        align_kwargs: Dict[str, Any] = {}

        def _align(**kw):
            align_kwargs.clear()
            align_kwargs.update(kw)
            return align_timeline_with_anchors_and_whisper(**kw)

        if not clean_lines and existing_tl:
            existing_lyrics = [(int(s.get("scene", 1)), sanitize_no_ai(s.get("text", ""))) for s in existing_tl
                               if (s.get("type", "lyric") == "lyric" and not str(s.get("text", "")).startswith("～")) or is_kept_instrumental_line(s)]
            if existing_lyrics:
                line_pairs = existing_lyrics
                clean_lines = [p[1] for p in line_pairs]
                target_sc_max = max(existing_sc_count, len(line_pairs) or 12)
                proj["scene_count"] = target_sc_max

        fallback_used = False
        whisper_src = "none"
        has_existing_lyrics = any(s.get("type", "lyric") == "lyric" and not str(s.get("text", "")).startswith("～") for s in (existing_tl or []))

        def _keep_timeline(reason: str, status_code: int = 409):
            local_update(False, "whisper", 0, "⚠️ 時間軸沒有變更", reason)
            return JSONResponse(status_code=status_code, content={"status": "error", "keep_timeline": True,
                                                                  "detail": f"{reason}（目前的時間軸沒有變更）"})

        try:
            if mode == "whisper_align":
                if not audio_file_path or not os.path.exists(audio_file_path):
                    if has_existing_lyrics:
                        return _keep_timeline("還沒有選擇母帶音檔，無法用 Whisper 對齊；請先在 Step 1 選音檔", 400)
                    fallback_used = True
                    warning_notes.append("⚠️ 提醒：您尚未在上方「Step 1」選擇母帶音檔！系統已先幫左側照片自動分配預設連續時間軸（您可先微調秒數）；"
                                         "若要使用 Whisper 語音辨識對齊，請先在 Step 1 下拉選單挑選音檔後再按一次！")
                    new_tl = _align(existing_timeline=existing_tl, line_pairs=line_pairs, w_segs=[], total_dur=total_dur,
                                    early_lead=early_lead, tail_ext=tail_ext, title=proj.get("title", ""), target_scene_count=target_sc_max)
                else:
                    w_path = proj["whisper_json"]
                    w_segs = []
                    cache_valid = False
                    if not force_whisper and os.path.exists(w_path):
                        try:
                            with open(w_path, "r", encoding="utf-8") as f:
                                w_data = json.load(f)
                            if isinstance(w_data, dict):
                                cached_dur = float(w_data.get("duration", 0.0))
                                cached_segs = w_data.get("segments", [])
                                cached_au = str(w_data.get("audio_file", ""))
                                same_au = (not cached_au) or (os.path.abspath(cached_au).lower() == os.path.abspath(audio_file_path).lower())
                                same_lead = bool(w_data.get("lead_requested", False)) == bool(proj.get("whisper_lead_only", False))
                                if cached_segs and same_au and same_lead and w_data.get("pipeline") == WHISPER_PIPELINE and (cached_dur <= 0 or abs(cached_dur - total_dur) < 2.5):
                                    w_segs = cached_segs
                                    cache_valid = True
                                    whisper_src = "cache"
                        except Exception:  # noqa: BLE001
                            w_segs = []
                    if cache_valid and w_segs:
                        local_update(True, "whisper", 45, "🎙️ 正在讀取 Whisper 逐字聲學定位快取...", os.path.basename(w_path))
                    else:
                        try:
                            w_segs, whisper_src = await run_whisper(proj, True)
                        except Exception as w_err:  # noqa: BLE001
                            if has_existing_lyrics:
                                return _keep_timeline(f"Whisper 沒有完成：{w_err}")
                            fallback_used = True
                            warning_notes.append(f"⚠️ Whisper 語音分析中途發生異常（{w_err}），系統已自動啟動容錯保底機制，為您填滿全部 {target_sc_max} 張照片的連續時間軸，您可直接微調秒數！")
                            w_segs = []
                    if w_segs:
                        if not clean_lines:
                            local_update(True, "whisper", 85, f"⚡ [階段 3/3] 正在依 Whisper 聲學自動切分並配對左側 {target_sc_max} 張分鏡圖...",
                                         f"套用 {early_lead}s 提前進字與無縫轉場銜接")
                            warning_notes.append(f"💡 提醒：因右側字幕框尚未貼入自訂歌詞，系統已自動用 Whisper 聽音辨識出的詞句填滿左側 {target_sc_max} 張照片的時間與字幕！"
                                                 "若台語/國語同音字有誤差，您可直接在卡片上改字，或貼上正確歌詞後點「✏️ 僅替換歌詞文字（保留時間）」。")
                            new_tl = auto_generate_timeline_from_whisper_only(w_segs=w_segs, total_dur=total_dur, early_lead=early_lead,
                                                                              tail_ext=tail_ext, title=proj.get("title", ""), target_scene_count=target_sc_max)
                            if existing_tl:
                                new_tl = apply_anchor_locks(new_tl, existing_tl, total_dur, w_segs, early_lead, tail_ext, proj.get("title", ""))
                        else:
                            local_update(True, "whisper", 85, f"⚡ [階段 3/3] 正在執行全局字詞流 DP 對齊 ({len(clean_lines)} 句歌詞 ↔ 左側分鏡)...",
                                         f"套用 {early_lead}s 提前進字與 +{tail_ext}s 尾韻延展（嚴格定錨約束）")
                            new_tl = _align(existing_timeline=existing_tl, line_pairs=line_pairs, w_segs=w_segs, total_dur=total_dur,
                                            early_lead=early_lead, tail_ext=tail_ext, title=proj.get("title", ""), target_scene_count=target_sc_max)
                    else:
                        if has_existing_lyrics:
                            return _keep_timeline("Whisper 沒有偵測到人聲")
                        fallback_used = True
                        if not warning_notes:
                            warning_notes.append(f"⚠️ Whisper 未偵測到有效人聲片段，系統已自動啟動保底機制，幫左側 {target_sc_max} 張照片分配連續時間軸，您可直接微調秒數！")
                        new_tl = _align(existing_timeline=existing_tl, line_pairs=line_pairs, w_segs=[], total_dur=total_dur,
                                        early_lead=early_lead, tail_ext=tail_ext, title=proj.get("title", ""), target_scene_count=target_sc_max)
            else:
                if not clean_lines:
                    warning_notes.append(f"💡 提醒：您尚未貼入歌詞，系統已先為左側 {target_sc_max} 張照片平均分配連續時間軸，您可直接微調時間或輸入歌詞！")
                new_tl = _align(existing_timeline=existing_tl, line_pairs=line_pairs, w_segs=[], total_dur=total_dur,
                                early_lead=early_lead, tail_ext=tail_ext, title=proj.get("title", ""), target_scene_count=target_sc_max)

            new_tl = enforce_anchor_invariants(new_tl, existing_tl, total_dur)
            for _role, _sc in role_scene.items():
                _segs = [x for x in new_tl if x.get("type") == _role]
                if _segs:
                    (_segs[0] if _role == "intro" else _segs[-1])["scene"] = _sc
            locked_cnt = sum(1 for s in new_tl if s.get("locked"))
            if locked_cnt > 0:
                warning_notes.append(f"🔒 定錨保護生效：已為您精準凍結 {locked_cnt} 個定錨段落（時間 100% 不變），其餘段落已完成 Whisper 重新對齊！")
            realign = None
            if align_kwargs:
                def _realign(anchors, _kw=dict(align_kwargs)):
                    return enforce_anchor_invariants(align_timeline_with_anchors_and_whisper(**_kw, interlude_anchors=anchors), existing_tl, total_dur)
                realign = _realign
            new_tl, iv_notes = restore_instrumentals(new_tl, existing_full, user_ivs, total_dur, realign)
            warning_notes.extend(iv_notes)
            proj["timeline"] = new_tl
            proj["early_lead_sec"] = early_lead
            proj["early_lead_applied"] = early_lead
            proj["tail_extend_sec"] = tail_ext
            saved = save_project_dict(proj)
            lyric_cnt = sum(1 for s in new_tl if s.get("type") == "lyric")
            local_update(False, "whisper", 100, f"✔ 時間軸自動配置完成！(共 {lyric_cnt} 段分鏡，已套用 {early_lead}s 提前進字)", "")
            return {"status": "ok", "mode_used": "fallback_even" if fallback_used else mode, "fallback_used": fallback_used,
                    "warning": " ".join(warning_notes) if warning_notes else "", "whisper_source": whisper_src,
                    "lyric_count": lyric_cnt, "count": len(new_tl), "project": saved}
        except Exception as unexpected_err:  # noqa: BLE001
            if has_existing_lyrics:
                return _keep_timeline(f"對齊時發生錯誤：{unexpected_err}", 500)
            new_tl = build_guaranteed_fallback_timeline(line_pairs=line_pairs, total_dur=total_dur, early_lead=early_lead,
                                                        title=proj.get("title", ""), target_scene_count=target_sc_max)
            if existing_tl:
                new_tl = apply_anchor_locks(new_tl, existing_tl, total_dur)
                locked_cnt = sum(1 for s in new_tl if s.get("locked"))
                if locked_cnt > 0:
                    warning_notes.append(f"🔒 定錨保護生效：已為您精準凍結 {locked_cnt} 個定錨段落（時間 100% 不變），其餘段落已完成 Whisper 重新對齊！")
            new_tl, _ = restore_instrumentals(new_tl, existing_full, user_ivs, total_dur)
            proj["timeline"] = new_tl
            proj["early_lead_applied"] = early_lead
            saved = save_project_dict(proj)
            lyric_cnt = sum(1 for s in new_tl if s.get("type") == "lyric")
            w_msg = f"⚠️ 對齊過程發生例外（{unexpected_err}），系統已自動切換保底機制填滿全部 {lyric_cnt} 張照片的時間軸，您現在可直接微調秒數！"
            local_update(False, "whisper", 100, "✔ 已啟動保底時間軸配置完成", w_msg)
            return {"status": "ok", "mode_used": "fallback_even", "fallback_used": True, "warning": w_msg,
                    "whisper_source": "fallback", "lyric_count": lyric_cnt, "count": len(new_tl), "project": saved}
        finally:
            local_progress["active"] = False

    @r.post("/api/mv/apply_early_lead")
    async def api_apply_early_lead(request: Request):
        """The input box is the total lead; only the difference to what the timeline already has is applied."""
        configure()
        body = await request.json()
        try:
            proj = client_project(body, str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        target = round(float(body.get("shift_sec", -0.70)), 2)
        tl = proj.get("timeline", [])
        applied = proj.get("early_lead_applied")
        applied = round(float(applied), 2) if applied is not None else -0.70
        delta = round(target - applied, 2)
        if abs(delta) < 0.005 or not tl:
            proj["early_lead_sec"] = target
            proj["early_lead_applied"] = applied if tl else target
            saved = save_project_dict(proj)
            return {"status": "ok", "shifted_count": 0, "shift_sec": target, "delta": 0.0, "applied": saved.get("early_lead_applied"),
                    "project": saved, "message": f"目前時間軸已經是提前 {target}s，不需要再移動"}
        orig_tl = json.loads(json.dumps(tl))
        total_dur = float(proj.get("audio_duration") or (tl[-1]["end"] if tl else 240.0))
        shifted_count = 0

        def _shifts(seg) -> bool:
            return (not seg.get("locked")) and seg.get("type", "lyric") == "lyric" \
                and not str(seg.get("text", "")).strip().startswith(("～", "~"))

        for i, seg in enumerate(tl):
            if not _shifts(seg):
                continue
            prev_locked = (i > 0 and tl[i - 1].get("locked"))
            min_st = (tl[i - 1]["end"] if prev_locked else (float(tl[i - 1]["start"]) + 0.40 if i > 0 else 0.0))
            new_st = round(float(seg["start"]) + delta, 2)
            if i + 1 < len(tl):
                nxt = tl[i + 1]
                nxt_st = float(nxt["start"]) + (delta if _shifts(nxt) else 0.0)
                new_st = min(new_st, round(nxt_st - 0.40, 2))
            new_st = max(round(min_st, 2), new_st)
            seg["start"] = new_st
            if i > 0 and not prev_locked:
                tl[i - 1]["end"] = new_st
            shifted_count += 1
        proj["timeline"] = enforce_anchor_invariants(tl, orig_tl, total_dur)
        proj["early_lead_sec"] = target
        proj["early_lead_applied"] = target
        saved = save_project_dict(proj)
        return {"status": "ok", "shifted_count": shifted_count, "shift_sec": target, "delta": delta, "applied": target,
                "project": saved, "message": f"已從提前 {applied}s 調整成提前 {target}s（移動 {delta:+.2f}s）"}

    # ------------------------------------------------------------------ preview / render / verify / whisper
    @r.post("/api/mv/preview_frame")
    async def api_preview_frame(request: Request):
        configure()
        body = await request.json()
        slug = str(body.get("slug", ""))
        seg_idx = int(body.get("seg_idx", 0))
        try:
            proj = client_project(body, slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        tl = proj.get("timeline", [])
        if not tl:
            seg = {"scene": max(1, seg_idx if seg_idx > 0 else 1), "start": 0.0, "end": 10.0,
                   "text": proj.get("title") or "分鏡畫面預覽", "type": "lyric"}
        else:
            if seg_idx < 0 or seg_idx >= len(tl):
                seg_idx = 0
            seg = tl[seg_idx]
        frame = await asyncio.to_thread(render_single_styled_frame, proj, seg)
        prev_dir = Path(core.project_dir(proj["slug"])) / "previews"
        prev_dir.mkdir(parents=True, exist_ok=True)
        for old in sorted(prev_dir.glob("preview_*.png"))[:-20]:   # keep the last 20 previews
            old.unlink(missing_ok=True)
        out_p = prev_dir / f"preview_{seg_idx}_{int(time.time() * 1000)}.png"
        await asyncio.to_thread(frame.save, out_p, compress_level=1)
        return {"status": "ok", "preview_path": str(out_p), "segment": seg}

    @r.post("/api/mv/render")
    async def api_render_mv(request: Request):
        cfg = configure()
        body = await request.json()
        try:
            if "project" in body:
                proj = save_project_dict(client_project(body, str(body["project"].get("slug", ""))))
            else:
                proj = load_project_dict(str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        if not os.path.exists(proj.get("audio_file", "")):
            return jerr(500, f"MV 合成失敗：找不到指定的音源檔案：{proj.get('audio_file', '')}")
        payload = {"slug": proj["slug"], "library_root": str(cfg["library_dir"]),
                   "brand": {"singer": core.BRAND["singer"], "studio": core.BRAND["studio"], "lang": core.BRAND["lang"]}}
        jid = start_job("mv_render", "mv_render.py", payload, f"MV：{proj.get('title') or proj['name']}",
                        proj["song_id"], 4 * 3600)
        job = await wait_job(jid)
        if job["status"] == "cancelled":
            local_update(False, "render", 0, "⏹️ 已取消 MV 合成", "")
            return JSONResponse(status_code=409, content={"status": "cancelled", "detail": "已取消 MV 合成"})
        if job["status"] != "succeeded":
            msg = job.get("error_message") or job.get("error_code") or "未知錯誤"
            local_update(False, "render", 0, "❌ MV 合成失敗", str(msg)[:300])
            return JSONResponse(status_code=500, content={"status": "error", "detail": f"MV 合成失敗：{msg}"})
        res = job.get("result") or {}
        local_update(False, "render", 100, f"🎉《{proj.get('title', '')}》1080p 60fps MV 合成渲染與驗收完成！(耗時 {res.get('elapsed_sec', '?')}s)",
                     f"編碼器：{res.get('encoder', '')} | 輸出：{res.get('output_mv', '')}")
        return res

    @r.post("/api/mv/verify")
    async def api_verify_mv(request: Request):
        configure()
        body = await request.json()
        try:
            proj = load_project_dict(str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        return await asyncio.to_thread(execute_mv_verification, proj, body.get("timestamps"))

    @r.post("/api/mv/whisper_analyze")
    async def api_whisper_analyze(request: Request):
        configure()
        body = await request.json()
        force_rerun = bool(body.get("force_rerun", False))
        try:
            proj = load_project_dict(str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        audio_file = proj.get("audio_file", "")
        if not os.path.exists(audio_file):
            return jerr(400, f"音源檔案不存在: {audio_file}")
        w_json = proj["whisper_json"]
        if os.path.exists(w_json) and not force_rerun:
            local_update(False, "whisper", 100, "✔ 已載入 Whisper 逐字聲學快取", os.path.basename(w_json))
            with open(w_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            segs = data.get("segments", data) if isinstance(data, dict) else data
            return {"status": "ok", "source": "cache", "whisper_json": w_json, "segments": segs}
        try:
            out_segs, src_lbl = await run_whisper(proj, force_rerun)
            local_update(False, "whisper", 100, f"✔ Whisper 逐字聲學剖析完成！(共 {len(out_segs)} 句)", os.path.basename(w_json))
            return {"status": "ok", "source": src_lbl, "whisper_json": w_json, "segments": out_segs}
        except RuntimeError as e:
            local_update(False, "whisper", 0, "Whisper 聲學分析中止", str(e))
            return jerr(409, str(e))
        except Exception as e:  # noqa: BLE001
            local_update(False, "whisper", 0, "Whisper 聲學分析失敗", str(e))
            return jerr(500, f"Whisper 分析失敗：{e}")

    # ------------------------------------------------------------------ uploads
    async def save_upload(file: UploadFile, target: Path, limit: int = MAX_UPLOAD) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".part")
        size = 0
        try:
            with open(tmp, "wb") as fh:
                while True:
                    chunk = await file.read(1 << 20)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("檔案太大")
                    fh.write(chunk)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def to_scene_png(raw: bytes, out_path: Path) -> None:
        with Image.open(BytesIO(raw)) as im:
            rgb = im.convert("RGB").resize((FRAME_W, FRAME_H), Image.Resampling.LANCZOS)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(out_path, compress_level=1)

    @r.post("/api/mv/upload_audio")
    async def api_upload_audio(slug: str = Form(...), file: UploadFile = File(...)):
        configure()
        try:
            proj = load_project_dict(slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        ext = os.path.splitext(file.filename or "")[1].lower() or ".wav"
        if ext not in AUDIO_EXT:
            return jerr(400, "請選擇 WAV／MP3／M4A／FLAC 音檔")
        out_filename = f"{core.safe_file_title(proj.get('title', ''), proj['name'])}_master{ext}"
        out_path = Path(core.project_dir(slug)) / "audio" / out_filename
        try:
            await save_upload(file, out_path)
        except ValueError as exc:
            return jerr(400, str(exc))
        probe = probe_media_file(str(out_path))
        old_audio = proj.get("audio_file", "")
        proj["audio_file"] = str(out_path)
        _fit_timeline_to_audio(proj, probe, 10)
        _drop_whisper_if_audio_changed(proj, old_audio, str(out_path))
        save_project_dict(proj)
        return {"status": "ok", "audio_file": str(out_path), "filename": out_filename, "probe": probe}

    @r.post("/api/mv/upload_scene")
    async def api_upload_scene(slug: str = Form(...), scene_id: int = Form(...), file: UploadFile = File(...)):
        configure()
        try:
            proj = load_project_dict(slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        sid = int(scene_id)
        if not 1 <= sid <= MAX_SCENES:
            return jerr(400, f"照片最多 {MAX_SCENES} 張")
        illust_dir = proj["illust_dir"]
        out_path = Path(illust_dir) / f"scene_{sid:02d}.png"
        try:
            await asyncio.to_thread(to_scene_png, await file.read(), out_path)
        except Exception as e:  # noqa: BLE001
            return jerr(400, f"讀不到這張圖片：{e}")
        for fn in _scene_files(illust_dir, sid):   # an old jpg/webp of the same slot would shadow nothing, but keep one file
            if fn != out_path.name:
                os.remove(os.path.join(illust_dir, fn))
        if sid > int(proj.get("scene_count", 12) or 12):
            proj["scene_count"] = sid
            save_project_dict(proj)
        return {"status": "ok", "scene_id": sid, "path": str(out_path), "scenes": _scene_payload(proj)}

    @r.post("/api/mv/upload_scenes_batch")
    async def api_upload_scenes_batch(slug: str = Form(...), start_scene: int = Form(1), files: List[UploadFile] = File(...),
                                      fill_empty: int = Form(0)):
        configure()
        try:
            proj = load_project_dict(slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        illust_dir = proj["illust_dir"]
        os.makedirs(illust_dir, exist_ok=True)

        def _nat_key(uf: UploadFile):
            parts = re.split(r"(\d+)", os.path.basename(uf.filename or ""))
            return [int(p) if p.isdigit() else p.lower() for p in parts]

        saved_scenes, skipped = [], []
        cur_sc = max(1, int(start_scene))
        for uf in sorted(files, key=_nat_key):
            if fill_empty:   # the batch button only fills empty slots after the last photo; never overwrites
                while cur_sc <= MAX_SCENES and resolve_scene_image_path(illust_dir, cur_sc):
                    cur_sc += 1
            if cur_sc > MAX_SCENES:
                skipped.append(uf.filename)
                continue
            out_path = Path(illust_dir) / f"scene_{cur_sc:02d}.png"
            try:
                await asyncio.to_thread(to_scene_png, await uf.read(), out_path)
            except Exception:  # noqa: BLE001
                skipped.append(uf.filename)
                continue
            saved_scenes.append({"scene_id": cur_sc, "path": str(out_path), "source_name": uf.filename})
            cur_sc += 1
        proj["scene_count"] = max(int(proj.get("scene_count", 12) or 12), cur_sc - 1)
        save_project_dict(proj)
        return {"status": "ok", "count": len(saved_scenes), "scenes": saved_scenes, "all_scenes": _scene_payload(proj),
                "skipped": skipped}

    @r.post("/api/mv/scenes/delete")
    async def api_delete_scenes(request: Request):
        configure()
        body = await request.json()
        try:
            proj = load_project_dict(str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        illust_dir = proj["illust_dir"]
        deleted_files = []
        clear_all = bool(body.get("clear_all", False))
        if os.path.exists(illust_dir):
            if clear_all:
                for fn in os.listdir(illust_dir):
                    if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                        os.remove(os.path.join(illust_dir, fn))
                        deleted_files.append(fn)
            else:
                for sid in body.get("scene_ids", []):
                    try:
                        s_int = int(sid)
                    except (ValueError, TypeError):
                        continue
                    for fn in _scene_files(illust_dir, s_int):
                        os.remove(os.path.join(illust_dir, fn))
                        deleted_files.append(fn)
        if deleted_files or clear_all:   # deleting photos means the alignment has to be redone (old rule)
            proj["timeline"] = []
            save_project_dict(proj)
        return {"status": "ok", "deleted_count": len(deleted_files), "deleted_files": deleted_files,
                "all_scenes": _scene_payload(proj), "project": proj}

    @r.post("/api/mv/interlude/add")
    async def api_add_interlude(request: Request):
        configure()
        body = await request.json()
        try:
            proj = client_project(body, str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        tl = proj.get("timeline") or []
        if not tl:
            return jerr(400, "還沒有時間軸：請先貼歌詞對齊，再加間奏")
        probe = probe_media_file(str(proj.get("audio_file", "")))
        total_dur = float(probe.get("duration") or 0) if probe.get("exists") else 0.0
        total_dur = max(total_dur, float(tl[-1]["end"]))
        try:
            st = round(max(0.0, float(body.get("start"))), 2)
            et = round(min(total_dur, float(body.get("end"))), 2)
        except (TypeError, ValueError):
            return jerr(400, "間奏的開始／結束時間不正確")
        if et - st < 1.0:
            return jerr(400, "間奏至少要 1 秒")
        for x in tl:
            if x.get("locked") and min(et, float(x["end"])) - max(st, float(x["start"])) > 0.01:
                return jerr(409, f"這段時間跟已鎖定的 Scene {int(x.get('scene', 1)):02d}（{x['start']}~{x['end']}s）重疊；請先解鎖或換個時間")
        before = {id(x): (float(x["start"]), float(x["end"])) for x in tl}
        sc = next((int(x.get("scene", 1)) for x in tl if float(x["start"]) <= st < float(x["end"])), int(tl[-1].get("scene", 1)))
        iv = {"scene": sc, "start": st, "end": et, "text": str(body.get("text") or "～ 間奏 ～"), "type": "interlude",
              "note": "使用者新增的間奏", "locked": False, "user": True}
        if not splice_interlude(tl, iv, total_dur):
            return jerr(409, "這段時間放不下間奏（前後都是鎖定段）")
        squeezed = [x["text"] for x in tl if id(x) in before and _is_plain_lyric(x)
                    and (float(x["end"]) - float(x["start"])) < 0.5 * (before[id(x)][1] - before[id(x)][0])]
        new_iv = next(x for x in tl if id(x) not in before)
        normalize_instrumental_fields(tl)
        proj["timeline"] = tl
        saved = save_project_dict(proj)
        warn = ("⚠️ 這段間奏蓋到歌詞，下列歌詞被壓短了一半以上：" + "、".join(f"「{t}」" for t in squeezed[:5])) if squeezed else ""
        return {"status": "ok", "project": saved, "interlude_id": new_iv.get("id"), "warning": warn}

    @r.post("/api/mv/interlude/detect")
    async def api_detect_interludes(request: Request):
        configure()
        body = await request.json()
        try:
            proj = client_project(body, str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        words = load_whisper_words(proj)
        if not words:
            return jerr(409, "還沒有 Whisper 辨識結果：請先在右側按「⚡ 貼上並依 Whisper 自動對齊」跑一次，再來找間奏")
        try:
            min_gap = max(2.0, min(60.0, float(body.get("min_gap", 8.0))))
        except (TypeError, ValueError):
            min_gap = 8.0
        tail = float(proj.get("tail_extend_sec", 2.5) if proj.get("tail_extend_sec") is not None else 2.5)
        lead = float(proj.get("early_lead_applied", -0.7) if proj.get("early_lead_applied") is not None else -0.7)
        cands = detect_interlude_candidates(words, proj.get("timeline") or [], min_gap, tail, lead)
        return {"status": "ok", "min_gap": min_gap, "candidates": cands,
                "first_voice": round(words[0]["start"], 2), "last_voice": round(words[-1]["end"], 2)}

    @r.post("/api/mv/karaoke_times")
    async def api_karaoke_times(request: Request):
        configure()
        body = await request.json()
        try:
            proj = client_project(body, str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        words = load_whisper_words(proj, 0.0)
        lead = abs(float(proj.get("early_lead_applied", -0.70) or 0.0))
        mode = proj.get("karaoke_timing") if proj.get("karaoke_timing") in KARAOKE_TIMING_MODES else "voice"
        out = []
        for sg in proj.get("timeline") or []:
            if not karaoke_enabled_for(sg):
                out.append(None)
                continue
            clean = sanitize_no_ai(str(sg.get("text", "")), str(sg.get("text", "")))
            out.append({"text": clean, "times": karaoke_char_times(clean, float(sg["start"]), float(sg["end"]), words, lead, mode,
                                                                   karaoke_advance(proj))})
        return {"status": "ok", "has_whisper": bool(words), "segments": out}

    @r.post("/api/mv/instrumental/upload_photo")
    async def api_upload_instrumental_photo(slug: str = Form(...), key: str = Form(...), file: UploadFile = File(...)):
        configure()
        if not INST_KEY_RE.fullmatch(key or ""):
            return jerr(400, f"照片代號不正確：{key}")
        try:
            proj = load_project_dict(slug)
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        out_path = Path(instrumental_photo_path(proj["illust_dir"], key))
        try:
            await asyncio.to_thread(to_scene_png, await file.read(), out_path)
        except Exception as e:  # noqa: BLE001
            return jerr(400, f"讀不到這張圖片：{e}")
        return {"status": "ok", "key": key, "path": str(out_path),
                "instrument_photos": list_instrumental_photos(proj["illust_dir"], proj.get("timeline", []))}

    @r.post("/api/mv/instrumental/delete_photo")
    async def api_delete_instrumental_photo(request: Request):
        configure()
        body = await request.json()
        key = str(body.get("key", ""))
        if not INST_KEY_RE.fullmatch(key):
            return jerr(400, f"照片代號不正確：{key}")
        try:
            proj = load_project_dict(str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        fp = instrumental_photo_path(proj["illust_dir"], key)
        deleted = False
        if os.path.exists(fp):
            os.remove(fp)
            deleted = True
        return {"status": "ok", "deleted": deleted,
                "instrument_photos": list_instrumental_photos(proj["illust_dir"], proj.get("timeline", []))}

    @r.post("/api/mv/scenes/delete_shift")
    async def api_delete_scenes_shift(request: Request):
        """Delete photos; later photos move up one number; segments that used a deleted photo take the previous line's photo."""
        configure()
        body = await request.json()
        try:
            proj = client_project(body, str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        illust_dir = proj["illust_dir"]
        try:
            ids = sorted({int(x) for x in (body.get("scene_ids") or [])}, reverse=True)
        except (TypeError, ValueError):
            return jerr(400, "照片編號不正確")
        ids = [x for x in ids if 1 <= x <= MAX_SCENES]
        if not ids:
            return jerr(400, "沒有指定要刪的照片")
        tl = proj.get("timeline") or []
        total_count = max(int(proj.get("scene_count", 12) or 12), count_existing_scene_images(illust_dir),
                          max([int(s.get("scene", 1)) for s in tl] + [0]))
        deleted, moved = [], 0
        for sid in ids:
            for fn in _scene_files(illust_dir, sid):
                os.remove(os.path.join(illust_dir, fn))
                deleted.append(fn)
            moved += renumber_scene_files(illust_dir, {k: k - 1 for k in range(sid + 1, MAX_SCENES + 1)})
            orphan = []
            for seg in tl:
                sc = int(seg.get("scene", 1))
                if sc == sid:
                    orphan.append(seg)
                elif sc > sid:
                    seg["scene"] = sc - 1
            for seg in orphan:
                i = tl.index(seg)
                prev = next((tl[j] for j in range(i - 1, -1, -1) if tl[j] not in orphan), None)
                seg["scene"] = int(prev["scene"]) if prev else max(1, sid - 1)
            total_count -= 1
        proj["scene_count"] = max(1, total_count)
        proj["timeline"] = tl
        saved = save_project_dict(proj)
        return {"status": "ok", "deleted_files": deleted, "renamed": moved, "project": saved, "all_scenes": _scene_payload(saved)}

    @r.post("/api/mv/scenes/swap")
    async def api_swap_scenes(request: Request):
        configure()
        body = await request.json()
        try:
            proj = load_project_dict(str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        illust_dir = proj["illust_dir"]
        try:
            a, b = int(body.get("a")), int(body.get("b"))
        except (TypeError, ValueError):
            return jerr(400, "照片編號不正確")
        if a == b or not (1 <= a <= MAX_SCENES and 1 <= b <= MAX_SCENES):
            return jerr(400, "照片編號不正確")
        if not _scene_files(illust_dir, a) and not _scene_files(illust_dir, b):
            return jerr(400, "兩格都沒有照片")
        os.makedirs(illust_dir, exist_ok=True)
        renumber_scene_files(illust_dir, {a: b, b: a})
        proj["scene_count"] = max(int(proj.get("scene_count", 12) or 12), a, b)
        saved = save_project_dict(proj)
        return {"status": "ok", "project": saved, "all_scenes": _scene_payload(saved)}

    @r.post("/api/mv/scenes/insert_slot")
    async def api_insert_scene_slot(request: Request):
        configure()
        body = await request.json()
        try:
            proj = client_project(body, str(body.get("slug", "")))
        except ProjectNotFound as exc:
            return jerr(404, str(exc))
        illust_dir = proj["illust_dir"]
        try:
            before = int(body.get("before"))
        except (TypeError, ValueError):
            return jerr(400, "位置不正確")
        tl = proj.get("timeline") or []
        total_count = max(int(proj.get("scene_count", 12) or 12), count_existing_scene_images(illust_dir),
                          max([int(s.get("scene", 1)) for s in tl] + [0]))
        if not 1 <= before <= total_count:
            return jerr(400, "位置不正確")
        if total_count >= MAX_SCENES:
            return jerr(409, f"照片最多 {MAX_SCENES} 張，已經滿了")
        moved = renumber_scene_files(illust_dir, {k: k + 1 for k in range(before, MAX_SCENES)})
        for seg in tl:
            sc = int(seg.get("scene", 1))
            if sc >= before:
                seg["scene"] = sc + 1
        proj["scene_count"] = total_count + 1
        proj["timeline"] = tl
        saved = save_project_dict(proj)
        return {"status": "ok", "new_scene_id": before, "renamed": moved, "project": saved, "all_scenes": _scene_payload(saved)}

    # ------------------------------------------------------------------ media
    @r.get("/api/mv/media")
    def serve_media_file(request: Request, path: str, download: bool = False, filename: Optional[str] = None):
        configure()
        try:
            p = Path(path).resolve()
            p.relative_to(songs_root().resolve())
        except (ValueError, OSError):
            return jerr(403, "只能開啟歌曲庫裡的檔案")
        ext = p.suffix.lower()
        if ext not in MEDIA_TYPES or not p.is_file():
            return jerr(404, "找不到檔案")
        if download:
            return FileResponse(p, filename=filename or p.name, media_type="application/octet-stream")
        return media_response(p, request, MEDIA_TYPES[ext], {"Cache-Control": "no-cache"})

    return r
