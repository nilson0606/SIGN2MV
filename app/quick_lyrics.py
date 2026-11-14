"""Lyric subtitles for the quick MV studio look (AI_COVER_MV 12_generate_dynamic_mv.py).

Lines come from LRC timestamps when the lyrics have them; otherwise the plain lines are
matched to the words Whisper recognized in the song (app/lyric_align.py; the old segment
packing put lines where they were not sung); without Whisper they are spread evenly (old fallback). The timing is then tuned per line on
the page (old 字幕時間軸微調) and saved per song and audio.
"""
from __future__ import annotations

import re
from typing import Any

from . import lyric_align

LRC = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")
MAX_LINES = 400


def lrc_lines(raw: str, total: float) -> list[dict] | None:
    """[mm:ss.xx] lines -> [{start, end, text}] (old: next line's start, at most 8 s; last one 6 s)."""
    temp = []
    for line in raw.split("\n"):
        m = LRC.match(line.strip())
        if m and m.group(3).strip():
            temp.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip()))
    if len(temp) < 2:
        return None
    temp.sort(key=lambda x: x[0])
    out = []
    for i, (st, txt) in enumerate(temp):
        et = temp[i + 1][0] if i + 1 < len(temp) else min(st + 6.0, total)
        et = min(et, st + 8.0)
        out.append({"start": round(st, 2), "end": round(max(et, st + 0.3), 2), "text": txt})
    return out


def plain_lines(raw: str) -> list[str]:
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    return [ln for ln in lines if not (ln.startswith("[") and re.match(r"^\[\d+:\d+", ln))]


def _words(segments: list[Any]) -> list[dict]:
    """Whisper segments -> words with times (a segment without word times counts as one long word)."""
    words = []
    for s in segments:
        if isinstance(s, dict):
            raw_t, st, et, ws = s.get("text", ""), float(s.get("start", 0)), float(s.get("end", 0)), s.get("words") or []
        elif isinstance(s, (list, tuple)) and len(s) >= 3:
            st, et, raw_t, ws = float(s[0]), float(s[1]), str(s[2]), []
        else:
            continue
        good = []
        for w in ws:
            try:
                a, b = float(w.get("start", 0)), float(w.get("end", 0))
            except (AttributeError, TypeError, ValueError):
                continue
            if b - a >= 0.02 and str(w.get("word", "")).strip():
                good.append({"word": str(w["word"]), "start": a, "end": b})
        if good:
            words.extend(good)
        elif et > st and str(raw_t).strip():
            words.append({"word": " " + str(raw_t).strip(), "start": st, "end": et})
    words.sort(key=lambda w: w["start"])
    return words


def align_report(lines: list[str], segments: list[Any]) -> dict:
    """The user's lines at the times they are sung: {"lines", "placed", "unsung"}.

    Each line is matched to the recognized words one character / word at a time (app/lyric_align.py) and
    starts with its own first word. A line stays until shortly after its last word, or until the next line
    when that follows within a second; lines too little of which was heard share the time between their
    neighbours (at most 8 s each). "unsung": singing that none of the lines accounts for."""
    words = _words(segments)
    if not words or not lines:
        return {"lines": [], "placed": 0, "unsung": []}
    found = lyric_align.align_lines(lines, words)
    lo, hi = words[0]["start"], max(w["end"] for w in words)
    spans = lyric_align.fill_unplaced(found["spans"], lines, lo, hi, words)
    out = []
    for i, (st, et, ok) in enumerate(spans):
        nxt = spans[i + 1][0] if i + 1 < len(spans) else None
        end = et + 0.5 if ok else min(et, st + 8.0)
        if nxt is not None and (nxt - et < 1.0 or end > nxt):
            end = nxt
        out.append({"start": round(st, 2), "end": round(max(end, st + 0.3), 2), "text": lines[i]})
    return {"lines": out, "placed": sum(1 for x in found["spans"] if x), "unsung": found["unsung"]}


def align(lines: list[str], segments: list[Any]) -> list[dict]:
    return align_report(lines, segments)["lines"]


def spread(lines: list[str], total: float) -> list[dict]:
    """Old fallback: evenly from 12 s to 10 s before the end, at most 5 s a line."""
    if not lines:
        return []
    st0 = 12.0
    end = max(st0 + 30.0, total - 10.0)
    dur = min(5.0, (end - st0) / len(lines))
    return [{"start": round(st0 + i * dur, 2), "end": round(min(st0 + i * dur + dur * 0.9, total), 2), "text": ln}
            for i, ln in enumerate(lines)]


def clean_lines(value: Any, total: float | None = None) -> list[dict] | None:
    """Lines sent by the page: sorted, trimmed, start < end, one line of text each."""
    if not isinstance(value, list) or len(value) > MAX_LINES:
        return None
    out = []
    for x in value:
        if not isinstance(x, dict):
            return None
        try:
            st, et = float(x.get("start")), float(x.get("end"))
        except (TypeError, ValueError):
            return None
        text = re.sub(r"[\x00-\x1f\x7f]", " ", str(x.get("text") or "")).strip()[:120]
        if not text or st < 0 or et <= st or (total and st >= total):
            continue
        out.append({"start": round(st, 2), "end": round(min(et, total) if total else et, 2), "text": text})
    out.sort(key=lambda x: x["start"])
    return out

