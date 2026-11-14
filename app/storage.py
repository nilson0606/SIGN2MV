"""Disk usage of the library, per song and per category.

Categories of a song folder (see docs/ARCHITECTURE for the layout):
  source   source/ + lyricvideo/   original video + audio, and the picture with lyrics made for it
  stems    stems/ + keys/          separation layers and key copies (cache, deletable one by one)
  cover    cover/versions + cover renders     finished covers
  cover_cache cover/rvc, midi, patches, tmp, preview   voice-conversion cache for quick remix
  sing     sing/ + sing renders + the song's takes in <library>/recordings
  mv       mv/ + quickmv/          MV projects (frames, previews, rendered videos) and quick MVs
  other    anything else
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .stems import dir_bytes

COVER_CACHE = ("rvc", "midi", "patches", "tmp", "preview")
CATEGORIES = ("source", "stems", "cover", "cover_cache", "sing", "mv", "other")


def _size(p: Path) -> int:
    try:
        if p.is_file():
            return p.stat().st_size
        if p.is_dir():
            return dir_bytes(p)
    except OSError:
        pass
    return 0


def recordings_index(library_root: Path) -> dict[str, list[Path]]:
    """videoId -> take folders in <library>/recordings (sing & record's shared format)."""
    root = Path(library_root) / "recordings"
    out: dict[str, list[Path]] = {}
    if not root.is_dir():
        return out
    for d in root.iterdir():
        meta = d / "metadata.json"
        if not meta.is_file():
            continue
        try:
            rec = json.loads(meta.read_text(encoding="utf-8")).get("recording") or {}
        except (OSError, ValueError):
            continue
        if rec.get("videoId"):
            out.setdefault(rec["videoId"], []).append(d)
    return out


def song_usage(song_dir: Path, recordings: list[Path] | None = None) -> dict[str, Any]:
    cats = {c: 0 for c in CATEGORIES}
    counts = {"cover_versions": 0, "sing_takes": len(recordings or []), "mv_projects": 0, "sing_prepared": 0,
              "quick_mvs": 0}
    if not song_dir.is_dir():
        return {"categories": cats, "counts": counts, "total": 0}
    for child in song_dir.iterdir():
        name = child.name
        if name in ("source", "lyricvideo"):   # lyricvideo: the song's picture with lyrics (api_lyricvideo)
            cats["source"] += _size(child)
        elif name in ("stems", "keys"):
            cats["stems"] += _size(child)
        elif name == "cover" and child.is_dir():
            for sub in child.iterdir():
                if sub.name in COVER_CACHE:
                    cats["cover_cache"] += _size(sub)
                else:
                    cats["cover"] += _size(sub)
                if sub.name == "versions" and sub.is_dir():
                    counts["cover_versions"] = sum(1 for v in sub.iterdir() if (v / "version.json").is_file())
        elif name == "sing":
            cats["sing"] += _size(child)
            if child.is_dir():
                counts["sing_prepared"] = sum(1 for v in child.iterdir() if (v / "reference.json").is_file())
        elif name == "mv":
            cats["mv"] += _size(child)
            if child.is_dir():
                counts["mv_projects"] = sum(1 for v in child.iterdir() if (v / "project.json").is_file())
        elif name == "quickmv":
            cats["mv"] += _size(child)
            if child.is_dir():
                counts["quick_mvs"] = sum(1 for v in child.iterdir() if (v / "video.mp4").is_file())
        elif name == "renders" and child.is_dir():
            for r in child.iterdir():
                kind = "other"
                try:
                    kind = json.loads((r / "render.json").read_text(encoding="utf-8")).get("kind") or "other"
                except (OSError, ValueError):
                    pass
                cats[kind if kind in ("cover", "sing", "mv") else "other"] += _size(r)
        else:
            cats["other"] += _size(child)
    for rec in recordings or []:
        cats["sing"] += _size(rec)
    return {"categories": cats, "counts": counts, "total": sum(cats.values())}


def disk(path: Path) -> dict[str, int]:
    try:
        u = shutil.disk_usage(path)
        return {"free": u.free, "total": u.total}
    except OSError:
        return {"free": 0, "total": 0}
