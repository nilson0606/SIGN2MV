"""The premium picture cards' shots that are put together from one or two painted cards
(cardworld.POST_FRAMES): two halves side by side, the view through a window, photos lying on the view,
a snow globe, a memory in faded colours, a tilted view. cardworld.draw() comes here for them.
"""
from __future__ import annotations

import math
import random
import zlib
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from . import cardworld as cw

W, H = cw.W, cw.H


def compose(spec: str, world: Dict[str, Any], seed: int = 0) -> Image.Image:
    place, light, wth, subject, prop, frame, pos, n = cw.parse(spec)  # type: ignore[misc]
    r = random.Random(zlib.crc32(spec.encode()) + int(seed) % 999983)
    ink = cw.LINES[world["line"]][0] or (70, 76, 100)

    def inner(**kw) -> Image.Image:
        sp = cw.card(kw.get("place", place), kw.get("light", light), kw.get("weather", wth), kw.get("subject", subject),
                     kw.get("prop", prop), kw.get("frame", "mid"), kw.get("pos", pos), n)
        return cw._paint(sp, world, seed).im.resize((W, H), Image.LANCZOS)

    im = {"split": _split, "window": _window, "photo": _photo, "globe": _globe, "memory": _memory, "tilt": _tilt}[frame](
        inner, world, r, place=place, light=light, subject=subject, prop=prop, n=n)
    im = cw._finish_im(im.convert("RGB"), ink, world["border"])
    return cw._finish_standard(im, zlib.crc32(spec.encode()))


def _other_place(world, place):
    rooms = cw.INDOOR + cw.INDOOR_STD
    out = [p for p in world["places"] if p not in rooms and p.split(".")[:2] != place.split(".")[:2]]
    return out or [place]


def _split(inner, world, r, place, light, subject, n, **_):
    """Each of the two in a half of the card, somewhere else: the lead on the left, the other on the right."""
    there = _other_place(world, place)
    left = inner(subject=("solo_front", "solo_think", "solo_look", "solo_heart")[n % 4], pos="c", prop="none")
    right = inner(place=there[n % len(there)], subject=("other_front", "other_away")[(n // 2) % 2], pos="c", prop="none",
                  light=light if light == "night" else ("dusk" if n % 2 else light))
    out = Image.new("RGB", (W, H))
    out.paste(right.crop((440, 0, 1480, H)), (880, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (1050, 0), (870, H), (0, H)], fill=255)
    shifted = Image.new("RGB", (W, H))
    shifted.paste(left.crop((440, 0, 1480, H)), (0, 0))
    out.paste(shifted, (0, 0), mask)
    ImageDraw.Draw(out).line([(1050, -10), (870, H + 10)], fill=(255, 255, 255), width=16)
    return out


def _window(inner, world, r, light, n, **_):
    """The card seen from a room, through its window."""
    view = inner(frame="wide").filter(ImageFilter.GaussianBlur(1.6))
    dark = light in ("night", "dusk")
    wall = (58, 50, 76) if dark else (150, 124, 120)
    out = Image.new("RGB", (W, H), wall)
    d = ImageDraw.Draw(out, "RGBA")
    for y in range(0, H, 6):                      # the wall, a little lighter near the window
        t = abs(y - 470) / 610.0
        d.line([(0, y), (W, y)], fill=tuple(int(c * (1.08 - 0.22 * t)) for c in wall), width=6)
    x0, y0, x1, y1 = 330, 110, 1590, 800
    out.paste(view.resize((x1 - x0, int((x1 - x0) * H / W))).crop((0, 10, x1 - x0, 10 + y1 - y0)), (x0, y0))
    d = ImageDraw.Draw(out, "RGBA")
    frame = (236, 222, 204) if not dark else (176, 164, 170)
    d.rectangle([x0 - 26, y0 - 26, x1 + 26, y1 + 26], outline=frame, width=30)
    d.line([((x0 + x1) // 2, y0), ((x0 + x1) // 2, y1)], fill=frame, width=18)
    d.line([(x0, y0 + 250), (x1, y0 + 250)], fill=frame, width=14)
    d.rectangle([x0 - 70, y1 + 26, x1 + 70, y1 + 62], fill=frame)                 # the sill
    d.rectangle([x0 - 70, y1 + 62, x1 + 70, y1 + 74], fill=tuple(int(c * 0.8) for c in frame))
    cloth = tuple(world[world["lead"]]["low"])
    cloth = tuple(int(c * (0.62 if dark else 0.95)) for c in cloth)
    for sx in (0, 1):                             # curtains, drawn back
        xa = x0 - 60 if sx == 0 else x1 + 60
        xb = x0 + 210 if sx == 0 else x1 - 210
        d.polygon([(xa, y0 - 50), (xb, y0 - 50), (xa + (70 if sx == 0 else -70), y1 - 180), (xa + (130 if sx == 0 else -130), y1 + 20), (xa, y1 + 20)], fill=cloth)
        for i in range(4):
            xx = xa + (i * 34 + 20) * (1 if sx == 0 else -1)
            d.line([(xx, y0 - 40), (xa + (40 + i * 14) * (1 if sx == 0 else -1), y1 - 180)], fill=tuple(int(c * 0.86) for c in cloth), width=5)
    d.rectangle([x0 - 90, y0 - 74, x1 + 90, y0 - 46], fill=tuple(int(c * 0.7) for c in frame))   # the rail
    px = (x0 + 190) if n % 2 else (x1 - 190)       # a plant on the sill
    d.polygon([(px - 46, y1 + 26), (px + 46, y1 + 26), (px + 36, y1 - 44), (px - 36, y1 - 44)], fill=(214, 130, 104))
    for a in (-0.9, -0.45, 0, 0.45, 0.9):
        d.ellipse([px + math.sin(a) * 80 - 26, y1 - 150 - math.cos(a) * 60 - 40, px + math.sin(a) * 80 + 26, y1 - 60 - math.cos(a) * 60 + 6], fill=(104, 170, 120) if not dark else (70, 118, 100))
    if dark:                                      # a lamp's light in the room
        glow = Image.new("RGB", (W, H), (255, 214, 150))
        m = Image.new("L", (W // 8, H // 8), 0)
        ImageDraw.Draw(m).ellipse([10, 96, 110, 190], fill=70)
        out = Image.composite(glow, out, m.filter(ImageFilter.GaussianBlur(12)).resize((W, H)))
    return out


def _polaroid(pic: Image.Image, wd: int, angle: float) -> Image.Image:
    ht = int(wd * H / W)
    card = Image.new("RGBA", (wd + 56, ht + 150), (252, 250, 244, 255))
    card.paste(pic.resize((wd, ht), Image.LANCZOS), (28, 28))
    ImageDraw.Draw(card).rectangle([28, 28, 28 + wd, 28 + ht], outline=(210, 204, 196), width=2)
    return card.rotate(angle, resample=Image.BICUBIC, expand=True)


def _photo(inner, world, r, place, light, subject, n, **_):
    """Photos lying on the view: the card itself, and one of somewhere else behind it."""
    back = inner(frame="wide", subject="none", prop="none").filter(ImageFilter.GaussianBlur(14))
    back = ImageEnhance.Brightness(back).enhance(0.72)
    there = _other_place(world, place)
    second = _polaroid(inner(place=there[n % len(there)], subject="none", prop="none", frame="wide", light="golden" if light != "golden" else "day"), 560, 9 if n % 2 else -9)
    first = _polaroid(inner(frame="mid"), 900, -5 if n % 2 else 5)
    out = back.convert("RGBA")
    for card, (cx, cy) in ((second, (1420 if n % 2 else 500, 330)), (first, (860 if n % 2 else 1060, 560))):
        sh = Image.new("RGBA", card.size, (0, 0, 0, 0))
        sh.paste((20, 16, 30, 120), (0, 0), card.split()[3])
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        x, y = cx - card.size[0] // 2, cy - card.size[1] // 2
        out.alpha_composite(sh, (max(0, x + 14), max(0, y + 18)))
        out.alpha_composite(card, (max(0, x), max(0, y)))
    return out.convert("RGB")


def _globe(inner, world, r, n, **_):
    """The card inside a snow globe on a table."""
    back = inner(frame="wide", subject="none", prop="none").filter(ImageFilter.GaussianBlur(16))
    out = ImageEnhance.Brightness(back).enhance(0.8)
    d = ImageDraw.Draw(out, "RGBA")
    wood = r.choice(((176, 128, 100), (150, 110, 92), (206, 156, 122)))
    d.rectangle([0, 860, W, H], fill=wood)
    for y in (900, 960, 1030):
        d.line([(0, y), (W, y)], fill=tuple(int(c * 0.86) for c in wood), width=4)
    cx, cy, rr = 960, 470, 380
    d.ellipse([cx - 420, 930, cx + 420, 1040], fill=(30, 20, 30, 70))
    scene = inner(frame="wide").crop((420, 0, 1500, H)).resize((rr * 2, rr * 2), Image.LANCZOS)
    mask = Image.new("L", (rr * 2, rr * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, rr * 2 - 1, rr * 2 - 1], fill=255)
    out.paste(scene, (cx - rr, cy - rr), mask)
    d = ImageDraw.Draw(out, "RGBA")
    for _ in range(90):                           # the snow in it
        a, q = r.uniform(0, 6.283), rr * math.sqrt(r.random()) * 0.96
        x, y, z = cx + math.cos(a) * q, cy + math.sin(a) * q, r.uniform(3, 8)
        d.ellipse([x - z, y - z, x + z, y + z], fill=(255, 255, 255, r.randint(170, 250)))
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, 230), width=10)
    d.arc([cx - rr + 40, cy - rr + 40, cx + rr - 40, cy + rr - 40], 200, 250, fill=(255, 255, 255, 200), width=18)
    d.arc([cx - rr + 70, cy - rr + 70, cx + rr - 70, cy + rr - 70], 20, 50, fill=(255, 255, 255, 110), width=12)
    base = r.choice(((196, 84, 84), (84, 110, 160), (120, 96, 84)))
    d.polygon([(cx - 300, 820), (cx + 300, 820), (cx + 350, 960), (cx - 350, 960)], fill=base)
    d.rectangle([cx - 350, 950, cx + 350, 976], fill=tuple(int(c * 0.8) for c in base))
    d.rectangle([cx - 150, 866, cx + 150, 916], fill=(250, 214, 110))
    return out


def _memory(inner, world, r, **_):
    """The card as something remembered: faded to brown, the edges gone white."""
    im = inner(frame="wide")
    sepia = ImageOps.colorize(ImageOps.grayscale(im), (70, 46, 40), (255, 244, 222))
    out = Image.blend(im, sepia, 0.78)
    edge = Image.new("L", (96, 54), 0)
    px = edge.load()
    for y in range(54):
        for x in range(96):
            dd = max(abs(x - 47.5) / 47.5, abs(y - 26.5) / 26.5) ** 3
            px[x, y] = int(min(1.0, max(0.0, (dd - 0.45) / 0.5)) * 235)
    out = Image.composite(Image.new("RGB", (W, H), (255, 250, 240)), out, edge.resize((W, H), Image.BICUBIC))
    d = ImageDraw.Draw(out, "RGBA")
    for _ in range(7):                            # scratches of an old film
        x = r.uniform(120, W - 120)
        d.line([(x, r.uniform(0, 300)), (x + r.uniform(-6, 6), r.uniform(600, H))], fill=(255, 255, 255, 60), width=2)
    return out


def _tilt(inner, world, r, n, **_):
    """The card with the camera leaning to one side."""
    im = inner(frame="mid")
    big = im.resize((int(W * 1.24), int(H * 1.24)), Image.LANCZOS).rotate(-7 if n % 2 else 7, resample=Image.BICUBIC)
    x, y = (big.size[0] - W) // 2, (big.size[1] - H) // 2
    return big.crop((x, y, x + W, y + H))
