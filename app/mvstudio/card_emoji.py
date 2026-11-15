"""Emoji pictures as more things for the standard and premium picture cards (card_emoji.json.gz, made by
tools/build_card_emoji.py from Fluent Emoji Flat, MIT, and the Unicode CLDR zh-Hant names and keywords).

ENTRIES maps a name ("e_rainbow") to (family, words): they join card_icons.TABLE after the hand-made icons,
so a line gets an emoji only when no earlier row (place, thing, icon) has the word it says. draw() paints one
into a card: its shapes are filled here (numpy, even-odd or non-zero like SVG), in the card's palette and light
unless it shines, with one outline round the whole of it in the card's ink, like the rest of the card.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "card_emoji.json.gz")


def _load() -> Tuple[Dict[str, Tuple[str, Tuple[str, ...]]], Dict[str, list], float]:
    try:
        with gzip.open(_PATH, "rt", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}, {}, 32.0
    entries, shapes = {}, {}
    for name, v in data.get("emoji", {}).items():
        key = "e_" + name.replace("-", "_")
        entries[key] = (str(v["family"]), tuple(v["words"]))
        shapes[key] = v["shapes"]
    return entries, shapes, float(data.get("box", 32))


ENTRIES, _SHAPES, BOX = _load()
_CACHE: Dict[Tuple[str, int], List[Tuple[Tuple[int, int, int], np.ndarray]]] = {}

# ------------------------------------------------------------------------------------------- SVG paths
_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def _tokens(d: str) -> List[str]:
    """Numbers and commands; an arc's two flags may be written together ("a1 1 0 011 1")."""
    out: List[str] = []
    pos, cmd, n = 0, "", 0
    while pos < len(d):
        ch = d[pos]
        if ch in " ,\t\n\r":
            pos += 1
            continue
        if ch.isalpha():
            out.append(ch); cmd, n = ch.upper(), 0
            pos += 1
            continue
        if cmd == "A" and n % 7 in (3, 4) and ch in "01":
            out.append(ch); n += 1
            pos += 1
            continue
        m = _TOKEN.match(d, pos)
        if not m:
            pos += 1
            continue
        out.append(m.group(0)); n += 1
        pos = m.end()
    return out


def _bez(p0, p1, p2, p3, steps):
    t = np.linspace(0, 1, steps + 1)[1:, None]
    p0, p1, p2, p3 = (np.array(p) for p in (p0, p1, p2, p3))
    return list(map(tuple, (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3))


def _arc(p0, rx, ry, phi, large, sweep, p1, steps_per_unit):
    """The SVG arc from p0 to p1 as points (the endpoint parametrisation of the SVG spec)."""
    x1, y1 = p0
    x2, y2 = p1
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [p1]
    rx, ry = abs(rx), abs(ry)
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = c * dx + s * dy, -s * dx + c * dy
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * yp / ry, -co * ry * xp / rx
    cx, cy = c * cxp - s * cyp + (x1 + x2) / 2, s * cxp + c * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    dt = ang((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(2, min(48, int(abs(dt) * max(rx, ry) * steps_per_unit) + 2))
    pts = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((c * x - s * y + cx, s * x + c * y + cy))
    return pts


def _subpaths(d: str, unit: float) -> List[List[Tuple[float, float]]]:
    """The path's outlines as closed point lists (in the 32-box); unit: points per box unit on curves."""
    toks = _tokens(d)
    subs: List[List[Tuple[float, float]]] = []
    cur: List[Tuple[float, float]] = []
    x = y = sx = sy = 0.0
    last_c = last_q = None
    i, cmd = 0, ""

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                if cur:
                    subs.append(cur)
                cur, x, y = [], sx, sy
                last_c = last_q = None
                continue
        if not cmd:
            break
        C, rel = cmd.upper(), cmd.islower()
        if i + _ARGS[C] > len(toks) or any(toks[j].isalpha() for j in range(i, i + _ARGS[C])):
            i += 1
            continue
        ox, oy = (x, y) if rel else (0.0, 0.0)
        steps = max(3, int(6 * unit / 8))
        if C == "M":
            if cur:
                subs.append(cur)
            x, y = num() + ox, num() + oy
            sx, sy, cur = x, y, [(x, y)]
            cmd = "l" if rel else "L"
            last_c = last_q = None
        elif C == "L":
            x, y = num() + ox, num() + oy
            cur.append((x, y)); last_c = last_q = None
        elif C == "H":
            x = num() + ox
            cur.append((x, y)); last_c = last_q = None
        elif C == "V":
            y = num() + oy
            cur.append((x, y)); last_c = last_q = None
        elif C in "CS":
            if C == "C":
                c1 = (num() + ox, num() + oy)
            else:
                c1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            c2 = (num() + ox, num() + oy)
            p = (num() + ox, num() + oy)
            cur += _bez((x, y), c1, c2, p, steps)
            last_c, last_q = c2, None
            x, y = p
        elif C in "QT":
            if C == "Q":
                q = (num() + ox, num() + oy)
            else:
                q = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
            p = (num() + ox, num() + oy)
            c1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            cur += _bez((x, y), c1, c2, p, steps)
            last_q, last_c = q, None
            x, y = p
        elif C == "A":
            rx, ry, phi = num(), num(), num()
            large, sweep = int(float(toks[i])), int(float(toks[i + 1])); i += 2
            p = (num() + ox, num() + oy)
            cur += _arc((x, y), rx, ry, phi, large, sweep, p, unit / 4)
            last_c = last_q = None
            x, y = p
    if cur:
        subs.append(cur)
    return [s for s in subs if len(s) >= 3]


def _ellipse(cx, cy, rx, ry, unit):
    n = max(12, min(96, int(2 * math.pi * max(rx, ry) * unit / 4)))
    return [[(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]]


def _rrect(x, y, w, h, r, unit):
    r = max(0.0, min(r, w / 2, h / 2))
    if r <= 0:
        return [[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]]
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for k in range(7):
            a = math.radians(a0 + 90 * k / 6)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return [pts]


def _fill(polys: List[List[Tuple[float, float]]], evenodd: bool, size: int, scale: float) -> np.ndarray:
    """Which pixels (centres) of a size x size square the outlines cover (SVG fill rules)."""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for poly in polys:
        a = np.asarray(poly, dtype=np.float64) * scale
        b = np.roll(a, -1, axis=0)
        xs0.append(a[:, 0]); ys0.append(a[:, 1]); xs1.append(b[:, 0]); ys1.append(b[:, 1])
    if not xs0:
        return np.zeros((size, size), bool)
    x0, y0, x1, y1 = (np.concatenate(v) for v in (xs0, ys0, xs1, ys1))
    keep = y0 != y1
    x0, y0, x1, y1 = x0[keep], y0[keep], x1[keep], y1[keep]
    up = y1 > y0
    wind = np.where(up, 1, -1)
    lo, hi = np.minimum(y0, y1), np.maximum(y0, y1)
    r0 = np.clip(np.ceil(lo - 0.5), 0, size).astype(int)
    r1 = np.clip(np.ceil(hi - 0.5), 0, size).astype(int)
    cnt = np.maximum(0, r1 - r0)
    acc = np.zeros((size, size + 1), np.int32)
    if cnt.sum():
        idx = np.repeat(np.arange(len(cnt)), cnt)
        rows = r0[idx] + (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt))
        yc = rows + 0.5
        t = (yc - y0[idx]) / (y1[idx] - y0[idx])
        xc = x0[idx] + t * (x1[idx] - x0[idx])
        col = np.clip(np.ceil(xc - 0.5), 0, size).astype(int)
        if evenodd:
            np.add.at(acc, (rows, col), 1)
        else:
            np.add.at(acc, (rows, col), wind[idx])
    w = np.cumsum(acc, axis=1)[:, :size]
    return (w % 2 == 1) if evenodd else (w != 0)


def _layers(name: str, px: int) -> List[Tuple[Tuple[int, int, int], np.ndarray]]:
    """The picture's shapes, filled at px x px: (colour, mask) in drawing order."""
    key = (name, px)
    if key in _CACHE:
        return _CACHE[key]
    scale = px / BOX
    unit = scale
    out = []
    for sh in _SHAPES[name]:
        col = tuple(int(sh[1][i:i + 2], 16) for i in (0, 2, 4))
        if sh[0] == "p":
            polys, eo = _subpaths(sh[3], unit), bool(sh[2])
        elif sh[0] == "e":
            polys, eo = _ellipse(sh[2], sh[3], sh[4], sh[5], unit), False
        else:
            polys, eo = _rrect(sh[2], sh[3], sh[4], sh[5], sh[6], unit), False
        out.append((col, _fill(polys, eo, px, scale)))
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def draw(k, name: str, ox: float, oy: float, z: float, shine: bool = True) -> None:
    """Paint the emoji in the 100 x 100 box whose top left corner is (ox, oy), one unit being z (as
    card_icons.draw_shapes). The canvas is twice the size of the card's coordinates."""
    from .cardworld import P
    if k.dark and name.startswith(("e_sun", "e_rainbow")):
        return                  # no sun (or rainbow) in a dusk or night sky
    px = max(8, int(round(P(100 * z))))
    layers = _layers(name, px)
    rgb = np.zeros((px, px, 3), np.uint8)
    cover = np.zeros((px, px), bool)
    for col, mask in layers:
        rgb[mask] = k.c(col, e=shine)[:3]
        cover |= mask
    alpha = Image.fromarray((cover * 255).astype(np.uint8), "L")
    # one outline round the whole picture, in the card's ink (as thick as the card's lines)
    lw = max(2, int(P(k.lw)))
    ring = alpha.filter(ImageFilter.MaxFilter(2 * (lw // 2) + 1))
    ink = k.ink if k.ink else (70, 76, 100)
    if k.flat:
        ink = k.flat
        rgb[:] = k.flat[:3]
    x, y = int(round(P(ox))), int(round(P(oy)))
    k.im.paste(Image.new("RGB", (px, px), tuple(ink[:3])), (x, y), ring)
    k.im.paste(Image.fromarray(rgb, "RGB"), (x, y), alpha.filter(ImageFilter.SMOOTH))
