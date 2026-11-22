"""Finished audio of a song ("renders"): sing & record takes and AI cover results.

The MV workspace offers a song's original mix plus every render as the MV
audio. Layout: songs/<id>/renders/<render id>/{audio.<ext>, render.json}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .context import Context
from .sing_archive import ID as RECORDING_ID
from .sing_archive import ArchiveError, RecordingArchive
from .sing_archive import ext as recording_ext

RENDER_ID = re.compile(r"^r[a-f0-9]{12}$")
KINDS = ("sing", "cover")


def _sniff(path: Path) -> str | None:
    with open(path, "rb") as fh:
        head = fh.read(16)
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == bytes([0x1A, 0x45, 0xDF, 0xA3]):
        return "webm"
    if head[4:8] == b"ftyp":
        return "m4a"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "mp3"
    if head[:4] == b"fLaC":
        return "flac"
    return None


def renders_dir(ctx: Context, song_id: str) -> Path:
    return ctx.library().song_dir(song_id) / "renders"


def save_render_file(ctx: Context, song_id: str, source: Path, *, title: str, kind: str,
                     extra: dict[str, Any] | None = None, move: bool = False) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("invalid_kind")
    fmt = _sniff(source)
    if not fmt:
        raise ValueError("unsupported_audio")
    base = renders_dir(ctx, song_id)
    base.mkdir(parents=True, exist_ok=True)
    rid = "r" + uuid.uuid4().hex[:12]
    tmp = base / (rid + ".tmp")
    tmp.mkdir()
    try:
        target = tmp / f"audio.{fmt}"
        if move:
            shutil.move(str(source), target)
        else:
            shutil.copyfile(source, target)
        info = {"schema_version": 1, "id": rid, "kind": kind, "title": (title or "")[:200], "audio": f"audio.{fmt}",
                "bytes": target.stat().st_size, "created_at": time.time(), **(extra or {})}
        (tmp / "render.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, base / rid)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return {**info, "song_id": song_id, "path": f"renders/{rid}/audio.{fmt}"}


def save_render(ctx: Context, song_id: str, data: bytes, *, title: str, kind: str,
                extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx.paths.tmp.mkdir(parents=True, exist_ok=True)
    tmp = ctx.paths.tmp / ("render-" + uuid.uuid4().hex)
    tmp.write_bytes(data)
    try:
        return save_render_file(ctx, song_id, tmp, title=title, kind=kind, extra=extra, move=True)
    finally:
        tmp.unlink(missing_ok=True)


def list_renders(ctx: Context, song_id: str) -> list[dict[str, Any]]:
    base = renders_dir(ctx, song_id)
    out = []
    if base.is_dir():
        for d in base.iterdir():
            if not RENDER_ID.match(d.name):
                continue
            try:
                info = json.loads((d / "render.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (d / info.get("audio", "")).is_file():
                out.append({**info, "song_id": song_id, "path": f"renders/{d.name}/{info['audio']}"})
    out.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return out


def rename_render(ctx: Context, song_id: str, rid: str, title: str) -> dict[str, Any]:
    if not RENDER_ID.match(rid or ""):
        raise ValueError("invalid_render")
    f = renders_dir(ctx, song_id) / rid / "render.json"
    info = json.loads(f.read_text(encoding="utf-8"))
    info["title"] = str(title or "").strip()[:200] or info["title"]
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, f)
    return info


def delete_render(ctx: Context, song_id: str, rid: str) -> None:
    if not RENDER_ID.match(rid or ""):
        raise ValueError("invalid_render")
    shutil.rmtree(renders_dir(ctx, song_id) / rid, ignore_errors=True)


# ---------------------------------------------------------------- saved sing & record takes
# [2026-11-22] The sing page's saved results (the list of its 「錄音後處理」: whole takes, segment mixes and the
# versions saved from post-production) are offered as MV audio too. A take is found by the song's videoId, the same
# link the sing page uses. The archive's metadata is large (about 15 MB for 240 takes, mostly pitch analyses), so a
# file is read again only when it changed.
_TAKES: dict[str, tuple[tuple[int, int], dict[str, Any] | None]] = {}
_TAKE_LOCK = threading.Lock()   # one find-or-copy at a time: two quick picks of the same take make one copy


def recordings_root(ctx: Context) -> Path:
    return Path(ctx.settings()["library_dir"]) / "recordings"


def _take(arc: RecordingArchive, rec_id: str) -> dict[str, Any] | None:
    """A take of the post-production list that can make an MV: complete, not one segment of a segmented
    take, not waiting in 「待確認」 (the same rule as the sing page's list and its 「完整 MV」 button)."""
    try:
        m = arc.get(rec_id)
    except ArchiveError:
        return None
    if not m.get("complete") or m.get("segmentTake") or m.get("postPending") or not isinstance(m.get("videoId"), str):
        return None
    return {"id": rec_id, "video_id": m["videoId"], "title": m["title"], "created": float(m["created"]),
            "mode": m.get("mode") or "", "bytes": m["bytes"], "path": str(arc.dir(rec_id) / f"mix.{recording_ext(m['mime'])}")}


_DELETED: dict[str, tuple[tuple[int, int], set[str]]] = {}


def _deleted(arc: RecordingArchive) -> set[str]:
    f = arc.root / ".deleted.json"
    try:
        st = f.stat()
    except OSError:
        return set()
    stamp = (st.st_mtime_ns, st.st_size)
    cached = _DELETED.get(str(f))
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        ids = set(arc.deleted())
    except ArchiveError:
        ids = set()
    _DELETED[str(f)] = (stamp, ids)
    return ids


def saved_takes(ctx: Context) -> list[dict[str, Any]]:
    """Every take of the post-production list, newest first. A take read before costs one stat (its folder is
    removed as a whole when it is deleted, and its metadata changes when anything about it does)."""
    root = recordings_root(ctx)
    if not root.is_dir():
        return []
    arc = RecordingArchive(root)
    deleted, out, seen = _deleted(arc), [], set()
    for d in root.iterdir():
        if not RECORDING_ID.match(d.name) or d.name in deleted:
            continue
        meta = d / "metadata.json"
        try:
            st = meta.stat()
        except OSError:
            continue
        key, stamp = str(meta), (st.st_mtime_ns, st.st_size)
        seen.add(key)
        cached = _TAKES.get(key)
        if cached and cached[0] == stamp:
            row = cached[1]
        else:
            row = None if d.is_symlink() else _take(arc, d.name)   # _take checks the folder and its files
            _TAKES[key] = (stamp, row)
        if row:
            out.append(row)
    prefix = str(root) + os.sep
    for key in [k for k in _TAKES if k.startswith(prefix) and k not in seen]:
        _TAKES.pop(key, None)
    out.sort(key=lambda r: r["created"], reverse=True)
    return out


def take_for_path(ctx: Context, path: str) -> dict[str, Any] | None:
    """The saved take whose finished mix is this file, or None (any other file, a deleted take, a segment)."""
    try:
        root = recordings_root(ctx).resolve()
        target = Path(path).resolve()
        rel = target.relative_to(root)
    except (OSError, ValueError):
        return None
    if len(rel.parts) != 2 or not RECORDING_ID.match(rel.parts[0]) or not rel.parts[1].startswith("mix."):
        return None
    arc = RecordingArchive(root)
    if rel.parts[0] in _deleted(arc):
        return None
    row = _take(arc, rel.parts[0])
    return row if row and Path(row["path"]).resolve() == target else None


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_for_take(ctx: Context, song_id: str, take: dict[str, Any]) -> dict[str, Any]:
    """The song's render of a saved take: the one made before (by the sing page's 「完整 MV」 or an earlier pick)
    or a new copy, the same as the sing page does. A copy keeps the MV's sound when the take is deleted later."""
    src = Path(take["path"])
    with _TAKE_LOCK:
        digest = _sha1(src)
        song_dir = ctx.library().song_dir(song_id)
        for rd in list_renders(ctx, song_id):
            if rd.get("kind") != "sing" or rd.get("recording_id") != take["id"]:
                continue
            old = rd.get("sha1")
            if not old:
                try:
                    old = _sha1(song_dir / rd["path"])
                except OSError:
                    continue
            if old == digest:
                return {**rd, "reused": True}
        return save_render_file(ctx, song_id, src, title=take["title"], kind="sing",
                                extra={"recording_id": take["id"], "sha1": digest})
