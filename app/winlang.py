"""Pick the first-run interface language from the Windows display language."""
from __future__ import annotations

import os

# Primary language "Chinese" with Traditional script regions: Taiwan, Hong Kong, Macao.
_TRADITIONAL_CHINESE_LANGIDS = {0x0404, 0x0C04, 0x1404, 0x7C04}


def windows_ui_langid() -> int | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        return int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
    except Exception:
        return None


def default_language() -> str:
    override = os.environ.get("SIGN2MV_LANG")
    if override in ("zh-TW", "en"):
        return override
    langid = windows_ui_langid()
    if langid in _TRADITIONAL_CHINESE_LANGIDS:
        return "zh-TW"
    return "en"
