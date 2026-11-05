"""Start the SIGN2MV server:  python -m app [--port 9700] [--no-browser]"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
import urllib.request

from . import APP_NAME, DEFAULT_PORT, VERSION
from .browser import open_app_window
from .childenv import cache_vars, ensure_dirs
from .paths import get_paths
from .proc import adopt_self_into_job


def _port_owner(port: int) -> str | None:
    """'self' if SIGN2MV already answers on the port, 'other' if something else does."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/system/status", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return "self" if data.get("app") == APP_NAME else "other"
    except Exception:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return "other" if sock.connect_ex(("127.0.0.1", port)) == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(prog="sign2mv")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SIGN2MV_PORT", DEFAULT_PORT)))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    paths = get_paths()
    # The server's own temp files and caches also stay inside the app folder.
    os.environ.update({k: v for k, v in cache_vars(paths).items()})
    # ffmpeg/ffprobe are also used by the server itself (MP3 export, MV probes).
    tool_dirs = [str(paths.ffmpeg_bin), str(paths.deno_dir)]
    os.environ["PATH"] = os.pathsep.join(tool_dirs + [os.environ.get("PATH", "")])
    ensure_dirs(paths)
    paths.logs.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(paths.logs / "server.log", maxBytes=2_000_000,
                                                   backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler(sys.stdout)],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("sign2mv")

    url = f"http://127.0.0.1:{args.port}/"
    owner = _port_owner(args.port)
    if owner == "self":
        print(f"{APP_NAME} is already running. Opening the window: {url}")
        if not args.no_browser:
            open_app_window(paths, url)
        return 0
    if owner == "other":
        print(f"ERROR: port {args.port} is used by another program. Close it, or start with --port <number>.")
        return 2

    in_job = adopt_self_into_job()
    log.info("%s %s starting on %s (root=%s, job_object=%s)", APP_NAME, VERSION, url, paths.root, in_job)

    import uvicorn
    from .server import create_app

    server_ref: dict = {}

    def request_shutdown() -> None:
        srv = server_ref.get("server")
        if srv is not None:
            srv.should_exit = True

    app = create_app(paths, port=args.port, request_shutdown=request_shutdown)
    # timeout_graceful_shutdown: an open page keeps connections (paused video, microphone stream) open
    # and uvicorn waited for them forever, so 全部關閉 left the black window running
    config = uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning",
                            access_log=False, lifespan="off", timeout_graceful_shutdown=3)
    server = uvicorn.Server(config)
    server_ref["server"] = server

    if not args.no_browser:
        def open_when_ready() -> None:
            for _ in range(100):
                if server.started:
                    open_app_window(paths, url)
                    return
                time.sleep(0.1)
        threading.Thread(target=open_when_ready, daemon=True).start()

    print("=" * 60)
    print(f" {APP_NAME} {VERSION} is running at {url}")
    print(" Keep this window open while you use SIGN2MV.")
    print(" To quit: press 'Shut down' in the web page (or close this window).")
    print("=" * 60)
    server.run()
    app.state.warmup.stop()
    app.state.jobs.stop(wait_s=5.0)
    log.info("%s stopped", APP_NAME)
    _exit_now()
    return 0


def _exit_now() -> None:
    """End the process even when a worker thread is still blocked (a stuck read keeps Python waiting at
    exit, and with it the start.bat window). Child processes go with the job object."""
    deadline = time.monotonic() + 3.0
    for t in threading.enumerate():
        if t is not threading.current_thread() and not t.daemon:
            t.join(timeout=max(0.0, deadline - time.monotonic()))
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
