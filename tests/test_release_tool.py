"""tools/release.py: release names by date and moving the changelog's Unreleased entries."""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("release", Path(__file__).resolve().parent.parent / "tools" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


def test_names_by_date():
    day = dt.date(2026, 11, 12)
    assert release.release_name(set(), day) == "2026.11.12"
    assert release.release_name({"2026.11.12"}, day) == "2026.11.12.2"
    assert release.release_name({"2026.11.12", "2026.11.12.2"}, day) == "2026.11.12.3"


def test_unreleased_moves_under_the_release():
    text = "# Changelog\n\n## Unreleased\n\n- New thing.\n\n## 0.1.0 — first\n\n- Old.\n"
    new, notes = release.move_unreleased(text, "2026.11.12")
    assert notes == "- New thing."
    assert new == "# Changelog\n\n## Unreleased\n\n## 2026.11.12\n\n- New thing.\n\n## 0.1.0 — first\n\n- Old.\n"
    with pytest.raises(SystemExit):
        release.move_unreleased(new, "2026.11.12.2")   # nothing new
