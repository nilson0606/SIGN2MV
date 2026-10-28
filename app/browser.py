"""Open the web page as an app window.

Microsoft Edge ships with Windows 10/11, so it is used in "--app" mode with
its own profile folder inside runtime/ (so browser caches do not go to C:).
If Edge cannot be found, the default browser is used instead.
"""
from __future__ import annotations

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
        try:
            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return
        except OSError:
            pass
    webbrowser.open(url)
