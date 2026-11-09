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


# ---- "check for updates" on the home page: ask GitHub how far the published code is ahead of this one.
# Only reads public information; nothing is downloaded or changed (updating stays the manual copy-over).
REPO = "nilson0606/SIGN2MV"
REPO_URL = f"https://github.com/{REPO}"


def _github(path: str) -> dict:
    import json
    import urllib.request
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "SIGN2MV"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_update(fetch=_github) -> dict:
    """{"state": "latest" | "update" | "ahead" | "unknown" | "offline", "behind": n, "latest": {commit, date}}.
    "update": GitHub's main has n more changes than this copy; "ahead": this copy has changes GitHub does not
    (development); "unknown": this copy's commit is not known (no code date) or not on GitHub."""
    current = build_info().get("commit")
    try:
        head = fetch("commits/main")
    except Exception:  # noqa: BLE001 - no network, GitHub down, rate limit
        return {"state": "offline", "repo": REPO_URL}
    latest = {"commit": str(head.get("sha", ""))[:7],
              "date": str(((head.get("commit") or {}).get("committer") or {}).get("date", ""))[:10]}
    out = {"repo": REPO_URL, "latest": latest, "current": build_info()}
    if not current:
        return {**out, "state": "unknown"}
    if str(head.get("sha", "")).startswith(current):
        return {**out, "state": "latest", "behind": 0}
    try:
        cmp = fetch(f"compare/{current}...main")
    except Exception:  # noqa: BLE001 - e.g. a commit GitHub does not have
        return {**out, "state": "unknown"}
    status = cmp.get("status")
    if status == "identical":
        return {**out, "state": "latest", "behind": 0}
    if status == "ahead":   # main is ahead of this copy
        return {**out, "state": "update", "behind": int(cmp.get("ahead_by") or 0)}
    if status == "behind":
        return {**out, "state": "ahead", "behind": 0}
    return {**out, "state": "update", "behind": int(cmp.get("ahead_by") or 0)}   # diverged: newer code exists
