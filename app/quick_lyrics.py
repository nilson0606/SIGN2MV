"""Lyric subtitles for the quick MV studio look (AI_COVER_MV 12_generate_dynamic_mv.py).

Lines come from LRC timestamps when the lyrics have them; otherwise the plain lines are
matched to the song's Whisper segments (old align_lyrics_with_acoustic_segments, unchanged);
without Whisper they are spread evenly (old fallback). The timing is then tuned per line on
the page (old 字幕時間軸微調) and saved per song and audio.
"""
from __future__ import annotations

import re
from typing import Any

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


def align(lines: list[str], segments: list[Any]) -> list[dict]:
    """Old align_lyrics_with_acoustic_segments: the text stays the user's; no line over 8 s;
    pauses between lines respected; nothing before the first sung moment."""
    clean = []
    for s in segments:
        if isinstance(s, dict):
            raw_t, st, et = s.get("text", ""), float(s.get("start", 0)), float(s.get("end", 0))
        elif isinstance(s, (list, tuple)) and len(s) >= 3:
            st, et, raw_t = float(s[0]), float(s[1]), str(s[2])
        else:
            continue
        t = re.sub(r"[^\w一-鿿]", "", raw_t)
        if t and et > st:
            clean.append({"start": st, "end": et, "text": t})
    if not clean or not lines:
        return []
    n_lines, n_segs = len(lines), len(clean)
    out, idx = [], 0
    for li, lyr in enumerate(lines):
        target = max(2, len(re.sub(r"[^\w一-鿿]", "", lyr)))
        if idx >= n_segs:
            break
        start = clean[idx]["start"]
        text, last_end = "", clean[idx]["end"]
        while idx < n_segs:
            text += clean[idx]["text"]
            last_end = clean[idx]["end"]
            idx += 1
            if len(text) >= target * 0.75:
                if idx < n_segs and clean[idx]["start"] - last_end >= 0.4:
                    break
                if idx < n_segs and len(text) + len(clean[idx]["text"]) > target * 1.3:
                    break
            if last_end - start >= 8.0:
                break
            if n_segs - idx <= n_lines - (li + 1):
                break
        last_end = min(last_end, start + 8.0)
        out.append({"start": round(start, 2), "end": round(last_end, 2), "text": lyr})
    return out


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

