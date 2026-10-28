from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def err(code: str, status: int = 400, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": code, **extra}, status_code=status)


async def body_json(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
