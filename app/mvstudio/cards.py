"""Simple picture cards for an MV without photos: flat, light "fresh comic" scenes drawn here, one per
part of the timeline (the MV page's 「產生簡易圖卡」). Nothing is fetched; a card is a 1920x1080 picture made
with Pillow at twice the size and scaled down.

pick() chooses a scene for every part: a line with a known word (rain, star, luck, goodbye, ...) gets the
scene that goes with it, other lines take turns through general scenes, never the same scene twice in a
row, and a scene used again is drawn in other light or mirrored. The words are Chinese; lines in other
languages get the general scenes. The choice is rough on purpose: the cards are for an MV that would
otherwise have no picture at all, and each one can be replaced by a photo like any other.
"""
from __future__ import annotations

import colorsys
import json
import math
import os
import random
import secrets
import zlib
from typing import Dict, List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from . import cardworld

W, H, S = 1920, 1080, 2
INK = (52, 62, 92)
SKIN = (255, 226, 205)
PAL = {
    "dawn": [(255, 214, 196), (255, 240, 214), (206, 232, 255)],
    "day": [(142, 208, 255), (196, 232, 255), (236, 250, 255)],
    "rain": [(150, 176, 204), (186, 206, 226), (216, 228, 238)],
    "sunset": [(255, 170, 140), (255, 208, 160), (255, 236, 200)],
    "dusk": [(126, 120, 190), (214, 150, 190), (255, 204, 180)],
    "night": [(34, 44, 96), (60, 72, 138), (112, 110, 170)],
    "mint": [(170, 232, 214), (214, 246, 230), (246, 255, 246)],
    "pink": [(255, 190, 210), (255, 220, 228), (255, 244, 240)],
}

def P(v): return int(round(v * S))

# ---- a song's own look -----------------------------------------------------------------------------------
# The scenes are the same for every song; what a song gets of its own is who is in them (hair, clothes), a
# slight turn of the landscape colours, where the small things are (clouds, flowers, stars), which way round
# each scene is and which of its two lights comes first. All of it follows from one number, the song's seed;
# seed 0 is the plain look.
GIRL_HAIR = ((92, 70, 70), (58, 52, 66), (132, 86, 60), (178, 130, 86), (114, 62, 68))
BOY_HAIR = ((58, 62, 84), (86, 66, 60), (40, 40, 48), (106, 94, 86))
SKIRTS = ((232, 120, 140), (92, 170, 176), (88, 104, 160), (226, 170, 84), (160, 132, 204), (120, 176, 120))
PANTS = ((88, 104, 160), (74, 80, 92), (150, 128, 96), (84, 128, 116))
TOPS = ((255, 255, 255), (255, 246, 224), (226, 240, 255), (255, 232, 236))
HAIR_STYLES = ("long", "bob", "ponytail", "twin")
HUES = (-14, -8, 8, 14)
PLAIN = {"girl_hair": GIRL_HAIR[0], "boy_hair": BOY_HAIR[0], "skirt": SKIRTS[0], "pants": PANTS[0], "girl_top": TOPS[0],
         "boy_top": TOPS[0], "hair_style": "long", "hue": 0}


def song_style(seed: int) -> Dict[str, object]:
    if not seed:
        return dict(PLAIN)
    r = random.Random(f"style:{seed}")
    st = {"girl_hair": r.choice(GIRL_HAIR), "boy_hair": r.choice(BOY_HAIR), "skirt": r.choice(SKIRTS), "pants": r.choice(PANTS),
          "girl_top": r.choice(TOPS), "boy_top": r.choice(TOPS), "hair_style": r.choice(HAIR_STYLES), "hue": r.choice(HUES)}
    if st["hair_style"] == "long" and st["skirt"] == SKIRTS[0] and st["girl_hair"] == GIRL_HAIR[0]:
        st["hair_style"] = "bob"          # never the plain girl again
    return st


def _turn(col, deg):
    """The colour with its hue turned by deg degrees (alpha, if any, kept)."""
    if not deg:
        return col
    h, l, sat = colorsys.rgb_to_hls(col[0] / 255, col[1] / 255, col[2] / 255)
    r, g, b = colorsys.hls_to_rgb((h + deg / 360) % 1.0, l, sat)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255))) + tuple(col[3:])

class C:
    def __init__(self, seed, style=None, mirrored=False):
        self.im = Image.new("RGB", (W * S, H * S), "white"); self.d = ImageDraw.Draw(self.im, "RGBA"); self.r = random.Random(seed)
        self.style = style or dict(PLAIN); self.hue = int(self.style.get("hue", 0) or 0)
        self.mirrored = mirrored          # the finished picture is mirrored: marks that read one way are drawn reversed
    def sky(self, name):
        a, b, c = (_turn(col, self.hue) for col in PAL[name])
        for y in range(H * S):
            t = y / (H * S - 1)
            col = [int(a[i] + (b[i] - a[i]) * (t / 0.55)) if t < 0.55 else int(b[i] + (c[i] - b[i]) * ((t - 0.55) / 0.45)) for i in range(3)]
            self.d.line([(0, y), (W * S, y)], fill=tuple(col))
    def ell(self, x, y, rx, ry, fill, outline=INK, w=4): self.d.ellipse([P(x - rx), P(y - ry), P(x + rx), P(y + ry)], fill=fill, outline=outline, width=P(w) if outline else 0)
    def rect(self, x0, y0, x1, y1, fill, outline=INK, w=4, r=0): self.d.rounded_rectangle([P(x0), P(y0), P(x1), P(y1)], radius=P(r), fill=fill, outline=outline, width=P(w) if outline else 0)
    def poly(self, pts, fill, outline=INK, w=4):
        q = [(P(x), P(y)) for x, y in pts]; self.d.polygon(q, fill=fill)
        if outline: self.d.line(q + [q[0]], fill=outline, width=P(w), joint="curve")
    def line(self, pts, fill=INK, w=4): self.d.line([(P(x), P(y)) for x, y in pts], fill=fill, width=P(w), joint="curve")
    def cloud(self, x, y, s=1.0, col=(255, 255, 255)):
        for dx, dy, r in ((-70, 10, 46), (-25, -18, 62), (35, -8, 54), (80, 14, 40), (10, 22, 58)):
            self.ell(x + dx * s, y + dy * s, r * s, r * s * 0.8, col + (245,), None)
    def clouds(self, n=4, y0=90, y1=380, col=(255, 255, 255)):
        for _ in range(n): self.cloud(self.r.uniform(120, W - 120), self.r.uniform(y0, y1), self.r.uniform(0.8, 1.7), col)
    def sun(self, x, y, r=90, col=(255, 236, 150)):
        for k in range(5, 0, -1): self.ell(x, y, r + k * 26, r + k * 26, col + (26,), None)
        self.ell(x, y, r, r, col)
    def moon(self, x, y, r=70):
        self.ell(x, y, r, r, (255, 248, 210)); self.ell(x + r * 0.42, y - r * 0.18, r * 0.82, r * 0.82, PAL["night"][0] + (255,), None)
    def stars(self, n=90, ymax=620):
        for _ in range(n):
            x, y, r = self.r.uniform(0, W), self.r.uniform(0, ymax), self.r.choice((1.5, 2, 2.5, 4))
            self.ell(x, y, r, r, (255, 255, 235, self.r.randint(150, 255)), None)
    def star(self, x, y, r, col=(255, 240, 150)):
        pts = [(x + math.cos(math.pi / 2 + k * math.pi / 5) * (r if k % 2 == 0 else r * 0.45), y - math.sin(math.pi / 2 + k * math.pi / 5) * (r if k % 2 == 0 else r * 0.45)) for k in range(10)]
        self.poly(pts, col)
    def shooting(self, x, y, L=420):
        for k in range(18):
            t = k / 18; self.line([(x + L * t, y - L * 0.45 * t), (x + L * (t + 0.06), y - L * 0.45 * (t + 0.06))], (255, 250, 200, int(230 * (1 - t))), 10 * (1 - t) + 2)
        self.star(x, y, 30)
    def rain(self, n=220, col=(255, 255, 255, 170), slant=-0.25):
        for _ in range(n):
            x, y, L = self.r.uniform(-100, W + 100), self.r.uniform(-50, H), self.r.uniform(30, 70)
            self.line([(x, y), (x + L * slant, y + L)], col, 3)
    def hills(self, y=760, cols=((150, 214, 170), (120, 198, 150)), amp=60):
        for j, col in enumerate(cols):
            col = _turn(col, self.hue)
            ph = self.r.uniform(0, 6); base = y + j * 70
            pts = [(x, base + math.sin(x / 260 + ph) * amp * (1 - j * 0.3) + math.sin(x / 97 + ph) * 14) for x in range(-20, W + 40, 20)]
            self.poly(pts + [(W + 20, H + 20), (-20, H + 20)], col, None)
    def ground(self, y=820, col=(170, 222, 160), edge=True):
        col = _turn(col, self.hue)
        self.rect(-10, y, W + 10, H + 10, col, None)
        if edge: self.line([(0, y), (W, y)], INK, 4)
    def grass(self, y=820, n=160, col=(96, 176, 120)):
        col = _turn(col, self.hue)
        for _ in range(n):
            x, h = self.r.uniform(0, W), self.r.uniform(14, 40); yy = self.r.uniform(y, H)
            self.line([(x, yy), (x + self.r.uniform(-8, 8), yy - h)], col, 3)
    def flowers(self, y=830, n=40, cols=((255, 190, 210), (255, 240, 150), (255, 255, 255))):
        for _ in range(n):
            x, yy, c = self.r.uniform(0, W), self.r.uniform(y, H - 10), self.r.choice(cols)
            for a in range(5): self.ell(x + math.cos(a * 1.257) * 9, yy + math.sin(a * 1.257) * 9, 7, 7, c, None)
            self.ell(x, yy, 5, 5, (255, 200, 90), None)
    def tree(self, x, y, s=1.0, crown=(150, 214, 160), blossom=False):
        self.poly([(x - 22 * s, y), (x - 14 * s, y - 230 * s), (x + 14 * s, y - 230 * s), (x + 22 * s, y)], (176, 132, 108))
        col = (255, 196, 214) if blossom else _turn(crown, self.hue)
        for dx, dy, r in ((-90, -260, 95), (80, -270, 100), (0, -350, 120), (-20, -250, 90), (130, -200, 60), (-140, -190, 60)):
            self.ell(x + dx * s, y + dy * s, r * s, r * s * 0.9, col)
        self.ell(x, y - 300 * s, 150 * s, 110 * s, col, None)
    def petals(self, n=60, col=(255, 200, 216)):
        for _ in range(n):
            x, y = self.r.uniform(0, W), self.r.uniform(0, H); a = self.r.uniform(0, 3.14)
            self.poly([(x, y), (x + 14 * math.cos(a), y + 14 * math.sin(a)), (x + 7 * math.cos(a + 1.2), y + 9 * math.sin(a + 1.2))], col + (230,), None)
    def school(self, x, y, s=1.0, clock=True):
        self.rect(x - 330 * s, y - 250 * s, x + 330 * s, y, (255, 248, 236), r=6)
        self.rect(x - 90 * s, y - 380 * s, x + 90 * s, y, (255, 240, 222), r=6)
        self.poly([(x - 110 * s, y - 380 * s), (x, y - 450 * s), (x + 110 * s, y - 380 * s)], (240, 140, 130))
        if clock:
            self.ell(x, y - 315 * s, 44 * s, 44 * s, (255, 255, 255)); self.line([(x, y - 315 * s), (x, y - 345 * s)], INK, 4); self.line([(x, y - 315 * s), (x + 20 * s, y - 305 * s)], INK, 4)
        for row in range(3):
            for k in range(-5, 6):
                if abs(k) < 2: continue
                self.rect(x + k * 56 * s - 18 * s, y - 220 * s + row * 68 * s, x + k * 56 * s + 18 * s, y - 180 * s + row * 68 * s, (170, 220, 250), w=3, r=3)
        self.rect(x - 34 * s, y - 90 * s, x + 34 * s, y, (190, 150, 120), r=4)
    def person(self, x, y, s=1.0, kind="girl", face="front", arm=None, col=None, hair=None):
        """Feet at (x, y); about 300 px tall at s=1."""
        st = self.style; girl = kind == "girl"; cut = st["hair_style"] if girl else ""
        hair = hair or (st["girl_hair"] if girl else st["boy_hair"]); top = col or (st["girl_top"] if girl else st["boy_top"]); low = st["skirt"] if girl else st["pants"]
        hy = y - 262 * s
        if girl and face != "back":       # the hair behind the head and shoulders
            if cut == "long": self.poly([(x - 52 * s, hy - 6 * s), (x + 52 * s, hy - 6 * s), (x + 46 * s, hy + 110 * s), (x - 46 * s, hy + 110 * s)], hair)
            elif cut == "bob": self.poly([(x - 54 * s, hy - 6 * s), (x + 54 * s, hy - 6 * s), (x + 58 * s, hy + 54 * s), (x - 58 * s, hy + 54 * s)], hair)
            elif cut == "ponytail": self.ell(x + 56 * s, hy + 34 * s, 17 * s, 52 * s, hair)
            else:
                for sx in (-1, 1): self.ell(x + sx * 60 * s, hy + 46 * s, 16 * s, 50 * s, hair)
        self.line([(x - 22 * s, y - 110 * s), (x - 24 * s, y)], INK, 16 * s); self.line([(x + 22 * s, y - 110 * s), (x + 24 * s, y)], INK, 16 * s)
        self.line([(x - 22 * s, y - 110 * s), (x - 24 * s, y - 4 * s)], SKIN if girl else low, 10 * s); self.line([(x + 22 * s, y - 110 * s), (x + 24 * s, y - 4 * s)], SKIN if girl else low, 10 * s)
        if girl: self.poly([(x - 40 * s, y - 150 * s), (x + 40 * s, y - 150 * s), (x + 62 * s, y - 84 * s), (x - 62 * s, y - 84 * s)], low)
        else: self.rect(x - 38 * s, y - 150 * s, x + 38 * s, y - 100 * s, low, r=6 * s)
        self.rect(x - 42 * s, y - 220 * s, x + 42 * s, y - 140 * s, top, r=16 * s)
        arms = {None: ((-52, -150), (52, -150)), "up": ((-70, -290), (52, -150)), "both": ((-78, -290), (78, -290)), "wave": ((-52, -150), (86, -300)), "reach": ((-52, -150), (110, -230)), "out": ((-120, -200), (120, -200))}[arm]
        for sx, (ax, ay) in zip((-1, 1), arms):
            self.line([(x + sx * 40 * s, y - 208 * s), (x + ax * s, y + ay * s)], INK, 18 * s); self.line([(x + sx * 40 * s, y - 208 * s), (x + ax * s, y + ay * s)], top, 11 * s)
            self.ell(x + ax * s, y + ay * s, 10 * s, 10 * s, SKIN, INK, 3)
        self.ell(x, hy, 46 * s, 46 * s, SKIN)
        if face == "back":
            self.ell(x, hy - 4 * s, 48 * s, 46 * s, hair)
            if girl and cut == "long": self.poly([(x - 48 * s, hy), (x + 48 * s, hy), (x + 44 * s, hy + 120 * s), (x - 44 * s, hy + 120 * s)], hair)
            elif girl and cut == "bob": self.poly([(x - 48 * s, hy), (x + 48 * s, hy), (x + 54 * s, hy + 58 * s), (x - 54 * s, hy + 58 * s)], hair)
            elif girl and cut == "ponytail":
                self.poly([(x - 15 * s, hy + 30 * s), (x + 15 * s, hy + 30 * s), (x + 20 * s, hy + 128 * s), (x - 20 * s, hy + 128 * s)], hair); self.ell(x, hy + 34 * s, 12 * s, 9 * s, (255, 170, 170))
            elif girl:
                for sx in (-1, 1): self.poly([(x + sx * 28 * s, hy + 26 * s), (x + sx * 52 * s, hy + 26 * s), (x + sx * 60 * s, hy + 120 * s), (x + sx * 34 * s, hy + 120 * s)], hair)
        else:
            self.d.pieslice([P(x - 48 * s), P(hy - 50 * s), P(x + 48 * s), P(hy + 40 * s)], 180, 360, fill=hair, outline=INK, width=P(4))
            dx = {"front": 0, "left": -8, "right": 8}[face] * s
            for e in (-16, 16): self.ell(x + e * s + dx, hy + 6 * s, 5 * s, 7 * s, INK, None)
            for e in (-26, 26): self.ell(x + e * s + dx, hy + 20 * s, 9 * s, 6 * s, (255, 170, 170, 150), None)
    def tear(self, x, y, s=1.0): self.poly([(x, y - 16 * s), (x + 9 * s, y + 4 * s), (x, y + 12 * s), (x - 9 * s, y + 4 * s)], (150, 210, 255), INK, 2)
    def umbrella(self, x, y, s=1.0, col=(255, 150, 160)):
        self.d.pieslice([P(x - 150 * s), P(y - 130 * s), P(x + 150 * s), P(y + 130 * s)], 180, 360, fill=col, outline=INK, width=P(4))
        self.line([(x, y), (x, y + 190 * s)], INK, 5)
    def heart(self, x, y, s=1.0, col=(255, 130, 150)):
        self.ell(x - 14 * s, y - 8 * s, 16 * s, 16 * s, col, None); self.ell(x + 14 * s, y - 8 * s, 16 * s, 16 * s, col, None)
        self.poly([(x - 29 * s, y - 2 * s), (x + 29 * s, y - 2 * s), (x, y + 32 * s)], col, None)
    def clover(self, x, y, s=1.0, col=(120, 200, 130)):
        self.line([(x, y), (x + 14 * s, y + 80 * s)], (90, 160, 100), 6 * s)
        for a in range(4):
            ang = a * math.pi / 2 + math.pi / 4; cx, cy = x + math.cos(ang) * 30 * s, y + math.sin(ang) * 30 * s
            for b in (-0.45, 0.45): self.ell(cx + math.cos(ang + b) * 14 * s, cy + math.sin(ang + b) * 14 * s, 20 * s, 20 * s, col, None)
        self.ell(x, y, 8 * s, 8 * s, (90, 170, 100), None)
    def bubble(self, x, y, w=260, h=150, tail=(-60, 110), marks="..."):
        self.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, (255, 255, 255), r=60)
        self.poly([(x + tail[0] - 26, y + h / 2 - 6), (x + tail[0] + 26, y + h / 2 - 6), (x + tail[0] * 1.6, y + tail[1])], (255, 255, 255)); self.rect(x + tail[0] - 30, y + h / 2 - 22, x + tail[0] + 30, y + h / 2 - 4, (255, 255, 255), None)
        if marks == "...":
            for k in (-1, 0, 1): self.ell(x + k * 50, y, 13, 13, INK, None)
        elif marks == "heart": self.heart(x, y - 6, 1.5)
        elif marks == "!":
            self.rect(x - 9, y - 44, x + 9, y + 14, (255, 130, 140), None, r=8); self.ell(x, y + 36, 11, 11, (255, 130, 140), None)
        elif marks == "?":
            a0, a1, k = (100, 340, -1) if self.mirrored else (200, 80, 1)
            self.d.arc([P(x - 26), P(y - 46), P(x + 26), P(y + 6)], a0, a1, fill=INK, width=P(9)); self.line([(x + 4 * k, y + 2), (x, y + 20)], INK, 9); self.ell(x, y + 40, 8, 8, INK, None)
    def bench(self, x, y, s=1.0):
        self.rect(x - 220 * s, y - 70 * s, x + 220 * s, y - 50 * s, (214, 170, 130), r=4); self.rect(x - 220 * s, y - 150 * s, x + 220 * s, y - 110 * s, (214, 170, 130), r=4)
        for k in (-180, 180): self.rect(x + k * s - 8 * s, y - 150 * s, x + k * s + 8 * s, y, (150, 120, 100), r=3)
    def lamp(self, x, y, h=420, glow=True):
        self.rect(x - 7, y - h, x + 7, y, (110, 120, 150), r=3); self.rect(x - 40, y - h - 26, x + 40, y - h, (255, 244, 190), r=10)
        if glow: self.poly([(x - 40, y - h), (x + 40, y - h), (x + 200, y), (x - 200, y)], (255, 244, 190, 60), None)
    def train(self, x, y, s=1.0):
        self.rect(x - 520 * s, y - 210 * s, x + 520 * s, y, (120, 200, 190), r=40 * s); self.rect(x - 520 * s, y - 70 * s, x + 520 * s, y - 40 * s, (255, 255, 255), None)
        for k in range(-4, 5): self.rect(x + k * 110 * s - 38 * s, y - 170 * s, x + k * 110 * s + 38 * s, y - 100 * s, (220, 244, 255), w=3, r=8)
        for k in (-380, -200, 200, 380): self.ell(x + k * s, y + 10 * s, 34 * s, 34 * s, (90, 100, 130))
    def bike(self, x, y, s=1.0):
        for k in (-90, 90): self.ell(x + k * s, y - 60 * s, 60 * s, 60 * s, (255, 255, 255, 60), INK, 6)
        self.line([(x - 90 * s, y - 60 * s), (x - 20 * s, y - 150 * s), (x + 60 * s, y - 150 * s), (x + 90 * s, y - 60 * s)], (240, 120, 130), 9); self.line([(x - 20 * s, y - 150 * s), (x + 10 * s, y - 60 * s), (x - 90 * s, y - 60 * s)], (240, 120, 130), 9)
        self.line([(x + 60 * s, y - 150 * s), (x + 50 * s, y - 190 * s), (x + 86 * s, y - 196 * s)], INK, 7); self.rect(x - 44 * s, y - 166 * s, x + 2 * s, y - 152 * s, INK, None, r=6)
    def plane(self, x, y, s=1.0, col=(255, 255, 255)):
        self.poly([(x - 110 * s, y + 10 * s), (x + 120 * s, y - 50 * s), (x - 20 * s, y + 50 * s)], col); self.poly([(x - 20 * s, y + 50 * s), (x + 120 * s, y - 50 * s), (x + 6 * s, y + 84 * s)], (226, 236, 250))
    def birds(self, n=6, y0=160, y1=420):
        for _ in range(n):
            x, y, s = self.r.uniform(200, W - 200), self.r.uniform(y0, y1), self.r.uniform(0.6, 1.3)
            self.line([(x - 30 * s, y - 12 * s), (x, y), (x + 30 * s, y - 12 * s)], INK, 5)
    def wings(self, x, y, s=1.0):
        for sx in (-1, 1):
            for k in range(5):
                self.poly([(x + sx * 30 * s, y), (x + sx * (150 + k * 16) * s, y - (150 - k * 46) * s), (x + sx * (110 + k * 6) * s, y + (10 + k * 24) * s)], (255, 255, 255, 240))
    def frames(self, xs, y, w=250, h=190):
        for i, x in enumerate(xs):
            a = (-6, 4, -3, 5)[i % 4]; fr = Image.new("RGBA", (P(w + 40), P(h + 80)), (0, 0, 0, 0)); fd = ImageDraw.Draw(fr)
            fd.rounded_rectangle([P(6), P(6), P(w + 34), P(h + 74)], radius=P(8), fill=(255, 255, 255), outline=INK, width=P(4))
            fd.rectangle([P(20), P(20), P(w + 20), P(h + 20)], fill=[(190, 226, 255), (255, 214, 196), (206, 240, 214), (255, 226, 236)][i % 4], outline=INK, width=P(3))
            fr = fr.rotate(a, expand=True, resample=Image.BICUBIC); self.im.paste(fr, (P(x) - fr.width // 2, P(y) - fr.height // 2), fr)
        self.d = ImageDraw.Draw(self.im, "RGBA")
    def envelope(self, x, y, s=1.0):
        self.rect(x - 150 * s, y - 100 * s, x + 150 * s, y + 100 * s, (255, 252, 244), r=8); self.line([(x - 150 * s, y - 100 * s), (x, y + 10 * s), (x + 150 * s, y - 100 * s)], INK, 4); self.heart(x, y + 6 * s, 1.1 * s)
    def road(self, y=860, wind=True):
        pts_l, pts_r = [], []
        for k in range(0, 21):
            t = k / 20; yy = H - (H - 560) * t; cx = W / 2 + (math.sin(t * 5.2) * 330 * (1 - t) if wind else 0); hw = 260 * (1 - t) + 14
            pts_l.append((cx - hw, yy)); pts_r.append((cx + hw, yy))
        self.poly(pts_l + pts_r[::-1], (236, 226, 206))
    def speed(self, n=26, col=(255, 255, 255, 120)):
        for _ in range(n):
            y = self.r.uniform(60, H - 60); x = self.r.uniform(0, W - 400); self.line([(x, y), (x + self.r.uniform(160, 420), y)], col, self.r.choice((3, 5, 8)))
    def dots(self, corner="br", col=(255, 255, 255, 90)):
        for i in range(0, 520, 26):
            for j in range(0, 380, 26):
                r = max(0, 11 - (i + j) / 70)
                if r <= 0.5: continue
                x = (W - 30 - i) if "r" in corner else (30 + i); y = (H - 30 - j) if "b" in corner else (30 + j)
                self.ell(x, y, r, r, col, None)
    def finish(self, mirror=False):
        im = self.im.resize((W, H), Image.LANCZOS)
        if mirror:
            im = ImageOps.mirror(im)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle([14, 14, W - 15, H - 15], radius=26, outline=(255, 255, 255), width=18); d.rounded_rectangle([24, 24, W - 25, H - 25], radius=20, outline=INK, width=4)
        return im



def _scene(name, c, v=0):
    alt = lambda a, b: b if v else a  # noqa: E731
    if name == "opening":
        c.sky("dawn"); c.sun(1500, 300, 110); c.clouds(5); c.hills(700); c.school(960, 800, 0.8); c.ground(800); c.grass(800, 120); c.flowers(860, 30); c.dots("bl")
    elif name == "rain_meadow":
        c.sky("rain"); c.clouds(5, col=(236, 240, 246)); c.hills(690, ((140, 206, 160), (110, 190, 140))); c.ground(820, (150, 214, 150)); c.grass(820, 260); c.rain(320)
        for _ in range(14): x, y = c.r.uniform(100, W - 100), c.r.uniform(860, 1020); c.d.arc([P(x - 40), P(y - 10), P(x + 40), P(y + 10)], 0, 360, fill=(255, 255, 255, 200), width=P(3))
    elif name == "school_bell":
        c.sky("day"); c.clouds(5); c.hills(720); c.school(1250, 800, 0.72); c.ground(800); c.grass(800, 120)
        for k, r in enumerate((60, 100, 140)): c.d.arc([P(1250 - r * 2.2), P(450 - r), P(1250 + r * 2.2), P(450 + r)], 200, 340, fill=(255, 255, 255, 220 - k * 50), width=P(6))
        c.person(430, 900, 1.0, "girl", "right"); c.dots("br")
    elif name == "window_quiet":
        c.sky("mint"); c.rect(160, 120, W - 160, H - 150, (236, 248, 255), r=14); c.line([(960, 120), (960, H - 150)], INK, 6); c.line([(160, 520), (W - 160, 520)], INK, 6)
        c.cloud(520, 330, 1.3); c.cloud(1380, 300, 1.0); c.rect(-10, H - 170, W + 10, H + 10, (226, 196, 160)); c.person(700, 1000, 1.25, "girl", "back"); c.bubble(1180, 520, marks="...", tail=(-90, 110))
    elif name == "calling":
        c.sky("day"); c.sun(300, 240, 80); c.clouds(4); c.ground(820, (190, 230, 170)); c.grass(820, 120); c.tree(1640, 840, 1.1)
        c.person(1300, 900, 1.05, "boy", "left", "wave"); c.bubble(1010, 430, 300, 170, tail=(120, 110), marks="!"); c.person(420, 900, 0.95, "girl", "back"); c.speed(14)
    elif name == "classroom_heart":
        c.sky("pink"); c.rect(-10, 700, W + 10, H + 10, (240, 214, 180)); c.rect(260, 640, 860, 720, (214, 170, 130), r=8); c.rect(1060, 640, 1660, 720, (214, 170, 130), r=8)
        c.person(560, 980, 1.2, "girl", "right"); c.person(1360, 980, 1.2, "boy", "left"); c.heart(960, 360, 2.6); c.bubble(700, 250, 190, 130, tail=(-30, 90), marks="?"); c.dots("br")
    elif name == "farewell_train":
        c.sky("sunset"); c.clouds(3, col=(255, 236, 220)); c.rect(-10, 800, W + 10, H + 10, (220, 210, 200)); c.train(1250, 800, 1.0); c.line([(0, 810), (W, 810)], INK, 5)
        c.person(360, 960, 1.15, "girl", "right", "wave"); c.tear(420, 650, 1.2); c.speed(16, (255, 255, 255, 150))
    elif name == "corridor_pass":
        c.sky("mint"); c.rect(-10, 760, W + 10, H + 10, (236, 226, 206)); c.rect(-10, 150, W + 10, 760, (250, 250, 244), None)
        for k in range(5): c.rect(120 + k * 360, 220, 380 + k * 360, 560, (190, 230, 255), r=6)
        c.person(700, 960, 1.15, "girl", "left"); c.person(1220, 960, 1.15, "boy", "right"); c.line([(790, 700), (1130, 700)], (255, 150, 160, 160), 6); c.dots("bl", (120, 200, 190, 70))
    elif name == "sunny_field":
        c.sky("day"); c.sun(960, 300, 130); c.clouds(4); c.hills(740); c.ground(830, (176, 226, 150)); c.flowers(840, 90); c.person(960, 940, 1.1, "girl", "front", "both"); c.dots("br")
    elif name == "smile_tear":
        c.sky(alt("pink", "mint")); c.rect(960 - 6, 40, 960 + 6, H - 40, (255, 255, 255), None)
        c.sun(480, 300, 90); c.cloud(1440, 300, 1.4, (226, 232, 244)); c.rain(70, (255, 255, 255, 150)) if False else None
        c.person(480, 940, 1.2, "girl", "front", "both"); c.person(1440, 940, 1.2, "girl", "front"); c.tear(1410, 690, 1.4); c.tear(1474, 700, 1.1); c.heart(640, 420, 1.2)
    elif name == "shooting_star":
        c.sky("night"); c.stars(140); c.moon(alt(1600, 320), 220); c.shooting(alt(520, 1100), 420); c.hills(780, ((70, 96, 150), (52, 76, 128))); c.person(alt(1200, 640), 930, 1.05, "girl", "back", "up")
    elif name == "path_leaves":
        c.sky(alt("dusk", "sunset")); c.clouds(3, col=(255, 230, 220)); c.ground(800, (226, 206, 176)); c.road(wind=True)
        for k in range(9): c.ell(960 + math.sin(k) * 60, 1040 - k * 52, 16 - k, 9 - k * 0.6, (180, 160, 140, 220 - k * 22), None)
        c.petals(40, (255, 214, 150)); c.person(alt(960, 1040), 620, 0.45, "girl", "back")
    elif name == "umbrella_wait":
        c.sky("rain" if not v else "night"); c.rect(-10, 820, W + 10, H + 10, (150, 160, 186)); c.lamp(alt(1280, 640), 880); c.rain(300)
        px = alt(1060, 860); c.umbrella(px, 560, 1.0, alt((255, 150, 160), (255, 220, 120))); c.person(px, 930, 1.1, "boy", "front")
    elif name == "clover":
        c.sky(alt("mint", "dawn")); c.sun(960, 520, 220, (255, 250, 200)); c.clover(960, 470, 3.4); c.ell(820, 860, 150, 70, SKIN); c.ell(1100, 860, 150, 70, SKIN)
        for k in range(10): c.star(c.r.uniform(300, 1620), c.r.uniform(150, 800), c.r.uniform(10, 22), (255, 255, 255))
    elif name == "bench_sunset":
        c.sky(alt("sunset", "dusk")); c.sun(960, 620, 150, (255, 226, 170)); c.ground(840, (226, 196, 170)); c.bench(960, 900, 1.3)
        c.person(800, 880, 1.0, "girl", "back"); c.person(1120, 880, 1.0, "boy", "back"); c.heart(960, 420, alt(1.8, 2.4))
    elif name == "shield":
        c.sky(alt("dusk", "rain")); [c.cloud(x, y, 2.2, (120, 124, 160)) for x, y in ((1500, 260), (1750, 420), (1300, 420))]; c.ground(840, (190, 196, 190)); c.speed(22)
        c.person(alt(760, 1160), 920, 1.15, "boy", alt("right", "left"), "out"); c.person(alt(520, 1400), 920, 1.0, "girl", alt("right", "left"))
    elif name == "rain_together":
        c.sky("rain"); c.clouds(4, col=(230, 236, 244)); c.rect(-10, 830, W + 10, H + 10, (160, 176, 196)); c.rain(380)
        c.person(alt(860, 1060), 930, 1.1, "girl", "front", "both"); c.person(alt(1080, 840), 930, 1.1, "boy", "front", "both"); c.heart(960, 330, 1.6)
    elif name == "photos":
        c.sky(alt("pink", "dawn")); c.frames([300, 700, 1220, 1620] if not v else [380, 820, 1100, 1540], 430); c.frames([500, 960, 1420], 760)
        for k in range(14): c.star(c.r.uniform(120, 1800), c.r.uniform(120, 960), c.r.uniform(8, 18), (255, 255, 255))
    elif name == "blossom_meet":
        c.sky(alt("day", "pink")); c.clouds(3); c.ground(840, (190, 230, 170)); c.tree(960, 850, 1.5, blossom=True); c.petals(110)
        c.person(680, 930, 1.05, "girl", "right"); c.person(1240, 930, 1.05, "boy", "left"); c.clover(960, alt(980, 300), 0.9)
    elif name == "tear_dusk":
        c.sky("dusk"); c.clouds(3, col=(255, 220, 226)); c.hills(780, ((150, 130, 180), (120, 104, 160))); px = alt(1300, 620)
        c.person(px, 940, 1.2, "girl", alt("right", "left")); c.tear(px + alt(40, -40), 690, 1.5); c.petals(30, (255, 230, 240))
    elif name == "horizon_birds":
        c.sky(alt("dawn", "day")); c.sun(alt(1500, 420), 760, 170); c.clouds(5); c.birds(8); c.rect(-10, 800, W + 10, H + 10, alt((150, 196, 226), (130, 200, 214)), None); c.line([(0, 800), (W, 800)], INK, 4)
        for k in range(12): c.line([(c.r.uniform(0, W - 200), 830 + k * 18), (c.r.uniform(200, W), 830 + k * 18)], (255, 255, 255, 110), 3)
    elif name == "wings":
        c.sky("day"); c.clouds(5); c.sun(alt(300, 1620), 220, 80); px = alt(960, 1040); c.wings(px, 500, 1.5); c.person(px, 760, 1.0, "boy", "back", "out"); c.plane(alt(1480, 420), 300, 1.1); c.birds(4)
    elif name == "red_thread":
        c.sky(alt("pink", "sunset")); c.clouds(3); c.ground(840, (236, 220, 200)); c.person(420, 930, 1.1, "girl", "right", "reach"); c.person(1500, 930, 1.1, "boy", "left", "reach")
        pts = [(540 + k * 42, 690 + math.sin(k / 2.4) * 46) for k in range(21)]; c.line(pts, (240, 90, 110), 7); c.heart(960, 420, 2.0)
    elif name == "watching":
        c.sky(alt("sunset", "night")); (c.stars(100) if v else c.clouds(3, col=(255, 236, 220))); c.ground(840, alt((230, 200, 170), (70, 90, 140)))
        c.person(alt(1380, 540), 900, 0.9, "boy", "back"); c.person(alt(1560, 360), 900, 0.9, "girl", "back", hair=(180, 130, 100)); c.heart(alt(1470, 450), 560, 1.2); c.person(alt(430, 1500), 960, 1.2, "girl", alt("right", "left")); c.dots(alt("bl", "br"))
    elif name == "bike_road":
        c.sky("day"); c.clouds(4); c.hills(700); c.ground(800, (180, 226, 160)); c.road(); c.bike(960, 1000, 1.5); c.person(940, 860, 0.9, "girl", "back"); c.speed(10)
    elif name == "rooftops_sunset":
        c.sky("sunset"); c.sun(960, 700, 190, (255, 220, 160)); c.clouds(3, col=(255, 230, 214))
        for k in range(9): h = c.r.uniform(120, 300); c.rect(k * 220 - 20, 1080 - h, k * 220 + 200, 1090, (120, 110, 150), r=4)
        c.person(960, 800, 1.0, "girl", "left"); c.petals(26, (255, 236, 200))
    elif name == "letter":
        c.sky("mint"); c.rect(-10, 640, W + 10, H + 10, (226, 196, 160)); c.envelope(960, 520, 2.0)
        for k in range(8): c.heart(c.r.uniform(200, 1720), c.r.uniform(120, 400), c.r.uniform(0.5, 1.0), (255, 180, 196))
        c.line([(1320, 760), (1560, 860)], (255, 200, 90), 14); c.dots("br", (120, 200, 190, 70))
    elif name == "arms_open":
        c.sky("dawn"); c.sun(960, 420, 150); c.clouds(5); c.rect(-10, 820, W + 10, H + 10, (206, 206, 216)); c.line([(0, 760), (W, 760)], INK, 5)
        for k in range(0, W, 120): c.line([(k, 760), (k, 820)], INK, 4)
        c.person(960, 930, 1.2, "girl", "back", "out"); c.birds(5); c.petals(30, (255, 255, 255))
    elif name == "ending":
        c.sky("night"); c.stars(170, 760); c.moon(1560, 220); c.hills(800, ((60, 84, 140), (44, 64, 112))); c.school(520, 860, 0.55, clock=False); c.clover(1100, 420, 2.2, (150, 220, 160))
        for k in range(8): c.star(c.r.uniform(700, 1500), c.r.uniform(160, 700), c.r.uniform(8, 16), (255, 250, 200))
    elif name == "sea":
        c.sky(alt("day", "sunset")); c.sun(alt(1480, 440), 300, 110); c.clouds(4, col=alt((255, 255, 255), (255, 232, 216))); c.birds(5)
        c.rect(-10, 640, W + 10, H + 10, alt((120, 196, 226), (150, 170, 214)), None); c.line([(0, 640), (W, 640)], INK, 4)
        for k in range(14): c.line([(c.r.uniform(0, W - 260), 680 + k * 16), (c.r.uniform(260, W), 680 + k * 16)], (255, 255, 255, 120), 3)
        c.poly([(-20, 900)] + [(x, 880 + math.sin(x / 150) * 22) for x in range(0, W + 40, 40)] + [(W + 20, H + 20), (-20, H + 20)], (250, 232, 196))
        c.person(alt(620, 1300), 1000, 1.0, "girl", "back"); c.dots("br")
    elif name == "city_night":
        c.sky("night"); c.stars(110, 520); c.moon(alt(1560, 360), 210)
        for k in range(12):
            h = c.r.uniform(260, 620); x0 = k * 165 - 30; c.rect(x0, 980 - h, x0 + 150, 1090, (52, 62, 110), r=4)
            for wy in range(int(1000 - h), 960, 46):
                for wx in range(int(x0 + 18), int(x0 + 130), 38):
                    if c.r.random() < 0.55: c.rect(wx, wy, wx + 20, wy + 26, (255, 232, 150), None, r=3)
        c.rect(-10, 980, W + 10, H + 10, (40, 48, 90), None); c.lamp(alt(480, 1440), 990, 300); c.person(alt(640, 1280), 1010, 0.8, "girl", "back")
    elif name == "mountain":
        c.sky(alt("dawn", "mint")); c.sun(960, 470, 130); c.clouds(4)
        for x, hgt, col in ((520, 470, (150, 190, 214)), (1380, 520, (136, 180, 208)), (960, 390, (170, 206, 224))):
            c.poly([(x - 560, 860), (x, 860 - hgt), (x + 560, 860)], col); c.poly([(x - 90, 860 - hgt + 76), (x, 860 - hgt), (x + 90, 860 - hgt + 76), (x + 30, 860 - hgt + 60), (x - 20, 860 - hgt + 84)], (255, 255, 255), None)
        c.ground(840, (176, 222, 160)); c.grass(840, 140); c.person(alt(480, 1440), 950, 0.9, "boy", "back", "both")
    elif name == "window_rain":
        c.sky("rain"); c.rain(160, (255, 255, 255, 130)); c.rect(-10, -10, W + 10, 130, (236, 226, 214), None); c.rect(-10, H - 200, W + 10, H + 10, (236, 226, 214), None)
        for x in (0, 640, 1280, 1905): c.rect(x - 16, 110, x + 16, H - 190, (236, 226, 214), None)
        c.line([(0, 130), (W, 130)], INK, 5); c.line([(0, H - 200), (W, H - 200)], INK, 5)
        for _ in range(26): x, y = c.r.uniform(60, W - 60), c.r.uniform(180, H - 260); c.tear(x, y, c.r.uniform(0.7, 1.3))
        c.rect(alt(1300, 420), H - 290, alt(1500, 620), H - 200, (255, 255, 255), r=10); c.ell(alt(1400, 520), H - 300, 60, 14, (255, 255, 255, 120), None); c.person(alt(520, 1400), H - 60, 1.2, "girl", "back")
    elif name == "balloons":
        c.sky(alt("day", "pink")); c.clouds(5); c.sun(alt(300, 1620), 220, 80)
        for k, col in enumerate(((255, 150, 160), (255, 220, 120), (150, 214, 190), (170, 190, 255), (255, 190, 220), (200, 170, 240))):
            x, y = 420 + k * 220 + c.r.uniform(-40, 40), c.r.uniform(260, 520)
            c.line([(x, y + 80), (x + c.r.uniform(-30, 30), y + 300)], INK, 3); c.ell(x, y, 62, 78, col); c.ell(x - 20, y - 26, 12, 18, (255, 255, 255, 150), None)
        c.ground(860, (190, 230, 170)); c.flowers(870, 40); c.person(alt(760, 1160), 950, 1.0, "girl", "front", "both"); c.person(alt(1160, 760), 950, 1.0, "boy", "front", "wave")
    else:
        raise KeyError(name)


# scenes that take the second look by themselves (other light, other places); the rest are mirrored
OWN_VARIANT = {"smile_tear", "shooting_star", "path_leaves", "umbrella_wait", "clover", "bench_sunset", "shield", "rain_together",
               "photos", "blossom_meet", "tear_dusk", "horizon_birds", "wings", "red_thread", "watching", "sea", "city_night",
               "mountain", "window_rain", "balloons"}
SCENES = ("opening", "rain_meadow", "school_bell", "window_quiet", "calling", "classroom_heart", "farewell_train", "corridor_pass",
          "sunny_field", "smile_tear", "shooting_star", "path_leaves", "umbrella_wait", "clover", "bench_sunset", "shield",
          "rain_together", "photos", "blossom_meet", "tear_dusk", "horizon_birds", "wings", "red_thread", "watching", "bike_road",
          "rooftops_sunset", "letter", "arms_open", "sea", "city_night", "mountain", "window_rain", "balloons", "ending")
# lines without a known word take turns through these
GENERAL = ("sunny_field", "horizon_birds", "bike_road", "mountain", "sea", "rooftops_sunset", "blossom_meet", "arms_open",
           "balloons", "city_night", "path_leaves", "bench_sunset")
# a song with a look of its own takes GENERAL_USED of these and the ones above, so that two songs do not show
# the same landscapes
GENERAL_MORE = ("shooting_star", "window_quiet", "letter", "school_bell")
GENERAL_USED = 11
# a word in the line -> scenes that go with it (the first that is not the scene before it). Earlier rows win.
WORDS: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (("傘", "守護", "守候", "原地", "等你", "等待", "等候"), ("umbrella_wait",)),
    (("淋",), ("rain_together", "rain_meadow")),
    (("雨",), ("rain_meadow", "rain_together", "umbrella_wait", "window_rain")),
    (("窗",), ("window_rain", "window_quiet")),
    (("鐘聲", "下課", "學校", "校園", "教室", "上課", "課堂"), ("school_bell", "classroom_heart", "corridor_pass")),
    (("呼喚", "呼喊", "喊", "名字", "姓名"), ("calling",)),
    (("聽不見", "沒有聽見", "沉默", "安靜", "無聲", "寂寞", "孤單", "想你", "想念", "思念"), ("window_quiet", "letter")),
    (("離別", "告別", "再見", "分手", "離開", "車站", "送別", "道別"), ("farewell_train", "tear_dusk")),
    (("流星", "星", "夜空", "銀河", "願望", "月光", "月亮"), ("shooting_star",)),
    (("幸運", "幸福", "奇蹟"), ("clover", "blossom_meet")),
    (("遇見", "相遇", "邂逅", "擦肩"), ("corridor_pass", "blossom_meet")),
    (("註定", "命運", "緣分", "牽"), ("red_thread",)),
    (("翅膀", "雙翼", "飛", "自由"), ("wings", "horizon_birds")),
    (("天際", "天空", "遠方", "地平線", "天邊"), ("horizon_birds", "mountain")),
    (("淚", "哭泣", "失去", "心碎", "痛", "傷", "苦", "難過"), ("tear_dusk", "smile_tear")),
    (("微笑", "笑", "哭"), ("smile_tear",)),
    (("對抗", "保護", "勇敢", "決定", "世界"), ("shield",)),
    (("一幕", "畫面", "照片", "回憶", "記憶", "真心"), ("photos", "path_leaves")),
    (("忘記", "遺忘", "曾經", "從前", "過去", "當時"), ("path_leaves", "photos")),
    (("靠近", "靠得", "身邊", "陪", "一起", "肩膀", "擁抱"), ("bench_sunset", "rain_together")),
    (("愛上", "喜歡", "心動", "暗戀", "愛情", "戀"), ("classroom_heart", "bench_sunset")),
    (("感謝", "謝謝", "勇氣", "信", "寫", "紙", "日記", "千言萬語"), ("letter",)),
    (("青春", "旅行", "旅程", "路上", "單車", "腳踏車"), ("bike_road",)),
    (("夕陽", "黃昏", "日落", "美麗", "晚霞"), ("rooftops_sunset", "sea")),
    (("海", "浪", "沙灘", "港口", "船"), ("sea",)),
    (("城市", "街", "霓虹", "路燈", "夜晚", "深夜", "黑夜", "夜裡"), ("city_night",)),
    (("山", "風", "雲"), ("mountain", "horizon_birds")),
    (("氣球", "快樂", "慶祝", "生日", "歡笑"), ("balloons",)),
    (("最好", "陽光", "晴", "太陽", "燦爛", "美好", "春天", "花"), ("sunny_field", "blossom_meet")),
    (("自己", "夢", "未來", "希望", "明天"), ("arms_open", "horizon_birds")),
    (("她", "別人", "祝福"), ("watching",)),
    (("愛",), ("classroom_heart", "bench_sunset", "red_thread", "blossom_meet")),
)


def _simple(text: str) -> str:
    """Traditional and Simplified lines find the same words."""
    try:
        from ..lyric_align import _t2s
        table = _t2s()
    except Exception:  # noqa: BLE001  (the cards work without the table; Simplified lines then get general scenes)
        table = {}
    # 妳 is 你 here, and the 星 of 星期 (a weekday) is no star
    return "".join(table.get(ch, ch) for ch in str(text or "").replace("妳", "你").replace("星期", ""))


def pick(parts: Sequence[Tuple[str, str]], seed: int = 0) -> List[Tuple[str, int]]:
    """parts: (kind, text) in timeline order, kind "intro" | "outro" | "interlude" | anything else. Returns (scene, look)
    for each: never the scene of the part before, and a scene used before comes back in its other look.
    seed is the song's (0: the plain choice); the same parts and seed always give the same answer."""
    words = [(tuple(_simple(w) for w in ws), scs) for ws, scs in WORDS]
    general: Sequence[str] = GENERAL
    if seed:        # the song's own choice: which general scenes, in which order, and which of a word's scenes first
        r = random.Random(f"pick:{int(seed)}")
        pool = list(GENERAL + GENERAL_MORE)
        r.shuffle(pool)
        general = pool[:GENERAL_USED]
        words = [(ws, tuple(r.sample(scs, len(scs)))) for ws, scs in words]
    used: Dict[str, int] = {}
    out: List[Tuple[str, int]] = []
    turn = 0
    last = ""
    for kind, text in parts:
        if kind == "intro":
            name = "opening"
        elif kind == "outro":
            name = "ending"
        else:
            line = "" if kind == "interlude" else _simple(text)
            options: List[str] = []
            for ws, scs in words:
                if any(w in line for w in ws):
                    options += [s for s in scs if s not in options]
            # the least used of the scenes that fit, not the one just shown; else the next general scene
            options = [s for s in options if s != last]
            if options:
                name = min(options, key=lambda s: (used.get(s, 0), options.index(s)))
            else:
                name = general[turn % len(general)]
                turn += 1
                if name == last:
                    name = general[turn % len(general)]
                    turn += 1
        out.append((name, used.get(name, 0) % LOOKS))
        used[name] = used.get(name, 0) + 1
        last = name
    return out


# One tone for all cards of a song (the MV page's 色調): the same drawing in other colours.
TONES = ("fresh", "warm", "night", "manga")
# A scene used again in a song: look 1 is its other light (or, for a scene with one light, its mirror image);
# looks 2 and 3 are those two again, the other way round and with the small things elsewhere.
LOOKS = 4


def _tone(im: Image.Image, tone: str) -> Image.Image:
    if tone == "warm":      # faded, warm paper
        im = ImageEnhance.Color(im).enhance(0.62)
        r, g, b = im.split()
        im = Image.merge("RGB", (r.point(lambda v: min(255, int(v * 1.05 + 6))), g.point(lambda v: int(v * 0.97 + 2)),
                                 b.point(lambda v: int(v * 0.84))))
    elif tone == "night":   # evening blue
        im = ImageEnhance.Color(im).enhance(0.8)
        r, g, b = im.split()
        im = Image.merge("RGB", (r.point(lambda v: int(v * 0.66)), g.point(lambda v: int(v * 0.76)),
                                 b.point(lambda v: min(255, int(v * 0.96 + 10)))))
    elif tone == "manga":   # black and white print
        im = ImageEnhance.Contrast(ImageOps.autocontrast(im.convert("L"), cutoff=1)).enhance(1.15).convert("RGB")
    return im


def song_seed(key: str) -> int:
    """The seed of a song's look from something that names the song (never 0, the plain look)."""
    return zlib.crc32(str(key).encode("utf-8")) % 2000000000 + 1


def valid_card(name: object) -> bool:
    """A scene of the first cards, or a card put together from parts (cardworld)."""
    return isinstance(name, str) and (name in SCENES or cardworld.parse(name) is not None)


def draw(name: str, look: int = 0, tone: str = "fresh", seed: int = 0, world: object = None) -> Image.Image:
    """The card as a 1920x1080 picture. The same name, look, tone, seed and world always give the same
    picture. A name from cardworld.plan() is drawn in the song's world; a scene name is one of the first
    cards (seed: the song's, song_style; 0 draws the plain look)."""
    if tone not in TONES:
        raise KeyError(tone)
    if cardworld.parse(name):
        return _tone(cardworld.draw(name, world, int(seed or 0)), tone)   # type: ignore[arg-type]
    if name not in SCENES:
        raise KeyError(name)
    look = int(look or 0) % LOOKS
    again, look = look // 2, look % 2
    seed = int(seed or 0)
    own = name in OWN_VARIANT
    turn = random.Random(f"scene:{seed}:{name}") if seed else None
    flip = bool(turn and turn.random() < 0.5)             # this song has the scene the other way round
    first = 1 if (turn and own and turn.random() < 0.5) else 0   # ... and starts with its other light
    v = (look ^ first) if own else 0
    mirror = bool(look and not own) ^ flip ^ bool(again and own)
    c = C(zlib.crc32(name.encode()) % 100000 + v + (seed % 999983) * 3 + again * 7919, song_style(seed), mirrored=mirror)
    _scene(name, c, v)
    return _tone(c.finish(mirror=mirror), tone)


# ---- which of a project's photos are cards -------------------------------------------------------------
# <project>/cards.json, beside photos.json: the fingerprint of every card drawn for the project (the same
# fingerprint as the photo list's), the tone they were drawn in and the seed of the song's look. A photo the user puts over a card has
# another fingerprint, so it is never taken for a card; a card that moves to another slot stays one.

def record_path(illust_dir: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(illust_dir)), "cards.json")


def read_record(illust_dir: str) -> Dict[str, object]:
    out: Dict[str, object] = {"tone": "", "cards": {}, "seed": None, "world": None, "round": 0}
    try:
        with open(record_path(illust_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
        got = data.get("cards")
        if isinstance(got, dict):
            out["cards"] = {str(k): v for k, v in got.items()
                            if isinstance(v, dict) and valid_card(v.get("card")) and v.get("tone") in TONES}
        if data.get("tone") in TONES:
            out["tone"] = data["tone"]
        if isinstance(data.get("seed"), int) and data["seed"] >= 0:
            out["seed"] = data["seed"]
        if cardworld.valid_world(data.get("world")):
            out["world"] = data["world"]
        if isinstance(data.get("round"), int) and 0 <= data["round"] < 100000:
            out["round"] = data["round"]
    except (OSError, ValueError, AttributeError):
        pass
    return out


def write_record(illust_dir: str, tone: str, found: Dict[str, Dict[str, object]], seed: object = None,
                 world: object = None, rnd: int = 0) -> None:
    """rnd counts how often the song's cards were taken out: each time the song starts with another look."""
    fp = record_path(illust_dir)
    tmp = fp + "." + secrets.token_hex(4) + ".tmp"
    data: Dict[str, object] = {"version": 1, "tone": tone if tone in TONES else "", "cards": found, "round": int(rnd or 0)}
    if isinstance(seed, int) and found:      # the look belongs to the cards that are there; with none left it starts anew
        data["seed"] = seed
        if world:
            data["world"] = world
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, fp)


# ---- what the songs before used ------------------------------------------------------------------------
# <library>/cards_history.json: the worlds of the last songs that got cards, newest last, so that the next
# song's world can keep away from them (cardworld.choose_world).
HISTORY = 12


def history_path(library_root: object) -> str:
    return os.path.join(str(library_root), "cards_history.json")


def read_history(library_root: object) -> List[Dict[str, object]]:
    try:
        with open(history_path(library_root), "r", encoding="utf-8") as f:
            got = json.load(f).get("songs")
        return [h for h in got if isinstance(h, dict) and isinstance(h.get("slug"), str) and cardworld.valid_world(h.get("world"))][-HISTORY:]
    except (OSError, ValueError, AttributeError, TypeError):
        return []


def note_history(library_root: object, slug: str, world: object) -> None:
    if not cardworld.valid_world(world):
        return
    songs = [h for h in read_history(library_root) if h.get("slug") != slug] + [{"slug": slug, "world": world}]
    fp = history_path(library_root)
    tmp = fp + "." + secrets.token_hex(4) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "songs": songs[-HISTORY:]}, f, indent=1)
        os.replace(tmp, fp)
    except OSError:
        pass
