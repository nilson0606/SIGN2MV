"""Sing & record: key versions that keep the singer's timbre (Rubber Band formant=preserved)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from app import stems
from app.api_sing import CACHE_RE, cache_key, parse_cache_key

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "workers"))
import key_shift  # noqa: E402

VID = "local_" + "a" * 64


def test_cache_key_keeps_the_option_apart():
    plain = cache_key(VID, 0, "lead", "demucs", "yin", "single", 4)
    kept = cache_key(VID, 0, "lead", "demucs", "yin", "single", 4, True)
    assert plain != kept and kept == plain + "_t" and CACHE_RE.match(kept)
    assert parse_cache_key(kept)["keyFormant"] is True and parse_cache_key(kept)["pitchShift"] == 4
    assert parse_cache_key(plain)["keyFormant"] is False
    assert cache_key(VID, 0, "all", "demucs", "yin", "single", 0, True) == cache_key(VID, 0, "all", "demucs", "yin", "single")


def test_key_copies_are_separate_folders():
    a, _ = stems.key_track("stems/x/vocals.wav", -3)
    b, _ = stems.key_track("stems/x/vocals.wav", -3, True)
    assert a.endswith("_m3") and b == a + "t"
    item = stems.key_item(Path("/s"), "stems/x/vocals.wav", -3, True)
    assert item["formant"] is True and item["info"]["formant"] is True and item["info"]["engine"] == "r3"


def test_worker_asks_rubber_band_to_keep_the_formants(tmp_path, monkeypatch):
    src = tmp_path / "vocals.wav"
    sf.write(src, np.zeros((4410, 2), np.float32), 44100)
    seen = []
    monkeypatch.setattr(key_shift, "run", lambda cmd, timeout=None: seen.append(cmd[cmd.index("-af") + 1]))
    for formant in (False, True):
        out = tmp_path / f"out{formant}"
        key_shift.shift_items([{"src": str(src), "dst": str(out / "vocals.wav"), "out_dir": str(out), "formant": formant,
                                "info": {}}], 2)
        assert (out / "info.json").is_file()
    assert "formant=preserved" not in seen[0] and "formant=preserved" in seen[1]
    assert "smoothing=536870912" in seen[1] and "smoothing" not in seen[0]   # R3 engine only with the option
