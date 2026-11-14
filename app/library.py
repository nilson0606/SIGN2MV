"""Song library.

Layout (see the development plan):
  <library>/songs/<song_id>/song.json
Song folders use short ASCII ids; titles (often Chinese) live only inside
song.json, so no tool ever has to deal with non-ASCII paths.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from .settings import atomic_write_json

SCHEMA_VERSION = 1
SONG_ID_RE = re.compile(r"^s[0-9a-z]{10}$")
_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
MAX_TITLE = 200


class LibraryError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def _new_id() -> str:
    return "s" + "".join(secrets.choice(_ALPHABET) for _ in range(10))


def _clean_title(title: Any) -> str:
    if not isinstance(title, str):
        raise LibraryError("invalid_title")
    title = " ".join(title.split())
    if not title or len(title) > MAX_TITLE:
        raise LibraryError("invalid_title")
    return title


def lost_lyric_picture(song_dir: Path, src: dict[str, Any]) -> bool:
    """The song uses a lyric picture (api_lyricvideo) that is gone from the disk: make the record say
    what is true, the imported picture (or none). Returns whether the record was changed."""
    if not src.get("lyric_video") or (song_dir / str(src.get("video") or "")).is_file():
        return False
    orig = src.pop("video_original", None) or {}
    src.pop("lyric_video", None)
    src["video"] = orig.get("video")
    if orig.get("video_size"):
        src["video_size"] = orig["video_size"]
    else:
        src.pop("video_size", None)
    return True


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._lock = threading.Lock()

    @property
    def songs_dir(self) -> Path:
        return self.root / "songs"

    def _song_dir(self, song_id: str) -> Path:
        if not SONG_ID_RE.match(song_id or ""):
            raise LibraryError("invalid_song_id")
        return self.songs_dir / song_id

    def _read(self, song_id: str) -> dict[str, Any]:
        path = self._song_dir(song_id) / "song.json"
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            raise LibraryError("song_not_found", 404)
        except (OSError, ValueError):
            raise LibraryError("song_unreadable", 500)
        # The import worker writes source/source.json; merge it in.
        try:
            with open(self._song_dir(song_id) / "source" / "source.json", encoding="utf-8") as fh:
                data["source"] = json.load(fh)
        except (OSError, ValueError):
            data["source"] = None
        src = data.get("source") or {}
        lost_lyric_picture(self._song_dir(song_id), src)
        if data.get("title_auto") and src.get("youtube_title"):
            data["title"] = src["youtube_title"]
        return data

    def song_dir(self, song_id: str) -> Path:
        return self._song_dir(song_id)

    def recover_interrupted_imports(self) -> int:
        """At start-up (no import can be running): a re-import that stopped between moving the old source
        aside and putting the new one in place left source.old without source; put it back. Same rule as
        workers/import_media.recover_source. Returns how many songs were put back."""
        n = 0
        if not self.songs_dir.is_dir():
            return 0
        for entry in self.songs_dir.iterdir():
            old, target = entry / "source.old", entry / "source"
            try:
                if not old.is_dir():
                    continue
                if target.exists():
                    shutil.rmtree(old, ignore_errors=True)
                else:
                    os.replace(old, target)
                    n += 1
            except OSError:
                continue
        return n

    def list(self) -> list[dict[str, Any]]:
        if not self.songs_dir.is_dir():
            return []
        songs = []
        for entry in self.songs_dir.iterdir():
            if entry.is_dir() and SONG_ID_RE.match(entry.name):
                try:
                    songs.append(self._read(entry.name))
                except LibraryError:
                    continue
        songs.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        return songs

    def get(self, song_id: str) -> dict[str, Any]:
        return self._read(song_id)

    def create(self, title: Any, auto_title: str | None = None) -> dict[str, Any]:
        title_auto = False
        if (title is None or (isinstance(title, str) and not title.strip())) and auto_title:
            title, title_auto = auto_title, True
        title = _clean_title(title)
        with self._lock:
            self.songs_dir.mkdir(parents=True, exist_ok=True)
            for _ in range(20):
                song_id = _new_id()
                folder = self.songs_dir / song_id
                try:
                    folder.mkdir()
                    break
                except FileExistsError:
                    continue
            else:
                raise LibraryError("id_allocation_failed", 500)
            now = time.time()
            song = {
                "schema_version": SCHEMA_VERSION,
                "song_id": song_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "title_auto": title_auto,
            }
            atomic_write_json(folder / "song.json", song)
            return self._read(song_id)

    def rename(self, song_id: str, title: Any) -> dict[str, Any]:
        title = _clean_title(title)
        with self._lock:
            path = self._song_dir(song_id) / "song.json"
            song = self._read(song_id)
            song.pop("source", None)
            song["title"] = title
            song["title_auto"] = False
            song["updated_at"] = time.time()
            atomic_write_json(path, song)
            return self._read(song_id)

    def delete(self, song_id: str) -> None:
        """Delete a song folder. Only ever called after the user confirmed it."""
        with self._lock:
            folder = self._song_dir(song_id)
            if not (folder / "song.json").is_file():
                raise LibraryError("song_not_found", 404)
            # Safety: the folder must really be inside <library>/songs.
            if folder.resolve().parent != self.songs_dir.resolve():
                raise LibraryError("invalid_song_id")
            trash = folder.with_name(folder.name + ".deleting")
            os.replace(folder, trash)
            shutil.rmtree(trash, ignore_errors=True)
