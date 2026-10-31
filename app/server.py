"""HTTP API and static web page."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import API_LEVEL, APP_NAME, VERSION, settings as settings_mod
from .context import Context
from .finished import FinishedSync
from .jobs import JobQueue
from .paths import Paths
from .util import body_json, err

CONTROL_HEADER = "x-sign2mv"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
_EXTRA_ROUTERS: list[Callable[[Context], Any]] = []


def register_router(factory: Callable[[Context], Any]) -> None:
    _EXTRA_ROUTERS.append(factory)


def _read_json(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def create_app(paths: Paths, *, port: int, request_shutdown: Callable[[], None] | None = None,
               queue: JobQueue | None = None) -> FastAPI:
    app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    jobs = queue or JobQueue()
    ctx = Context(paths, jobs)
    ctx.finished = FinishedSync(ctx)
    jobs.finished_listeners.append(ctx.finished.request)
    state = {"shutting_down": False}
    app.state.jobs = jobs
    app.state.ctx = ctx
    app.state.paths = paths

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # Only answer requests addressed to this machine (blocks DNS rebinding).
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
        if host not in ALLOWED_HOSTS:
            return err("forbidden_host", 403)
        # Any request that changes something must carry our custom header.
        # A web page from another site cannot add it without a CORS preflight,
        # which this server never approves.
        # /sr/* (sing & record) uses its own custom token headers, which need
        # the same preflight, so the same protection applies there.
        sr = request.url.path.startswith("/sr/")
        if request.method not in ("GET", "HEAD") and not sr and request.headers.get(CONTROL_HEADER) != "1":
            return err("missing_control_header", 403)
        response = await call_next(request)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            ctx.finished.request()   # something may have been added, renamed or deleted
        if not request.url.path.startswith("/media/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # ---------------- system ----------------
    @app.get("/api/system/status")
    def status() -> dict[str, Any]:
        cfg = settings_mod.load(paths)
        report = _read_json(paths.install_report) or {}
        return {
            "app": APP_NAME,
            "version": VERSION,
            "api_level": API_LEVEL,
            "port": port,
            "root": str(paths.root),
            "language": settings_mod.effective_language(cfg),
            "language_chosen": cfg.get("language") is not None,
            "install": {
                "completed": bool(report.get("completed")),
                "device": report.get("device"),
                "gpu_name": report.get("gpu_name"),
                "checks": report.get("checks", {}),
                "c_drive_delta_bytes": report.get("c_drive_delta_bytes"),
                "finished_at": report.get("finished_at"),
                "sucial": report.get("sucial", False),
            },
            "lanes": jobs.lanes,
            "shutting_down": state["shutting_down"],
        }

    @app.post("/api/system/shutdown")
    async def shutdown(request: Request):
        body = await body_json(request)
        active = jobs.active()
        other: list[str] = []
        for hook in getattr(ctx, "busy_hooks", []):
            try:
                other += list(hook() or [])
            except Exception:  # noqa: BLE001
                pass
        if (active or other) and not body.get("force"):
            return err("jobs_running", 409, jobs=active, busy=other)
        state["shutting_down"] = True

        def later() -> None:
            jobs.stop(wait_s=5.0)
            if request_shutdown:
                request_shutdown()

        threading.Timer(0.3, later).start()
        return {"ok": True, "cancelled": len(active)}

    # ---------------- settings ----------------
    @app.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        cfg = settings_mod.load(paths)
        cfg["effective_language"] = settings_mod.effective_language(cfg)
        return cfg

    picker: dict[str, Any] = {"proc": None}

    @app.post("/api/settings/pick-library")
    async def pick_library():
        """Windows folder dialog for the library location (sign_record's 「選擇資料夾」)."""
        import subprocess
        from starlette.concurrency import run_in_threadpool
        if os.name != "nt":
            return err("folder_picker_windows_only")
        if picker["proc"] is not None:
            return err("folder_picker_open", 409)
        script = Path(__file__).with_name("select_folder.ps1")
        current = settings_mod.load(paths).get("library_dir") or ""

        def run() -> dict[str, Any]:
            proc = subprocess.Popen(["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File",
                                     str(script), "-InitialPath", current], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
            picker["proc"] = proc
            try:
                out, _ = proc.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                return {"cancelled": True}
            finally:
                picker["proc"] = None
            try:
                return json.loads(out.decode("utf-8", "replace").lstrip("\ufeff").strip().splitlines()[-1])
            except (ValueError, IndexError):
                return {"cancelled": True}
        return await run_in_threadpool(run)

    @app.post("/api/settings/pick-library/cancel")
    def cancel_pick():
        proc = picker["proc"]
        if proc is not None:
            proc.kill()
        return {"cancelled": True}

    @app.put("/api/settings")
    async def put_settings(request: Request):
        body = await body_json(request)
        if "library_dir" in body and body["library_dir"] != settings_mod.load(paths).get("library_dir"):
            busy = list(jobs.active())
            for hook in getattr(ctx, "busy_hooks", []):
                try:
                    busy += list(hook() or [])
                except Exception:  # noqa: BLE001
                    pass
            if busy:   # sign_record refused too: songs, audio or MV work in progress
                return err("library_change_busy", 409)
        try:
            cfg = settings_mod.update(paths, body)
        except settings_mod.SettingsError as exc:
            return err(exc.code)
        cfg["effective_language"] = settings_mod.effective_language(cfg)
        return cfg

    # ---------------- jobs ----------------
    @app.get("/api/jobs")
    def list_jobs():
        return {"jobs": jobs.list()}

    @app.get("/api/jobs/{job_id}/log")
    def job_log(job_id: str, after: int = 0):
        data = jobs.log(job_id, max(0, int(after)))
        if data is None:
            return err("job_not_found", 404)
        return data

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = jobs.get(job_id)
        return job if job else err("job_not_found", 404)

    @app.post("/api/jobs")
    async def create_demo_job(request: Request):
        """Demo jobs only (to try the queue). Real jobs are started by their own APIs."""
        if state["shutting_down"]:
            return err("shutting_down", 409)
        body = await body_json(request)
        if body.get("kind") != "demo":
            return err("unknown_job_kind")
        lane = body.get("lane", "gpu")
        if lane not in jobs.lanes:
            return err("unknown_lane")
        try:
            seconds = float(body.get("seconds", 10))
            timeout_s = float(body.get("timeout_s", 600))
        except (TypeError, ValueError):
            return err("invalid_number")
        return ctx.submit(kind="demo", lane=lane, script="demo_job.py",
                          input={"seconds": seconds, "fail": bool(body.get("fail"))},
                          title=str(body.get("title") or "demo")[:80],
                          timeout_s=max(1.0, min(timeout_s, 3600.0)),
                          args=[sys.executable, "-u", str(paths.workers / "demo_job.py")])

    @app.post("/api/jobs/clear-finished")
    def clear_finished_jobs():
        return {"cleared": jobs.clear_finished()}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        if jobs.get(job_id) is None:
            return err("job_not_found", 404)
        return {"ok": jobs.cancel(job_id)}

    # ---------------- feature routers ----------------
    from . import api_songs
    app.include_router(api_songs.router(ctx))
    for factory in _load_feature_routers():
        app.include_router(factory(ctx))

    # ---------------- finished-outputs folder (<library>/成品) ----------------
    @app.get("/api/finished")
    def finished_status():
        cfg = settings_mod.load(paths)
        from .finished import MANIFEST, ROOT_NAMES, lang_key
        lib = Path(cfg["library_dir"])
        man = _read_json(lib / MANIFEST) or {}
        name = man.get("root") or ROOT_NAMES[lang_key(settings_mod.effective_language(cfg))]
        return {"path": str(lib / name), "songs": {k: v.get("folder") for k, v in (man.get("songs") or {}).items()},
                "last": ctx.finished.last}

    @app.post("/api/finished/open")
    async def finished_open(request: Request):
        """Bring the folder up to date, then show it (or one song's folder) in Explorer."""
        import subprocess
        from starlette.concurrency import run_in_threadpool
        body = await body_json(request)
        await run_in_threadpool(ctx.finished.run_now)
        info = finished_status()
        target = Path(info["path"])
        folder = info["songs"].get(str(body.get("song_id") or ""))
        if folder and (target / folder).is_dir():
            target = target / folder
        if not target.is_dir():
            return err("file_not_found", 404)
        if os.name != "nt":
            return err("open_folder_windows_only")
        subprocess.Popen(["explorer", str(target)])
        return {"ok": True, "path": str(target)}

    ctx.finished.request()   # bring the folder up to date at start

    # ---------------- web page ----------------
    @app.get("/")
    def index():
        return FileResponse(paths.web / "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return Response(status_code=204)

    app.mount("/", StaticFiles(directory=str(paths.web)), name="web")
    return app


def _load_feature_routers() -> list[Callable[[Context], Any]]:
    """Workspace routers (sing & record, MV, cover). Missing ones are skipped."""
    import importlib
    factories = list(_EXTRA_ROUTERS)
    for name in ("api_sing", "api_mv", "api_cover", "api_quickmv"):
        try:
            mod = importlib.import_module(f"app.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.{name}":
                continue
            raise
        factories.append(mod.router)
    return factories
