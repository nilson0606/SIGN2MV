"""All filesystem locations used by SIGN2MV.

Everything lives under the application root (the folder that contains
install.bat). Nothing is written to the user profile on the system drive,
so the app can sit on D: (or wherever it was unzipped) without filling C:.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_root() -> Path:
    override = os.environ.get("SIGN2MV_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def runtime(self) -> Path:
        return self.root / "runtime"

    @property
    def envs(self) -> Path:
        return self.runtime / "envs"

    def env_python(self, name: str) -> Path:
        """Python executable of one of the virtual environments."""
        if os.name == "nt":
            return self.envs / name / "Scripts" / "python.exe"
        return self.envs / name / "bin" / "python"

    @property
    def cache(self) -> Path:
        return self.runtime / "cache"

    @property
    def tmp(self) -> Path:
        return self.runtime / "tmp"

    @property
    def ffmpeg_bin(self) -> Path:
        return self.runtime / "ffmpeg" / "bin"

    @property
    def deno_dir(self) -> Path:
        return self.runtime / "deno"

    @property
    def applio(self) -> Path:
        return self.runtime / "applio"

    @property
    def browser_profile(self) -> Path:
        return self.runtime / "browser"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def voices(self) -> Path:
        """RVC voice models: voices/<Name>/<file>.pth (+ .index, epochs/)."""
        return self.models / "voices"

    @property
    def soundfonts(self) -> Path:
        return self.models / "soundfonts"

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def settings_file(self) -> Path:
        return self.config / "settings.json"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def web(self) -> Path:
        return self.root / "web"

    @property
    def workers(self) -> Path:
        return self.root / "workers"

    @property
    def install_report(self) -> Path:
        return self.runtime / "install_report.json"

    @property
    def default_library(self) -> Path:
        return self.root / "library"


def get_paths() -> Paths:
    return Paths(_default_root())
