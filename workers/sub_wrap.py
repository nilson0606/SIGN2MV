"""Subtitle rows for the burnt-in lyrics (quick MV and the library's lyric picture).

libass does not break a line of CJK text that has no spaces, and it sizes a font by its line height
while Pillow sizes it by its em, so the rows are made here from the font's real widths.
"""
from __future__ import annotations


def _units(text: str) -> list[str]:
    """Pieces a row may be broken between: one CJK character, or a word with the spaces after it."""
    out: list[str] = []
    word = ""
    for ch in text:
        wide = ord(ch) >= 0x2E80
        if wide:
            if word:
                out.append(word)
                word = ""
            out.append(ch)
        elif ch == " ":
            word += ch
            out.append(word)
            word = ""
        else:
            word += ch
    if word:
        out.append(word)
    return out


def line_ratio(font_path: str) -> float:
    """libass sizes a font by its line height (ascent + descent), Pillow by its em: ASS size = em * this."""
    from PIL import ImageFont
    asc, desc = ImageFont.truetype(font_path, 200).getmetrics()
    return max(1.0, (asc + desc) / 200.0)


def wrap(text: str, font_path: str, em: int, max_w: int, max_rows: int = 3) -> tuple[list[str], int]:
    """Rows that fit max_w, of about the same width, and the em size used (smaller only when max_rows
    would not hold the line). Done here because libass does not break CJK text that has no spaces."""
    from PIL import ImageFont
    units = _units(text)
    floor = max(10, int(em * 0.55))

    def rows_for(font, limit: float) -> list[str]:
        rows, cur = [], ""
        for u in units:
            if cur and font.getlength((cur + u).rstrip()) * 1.06 > limit:   # 1.06: the subtitle is drawn bold
                rows.append(cur.rstrip())
                cur = u.lstrip()
            else:
                cur += u
        if cur.strip():
            rows.append(cur.rstrip())
        return rows

    while True:
        font = ImageFont.truetype(font_path, em)
        rows = rows_for(font, max_w)
        fits = len(rows) <= max_rows and all(font.getlength(r) * 1.06 <= max_w for r in rows)
        if fits or em <= floor:
            break
        em = max(floor, int(em * 0.9))
    if len(rows) > 1:   # the narrowest limit that needs no more rows: no last row of one character
        limit = font.getlength(text) * 1.06 / len(rows)
        while limit < max_w:
            even = rows_for(font, limit)
            if len(even) <= len(rows):
                rows = even
                break
            limit *= 1.04
    return rows or [text], em
