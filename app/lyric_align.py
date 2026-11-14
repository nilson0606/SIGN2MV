"""Where each lyric line is sung: the lyrics matched to Whisper's words, one character or word at a time.

The old matching (MV Studio's clause DP, the quick MV's segment packing) gave one line to one to four
recognized clauses. Whisper often runs two lines into one clause or cuts a line in two, and then lines were
placed by guessing: on a song whose words were all recognized, 38 of 46 lines started more than 0.6 s off.

Here both texts become token lists (a CJK character, or a word of letters and digits) and are aligned as whole
sequences, so a line starts at the time of its own first character wherever the clause borders fall. Runs of
matches score extra, so a line is not spread over a stretch that was sung without lyrics, and of equal
alignments the earliest is taken (lyrics that hold the chorus twice for three sung choruses get the first two).

Pure Python, no dependencies; used by app/mvstudio/align.py and app/quick_lyrics.py.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

Word = Dict[str, Any]           # {"word", "start", "end"} as written by workers/mv_whisper.py

MATCH, SOFT, RUN, MISS, GAP = 4, 2, 1, -2, -2   # scores (integers): exact, similar word, match right after a match
OPEN, EDGE = -8, -1             # starting to pass heard tokens; passing them before / after all the lyrics
CLUSTER_GAP_S = 4.0             # matches of one line further apart than this are two places in the song
UNSUNG_MIN_S = 4.0              # a stretch of unmatched singing worth telling the user about ...
UNSUNG_MIN_TOKENS = 8           # ... has at least this many characters / words

_T2S: Optional[Dict[str, str]] = None


def _t2s() -> Dict[str, str]:
    """Traditional -> Simplified per character: Whisper mixes both scripts in one song."""
    global _T2S
    if _T2S is None:
        table: Dict[str, str] = {}
        try:
            for line in (Path(__file__).with_name("t2s_chars.txt")).read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    continue
                for i in range(0, len(line) - 1, 2):
                    table[line[i]] = line[i + 1]
        except OSError:
            pass
        # characters the table leaves alone because they are right in both scripts, but that lyrics and
        # Whisper write differently all the time
        table.update({"著": "着", "妳": "你", "祢": "你", "牠": "它", "祂": "他", "裏": "里", "乾": "干", "於": "于",
                      "瞭": "了", "甚": "什", "嘆": "叹", "麽": "么", "衹": "只", "祇": "只", "纔": "才", "啓": "启"})
        _T2S = table
    return _T2S


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x3040 <= o <= 0x30FF or 0xAC00 <= o <= 0xD7AF
            or 0xF900 <= o <= 0xFAFF or 0x20000 <= o <= 0x2FA1F)


def tokens(text: str) -> List[str]:
    """Comparable tokens: each CJK character (Simplified), each run of letters/digits (lower case, no accents)."""
    t2s = _t2s()
    out: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        if buf:
            word = "".join(c for c in unicodedata.normalize("NFKD", "".join(buf).casefold())
                           if not unicodedata.combining(c))
            out.append(word.replace("ё", "е") or "".join(buf))
            buf.clear()

    for ch in unicodedata.normalize("NFKC", str(text or "")):
        if _is_cjk(ch):
            flush()
            out.append(t2s.get(ch, ch))
        elif ch.isalnum():
            buf.append(ch)
        elif ch in "'’ʼ" and buf:
            continue                     # don't -> dont
        else:
            flush()
    flush()
    return out


def _soft(a: str, b: str) -> bool:
    """Two words that are probably the same word heard a little differently (never for single CJK characters)."""
    if len(a) < 4 or len(b) < 4 or _is_cjk(a[0]) or _is_cjk(b[0]):
        return False
    if a[:4] == b[:4]:
        return True
    return abs(len(a) - len(b)) <= 1 and a[:3] == b[:3] and a[-2:] == b[-2:]


def word_tokens(words: Sequence[Word]) -> List[Tuple[str, float, float, int]]:
    """Whisper words -> (token, start, end, word index); a word of several characters is divided evenly."""
    out: List[Tuple[str, float, float, int]] = []
    for wi, w in enumerate(words):
        try:
            st, et = float(w.get("start", 0.0)), float(w.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        toks = tokens(str(w.get("word", "")))
        if not toks or et < st:
            continue
        step = (et - st) / len(toks)
        for k, tok in enumerate(toks):
            out.append((tok, st + k * step, st + (k + 1) * step, wi))
    return out


def _pairs(a: List[str], b: List[str]) -> List[Tuple[int, int, int]]:
    """Global alignment of a (lyrics) and b (heard). Returns (i, j, kind) for paired tokens, in order;
    kind 2 = same, 1 = similar word, 0 = different tokens at the same place (a mishearing).

    Three layers by the last step: M paired two equal tokens, O paired unequal ones or passed a lyric token,
    H passed a heard token. Passing heard tokens costs OPEN once per stretch (a line is not spread over two
    repeats of a chorus) and less before the first and after the last lyric token (a repeat that the pasted
    lyrics lack is left over at the end, not in the middle)."""
    n, m = len(a), len(b)
    if not n or not m:
        return []
    # Reversed, so that walking back from the end prefers the earliest of equally good alignments.
    ra, rb = a[::-1], b[::-1]
    ids: Dict[str, int] = {}
    ia = [ids.setdefault(x, len(ids)) for x in ra]
    ib = [ids.setdefault(x, len(ids)) for x in rb]
    soft_rows: Dict[int, set] = {}
    latin_b = [(j, x) for j, x in enumerate(rb) if len(x) >= 4 and not _is_cjk(x[0])]
    if latin_b:
        for i, x in enumerate(ra):
            if len(x) >= 4 and not _is_cjk(x[0]):
                hit = {j for j, y in latin_b if y != x and _soft(x, y)}
                if hit:
                    soft_rows[i] = hit
    neg = -10 ** 9
    pm = [neg] * (m + 1)                                   # previous row, per layer
    po = [neg] * (m + 1)
    ph = [EDGE * j for j in range(m + 1)]
    po[0] = 0
    ph[0] = neg
    bm = [bytearray(m + 1) for _ in range(n + 1)]          # layer it came from: 0 M, 1 O, 2 H
    bo = [bytearray(m + 1) for _ in range(n + 1)]          # move * 3 + layer; move 0 = pair, 1 = pass lyric token
    bh = [bytearray(m + 1) for _ in range(n + 1)]          # layer it came from
    for j in range(1, m + 1):
        bh[0][j] = 2 if j > 1 else 1
    for i in range(1, n + 1):
        cm = [neg] * (m + 1)
        co = [neg] * (m + 1)
        ch = [neg] * (m + 1)
        # column 0: only lyric tokens passed
        x, y, z = pm[0], po[0], ph[0]
        if x >= y and x >= z:
            co[0], bo[i][0] = x + GAP, 3
        elif y >= z:
            co[0], bo[i][0] = y + GAP, 4
        else:
            co[0], bo[i][0] = z + GAP, 5
        ai = ia[i - 1]
        soft = soft_rows.get(i - 1)
        rm, ro, rh = bm[i], bo[i], bh[i]
        step, opening = (EDGE, 0) if i == n else (GAP, OPEN)
        for j in range(1, m + 1):
            x, y, z = pm[j - 1], po[j - 1], ph[j - 1]
            if ai == ib[j - 1]:
                x += RUN
                if x >= y and x >= z:
                    cm[j] = x + MATCH
                elif y >= z:
                    cm[j], rm[j] = y + MATCH, 1
                else:
                    cm[j], rm[j] = z + MATCH, 2
                best, code = neg, 0
            else:
                gain = SOFT if soft and (j - 1) in soft else MISS
                if x >= y and x >= z:
                    best, code = x + gain, 0
                elif y >= z:
                    best, code = y + gain, 1
                else:
                    best, code = z + gain, 2
            x, y, z = pm[j], po[j], ph[j]
            if x >= y and x >= z:
                up, lay = x, 0
            elif y >= z:
                up, lay = y, 1
            else:
                up, lay = z, 2
            if up + GAP > best:
                best, code = up + GAP, 3 + lay
            co[j] = best
            ro[j] = code
            x, y, z = cm[j - 1], co[j - 1], ch[j - 1]
            if x >= y:
                came, lay = x + opening, 0
            else:
                came, lay = y + opening, 1
            if z > came:
                came, lay = z, 2
            ch[j] = came + step
            rh[j] = lay
        pm, po, ph = cm, co, ch
    out: List[Tuple[int, int, int]] = []
    i, j = n, m
    x, y, z = pm[m], po[m], ph[m]
    layer = 0 if (x >= y and x >= z) else (1 if y >= z else 2)
    while i > 0 or j > 0:
        if layer == 0:
            out.append((n - i, m - j, 2))
            layer = bm[i][j]
            i, j = i - 1, j - 1
        elif layer == 1:
            code = bo[i][j]
            layer = code % 3
            if code < 3:
                out.append((n - i, m - j, 1 if _soft(ra[i - 1], rb[j - 1]) else 0))
                i, j = i - 1, j - 1
            else:
                i -= 1
        else:
            layer = bh[i][j]
            j -= 1
    return out      # reversed input walked backwards = original order


def _median(values: List[float], default: float) -> float:
    vals = sorted(v for v in values if v > 0)
    return vals[len(vals) // 2] if vals else default


def align_lines(lines: Sequence[str], words: Sequence[Word]) -> Dict[str, Any]:
    """Match lyric lines to recognized words.

    Returns {"spans": [(start, end) | None per line], "matched": [tokens matched per line],
             "total": [tokens per line], "unsung": [{"start", "end", "text"}]}.
    A span is where the line's own words were heard (start of its first word, end of its last);
    None when too little of the line was heard to place it (the caller spreads those between their neighbours)."""
    heard = word_tokens(words)
    line_tokens = [tokens(t) for t in lines]
    flat: List[str] = []
    owner: List[int] = []
    for li, toks in enumerate(line_tokens):
        flat.extend(toks)
        owner.extend([li] * len(toks))
    total = [len(t) for t in line_tokens]
    spans: List[Optional[Tuple[float, float]]] = [None] * len(lines)
    matched = [0] * len(lines)
    if not flat or not heard:
        return {"spans": spans, "matched": matched, "total": total, "unsung": _unsung(heard, set(), words)}

    pairs = _pairs(flat, [h[0] for h in heard])
    per_line: List[List[Tuple[int, int, int]]] = [[] for _ in lines]
    used_heard = set()
    for i, j, kind in pairs:
        per_line[owner[i]].append((i, j, kind))
        if kind:
            used_heard.add(j)
    first_tok = []
    pos = 0
    for n in total:
        first_tok.append(pos)
        pos += n

    prev_end = float("-inf")
    for li, prs in enumerate(per_line):
        hits = [(i, j) for i, j, kind in prs if kind]
        n = total[li]
        if not n or not hits:
            continue
        # one place in the song: drop a few matches that lie far from the rest of the line
        groups: List[List[Tuple[int, int]]] = [[hits[0]]]
        for h in hits[1:]:
            if heard[h[1]][1] - heard[groups[-1][-1][1]][2] > CLUSTER_GAP_S:
                groups.append([h])
            else:
                groups[-1].append(h)
        if len(groups) > 1:
            big = max(groups, key=len)
            if len(big) * 5 >= len(hits) * 3:
                for g in groups:
                    if g is not big:
                        used_heard.difference_update(j for _, j in g)
                hits = big
        need = 1 if n == 1 else max(2, -(-n * 3 // 10))          # at least 30 % of the line, two tokens
        if len(hits) < min(need, n):
            used_heard.difference_update(j for _, j in hits)
            continue
        matched[li] = len(hits)
        step = _median([heard[b[1]][1] - heard[a[1]][1] for a, b in zip(hits, hits[1:]) if b[0] - a[0] == 1], 0.32)
        step = min(step, 0.8)
        i0, j0 = hits[0]
        start = heard[j0][1]
        lead = i0 - first_tok[li]                                 # tokens of the line before its first match
        if lead > 0:
            # a mishearing at the head of the line still sits where the line begins
            cand = [heard[j][1] for i, j, kind in prs if not kind and i < i0
                    and start - (lead * 0.8 + 0.5) <= heard[j][1] <= start and heard[j][1] >= prev_end - 0.05]
            start = min(cand) if cand else max(start - lead * step, prev_end, start - 2.5, 0.0)
        i1, j1 = hits[-1]
        end = heard[j1][2]
        tail = first_tok[li] + n - 1 - i1
        if tail > 0:
            cand = [heard[j][2] for i, j, kind in prs if not kind and i > i1
                    and end <= heard[j][2] <= end + tail * 0.8 + 0.5]
            end = max(cand) if cand else end + min(tail * step, 2.5)
        start = max(start, 0.0)
        end = max(end, start + 0.05)
        spans[li] = (round(start, 2), round(end, 2))
        prev_end = heard[j1][2]
    # keep the lines in order (a line placed before the one above it is dropped)
    last = float("-inf")
    for li, sp in enumerate(spans):
        if sp is None:
            continue
        if sp[0] < last - 0.01:
            spans[li] = None
            matched[li] = 0
        else:
            last = sp[0]
    return {"spans": spans, "matched": matched, "total": total, "unsung": _unsung(heard, used_heard, words)}


def _unsung(heard: List[Tuple[str, float, float, int]], used: set, words: Sequence[Word]) -> List[Dict[str, Any]]:
    """Stretches of singing that no lyric line accounts for (lyrics pasted without a repeat, or a missing verse)."""
    out: List[Dict[str, Any]] = []
    run: List[int] = []

    def close() -> None:
        if len(run) >= UNSUNG_MIN_TOKENS:
            st, et = heard[run[0]][1], heard[run[-1]][2]
            if et - st >= UNSUNG_MIN_S:
                wi0, wi1 = heard[run[0]][3], heard[run[-1]][3]
                text = "".join(str(words[k].get("word", "")) for k in range(wi0, wi1 + 1)).strip()
                out.append({"start": round(st, 2), "end": round(et, 2), "text": text})
        run.clear()

    for j, h in enumerate(heard):
        if j in used:
            close()
        elif run and h[1] - heard[run[-1]][2] > CLUSTER_GAP_S:
            close()
            run.append(j)
        else:
            run.append(j)
    close()
    return out


def fill_unplaced(spans: List[Optional[Tuple[float, float]]], lines: Sequence[str], lo: float, hi: float,
                  words: Sequence[Word] = (), min_dur: float = 0.4) -> List[Tuple[float, float, bool]]:
    """(start, end, matched) for every line: unplaced lines share the time between their placed neighbours
    by text length; when unmatched singing was heard there, they stay inside it."""
    n = len(spans)
    out: List[Optional[Tuple[float, float, bool]]] = [(s[0], s[1], True) if s else None for s in spans]
    heard = [(float(w.get("start", 0.0)), float(w.get("end", 0.0))) for w in words
             if tokens(str(w.get("word", ""))) and float(w.get("end", 0.0)) - float(w.get("start", 0.0)) >= 0.02]
    i = 0
    while i < n:
        if out[i] is not None:
            i += 1
            continue
        j = i
        while j < n and out[j] is None:
            j += 1
        cnt = j - i
        a = out[i - 1][1] if i > 0 else lo
        b = out[j][0] if j < n else hi
        if all(tokens(lines[k]) for k in range(i, j)):
            inside = [(s, e) for s, e in heard if s >= a - 0.05 and e <= b + 0.05]
            if inside:
                a, b = max(a, inside[0][0]), min(b, max(e for _, e in inside))
        span = max(min_dur * cnt, b - a)
        weights = [max(3, len(tokens(lines[i + k]))) for k in range(cnt)]
        tot = float(sum(weights)) or float(cnt)
        cur = a
        for k in range(cnt):
            st = round(cur, 2)
            cur += weights[k] / tot * span
            out[i + k] = (st, round(cur, 2) if k < cnt - 1 else round(max(b, st + min_dur), 2), False)
        i = j
    return [x or (lo, hi, False) for x in out]
