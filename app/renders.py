"""Finished audio of a song ("renders"): sing & record takes and AI cover results.

The MV workspace offers a song's original mix plus every render as the MV
audio. Layout: songs/<id>/renders/<render id>/{audio.<ext>, render.json}
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from .context import Context

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
