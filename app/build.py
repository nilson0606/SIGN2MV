"""Which version of the code this is: the commit date and short hash.

app/BUILD.txt holds "$Format:%cs %h$"; git (and GitHub's Download ZIP, which uses git archive) fills it in,
so an install made from a ZIP knows its date. In a git checkout the placeholder is still there, so the date
is read from git instead. Shown on the home page next to the version number, to compare with GitHub.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_FILE = Path(__file__).with_name("BUILD.txt")
_cache: dict[str, str | None] | None = None


def build_info() -> dict[str, str | None]:
    global _cache
    if _cache is None:
        _cache = _read()
    return _cache


def _read() -> dict[str, str | None]:
    try:
        text = _FILE.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) ([0-9a-f]{7,40})", text)
    if m:
        return {"date": m.group(1), "commit": m.group(2)}
    try:   # a git checkout (development)
        out = subprocess.run(["git", "log", "-1", "--format=%cs %h"], cwd=_FILE.parent, capture_output=True,
                             text=True, timeout=5).stdout.strip()
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) ([0-9a-f]{7,40})", out)
        if m:
            return {"date": m.group(1), "commit": m.group(2)}
    except (OSError, subprocess.SubprocessError):
        pass
    return {"date": None, "commit": None}
