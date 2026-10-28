"""Environment for every child process SIGN2MV starts.

Tools such as pip, uv, Hugging Face, torch.hub and Whisper cache large files
in the user profile on C: by default. These variables redirect all of them
into the application folder. They are applied only to processes started by
SIGN2MV; the Windows-wide environment is never changed, so the old systems
on this computer are not affected.
"""
from __future__ import annotations

import os
from typing import Mapping

from .paths import Paths


def cache_vars(paths: Paths) -> dict[str, str]:
    cache = paths.cache
    return {
        "SIGN2MV_ROOT": str(paths.root),
        "PIP_CACHE_DIR": str(cache / "pip"),
        "UV_CACHE_DIR": str(cache / "uv"),
        "UV_PYTHON_INSTALL_DIR": str(paths.runtime / "python"),
        "UV_PYTHON_BIN_DIR": str(paths.runtime / "python" / "bin"),
        "UV_TOOL_DIR": str(paths.runtime / "uv-tools"),
        "HF_HOME": str(cache / "huggingface"),
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TORCH_HOME": str(paths.models / "torch"),
        "XDG_CACHE_HOME": str(cache),
        "MPLCONFIGDIR": str(cache / "matplotlib"),
        "NUMBA_CACHE_DIR": str(cache / "numba"),
        "AUDIO_SEPARATOR_MODEL_DIR": str(paths.models / "separation"),
        # Applio would otherwise read/write %APPDATA%\Applio (shared with the
        # old Applio desktop app on this computer). Keep ours separate.
        "APPLIO_ROOT": str(paths.applio),
        "APPLIO_CONFIG_DIR": str(paths.runtime / "applio-config"),
        "APPLIO_LOGS_DIR": str(paths.runtime / "applio-logs"),   # training scratch (cleaned after training)
        "TEMP": str(paths.tmp),
        "TMP": str(paths.tmp),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def child_env(paths: Paths, extra: Mapping[str, str] | None = None,
              base: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env.update(cache_vars(paths))
    tool_dirs = [str(paths.ffmpeg_bin), str(paths.deno_dir), str(paths.runtime / "uv")]
    env["PATH"] = os.pathsep.join(tool_dirs + [env.get("PATH", "")])
    if extra:
        env.update(extra)
    return env


def ensure_dirs(paths: Paths) -> None:
    for key in ("HF_HOME", "TORCH_HOME", "PIP_CACHE_DIR", "UV_CACHE_DIR", "MPLCONFIGDIR", "TEMP",
                "APPLIO_CONFIG_DIR", "APPLIO_LOGS_DIR", "AUDIO_SEPARATOR_MODEL_DIR"):
        os.makedirs(cache_vars(paths)[key], exist_ok=True)
