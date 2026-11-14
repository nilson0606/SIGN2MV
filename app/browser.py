"""Open the web page as an app window.

Microsoft Edge ships with Windows 10/11, so it is used in "--app" mode with
its own profile folder inside runtime/ (so browser caches do not go to C:).
If Edge cannot be found, the default browser is used instead.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path

from .paths import Paths


def find_edge() -> str | None:
    candidates = []
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    for path in candidates:
        if path.is_file():
            return str(path)
    return shutil.which("msedge")


# TEMPORARY (11-14), backlog #22: the window stops drawing for 1-3 s while a video plays (page code keeps
# running; the window draws with the NVIDIA card). To tell which part of Edge's video path it is, extra
# switches for the app window can be listed in config/window_flags.txt, one per line. Only the switches
# below are accepted; an empty or missing file means none. They apply to this window's own profile only
# and are not stored by Edge: remove the line, start again, and the window is as before.
WINDOW_FLAGS = (
    "--disable-direct-composition-video-overlays",   # video drawn with the page instead of in its own overlay
    "--disable-accelerated-video-decode",            # video decoded by the CPU instead of the graphics card
    "--disable-gpu-compositing",                     # page put together by the CPU
    "--disable-gpu",                                 # no graphics card at all for the window
)


def window_flags(paths: Paths) -> list[str]:
    try:
        text = (paths.config / "window_flags.txt").read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return []
    lines = [ln.strip() for ln in text.splitlines()]
    return [f for f in WINDOW_FLAGS if f in lines]


def open_app_window(paths: Paths, url: str) -> None:
    if os.environ.get("SIGN2MV_NO_BROWSER"):
        return
    edge = find_edge() if os.name == "nt" else None
    if edge:
        profile = paths.browser_profile
        profile.mkdir(parents=True, exist_ok=True)
        args = [edge, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
                "--no-default-browser-check", "--disable-features=Translate",
                "--autoplay-policy=no-user-gesture-required", "--window-size=1480,940"]
        extra = window_flags(paths)
        if extra:
            logging.getLogger("sign2mv").info("app window opened with extra switches: %s", " ".join(extra))
        args += extra
        try:
            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return
        except OSError:
            pass
    webbrowser.open(url)
