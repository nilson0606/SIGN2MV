"""Windows sound settings that change what the sing page's headphone switches can do.

Windows "Mono audio" (Settings > Accessibility > Audio) mixes left and right for every program after the
program's own output, so the sing page's per-ear switches and its headphone mono have no effect while it
is on. It is read, never changed: HKCU\\Software\\Microsoft\\Multimedia\\Audio, AccessibilityMonoMixState
(DWORD, 1 = on). None when it cannot be read (not Windows, value absent = off).
"""
from __future__ import annotations

import os
import sys


def mono_audio() -> bool | None:
    fake = os.environ.get("SIGN2MV_FAKE_WINDOWS_MONO")   # tests and the demo install
    if fake in ("0", "1"):
        return fake == "1"
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Multimedia\Audio") as key:
            value, _ = winreg.QueryValueEx(key, "AccessibilityMonoMixState")
        return bool(value)
    except FileNotFoundError:
        return False   # never switched on: the value does not exist
    except OSError:
        return None
