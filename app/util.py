from __future__ import annotations

from typing import Any

import re
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response

IN_MEMORY_MAX = 96 * 1024 * 1024
AUDIO_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".flac": "audio/flac",
               ".ogg": "audio/ogg", ".aac": "audio/aac"}


def err(code: str, status: int = 400, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": code, **extra}, status_code=status)


async def body_json(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def media_response(path: Path, request: Request, media_type: str | None = None,
                   headers: dict[str, str] | None = None):
    """Serve a media file. Audio files (up to 96 MB) are read for each request and the file is
    closed before the response is sent: a browser keeping an <audio> stream open then never
    holds the file, so a remix or a new render can replace it on Windows."""
    suffix = path.suffix.lower()
    size = path.stat().st_size
    base = {"Accept-Ranges": "bytes", **(headers or {})}
    if suffix not in AUDIO_TYPES or size > IN_MEMORY_MAX:
        return FileResponse(path, media_type=media_type, headers=base)
    mt = media_type or AUDIO_TYPES[suffix]
    rng = request.headers.get("range") or ""
    m = re.match(r"^bytes=(\d*)-(\d*)$", rng.strip())
    if m and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
        else:
            start = max(0, size - int(m.group(2)))
            end = size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            return Response(status_code=416, headers={**base, "Content-Range": f"bytes */{size}"})
        with open(path, "rb") as fh:
            fh.seek(start)
            data = fh.read(end - start + 1)
        return Response(data, status_code=206, media_type=mt,
                        headers={**base, "Content-Range": f"bytes {start}-{end}/{size}"})
    with open(path, "rb") as fh:
        data = fh.read()
    return Response(data, media_type=mt, headers=base)
