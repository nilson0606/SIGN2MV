"""Re-import ("replace the source"): the old source is only deleted once the new one is in place."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "workers"))
import import_media  # noqa: E402

from app.library import Library  # noqa: E402


def _dirs(song: Path) -> tuple[Path, Path]:
    (song / "source").mkdir(parents=True)
    (song / "source" / "audio.wav").write_text("old")
    work = song / "source.importing"
    work.mkdir()
    (work / "audio.wav").write_text("new")
    return song / "source", work


def test_commit_replaces(tmp_path):
    target, work = _dirs(tmp_path / "s1")
    import_media.commit_source(tmp_path / "s1", work)
    assert (target / "audio.wav").read_text() == "new"
    assert not (tmp_path / "s1" / "source.old").exists() and not work.exists()


def test_failed_commit_keeps_the_old_source(tmp_path, monkeypatch):
    song = tmp_path / "s1"
    target, work = _dirs(song)
    real = os.replace

    def flaky(src, dst):
        if Path(src) == work:
            raise PermissionError("locked")
        return real(src, dst)
    monkeypatch.setattr(import_media.os, "replace", flaky)
    with pytest.raises(PermissionError):
        import_media.commit_source(song, work)
    assert (target / "audio.wav").read_text() == "old" and not (song / "source.old").exists()


def test_interrupted_commit_is_recovered(tmp_path):
    lib = Library(tmp_path / "lib")
    a = lib.songs_dir / "a"           # stopped between the two moves: only source.old
    (a / "source.old").mkdir(parents=True)
    (a / "source.old" / "audio.wav").write_text("old")
    b = lib.songs_dir / "b"           # stopped after the new one arrived: source.old is left over
    (b / "source").mkdir(parents=True)
    (b / "source.old").mkdir()
    assert lib.recover_interrupted_imports() == 1
    assert (a / "source" / "audio.wav").read_text() == "old" and not (b / "source.old").exists()
    c = tmp_path / "c"
    (c / "source.old").mkdir(parents=True)
    import_media.recover_source(c)
    assert (c / "source").is_dir() and not (c / "source.old").exists()
