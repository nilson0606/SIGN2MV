"""AI cover workspace API (/api/cover/*).

Replaces the AI cover page of AI_COVER_MV with the same features, reorganised
around the SIGN2MV song library:
  * voice models in models/voices/<Name>/ (import from a folder such as the old
    D:\\AI_COVER_MV\\models, upload, delete, epoch versions, loss curve);
  * training with Applio (GPU lane job, scratch in runtime/applio-logs);
  * a cover of a library song = a version (cover/versions/<vid>) whose mixed MP3
    is a render of the song (kind "cover"), so the MV workspace can use it;
  * quick remix of a version (volumes, instrument, sections, volume envelopes),
    in place or as a new version; key preview; section clips upload.
Conversions, separation and mixing run as queue jobs (workers/cover_run.py).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from . import cover
from .context import Context
from .cover import CoverError
from .library import LibraryError
from .renders import delete_render, renders_dir
from .tb_scalars import latest_event_file, loss_by_epoch
from .util import body_json, err

RUN_TIMEOUT = 3 * 3600.0
TRAIN_TIMEOUT = 48 * 3600.0
MAX_UPLOAD = 2 * 1024 ** 3
AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus", ".webm", ".mp4", ".mkv", ".mov",
              ".m4v", ".avi")
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
TOKEN = re.compile(r"^[a-f0-9]{16}$")
DEFAULTS_FILE = "cover_defaults.json"


def time_now() -> float:
    import time
    return time.time()


def glob_escape(s: str) -> str:
    import glob
    return glob.escape(s)


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def _sanitize_name(raw: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.\-]", "_", (raw or "").strip()).strip("_.-")
    name = re.sub(r"_+", "_", name)[:60]
    return name if cover.MODEL_NAME.match(name) else ""


def _copy_model(src_dir: Path | None, pth: Path | None, dest: Path, index: Path | None = None) -> None:
    """Copy one model (weights, index, notes, epoch versions) into dest atomically."""
    tmp = dest.with_name(f"_{dest.name}.importing")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        if src_dir is not None:
            for f in src_dir.iterdir():
                if f.is_file() and f.suffix.lower() in (".pth", ".index", ".txt"):
                    shutil.copy2(f, tmp / f.name)
            ep = src_dir / "epochs"
            if ep.is_dir():
                (tmp / "epochs").mkdir()
                for f in ep.iterdir():
                    if f.is_file() and (cover.EPOCH_FILE.search(f.name) or f.name == "loss.json"):
                        shutil.copy2(f, tmp / "epochs" / f.name)
        if pth is not None:
            shutil.copy2(pth, tmp / pth.name)
            base = re.sub(r"_\d+e(_\d+s)?$", "", pth.stem)
            idx = index or next(iter(sorted(pth.parent.glob(glob_escape(base) + "*.index"))), None)
            if idx and idx.is_file():
                shutil.copy2(idx, tmp / idx.name)
        if not any(tmp.glob("*.pth")):
            raise CoverError("no_model_file")
        os.replace(tmp, dest)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def router(ctx: Context) -> APIRouter:
    r = APIRouter()
    paths = ctx.paths

    # ------------------------------------------------------------------ helpers
    def voices() -> Path:
        paths.voices.mkdir(parents=True, exist_ok=True)
        return paths.voices

    def applio_python() -> str:
        override = os.environ.get("SIGN2MV_APPLIO_PYTHON")
        if override:
            return override
        exe = paths.env_python("applio")
        return str(exe) if exe.exists() else ""

    def applio_status() -> dict[str, Any]:
        a = paths.applio
        missing = [n for n, p in (("applio", a / "core.py"), ("rmvpe", a / "rvc/models/predictors/rmvpe.pt"),
                                  ("contentvec", a / "rvc/models/embedders/contentvec/pytorch_model.bin"))
                   if not p.is_file()]
        if not applio_python():
            missing.insert(0, "applio_env")
        pre = a / "rvc/models/pretraineds/hifi-gan"
        return {"ready": not missing, "missing": missing,
                "train_ready": not missing and (pre / "f0G40k.pth").is_file() and (pre / "f0D40k.pth").is_file()}

    def manifest_file(key: str) -> str:
        try:
            m = json.loads((paths.root / "installer" / "manifest.json").read_text(encoding="utf-8"))
            return m["models"][key]["file"]
        except (OSError, ValueError, KeyError):
            return ""

    def separators() -> dict[str, bool]:
        out = {}
        for k, key in (("aufr33", "male_female_aufr33"), ("sucial", "male_female_sucial"),
                       ("bs_roformer", "bs_roformer"), ("mel_roformer", "mel_roformer_kim"),
                       ("karaoke", "karaoke_aufr33")):
            f = manifest_file(key)
            out[k] = bool(f) and (paths.models / f).is_file()
        out["demucs"] = True
        return out

    def instruments() -> dict[str, bool]:
        sf = paths.soundfonts
        gm = (sf / "GeneralUser-GS.sf2").is_file()
        gz = (sf / "guzheng").is_dir() and any((sf / "guzheng").glob("*.ogg"))
        dz = (sf / "dizi").is_dir() and any((sf / "dizi").glob("*.ogg"))
        return {"none": True, "steel_guitar": gm, "yangqin": gm, "guzheng": gz, "dizi": dz, "duet": gz and dz}

    def defaults() -> dict[str, Any]:
        saved = cover.read_json(paths.config / DEFAULTS_FILE, {}) or {}
        p = cover.clean_params(saved)
        p["masks"], p["vol_segments"] = [], []
        if not p["model"] or not cover.model_dir(voices(), p["model"].split("__e")[0]):
            models = cover.list_models(voices())
            p["model"] = max(models, key=lambda m: m["mtime"])["name"] if models else ""
        return p

    def song_ctx(song_id: str):
        lib = ctx.library()
        song = lib.get(song_id)
        return lib, song, lib.song_dir(song_id)

    def resolver():
        cache: dict[str, dict] = {}

        def resolve(name: str) -> dict:
            if name not in cache:
                cache[name] = cover.resolve_model(voices(), name)
            return cache[name]
        return resolve

    def fail(exc: Exception):
        if isinstance(exc, CoverError) and exc.code.startswith("separator_missing:"):
            return err("separator_missing", 409, missing=exc.code.split(":", 1)[1].split(","))
        if isinstance(exc, (CoverError, LibraryError)):
            return err(exc.code, getattr(exc, "status", 400))
        if isinstance(exc, cover.stems_mod.RecipeError):
            return err(exc.code)
        raise exc

    def active_job(kind: str) -> dict | None:
        return next((j for j in ctx.jobs.active() if j["kind"] == kind), None)

    def version_out(song_id: str, sdir: Path, v: dict) -> dict:
        rid = v.get("render_id") or ""
        info = cover.read_json(renders_dir(ctx, song_id) / rid / "render.json", {}) or {}
        audio = info.get("audio")
        out = {k: v.get(k) for k in ("id", "number", "title", "label", "created_at", "updated_at", "render_id",
                                      "params", "duration", "instrument_used", "source_version", "stats")}
        out["audio"] = f"renders/{rid}/{audio}" if audio and (sdir / "renders" / rid / audio).is_file() else None
        out["bytes"] = info.get("bytes")
        return out

    # ------------------------------------------------------------------ status / models
    @r.get("/api/cover/status")
    def status():
        train = active_job("cover_train")
        return {"applio": applio_status(), "separators": separators(), "instruments": instruments(),
                "models": cover.list_models(voices()), "defaults": defaults(), "training": train,
                "voices_dir": str(voices()), "soundfonts_dir": str(paths.soundfonts)}

    @r.get("/api/cover/models")
    def models():
        return {"models": cover.list_models(voices())}

    @r.post("/api/cover/models/import")
    async def import_models(request: Request):
        """Body: {"path": folder of one model | folder of model folders | .pth file, "name"?: str}"""
        body = await body_json(request)
        src = Path(str(body.get("path") or "").strip().strip('"'))
        if not str(src) or not src.exists():
            return err("path_not_found", 404)

        def work() -> dict[str, Any]:
            imported, skipped = [], []

            def one(name_raw: str, src_dir: Path | None, pth: Path | None) -> None:
                name = _sanitize_name(name_raw)
                if not name:
                    skipped.append({"source": name_raw, "reason": "invalid_model_name"})
                    return
                if cover.model_dir(voices(), name):
                    skipped.append({"source": name_raw, "name": name, "reason": "model_exists"})
                    return
                try:
                    _copy_model(src_dir, pth, voices() / name)
                    imported.append(name)
                except CoverError as exc:
                    skipped.append({"source": name_raw, "reason": exc.code})

            if src.is_file():
                if src.suffix.lower() != ".pth":
                    raise CoverError("no_model_file")
                one(body.get("name") or re.sub(r"_\d+e(_\d+s)?$", "", src.stem) or src.stem, None, src)
            elif any(src.glob("*.pth")):
                one(body.get("name") or src.name, src, None)
            else:
                subs = [d for d in sorted(src.iterdir()) if d.is_dir() and any(d.glob("*.pth"))]
                if not subs:
                    raise CoverError("no_model_file")
                for d in subs:
                    one(d.name, d, None)
            return {"imported": imported, "skipped": skipped, "models": cover.list_models(voices())}
        try:
            return await run_in_threadpool(work)
        except CoverError as exc:
            return err(exc.code, exc.status)
        except OSError as exc:
            return err("import_failed", 500, detail=str(exc)[-300:])

    @r.post("/api/cover/models/upload")
    async def upload_model(name: str = Form(...), pth: UploadFile = File(...), index: UploadFile | None = File(None)):
        clean = _sanitize_name(name)
        if not clean:
            return err("invalid_model_name")
        if cover.model_dir(voices(), clean):
            return err("model_exists", 409)
        if not (pth.filename or "").lower().endswith(".pth"):
            return err("no_model_file")
        tmp = voices() / f"_{clean}.uploading"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)

        def save(up: UploadFile, dst: Path) -> None:
            with open(dst, "wb") as fh:
                shutil.copyfileobj(up.file, fh, 1 << 20)
        try:
            await run_in_threadpool(save, pth, tmp / os.path.basename(pth.filename.replace("\\", "/")))
            if index is not None and index.filename:
                if not index.filename.lower().endswith(".index"):
                    raise CoverError("invalid_index_file")
                await run_in_threadpool(save, index, tmp / os.path.basename(index.filename.replace("\\", "/")))
            os.replace(tmp, voices() / clean)
        except CoverError as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            return err(exc.code)
        except OSError as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            return err("import_failed", 500, detail=str(exc)[-300:])
        return {"name": clean, "models": cover.list_models(voices())}

    @r.delete("/api/cover/models/{name}")
    def delete_model(name: str):
        d = cover.model_dir(voices(), name)
        if not d:
            return err("model_not_found", 404)
        train = active_job("cover_train")
        if train and (train.get("title") or "").endswith(f": {d.name}"):
            return err("model_training", 409)
        if active_job("cover"):
            return err("model_in_use", 409)
        shutil.rmtree(d, ignore_errors=True)
        if d.exists():
            return err("delete_failed", 500)
        return {"models": cover.list_models(voices())}

    @r.delete("/api/cover/models/{name}/epochs/{epoch}")
    def delete_epoch(name: str, epoch: int):
        d = cover.model_dir(voices(), name)
        if not d:
            return err("model_not_found", 404)
        hit = [e for e in cover.epoch_files(d) if e["epoch"] == epoch]
        if not hit:
            return err("epoch_not_found", 404)
        (d / "epochs" / hit[0]["file"]).unlink(missing_ok=True)
        return {"freed": hit[0]["size"], "models": cover.list_models(voices())}

    @r.get("/api/cover/models/{name}/loss")
    def model_loss(name: str):
        d = cover.model_dir(voices(), name)
        if d and (d / "epochs" / "loss.json").is_file():
            data = cover.read_json(d / "epochs" / "loss.json", {}) or {}
            data["source"] = "saved"
            data["kept_epochs"] = [e["epoch"] for e in cover.epoch_files(d)] + (
                [data["final_epoch"]] if data.get("final_epoch") else [])
            return data
        live = paths.runtime / "applio-logs" / _sanitize_name(name)
        ev = latest_event_file(str(live)) if live.is_dir() else None
        if ev:
            data = loss_by_epoch(ev)
            data.update(source="live", model=name)
            return data
        return {"epoch": [], "source": "none"}

    # ------------------------------------------------------------------ training
    @r.post("/api/cover/train/files")
    async def train_files(files: list[UploadFile] = File(...), token: str = Form("")):
        token = token if TOKEN.match(token or "") else uuid.uuid4().hex[:16]
        d = paths.tmp / "train-uploads" / token
        d.mkdir(parents=True, exist_ok=True)
        saved = []
        for up in files:
            base = os.path.basename((up.filename or "audio").replace("\\", "/"))
            stem, ext = os.path.splitext(base)
            if ext.lower() not in AUDIO_EXTS:
                continue
            safe = re.sub(r"[^\w.\-]", "_", stem)[:80] or "audio"
            dst = d / f"{len(list(d.iterdir())):03d}_{safe}{ext.lower()}"

            def save(u=up, p=dst) -> None:
                with open(p, "wb") as fh:
                    shutil.copyfileobj(u.file, fh, 1 << 20)
            await run_in_threadpool(save)
            saved.append({"name": base, "size": dst.stat().st_size})
        listing = [{"name": f.name, "size": f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file()]
        return {"token": token, "added": saved, "files": listing}

    @r.post("/api/cover/train")
    async def train(request: Request):
        body = await body_json(request)
        name = _sanitize_name(str(body.get("name") or ""))
        if not name or name != str(body.get("name") or "").strip():
            return err("invalid_model_name")
        st = applio_status()
        if not st["train_ready"]:
            return err("applio_missing", 409, missing=st["missing"])
        if active_job("cover_train"):
            return err("train_busy", 409)
        if cover.model_dir(voices(), name) and not body.get("overwrite"):
            return err("model_exists", 409)
        inputs = []
        token = str(body.get("token") or "")
        upload_dir = None
        if TOKEN.match(token) and (paths.tmp / "train-uploads" / token).is_dir():
            upload_dir = paths.tmp / "train-uploads" / token
            inputs.append(str(upload_dir))
        for p in body.get("paths") or []:
            p = str(p).strip().strip('"')
            if p and Path(p).exists():
                inputs.append(p)
            elif p:
                return err("path_not_found", 404, path=p)
        if not inputs:
            return err("train_no_audio")

        def num(key: str, d: int, lo: int, hi: int) -> int:
            try:
                return max(lo, min(hi, int(body.get(key, d))))
            except (TypeError, ValueError):
                return d
        sr = num("sample_rate", 40000, 32000, 48000)
        if sr not in (32000, 40000, 48000):
            sr = 40000
        payload = {"name": name, "inputs": inputs, "epochs": num("epochs", 100, 1, 2000),
                   "batch_size": num("batch_size", 8, 1, 64), "save_every": num("save_every", 10, 1, 500),
                   "sample_rate": sr, "logs_dir": str(paths.runtime / "applio-logs"), "voices_dir": str(voices()),
                   "upload_dir": str(upload_dir) if upload_dir else ""}
        py = applio_python()
        job = ctx.submit(kind="cover_train", lane="gpu", script="cover_train.py", input=payload,
                         title=f"train: {name}", timeout_s=TRAIN_TIMEOUT, env_name="applio", cwd=paths.applio,
                         args=[py, "-u", str(paths.workers / "cover_train.py")])
        return {"job": job}

    @r.post("/api/cover/train/cleanup")
    def train_cleanup():
        if active_job("cover_train"):
            return err("train_busy", 409)
        freed = 0
        for d in (paths.runtime / "applio-logs", paths.tmp / "train-uploads"):
            if d.is_dir():
                for f in d.rglob("*"):
                    try:
                        if f.is_file():
                            freed += f.stat().st_size
                    except OSError:
                        pass
                shutil.rmtree(d, ignore_errors=True)
        for d in voices().glob("_*"):
            try:
                if d.stat().st_mtime < time_now() - 600:   # not an import / upload in progress
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
        return {"freed": freed}

    # ------------------------------------------------------------------ instrument sounds
    @r.post("/api/cover/soundfonts/import")
    async def import_soundfonts(request: Request):
        """Body: {"path": folder that contains guzheng/ and/or dizi/ (and optionally a GeneralUser .sf2)}"""
        body = await body_json(request)
        src = Path(str(body.get("path") or "").strip().strip('"'))
        if not src.is_dir():
            return err("path_not_found", 404)

        def work() -> dict[str, Any]:
            dst = paths.soundfonts
            dst.mkdir(parents=True, exist_ok=True)
            done = []
            for name in ("guzheng", "dizi"):
                sd = src / name if (src / name).is_dir() else (src if src.name.lower() == name else None)
                if sd and any(sd.glob("*.ogg")):
                    tmp = dst / f"_{name}.importing"
                    shutil.rmtree(tmp, ignore_errors=True)
                    tmp.mkdir()
                    for f in sd.glob("*.ogg"):
                        shutil.copy2(f, tmp / f.name)
                    shutil.rmtree(dst / name, ignore_errors=True)
                    os.replace(tmp, dst / name)
                    done.append(name)
            if not (dst / "GeneralUser-GS.sf2").is_file():
                sf2 = next(iter(sorted(src.glob("GeneralUser*.sf2"))), None)
                if sf2:
                    shutil.copy2(sf2, dst / "GeneralUser-GS.sf2")
                    done.append("GeneralUser-GS.sf2")
            if not done:
                raise CoverError("no_instrument_files")
            return {"imported": done, "instruments": instruments()}
        try:
            return await run_in_threadpool(work)
        except CoverError as exc:
            return err(exc.code)

    # ------------------------------------------------------------------ songs
    @r.get("/api/cover/songs/{song_id}")
    def song_state(song_id: str):
        try:
            _lib, song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        saved = cover.read_json(cover.cover_dir(sdir) / "settings.json")
        settings = cover.clean_params(saved) if isinstance(saved, dict) else defaults()
        if isinstance(saved, dict) and not saved.get("model"):
            settings["model"] = defaults()["model"]
        job = ctx.pending_job(song_id, "cover")
        return {"song_id": song_id, "title": song["title"], "has_source": bool(song.get("source")),
                "duration": (song.get("source") or {}).get("duration"), "settings": settings,
                "versions": [version_out(song_id, sdir, v) for v in cover.list_versions(sdir)], "job": job}

    @r.put("/api/cover/songs/{song_id}/settings")
    async def save_settings(song_id: str, request: Request):
        try:
            _lib, _song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        p = cover.clean_params((await body_json(request)).get("params"))
        cover.write_json(cover.cover_dir(sdir) / "settings.json", p)
        return {"settings": p}

    def check_separators(plan: dict) -> None:
        have = separators()
        need = set()
        for layer in plan["layers"]:
            need.add("karaoke" if layer["kind"] == "lead" else layer["model"])
        for j in plan["seg_jobs"]:
            need.add(j["sep"]["sep_model"])
            if j["sep"]["vocal_mode"] != "full":
                need.add("karaoke")
        missing = sorted(n for n in need if have.get(n) is False)
        if missing:
            raise CoverError("separator_missing:" + ",".join(missing))

    def submit_cover(song_id: str, song: dict, sdir: Path, p: dict, version: dict, render: dict,
                     reuse: dict | None = None) -> dict:
        plan = cover.plan(sdir, song, p, resolver(), reuse=reuse)
        check_separators(plan)
        if plan["need_gpu"] and not applio_status()["ready"] and any(
                not (sdir / t["output"]).is_file() for t in plan["rvc_tasks"]):
            raise CoverError("applio_missing", 409)
        payload = {"song_dir": str(sdir), "plan": plan, "params": p, "version": version, "render": render,
                   "applio": {"python": applio_python(), "dir": str(paths.applio)},
                   "soundfonts": str(paths.soundfonts)}
        lane = "gpu" if plan["need_gpu"] else "cpu"
        return ctx.submit(kind="cover", lane=lane, script="cover_run.py", input=payload,
                          title=f"cover: {song['title']} ({version['label']})", song_id=song_id,
                          timeout_s=RUN_TIMEOUT, dedupe="cover")

    @r.post("/api/cover/songs/{song_id}/run")
    async def run_cover(song_id: str, request: Request):
        body = await body_json(request)
        try:
            _lib, song, sdir = song_ctx(song_id)
            if not song.get("source"):
                raise CoverError("song_has_no_audio")
            if ctx.pending_job(song_id, "cover"):
                raise CoverError("cover_busy", 409)
            p = cover.clean_params(body.get("params"))
            cover.validate(p)
            cover.write_json(cover.cover_dir(sdir) / "settings.json", p)
            cover.write_json(paths.config / DEFAULTS_FILE, {k: v for k, v in p.items() if k not in ("masks", "vol_segments")})
            number = cover.next_number(sdir)
            label = cover.version_label(p)
            vid = cover.new_version_id()
            version = {"id": vid, "number": number, "label": label, "title": f"#{number} {label}"}
            render = {"id": "r" + uuid.uuid4().hex[:12], "replace": False, "title": f"{song['title']} · {label} #{number}"}
            job = submit_cover(song_id, song, sdir, p, version, render)
        except Exception as exc:  # noqa: BLE001
            return fail(exc)
        return {"job": job, "version_id": vid}

    @r.post("/api/cover/songs/{song_id}/versions/{vid}/remix")
    async def remix(song_id: str, vid: str, request: Request):
        """Body: {"mix", "masks", "vol_segments", "backing_on", "mf_vols": {"male","female"}, "save_as_new"}"""
        body = await body_json(request)
        try:
            _lib, song, sdir = song_ctx(song_id)
            if ctx.pending_job(song_id, "cover"):
                raise CoverError("cover_busy", 409)
            base = cover.load_version(sdir, vid)
            raw = dict(base.get("params") or {})
            for k in ("mix", "masks", "vol_segments", "backing_on"):
                if k in body:
                    raw[k] = body[k]
            if raw.get("mf") and isinstance(body.get("mf_vols"), dict):
                for side in ("male", "female"):
                    if side in body["mf_vols"]:
                        raw["mf"][side]["vol"] = body["mf_vols"][side]
            p = cover.clean_params(raw)
            cover.validate(p)
            label = cover.version_label(p)
            if body.get("save_as_new"):
                number = cover.next_number(sdir)
                version = {"id": cover.new_version_id(), "number": number, "label": label,
                           "title": f"#{number} {label}", "source_version": vid}
                render = {"id": "r" + uuid.uuid4().hex[:12], "replace": False,
                          "title": f"{song['title']} · {label} #{number}"}
            else:
                version = {k: base[k] for k in ("id", "number", "title", "created_at") if k in base}
                version.update(label=label, source_version=base.get("source_version"))
                render = {"id": base.get("render_id") or "r" + uuid.uuid4().hex[:12], "replace": True, "title": None}
            job = submit_cover(song_id, song, sdir, p, version, render, reuse=(base.get("plan") or {}).get("vocal"))
        except Exception as exc:  # noqa: BLE001
            return fail(exc)
        return {"job": job, "version_id": version["id"]}

    @r.patch("/api/cover/songs/{song_id}/versions/{vid}")
    async def rename_version(song_id: str, vid: str, request: Request):
        body = await body_json(request)
        title = str(body.get("title") or "").strip()[:120]
        if not title:
            return err("invalid_title")
        try:
            _lib, _song, sdir = song_ctx(song_id)
            v = cover.load_version(sdir, vid)
        except Exception as exc:  # noqa: BLE001
            return fail(exc)
        v["title"] = title
        cover.write_json(cover.cover_dir(sdir) / "versions" / vid / "version.json", v)
        rj = renders_dir(ctx, song_id) / (v.get("render_id") or "_") / "render.json"
        info = cover.read_json(rj)
        if isinstance(info, dict):
            info["title"] = title
            cover.write_json(rj, info)
        return version_out(song_id, sdir, v)

    @r.delete("/api/cover/songs/{song_id}/versions/{vid}")
    def delete_version(song_id: str, vid: str):
        try:
            _lib, _song, sdir = song_ctx(song_id)
            v = cover.load_version(sdir, vid)
        except Exception as exc:  # noqa: BLE001
            return fail(exc)
        if ctx.pending_job(song_id, "cover"):
            return err("cover_busy", 409)
        if v.get("render_id"):
            delete_render(ctx, song_id, v["render_id"])
        shutil.rmtree(cover.cover_dir(sdir) / "versions" / vid, ignore_errors=True)
        freed = cover.collect_garbage(sdir, min_age_s=0)
        return {"freed": freed}

    @r.get("/api/cover/songs/{song_id}/versions/{vid}/tracks")
    def version_tracks(song_id: str, vid: str):
        try:
            _lib, _song, sdir = song_ctx(song_id)
            v = cover.load_version(sdir, vid)
        except Exception as exc:  # noqa: BLE001
            return fail(exc)
        pl = v.get("plan") or {}
        t = pl.get("tracks") or {}
        items = [("mix", t.get("mix")), ("vocals", t.get("vocals")), ("instrumental", t.get("instrumental")),
                 ("instrumental_first", t.get("instrumental_first")), ("residual_vocals", t.get("residual_vocals")),
                 ("lead", t.get("lead")), ("backing", t.get("backing")), ("backing2", t.get("backing2")),
                 ("male", t.get("male")), ("female", t.get("female"))]
        comb = (pl.get("vocal") or {}).get("combine")
        if comb:
            items += [("ai_male", comb.get("male")), ("ai_female", comb.get("female"))]
        items.append(("ai_vocal", (pl.get("vocal") or {}).get("path")))
        if pl.get("key"):
            items.append(("bgm_key", pl.get("bgm")))
            items += [(f"backing_key{i + 1}", b) for i, b in enumerate(pl.get("backings") or [])]
        out = [{"key": k, "path": rel} for k, rel in items if rel and (sdir / rel).is_file()]
        return {"tracks": out}

    # ------------------------------------------------------------------ section clips / key preview
    @r.post("/api/cover/songs/{song_id}/patches")
    async def upload_patch(song_id: str, file: UploadFile = File(...)):
        try:
            _lib, _song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        pdir = cover.cover_dir(sdir) / "patches"
        pdir.mkdir(parents=True, exist_ok=True)
        tmp = paths.tmp / f"patch-{uuid.uuid4().hex}{os.path.splitext(file.filename or '')[1][:8]}"
        paths.tmp.mkdir(parents=True, exist_ok=True)

        def work() -> dict[str, Any]:
            h = hashlib.sha256()
            size = 0
            with open(tmp, "wb") as fh:
                while True:
                    chunk = file.file.read(1 << 20)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 300 * 1024 ** 2:
                        raise CoverError("file_too_large")
                    h.update(chunk)
                    fh.write(chunk)
            if not size:
                raise CoverError("upload_missing")
            name = f"up_{h.hexdigest()[:12]}.wav"
            out = pdir / name
            if not out.is_file():
                part = pdir / (name + ".part.wav")
                res = subprocess.run([_ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", str(tmp), "-vn", "-ar", "44100",
                                      "-ac", "2", "-c:a", "pcm_f32le", str(part)], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
                if res.returncode != 0 or not part.is_file():
                    part.unlink(missing_ok=True)
                    raise CoverError("unsupported_audio")
                os.replace(part, out)
            dur = max(0.0, (out.stat().st_size - 80) / (44100 * 2 * 4))
            return {"file": name, "name": os.path.basename(file.filename or name)[:80], "duration": round(dur, 2),
                    "path": f"cover/patches/{name}"}
        try:
            return await run_in_threadpool(work)
        except CoverError as exc:
            return err(exc.code)
        finally:
            tmp.unlink(missing_ok=True)

    @r.post("/api/cover/songs/{song_id}/key_preview")
    async def key_preview(song_id: str, request: Request):
        body = await body_json(request)
        try:
            _lib, song, sdir = song_ctx(song_id)
        except LibraryError as exc:
            return err(exc.code, exc.status)
        src = song.get("source") or {}
        if not src.get("audio"):
            return err("song_has_no_audio")
        try:
            key = max(cover.KEY_MIN, min(cover.KEY_MAX, int(body.get("key", 0))))
        except (TypeError, ValueError):
            return err("invalid_key")
        if key == 0:
            return {"key": 0, "path": src["audio"]}
        sig = hashlib.sha1(str(src.get("source_hash") or src["audio"]).encode()).hexdigest()[:10]
        rel = f"cover/preview/{sig}_k{key}.mp3"
        out = sdir / rel

        def work() -> None:
            out.parent.mkdir(parents=True, exist_ok=True)
            part = out.with_name(out.stem + ".part.mp3")
            res = subprocess.run([_ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", str(sdir / src["audio"]), "-vn",
                                  "-af", f"rubberband=tempo=1:pitch={2 ** (key / 12):.6f}:pitchq=quality:channels=together",
                                  "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2", str(part)],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 creationflags=NO_WINDOW)
            if res.returncode != 0 or not part.is_file():
                part.unlink(missing_ok=True)
                raise CoverError("rubberband_missing" if "rubberband" in (res.stderr or "").lower() else "key_shift_failed")
            os.replace(part, out)
        if not out.is_file():
            try:
                await run_in_threadpool(work)
            except CoverError as exc:
                return err(exc.code, 500)
        os.utime(out)
        return {"key": key, "path": rel}

    return r
