"""User settings stored in config/settings.json (never committed to git)."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .paths import Paths
from .winlang import default_language

SCHEMA_VERSION = 1
LANGUAGES = ("zh-TW", "en")

_lock = threading.Lock()


def _defaults(paths: Paths) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        # None = not chosen yet; the page then follows the Windows UI language.
        "language": None,
        "library_dir": str(paths.default_library),
        "cover_singer_name": "",
        "studio_name": "",
    }


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def load(paths: Paths) -> dict[str, Any]:
    data = _defaults(paths)
    try:
        with open(paths.settings_file, encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in data})
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        # A damaged settings file must not stop the app from starting.
        pass
    data["schema_version"] = SCHEMA_VERSION
    return data


class SettingsError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def check_library_dir(paths: Paths, value: Any) -> str:
    """Same rules as sign_record's library location: a full local path, not a drive root, not one
    of SIGN2MV's own folders, created if missing and writable."""
    import uuid
    if not isinstance(value, str) or not value.strip():
        raise SettingsError("invalid_library_dir")
    requested = Path(value.strip()).expanduser()
    if not requested.is_absolute():
        raise SettingsError("library_dir_not_absolute")
    requested = Path(os.path.abspath(requested))
    if requested == Path(requested.anchor):
        raise SettingsError("library_dir_root")
    for reserved in (paths.runtime, paths.root / "models", paths.root / "app", paths.root / "workers",
                     paths.root / "web", paths.root / "installer"):
        inside = requested == reserved or reserved in requested.parents
        if inside:
            raise SettingsError("library_dir_reserved")
    try:
        requested.mkdir(parents=True, exist_ok=True)
        probe = requested / f".sign2mv-write-test-{uuid.uuid4().hex}"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        raise SettingsError("library_dir_not_writable")
    return str(requested.resolve())


def update(paths: Paths, changes: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        data = load(paths)
        for key, value in changes.items():
            if key == "language":
                if value is not None and value not in LANGUAGES:
                    raise SettingsError("invalid_language")
            elif key == "library_dir":
                value = check_library_dir(paths, value)
            elif key in ("cover_singer_name", "studio_name"):
                if not isinstance(value, str) or len(value) > 80:
                    raise SettingsError("invalid_name")
                value = value.strip()
            else:
                raise SettingsError("unknown_setting")
            data[key] = value
        atomic_write_json(paths.settings_file, data)
        return data


def effective_language(settings: dict[str, Any]) -> str:
    return settings.get("language") or default_language()
