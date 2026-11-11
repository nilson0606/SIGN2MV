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


# ---- "check for updates" on the home page: ask GitHub how far the latest published release is ahead of this
# copy. Only reads public information; nothing is downloaded or changed (updating stays the manual copy-over).
# Releases are named by date (2026.11.12, 2026.11.12.2, ...) and carry SIGN2MV.zip (tools/release.py); before the
# first release the comparison is with main.
REPO = "nilson0606/SIGN2MV"
REPO_URL = f"https://github.com/{REPO}"
DOWNLOAD_URL = f"{REPO_URL}/releases/latest/download/SIGN2MV.zip"


def _github(path: str) -> dict:
    import json
    import urllib.request
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "SIGN2MV"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_update(fetch=_github) -> dict:
    """{"state": "latest" | "update" | "ahead" | "unknown" | "offline", "behind": n, "latest": {commit, date, tag}}.
    "update": the latest release has n more changes than this copy; "ahead": this copy has changes the release
    does not (development, or installed before the release was published); "unknown": this copy's commit is not
    known (no code date) or not on GitHub."""
    current = build_info().get("commit")
    try:
        try:
            release = fetch("releases/latest")
            ref = str(release["tag_name"])
        except Exception:  # noqa: BLE001 - no release yet: compare with main
            release, ref = None, "main"
        head = fetch(f"commits/{ref}")
    except Exception:  # noqa: BLE001 - no network, GitHub down, rate limit
        return {"state": "offline", "repo": REPO_URL}
    latest = {"commit": str(head.get("sha", ""))[:7], "tag": release["tag_name"] if release else None,
              "date": str(((head.get("commit") or {}).get("committer") or {}).get("date", ""))[:10]}
    out = {"repo": REPO_URL, "latest": latest, "current": build_info(),
           "download": DOWNLOAD_URL if release else None}
    if not current:
        return {**out, "state": "unknown"}
    if str(head.get("sha", "")).startswith(current):
        return {**out, "state": "latest", "behind": 0}
    try:
        cmp = fetch(f"compare/{current}...{ref}")
    except Exception:  # noqa: BLE001 - e.g. a commit GitHub does not have
        return {**out, "state": "unknown"}
    status = cmp.get("status")
    if status == "identical":
        return {**out, "state": "latest", "behind": 0}
    if status == "behind":   # the release is behind this copy
        return {**out, "state": "ahead", "behind": 0}
    return {**out, "state": "update", "behind": int(cmp.get("ahead_by") or 0)}   # ahead, or diverged
