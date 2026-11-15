"""Whisper again on just the stretches it missed ("空檔重聽"), for the library's lyric timing and the MV page.

When lines are anchored (locked) by the user and some lines between two placed lines were not heard at
all, workers/mv_whisper.py (input "windows") listens to only that stretch of the separated voice once
more, with those lines of the lyrics as its prompt and without its own silence filter.

What it hears is kept apart from the song's Whisper result, in <whisper json>.relisten.json, and only
alignment with anchors uses it (merged()): without anchors everything is timed exactly as before, from
the Whisper result as it was. The worker writes to <whisper json>.relisten.new.json; collect() moves that
into the store. A new Whisper result (listening to the whole song again) drops both (forget()).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MIN_S = 2.0           # shorter stretches are not worth a second listen
MAX_S = 120.0         # nor are longer ones (an anchor is missing)
PROMPT_CHARS = 220


def store_file(w_json: Any) -> Path:
    return Path(str(w_json) + ".relisten.json")


def new_file(w_json: Any) -> Path:
    """Where workers/mv_whisper.py (input "windows") leaves what it heard."""
    return Path(str(w_json) + ".relisten.new.json")


def _read(path: Path) -> list[dict]:
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    wins = got.get("windows") if isinstance(got, dict) else None
    return [w for w in wins if isinstance(w, dict)] if isinstance(wins, list) else []


def collect(w_json: Any) -> int:
    """Move what the worker heard into the store. Returns how many stretches were added."""
    new = new_file(w_json)
    if not new.is_file():
        return 0
    added = _read(new)
    if added:
        store = store_file(w_json)
        tmp = Path(str(store) + ".tmp")
        tmp.write_text(json.dumps({"windows": _read(store) + added}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, store)
    try:
        new.unlink()
    except OSError:
        pass
    return len(added)


def forget(w_json: Any) -> None:
    for p in (store_file(w_json), new_file(w_json)):
        try:
            p.unlink()
        except OSError:
            pass


def done(w_json: Any) -> list[dict]:
    """The stretches listened to again so far: {start, end, segments}."""
    return _read(store_file(w_json))


def merged(data: Any, w_json: Any) -> list[dict]:
    """The Whisper segments with every stretch listened to again put in (for alignment with anchors only)."""
    segs = data.get("segments", []) if isinstance(data, dict) else (data or [])
    out = {"segments": list(segs)}
    for w in done(w_json):
        out = merge(out, w, w.get("segments") or [])
    return out["segments"]


def windows(gaps: list[dict], w_json: Any) -> list[dict]:
    """The stretches to listen to again: {start, end, prompt}. A stretch that overlaps one listened to
    before by more than half is left out (listening again would hear the same)."""
    before = done(w_json)
    out = []
    for g in gaps:
        st, et = float(g["start"]), float(g["end"])
        if not (MIN_S <= et - st <= MAX_S) or not g.get("lines"):
            continue
        if any(min(et, float(b["end"])) - max(st, float(b["start"])) > 0.5 * (et - st) for b in before):
            continue
        prompt = "，".join(str(x) for x in g["lines"])[:PROMPT_CHARS]
        out.append({"start": round(max(0.0, st - 0.3), 2), "end": round(et + 0.3, 2), "prompt": prompt})
    return out[:12]


def merge(data: dict, window: dict, segments: list[dict]) -> dict:
    """{"segments"} with what was heard in one stretch replaced by what was heard in it again, word by word:
    the old words inside the stretch go (a segment keeps its words outside it), the new ones are clipped to
    it. A segment without word times goes when its middle lies in the stretch."""
    st, et = float(window["start"]), float(window["end"])

    def inside(w: dict) -> bool:
        return st - 0.05 <= float(w["start"]) and float(w["end"]) <= et + 0.05

    keep = []
    for s in data.get("segments", []):
        words = s.get("words") or []
        if not words:
            if not (st <= (float(s["start"]) + float(s["end"])) / 2 <= et):
                keep.append(s)
            continue
        rest = [w for w in words if not inside(w)]
        if len(rest) == len(words) and not (float(words[0]["start"]) < st and float(words[-1]["end"]) > et):
            keep.append(s)
            continue
        # a segment reaching over the stretch is cut in two around it, so the words stay in order
        for part in ([w for w in rest if float(w["start"]) < st], [w for w in rest if float(w["start"]) >= st]):
            if part:
                keep.append({**s, "words": part, "start": part[0]["start"], "end": part[-1]["end"],
                             "text": "".join(str(w.get("word", "")) for w in part).strip()})
    new = []
    for s in segments:
        words = [w for w in s.get("words") or [] if inside(w)]
        if words:
            new.append({**s, "words": words, "start": words[0]["start"], "end": words[-1]["end"]})
    return {**data, "segments": sorted(keep + new, key=lambda s: float(s["start"]))}


def payload(wins: list[dict], voice: Any, w_json: Any) -> dict:
    return {"windows": wins, "voice": str(voice), "out": str(new_file(w_json))}
