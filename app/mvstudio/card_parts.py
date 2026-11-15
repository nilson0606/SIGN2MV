"""More parts for the picture cards' put-together places (cardworld's "terrain.landmark.front"):
eighteen more terrains and sixteen more foregrounds, painted like cardworld's own, and a hundred more
landmarks, each one line of shapes in LANDMARKS (the shapes of card_icons, in a box 100 wide whose bottom
middle is where the landmark stands; 100 units are 400 pixels at size 1, and y can go above 0 for tall things).

A landmark line is  name|flags|terrains|words|shapes:  flags "w" for a wide one (painted once, in the middle);
terrains the only terrains it makes sense on (empty: any); words what a lyric line says to get it.
cardworld takes everything in from here; nothing in this file knows cardworld.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, Tuple

from . import card_icons

W, H, S = 1920, 1080, 2


def P(v):
    return int(round(v * S))


def _mix(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a[:3], b[:3]))


# ------------------------------------------------------------------------------------------- the terrains
def tr_lake(k):
    k.ridge(590, 70, (150, 170, 200), far=0.7); k.ridge(660, 44, (130, 180, 170), far=0.45)
    k.band(700, 866, (176, 218, 238), (112, 178, 216))
    for i in range(13):
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, 714 + i * 12), (x + k.r.uniform(100, 320), 714 + i * 12)], (255, 255, 255, 100), 3)
    k.band(860, H, (176, 222, 160), (130, 196, 134)); k.ridge(862, 10, (176, 222, 160), rough=0.6)
    return {"ground": 930, "base": 868}


def tr_terraces(k):
    k.ridge(590, 60, (140, 190, 170), far=0.6)
    for i in range(6):
        pts = k.ridge(650 + i * 34, 22, _mix((156, 210, 140), (104, 172, 110), i / 6), step=20, rough=0.8, far=max(0.0, 0.36 - i * 0.08))
        k.stroke(pts, (255, 255, 255, 90), 3)
    k.band(852, H, (166, 214, 140), (124, 186, 116)); k.ridge(852, 8, (166, 214, 140), rough=0.7)
    return {"ground": 910, "base": 858}


def tr_harbor(k):
    k.band(630, 852, (150, 206, 230), (90, 160, 206))
    for i in range(5):       # cranes on the far side
        x, col = 120 + i * 420 + k.r.uniform(-60, 60), k.far((200, 110, 100), 0.45)
        k.stroke([(x, 640), (x, 470)], col, 10, raw=True); k.stroke([(x - 30, 480), (x + 150, 440)], col, 8, raw=True)
        k.stroke([(x + 140, 444), (x + 140, 540)], col, 3, raw=True)
        k.rect(x - 40, 610, x + 60, 645, k.far((120, 132, 170), 0.4), line=False, raw=True)
    for _ in range(3):
        x, y = k.r.uniform(200, W - 200), k.r.uniform(700, 790)
        k.poly([(x - 80, y), (x + 80, y), (x + 60, y + 28), (x - 60, y + 28)], (255, 252, 244)); k.rect(x - 30, y - 30, x + 30, y, (226, 100, 100))
    k.band(850, H, (206, 204, 210), (176, 174, 188)); k.stroke([(0, 850), (W, 850)], None, k.lw)
    for x in range(140, W, 330):
        k.rect(x - 16, 822, x + 16, 862, (84, 92, 120), r=8)
    return {"ground": 930, "base": 854}


def tr_canyon(k):
    for y, far in ((560, 0.6), (640, 0.35)):
        x = -60.0
        while x < W:
            wd, h = k.r.uniform(200, 420), k.r.uniform(80, 240)
            k.poly([(x, 800), (x + 20, y + 240 - h), (x + wd - 30, y + 240 - h), (x + wd, 800)], k.far((214, 130, 100), far), line=False, raw=True)
            for j in range(3):
                k.stroke([(x + 20, y + 262 - h + j * 26), (x + wd - 22, y + 262 - h + j * 26)], k.far((190, 104, 84), far), 4, raw=True)
            x += wd + k.r.uniform(-20, 120)
    k.band(790, H, (240, 190, 140), (214, 150, 110)); k.ridge(790, 10, (240, 190, 140), rough=0.7)
    return {"ground": 900, "base": 800}


def tr_bamboo(k):
    k.band(560, 822, (176, 216, 172), (140, 196, 150))
    for layer, far in ((0, 0.5), (1, 0.2)):
        for _ in range(26):
            x, wd = k.r.uniform(0, W), 12 + layer * 8
            k.rect(x - wd / 2, -20, x + wd / 2, 830, k.far((120, 180, 110), far), line=False, raw=True)
            for y in range(60, 820, 110):
                k.stroke([(x - wd / 2, y + x % 50), (x + wd / 2, y + x % 50)], k.far((90, 150, 90), far), 3, raw=True)
            for _ in range(3):
                yy, sx = k.r.uniform(40, 500), k.r.choice((-1, 1))
                k.poly([(x, yy), (x + sx * 90, yy - 30), (x + sx * 70, yy + 6)], k.far((130, 196, 120), far), line=False, raw=True)
    k.band(820, H, (176, 206, 150), (140, 180, 120))
    return {"ground": 900, "base": 828}


def tr_orchard(k):
    k.ridge(640, 40, (140, 196, 170), far=0.55)
    k.band(700, H, (176, 220, 150), (134, 196, 128))
    for row in range(3):
        y, sc = 740 + row * 40, 0.42 + row * 0.12
        for x in range(-40 + row * 60, W + 100, 190 + row * 40):
            k.tree(x, y, sc, far=0.32 - row * 0.12)
            for _ in range(4):
                k.ell(x + k.r.uniform(-60, 60) * sc, y - k.r.uniform(180, 300) * sc, 9 * sc + 3, 9 * sc + 3, (240, 110, 90), line=False)
    k.ridge(832, 10, (170, 216, 150), rough=0.6)
    return {"ground": 904, "base": 838}


def tr_lavender(k):
    k.ridge(640, 44, (150, 180, 200), far=0.6); k.ridge(700, 20, (150, 200, 160), far=0.3)
    k.band(740, H, (190, 170, 230), (150, 120, 204))
    for i in range(-14, 15):                 # rows running to one point on the horizon
        k.poly([(960 + i * 26, 744), (960 + i * 26 + 10, 744), (960 + i * 190 + 80, H + 20), (960 + i * 190, H + 20)], (132, 104, 190), line=False)
    for _ in range(170):
        x, y = k.r.uniform(0, W), k.r.uniform(770, H)
        k.ell(x, y, 5 + (y - 760) / 40, 3 + (y - 760) / 60, (214, 190, 250), line=False)
    return {"ground": 900, "base": 764}


def tr_rooftops(k):
    for i in range(22):
        x, h = i * 96 - 40 + k.r.uniform(-10, 10), k.r.uniform(60, 240)
        k.rect(x, 800 - h, x + 84, 820, k.far((130, 140, 176), 0.5), line=False, raw=True)
        k.windows(x + 10, 812 - h, x + 76, 800, cw=14, ch=18, gap=12, lit=0.45)
    x = -30.0
    while x < W:                             # nearer roofs
        wd, y = k.r.uniform(170, 260), k.r.uniform(744, 790)
        col = k.r.choice(((204, 120, 104), (150, 160, 190), (120, 150, 150), (214, 160, 110)))
        k.rect(x + 8, y, x + wd - 8, 850, k.far((240, 226, 210), 0.15), raw=True); k.poly([(x, y), (x + wd / 2, y - 60), (x + wd, y)], k.far(col, 0.15), raw=True)
        x += wd
    k.band(840, H, (214, 206, 204), (184, 176, 184))
    k.rect(-10, 818, W + 10, 846, (236, 230, 226))          # the parapet
    for y in (910, 1000):
        k.stroke([(0, y), (W, y)], (196, 188, 190), 3)
    return {"ground": 930, "base": 848}


def tr_island(k):
    k.band(640, 900, (146, 218, 228), (80, 180, 206))
    for _ in range(3):
        x, wd = k.r.uniform(60, W - 420), k.r.uniform(180, 380)
        pts = [(x + wd * j / 12, 664 - math.sin(j / 12 * math.pi) * wd * 0.22) for j in range(13)]
        k.poly(pts, k.far((120, 190, 140), 0.45), line=False, raw=True)
    for i in range(14):
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, 690 + i * 14), (x + k.r.uniform(120, 340), 690 + i * 14)], (255, 255, 255, 110), 3)
    pts = [(x, 876 + math.sin(x / 190 + 0.6) * 18) for x in range(-30, W + 60, 30)]
    k.poly([(x, y - 12) for x, y in pts] + [(W + 30, H + 30), (-30, H + 30)], (255, 255, 255), line=False)
    k.poly(pts + [(W + 30, H + 30), (-30, H + 30)], (252, 236, 196), line=False)
    return {"ground": 940, "base": 892}


def tr_waterfall(k):
    k.ridge(300, 40, (128, 150, 150), far=0.25)
    for _ in range(26):
        x, y = k.r.uniform(0, W), k.r.uniform(360, 720)
        k.stroke([(x, y), (x + k.r.uniform(-24, 24), y + k.r.uniform(40, 110))], k.far((100, 124, 128), 0.25), 5, raw=True)
    k.band(800, 884, (166, 222, 238), (110, 186, 220))
    cx = 960 + k.r.choice((-1, 1)) * k.r.uniform(120, 260)
    k.poly([(cx - 70, 292), (cx + 70, 292), (cx + 100, 812), (cx - 100, 812)], (240, 250, 255), line=False, e=True)
    for i in range(7):
        k.stroke([(cx - 60 + i * 20, 300), (cx - 84 + i * 28, 800)], (200, 230, 250), 4, e=True)
    for _ in range(14):
        k.ell(cx + k.r.uniform(-150, 150), 806 + k.r.uniform(-14, 14), k.r.uniform(20, 46), k.r.uniform(12, 24), (255, 255, 255, 200), line=False, e=True)
    k.band(874, H, (150, 206, 150), (116, 180, 124)); k.ridge(876, 8, (150, 206, 150), rough=0.7)
    return {"ground": 940, "base": 884, "x": cx - 560 if cx > 960 else cx + 560}


def tr_savanna(k):
    k.ridge(690, 16, (214, 190, 130), far=0.5)
    for _ in range(5):                       # flat-topped trees far away
        x, s = k.r.uniform(60, W - 60), k.r.uniform(0.5, 0.9)
        k.stroke([(x, 734), (x, 734 - 110 * s)], k.far((120, 96, 80), 0.35), 10 * s, raw=True)
        k.ell(x, 734 - 130 * s, 120 * s, 30 * s, k.far((110, 150, 100), 0.35), line=False, raw=True)
    k.band(724, H, (240, 214, 140), (220, 184, 110))
    for _ in range(130):
        x, y = k.r.uniform(0, W), k.r.uniform(760, H)
        k.stroke([(x, y), (x + k.r.uniform(-8, 8), y - k.r.uniform(20, 50))], (200, 164, 96), 3)
    return {"ground": 900, "base": 744}


def tr_aurora(k):
    if k.dark:
        for i, col in enumerate(((120, 255, 190), (130, 220, 255), (190, 150, 255))):
            ph = k.r.uniform(0, 6)
            pts = [(x, 200 + i * 70 + math.sin(x / 260 + ph) * 60) for x in range(-40, W + 80, 40)]
            for j in range(10):
                k.d.line([(P(x), P(y + j * 22)) for x, y in pts], fill=col + (58 - j * 5,), width=P(24))
    k.ridge(650, 60, (200, 214, 236), far=0.5)
    k.band(720, H, (240, 248, 255), (206, 222, 244)); k.ridge(722, 14, (240, 248, 255), rough=0.5)
    for _ in range(8):
        x, y = k.r.uniform(0, W), k.r.uniform(760, 850)
        k.poly([(x - 30, y), (x, y - 50), (x + 34, y)], (220, 236, 250))
    return {"ground": 900, "base": 744}


def tr_reeds(k):
    k.ridge(660, 26, (150, 190, 170), far=0.55)
    k.band(700, H, (176, 214, 190), (130, 184, 160))
    for _ in range(9):
        x, y, rx = k.r.uniform(60, W - 60), k.r.uniform(740, 1040), k.r.uniform(120, 300)
        k.d.ellipse([P(x - rx), P(y - rx * 0.14), P(x + rx), P(y + rx * 0.14)], fill=k.sky3[1] + (170,))
    for _ in range(110):
        x, y, h = k.r.uniform(0, W), k.r.uniform(730, 870), k.r.uniform(40, 110)
        k.stroke([(x, y), (x + k.r.uniform(-10, 10), y - h)], (130, 166, 110), 4); k.ell(x, y - h - 8, 4, 12, (150, 110, 80), line=False)
    return {"ground": 910, "base": 770}


def tr_tracks(k):
    k.ridge(660, 34, (140, 196, 170), far=0.55); k.band(720, H, (176, 220, 160), (136, 196, 130))
    k.band(768, 802, (184, 174, 174), (160, 150, 156))              # the embankment
    for x in range(-20, W + 40, 44):
        k.rect(x, 776, x + 16, 798, (120, 96, 84), line=False)
    for y in (779, 795):
        k.stroke([(0, y), (W, y)], (90, 96, 120), 5)
    for x in range(100, W, 380):
        k.stroke([(x, 792), (x, 540)], (110, 100, 104), 8); k.stroke([(x - 40, 566), (x + 40, 566)], (110, 100, 104), 6)
        k.stroke([(x - 36, 566), (x + 154, 600), (x + 344, 566)], (90, 96, 120), 2); k.stroke([(x + 36, 566), (x + 226, 596), (x + 416, 566)], (90, 96, 120), 2)
    k.ridge(832, 10, (170, 216, 150), rough=0.6)
    return {"ground": 910, "base": 838}


def tr_oldtown(k):
    k.ridge(660, 30, (150, 180, 180), far=0.6)
    x = -40.0
    while x < W:
        wd, h = k.r.uniform(200, 300), k.r.uniform(100, 170)
        k.rect(x + 16, 800 - h, x + wd - 16, 808, k.far((246, 240, 230), 0.15), raw=True)
        k.poly([(x - 10, 800 - h + 8), (x + 26, 800 - h - 44), (x + wd - 26, 800 - h - 44), (x + wd + 10, 800 - h + 8)], k.far((84, 90, 110), 0.15), raw=True)
        k.rect(x + wd / 2 - 24, 730, x + wd / 2 + 24, 808, k.far((150, 96, 84), 0.15), raw=True)
        for t in (0.25, 0.75):
            k.ell(x + wd * t, 800 - h + 34, 11, 15, (236, 80, 70), e=k.dark)
        x += wd
    k.band(806, H, (214, 210, 206), (180, 176, 182)); k.stroke([(0, 806), (W, 806)], None, k.lw)
    for y in (880, 960, 1040):
        k.stroke([(0, y), (W, y)], (190, 186, 190), 3)
    return {"ground": 900, "base": 814}


def tr_park(k):
    k.ridge(640, 30, (140, 196, 176), far=0.6)
    for x in range(-60, W + 200, 230):
        k.tree(x + k.r.uniform(-30, 30), 804, k.r.uniform(0.8, 1.1), col=k.r.choice(((118, 190, 132), (140, 200, 120), (104, 176, 140))), far=0.25)
    k.band(792, H, (176, 224, 160), (134, 198, 134))
    k.poly([(-40, 962), (W + 40, 904), (W + 40, 996), (-40, 1064)], (236, 222, 196), line=False)
    return {"ground": 890, "base": 806}


def tr_highway(k):
    k.ridge(640, 50, (150, 180, 200), far=0.65); k.ridge(700, 24, (160, 200, 160), far=0.35)
    k.band(740, H, (196, 214, 150), (160, 190, 120))
    vx = 960 + k.r.choice((-1, 1)) * k.r.uniform(80, 260)
    k.poly([(vx - 8, 742), (vx + 8, 742), (960 + 640, H + 20), (960 - 640, H + 20)], (120, 124, 140), line=False)
    for i in range(7):                       # the dashes of the middle line, nearer and larger
        t0, t1 = (i / 7) ** 2.2, ((i + 0.5) / 7) ** 2.2
        (x0, y0), (x1, y1) = (vx + (960 - vx) * t0, 742 + t0 * 340), (vx + (960 - vx) * t1, 742 + t1 * 340)
        k.poly([(x0 - 2 - t0 * 14, y0), (x0 + 2 + t0 * 14, y0), (x1 + 2 + t1 * 14, y1), (x1 - 2 - t1 * 14, y1)], (255, 246, 200), line=False)
    for sx in (-1, 1):                       # poles along the road
        for i in range(5):
            t = ((i + 1) / 6) ** 2
            x, y = vx + (960 - vx) * t + sx * (40 + t * 760), 744 + t * 250
            k.stroke([(x, y), (x, y - 60 - t * 300)], (110, 100, 104), 3 + t * 8)
    return {"ground": 900, "base": 764, "x": vx - 560 if vx > 960 else vx + 560}


def tr_boardwalk(k):
    k.band(620, 860, (150, 214, 236), (90, 170, 214))
    for i in range(16):
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, 640 + i * 14), (x + k.r.uniform(120, 360), 640 + i * 14)], (255, 255, 255, 110), 3)
    k.band(852, H, (214, 176, 140), (186, 146, 116))
    for y in range(884, H, 46):
        k.stroke([(0, y), (W, y)], (170, 130, 104), 3)
    for x in range(0, W + 1, 150):
        k.rect(x - 10, 762, x + 10, 858, (160, 120, 96), r=4)
    k.rect(-10, 760, W + 10, 776, (176, 136, 108)); k.stroke([(0, 812), (W, 812)], (160, 120, 96), 6)
    return {"ground": 930, "base": 858}


def tr_cloudsea(k):
    for i in range(3):                       # peaks standing out of the clouds
        x = 200 + i * 640 + k.r.uniform(-120, 120)
        k.poly([(x - 220, 780), (x - 20, 520 + i * 36), (x + 30, 560 + i * 36), (x + 240, 780)], k.far((120, 130, 170), 0.5), line=False, raw=True)
    for row in range(4):
        for x in range(-80, W + 160, 150):
            k.cloud(x + k.r.uniform(-40, 40), 690 + row * 36 + k.r.uniform(-10, 10), 1.5 + row * 0.25)
    k.poly([(-30, 884), (300, 856), (900, 874), (1500, 850), (W + 30, 880), (W + 30, H + 30), (-30, H + 30)], (156, 160, 170))
    for _ in range(40):
        x, y = k.r.uniform(0, W), k.r.uniform(900, H)
        k.stroke([(x, y), (x + k.r.uniform(-6, 6), y - k.r.uniform(10, 26))], (120, 170, 120), 3)
    return {"ground": 934, "base": 868}


TERRAIN_FN: Dict[str, Callable] = {
    "lake": tr_lake, "terraces": tr_terraces, "harbor": tr_harbor, "canyon": tr_canyon, "bamboo": tr_bamboo, "orchard": tr_orchard,
    "lavender": tr_lavender, "rooftops": tr_rooftops, "island": tr_island, "waterfall": tr_waterfall, "savanna": tr_savanna,
    "aurora": tr_aurora, "reeds": tr_reeds, "tracks": tr_tracks, "oldtown": tr_oldtown, "park": tr_park, "highway": tr_highway,
    "boardwalk": tr_boardwalk, "cloudsea": tr_cloudsea}
# what a line says to get a terrain (these go before cardworld's own words, so "湖畔" is the lake, not the peaks)
TERRAIN_WORDS = {
    "lake": ("湖畔", "湖面", "湖水", "湖心", "湖邊", "lakeside"), "terraces": ("梯田", "茶園", "採茶", "茶山"),
    "harbor": ("港口", "海港", "港灣", "漁港", "harbor", "harbour"), "canyon": ("峽谷", "山谷", "深谷", "canyon", "valley"),
    "bamboo": ("竹林", "竹子", "翠竹"), "orchard": ("果園", "葡萄園", "橘子園"), "lavender": ("薰衣草", "花海", "花田"),
    "rooftops": ("屋頂", "天台", "頂樓", "rooftop"), "island": ("小島", "島嶼", "孤島", "island"),
    "waterfall": ("瀑布", "飛瀑", "waterfall"), "savanna": ("非洲", "荒原", "曠野"), "aurora": ("極光", "北極", "冰原", "aurora"),
    "reeds": ("蘆葦", "濕地", "沼澤", "水鄉"), "tracks": ("鐵道", "鐵軌", "軌道", "rails"),
    "oldtown": ("古城", "古鎮", "老城", "古街", "江南", "長安"), "park": ("公園", "草坪", "林蔭"),
    "highway": ("公路", "高速公路", "highway"), "boardwalk": ("棧道", "木棧道", "海堤", "堤防"),
    "cloudsea": ("雲海", "雲端", "雲上", "山頂", "頂峰")}
# groups of terrains, for "this only makes sense on ..." (cardworld's own terrains among them)
WATER = ("coast", "cliff", "river", "lake", "harbor", "island", "boardwalk", "reeds")
URBAN = ("town", "skyline", "plaza", "oldtown", "park", "harbor", "rooftops")
# the terrains on which only a few landmarks make sense
TERRAIN_ALLOWS = {
    "cloudsea": ("hotair", "jet", "airship", "helicopter", "observatory", "telescope", "cabin", "radiotower", "cablecar", "bigtree", "torii",
                 "pagoda", "temple", "signpost", "benchlamp", "watchtower", "dish", "windturbine", "pinetree", "boulder", "stonelantern",
                 "monument", "wishtree", "skylanterns", "bicycle", "baretree"),
    "rooftops": ("watertower", "radiotower", "dish", "billboard", "telescope", "piano", "greenhouse", "benchlamp", "helicopter", "airship",
                 "hotair", "jet", "skyscraper", "eiffel", "crane", "stage", "terrace", "easel", "powerpole", "skylanterns", "hoop",
                 "bicycle", "signpost", "bigtree", "heartsign", "porchswing")}
# more terrains for cardworld's own landmarks that were tied to a few
MORE_ON = {"lighthouse": ("island", "harbor", "boardwalk"), "sailboats": ("lake", "harbor", "island", "boardwalk"), "lifeguard": ("island", "boardwalk"),
           "jetty": ("lake", "harbor", "island", "reeds"), "snowman": ("aurora",), "scarecrow": ("orchard", "terraces", "savanna"),
           "barn": ("orchard", "terraces", "savanna", "lavender"), "farbridge": ("lake", "harbor", "boardwalk", "oldtown"),
           "trainpass": ("tracks", "park", "savanna", "highway", "lavender", "orchard"), "vending": ("oldtown", "park", "harbor", "tracks", "highway"),
           "phonebooth": ("oldtown", "park", "harbor", "tracks", "highway"), "shelter": ("oldtown", "park", "harbor", "tracks", "highway"),
           "stage": ("park", "harbor", "boardwalk", "oldtown"), "carousel": ("park", "harbor", "boardwalk"),
           "ferris": ("park", "harbor", "boardwalk", "island", "lake")}
# landmarks a song only gets when its words ask for them (a song's world is not given one of these by chance)
KEYWORD_ONLY = ("dinosaur", "robot", "launchpad", "pyramid", "igloo", "grave", "hospital", "factory", "gasstation", "crane", "trafficlight",
                "billboard", "truck", "tractor", "dish", "powerpole", "stadium", "helicopter", "tunnel", "crossing", "hoop", "goal", "pool",
                "bbq", "doghouse", "beehive", "shipwreck", "circus", "rollercoaster", "pirateship", "caravan", "monument", "statue", "museum",
                "skyscraper", "apartment", "hotel", "cinema", "store", "postoffice", "ticketbooth", "foodcart", "fruitstand", "icestand",
                "balloonstand", "aquarium", "dragonboat", "koiflags", "skylanterns", "greatwall", "eiffel", "arch", "palace", "yurt", "sled",
                "surfboard", "airship", "buoy", "cave", "raft", "seesaw", "baretree", "weddingarch")
DRY = ("dunes", "canyon", "savanna")          # no blossom trees, fountains ... here (cardworld's NOT_ON["dunes"])


# ----------------------------------------------------------------------------------------- the foregrounds
def fr_reeds(k, front):
    if front:
        for _ in range(70):
            x = k.r.uniform(0, W)
            if 480 < x < 1440 and k.r.random() < 0.75:
                continue                     # the middle stays open
            h, lean = k.r.uniform(120, 300), k.r.uniform(-30, 30)
            k.stroke([(x, H + 10), (x + lean, H - h)], (120, 160, 100), 7); k.ell(x + lean, H - h - 26, 9, 30, (150, 110, 80))


def fr_tulips(k, front):
    if front:
        for i in range(34):
            x, h = i * 58 + k.r.uniform(-16, 16), k.r.uniform(30, 110)
            col = k.r.choice(((240, 100, 110), (255, 200, 90), (255, 150, 180), (190, 140, 230), (255, 255, 255)))
            k.stroke([(x, H + 10), (x, H - h)], (104, 170, 110), 7); k.ell(x, H - h - 18, 20, 24, col)
            k.poly([(x - 20, H - h - 26), (x - 10, H - h - 48), (x, H - h - 32), (x + 10, H - h - 48), (x + 20, H - h - 26)], col, line=False)


def fr_sunflowers(k, front):
    if front:
        for x in [k.r.uniform(-20, 420) for _ in range(5)] + [k.r.uniform(1500, W + 20) for _ in range(5)]:
            h = k.r.uniform(200, 420)
            k.stroke([(x, H + 10), (x, H - h)], (104, 160, 100), 10); k.ell(x + 40, H - h * 0.5, 44, 18, (120, 180, 110))
            for a in range(12):
                k.ell(x + math.cos(a * 0.524) * 56, H - h + math.sin(a * 0.524) * 56, 22, 22, (255, 210, 80), line=False)
            k.ell(x, H - h, 40, 40, (150, 104, 80))


def fr_bushes(k, front):
    if not front:
        for x in (k.r.uniform(20, 240), k.r.uniform(260, 420), k.r.uniform(1500, 1660), k.r.uniform(1680, 1900)):
            col = k.r.choice(((118, 190, 132), (104, 176, 124), (140, 200, 130)))
            for dx, dy, rr in ((-60, 0, 60), (0, -34, 76), (64, -4, 62)):
                k.ell(x + dx, 850 + dy, rr, rr * 0.8, col)
            for _ in range(6):
                k.ell(x + k.r.uniform(-90, 90), 850 + k.r.uniform(-70, 10), 8, 8, (255, 190, 210), line=False)


def fr_vines(k, front):
    if front:
        for _ in range(16):
            x, h = k.r.choice((k.r.uniform(-10, 520), k.r.uniform(1400, W + 10))), k.r.uniform(120, 420)
            k.stroke([(x, -10), (x + k.r.uniform(-20, 20), h)], (96, 150, 100), 5)
            for y in range(20, int(h), 44):
                k.ell(x + k.r.choice((-18, 18)), y, 20, 12, (116, 184, 120), line=False)


def _string(k, y0, sag, items):
    pts = [(x, y0 + math.sin(max(0.0, min(1.0, (x + 40) / (W + 80))) * math.pi) * sag) for x in range(-40, W + 41, 40)]
    k.stroke(pts, (90, 90, 110), 3)
    for i in range(items):
        x = (i + 0.5) * W / items
        yield x, y0 + math.sin((x + 40) / (W + 80) * math.pi) * sag


def fr_lanternline(k, front):
    if front:
        for x, y in _string(k, 60, 90, 9):
            k.rect(x - 6, y, x + 6, y + 10, (150, 110, 80), line=False)
            if k.dark:
                k.d.ellipse([P(x - 56), P(y - 20), P(x + 56), P(y + 92)], fill=(255, 200, 120, 40))
            k.ell(x, y + 36, 24, 28, (236, 84, 74), e=k.dark); k.rect(x - 8, y + 62, x + 8, y + 70, (250, 206, 96), line=False)


def fr_bunting(k, front):
    if front:
        cols = ((255, 150, 160), (255, 220, 120), (150, 214, 190), (170, 190, 255), (255, 190, 220))
        for i, (x, y) in enumerate(_string(k, 50, 80, 18)):
            k.poly([(x - 30, y), (x + 30, y), (x, y + 60)], cols[i % 5])


def fr_wires(k, front):
    if not front:
        for x in (150, W - 150):
            k.stroke([(x, 880), (x, 250)], (110, 100, 104), 12); k.stroke([(x - 70, 290), (x + 70, 290)], (110, 100, 104), 9)
        for dy in (0, 26):
            k.stroke([(x, 290 + dy + math.sin(x / W * math.pi) * 60) for x in range(-40, W + 41, 40)], (80, 84, 104), 2)
        for _ in range(k.r.randint(2, 5)):
            x = k.r.uniform(400, 1500)
            y = 290 + math.sin(x / W * math.pi) * 60
            k.ell(x, y - 12, 12, 14, (70, 74, 96), line=False); k.ell(x + 8, y - 26, 8, 8, (70, 74, 96), line=False)


def fr_stones(k, front):
    if not front:
        for i in range(7):
            x, y = 220 + i * 250 + k.r.uniform(-40, 40), 960 + (i % 2) * 50
            k.ell(x, y, k.r.uniform(60, 90), k.r.uniform(18, 26), (200, 200, 208))


def fr_posts(k, front):
    if not front:
        for x in range(60, W + 1, 300):
            k.rect(x - 12, 770, x + 12, 860, (170, 130, 104), r=6)
        for x in range(60, W - 200, 300):
            k.stroke([(x, 790), (x + 150, 822), (x + 300, 790)], (214, 196, 170), 6)


def fr_snowdrift(k, front):
    if front:
        for _ in range(6):
            x, rx = k.r.uniform(0, W), k.r.uniform(200, 420)
            k.d.ellipse([P(x - rx), P(H - rx * 0.2), P(x + rx), P(H + rx * 0.3)], fill=(250, 252, 255))


def fr_shells(k, front):
    if front:
        for _ in range(9):
            x, y = k.r.choice((k.r.uniform(20, 560), k.r.uniform(1360, W - 20))), k.r.uniform(1000, 1060)
            if k.r.random() < 0.5:
                col = k.r.choice(((255, 190, 170), (255, 226, 200), (240, 170, 190)))
                k.d.pieslice([P(x - 36), P(y - 36), P(x + 36), P(y + 36)], 180, 360, fill=k.c(col), outline=k.edge(k.c(col)), width=P(k.lw))
            else:
                pts = [(x + math.cos(a * 0.628 - 1.57) * (34 if a % 2 == 0 else 14), y - 10 + math.sin(a * 0.628 - 1.57) * (34 if a % 2 == 0 else 14)) for a in range(10)]
                k.poly(pts, (255, 160, 120))


def fr_candles(k, front):
    if front:
        for x in [k.r.uniform(30, 460) for _ in range(5)] + [k.r.uniform(1460, W - 30) for _ in range(5)]:
            h = k.r.uniform(50, 130)
            k.d.ellipse([P(x - 80), P(H - h - 110), P(x + 80), P(H - h + 50)], fill=(255, 214, 130, 44))
            k.rect(x - 16, H - h, x + 16, H + 10, (255, 250, 236), r=4); k.ell(x, H - h - 18, 9, 18, (255, 196, 90), line=False, e=True)


def fr_wheat(k, front):
    if front:
        for _ in range(80):
            x = k.r.uniform(0, W)
            if 520 < x < 1400 and k.r.random() < 0.6:
                continue
            h, lean = k.r.uniform(70, 200), k.r.uniform(-24, 24)
            k.stroke([(x, H + 10), (x + lean, H - h)], (214, 180, 100), 4)
            for j in range(4):
                k.ell(x + lean * (1 + j * 0.04), H - h - j * 14, 7, 11, (240, 204, 110), line=False)


def fr_stringlights(k, front):
    if front:
        for x, y in _string(k, 40, 110, 22):
            k.d.ellipse([P(x - 30), P(y - 16), P(x + 30), P(y + 44)], fill=(255, 236, 160, 50))
            k.ell(x, y + 14, 10, 13, (255, 240, 180), line=False, e=True)


def fr_clothesline(k, front):
    if front:
        cols = ((255, 255, 255), (170, 200, 240), (255, 190, 200), (255, 230, 150), (190, 230, 200))
        for i, (x, y) in enumerate(_string(k, 30, 70, 9)):
            if i in (3, 4, 5):
                continue                     # nothing hangs over the middle
            wd, h = k.r.uniform(50, 90), k.r.uniform(80, 150)
            k.rect(x - wd, y + 4, x + wd, y + h, cols[i % 5], r=6)
            for sx in (-1, 1):
                k.rect(x + sx * wd * 0.7 - 5, y - 8, x + sx * wd * 0.7 + 5, y + 12, (206, 156, 122), line=False)


FRONT_FN: Dict[str, Callable] = {
    "reeds": fr_reeds, "tulips": fr_tulips, "sunflowers": fr_sunflowers, "bushes": fr_bushes, "vines": fr_vines,
    "lanternline": fr_lanternline, "bunting": fr_bunting, "wires": fr_wires, "stones": fr_stones, "posts": fr_posts,
    "snowdrift": fr_snowdrift, "shells": fr_shells, "candles": fr_candles, "wheat": fr_wheat, "stringlights": fr_stringlights,
    "clothesline": fr_clothesline}
FRONT_ONLY = {"snowdrift": ("snow", "aurora", "peaks"), "shells": ("coast", "island", "boardwalk", "harbor", "cliff"),
              "wheat": ("wheat", "grass", "savanna", "orchard", "terraces"), "clothesline": ("town", "rooftops", "oldtown", "skyline"),
              "wires": ("town", "tracks", "highway", "grass", "wheat", "rooftops", "skyline", "oldtown"),
              "reeds": ("reeds", "lake", "river", "grass"), "lanternline": ("oldtown", "town", "plaza", "park", "harbor", "boardwalk"),
              "tulips": ("grass", "park", "lake", "town", "orchard", "river", "plaza"), "sunflowers": ("grass", "wheat", "orchard", "park", "lake", "savanna"),
              "vines": ("woods", "bamboo", "waterfall", "park", "oldtown", "orchard", "canyon"), "bushes": ("grass", "park", "town", "lake", "plaza", "orchard", "river", "tracks", "oldtown")}


# -------------------------------------------------------------------------------------------- the landmarks
LANDMARKS = """
pagoda|||寶塔,佛塔,古塔,pagoda|r 38,80 62,100 H;p 30,80 50,70 70,80 E;r 40,58 60,70 H;p 32,58 50,48 68,58 E;r 42,36 58,48 H;p 34,36 50,26 66,36 E;r 44,16 56,26 H;p 36,16 50,4 64,16 E;l 50,4 50,-8 I 1.5;r 46,86 54,100 N 2;w 46,60 54,68;w 47,38 53,46
temple|||寺廟,廟宇,廟口,古寺,temple|r 16,58 84,100 E;p 2,60 22,38 78,38 98,60 M;r 22,62 30,100 R;r 70,62 78,100 R;r 42,70 58,100 N 2;l 6,58 2,52 M 2;l 94,58 98,52 M 2;w 32,70 38,82;w 62,70 68,82
torii|||鳥居,神社,shrine|l 24,100 26,30 R 5;l 76,100 74,30 R 5;p 8,24 92,24 96,16 4,16 R;r 18,38 82,44 R 1;r 47,24 53,38 R
arch|||凱旋門,拱門,城門|r 14,22 86,100 H;r 10,14 90,24 H 1;p 36,100 36,62 43,50 57,50 64,62 64,100 M;l 14,36 86,36 J 1.5
eiffel|||巴黎,艾菲爾,paris,eiffel|p 50,-30 56,20 44,20 Z;p 44,20 56,20 64,60 36,60 Z;p 36,60 64,60 82,100 70,100 50,74 30,100 18,100 Z;r 34,58 66,62 I;r 42,18 58,21 I;l 50,-30 50,-40 I 1
pyramid||dunes,savanna,canyon|金字塔,埃及,pyramid|p 0,100 50,20 100,100 D;p 50,20 100,100 70,100 J
igloo||snow,aurora|冰屋,雪屋,igloo|p 10,100 14,74 30,58 50,52 70,58 86,74 90,100 W;r 42,78 58,100 M 6;l 14,80 86,80 L 1;l 22,66 78,66 L 1;l 36,56 36,66 L 1;l 64,56 64,66 L 1;l 50,66 50,80 L 1
hut|||茅屋,草屋,茅草屋|r 26,66 74,100 J;p 16,68 50,36 84,68 D;r 44,78 56,100 N 2;w 30,74 40,84;l 22,64 50,40 78,64 N 1
treehouse||grass,woods,park,orchard,lake,river,bamboo|樹屋,treehouse|l 50,100 50,40 N 7;e 50,30 44 30 F;r 34,40 66,62 J;p 30,40 50,26 70,40 E;w 44,46 56,56;l 60,62 66,100 N 1.5;l 54,62 60,100 N 1.5
skyscraper||skyline,town,plaza,harbor,rooftops,park|摩天大樓,大廈,大樓,辦公室,skyscraper|r 34,-30 66,100 Z;r 44,-44 56,-30 Z;l 50,-44 50,-58 I 1;w 38,-22 62,-14;w 38,-6 62,2;w 38,10 62,18;w 38,26 62,34;w 38,42 62,50;w 38,58 62,66;w 38,74 62,82
factory|||工廠,煙囪,加班,factory|r 10,60 90,100 A;p 10,60 30,44 30,60 50,44 50,60 70,44 70,60 A;r 74,10 86,60 E;e 82,2 8 6 W;e 90,-8 10 7 W;w 18,72 30,84;w 40,72 52,84;r 62,76 76,100 I
hospital|||醫院,病房,病床,hospital|r 20,30 80,100 W;r 44,18 56,30 W;r 48,19 52,29 R;r 45,22 55,26 R;w 26,38 38,48;w 62,38 74,48;w 26,56 38,66;w 62,56 74,66;r 42,76 58,100 L 2
store||town,skyline,plaza,oldtown,park,harbor,grass,highway|便利商店,小店,雜貨店,商店,超商,store,shop|r 14,50 86,100 W;r 10,40 90,54 G 2;r 10,46 90,50 O;w 20,62 52,90;r 60,62 80,100 L 1;g 50,76 30
cinema|||電影院,電影,散場,movie,cinema|r 12,30 88,100 E;r 20,40 80,62 W 1;r 8,24 92,32 D 2;r 40,74 60,100 I 2;e 20,28 2 2 W;e 35,28 2 2 W;e 50,28 2 2 W;e 65,28 2 2 W;e 80,28 2 2 W;l 28,51 72,51 K 2;g 50,50 26
circus|||馬戲團,小丑,雜耍,circus|p 10,100 14,60 86,60 90,100 W;p 14,60 50,20 86,60 R;p 26,100 28,60 38,60 36,100 R;p 64,100 62,60 72,60 74,100 R;p 44,100 46,72 54,72 56,100 I;l 50,20 50,8 I 1;p 50,8 62,11 50,14 Y
rollercoaster|w||雲霄飛車,過山車,roller coaster|l -30,30 -30,100 A 1.5;l 30,10 30,100 A 1.5;l 90,40 90,100 A 1.5;l 0,60 0,100 A 1.5;l 60,70 60,100 A 1.5;l 120,80 120,100 A 1.5;l -60,90 -30,30 0,60 30,10 60,70 90,40 120,80 160,90 R 4;r 22,2 40,10 Y 2
waterwheel||river,lake,reeds,terraces,waterfall,grass|水車,磨坊|r 50,50 92,100 J;p 46,52 71,30 96,52 E;e 34,66 30 30 N;e 34,66 22 22 L;l 34,36 34,96 N 2;l 4,66 64,66 N 2;l 13,45 55,87 N 2;l 55,45 13,87 N 2;e 34,66 4 4 I
archbridge||river,lake,reeds,park,oldtown,bamboo,grass|拱橋,小橋,石橋,橋上|p -10,100 -10,78 20,64 50,58 80,64 110,78 110,100 90,100 80,84 50,76 20,84 10,100 A;l -10,74 20,60 50,54 80,60 110,74 I 1.5
watchtower|||瞭望台,高塔,瞭望,塔頂|l 36,100 42,20 N 3;l 64,100 58,20 N 3;l 38,80 62,60 N 1.5;l 62,80 38,60 N 1.5;l 40,50 60,30 N 1.5;l 60,50 40,30 N 1.5;r 30,2 70,20 J 1;p 26,2 50,-14 74,2 E;w 44,6 56,16
billboard||town,skyline,plaza,highway,rooftops,tracks,harbor|廣告牌,看板,招牌,billboard|l 40,100 40,60 I 3;l 60,100 60,60 I 3;r 8,14 92,60 W 2;r 14,20 86,54 P 1;e 34,36 10 10 Y;l 50,30 78,30 W 3;l 50,42 70,42 W 3;g 50,36 30
trafficlight||town,skyline,plaza,highway,oldtown,tracks,park|紅綠燈,紅燈,綠燈,斑馬線,十字路口,traffic|l 50,100 50,40 I 3;r 40,0 60,44 K 4;e 50,8 6 6 R;e 50,22 6 6 Y;e 50,36 6 6 G
statue|||雕像,銅像,塑像,statue|r 32,76 68,100 A 1;r 38,68 62,76 A 1;p 40,68 42,38 58,38 60,68 Z;l 58,42 72,20 Z 3;l 42,42 32,58 Z 3;e 50,26 9 9 Z
monument|||紀念碑,石碑,碑文,monument|p 42,100 44,10 50,0 56,10 58,100 A;r 30,90 70,100 A 1;l 46,40 54,40 I 1;l 46,48 54,48 I 1;l 46,56 54,56 I 1
grave|||墓碑,墳前,墳墓,長眠,安息,grave|p 34,100 34,56 40,44 50,40 60,44 66,56 66,100 A;l 50,52 50,74 I 2;l 43,60 57,60 I 2;e 28,98 10 4 F;e 74,98 12 4 F;l 76,96 76,84 G 1.5;e 76,82 4 4 P
palace|||宮殿,皇宮,殿堂,王宮,palace|r 6,60 94,100 H;p 0,62 14,40 86,40 100,62 D;r 24,24 76,42 H;p 16,26 30,6 70,6 84,26 D;r 16,62 22,100 R;r 44,70 56,100 R 1;r 78,62 84,100 R;w 28,70 36,84;w 64,70 72,84
greatwall|w|peaks,grass,canyon,savanna,woods,snow|長城,城牆,great wall|p -150,100 -150,70 -90,50 -30,66 30,40 90,60 150,36 210,60 250,50 250,100 A;r -100,32 -80,54 A;r 20,22 40,44 A;r 140,18 160,40 A;l -150,68 -90,48 -30,64 30,38 90,58 150,34 210,58 250,48 I 2
yurt||grass,savanna,snow,dunes,peaks,lake|蒙古包,草原上,牧民,yurt|p 14,100 14,70 86,70 86,100 W;p 10,70 34,44 66,44 90,70 W;e 50,44 16 5 O;l 14,84 86,84 R 2;r 42,74 58,100 E 2;l 14,70 86,70 B 1.5
shipwreck||coast,island,cliff,reeds|沉船,擱淺,殘骸,shipwreck|p 10,100 22,62 88,74 96,100 N;l 40,66 30,10 N 3;l 30,24 56,34 N 2;p 30,12 30,34 52,30 C;l 22,80 90,88 I 1.5;e 60,86 3 3 I;e 74,88 3 3 I
bigship|w|coast,island,harbor,cliff,boardwalk|郵輪,輪船,大船,遠洋,cruise|p -40,60 140,60 124,84 -24,84 W;p -40,60 140,60 138,64 -38,64 R;r -10,40 110,60 W;r 10,26 90,40 W;r 30,6 44,26 R;r 56,6 70,26 R;e 37,0 8 5 A;w -2,46 6,54;w 14,46 22,54;w 30,46 38,54;w 46,46 54,54;w 62,46 70,54;w 78,46 86,54;w 94,46 102,54
rowboat||lake,river,reeds,coast,island,harbor,waterfall|小船,划船,木舟,扁舟,搖櫓,rowboat|p 6,84 94,84 82,100 18,100 N;p 6,84 94,84 90,88 10,88 J;l 30,70 70,96 J 2;l 26,66 34,74 J 3
fishingboat||coast,island,harbor,cliff,boardwalk,lake|漁船,漁火,出海,打魚,漁夫|p 4,78 96,78 84,100 16,100 B;r 36,56 64,78 W 1;w 42,60 52,70;l 66,78 66,30 N 2;p 66,30 66,50 86,50 R;l 20,78 14,54 N 1.5;g 47,65 14
surfboard||coast,island,boardwalk|衝浪,浪板,surf|p 44,100 40,50 44,22 50,10 56,22 60,50 56,100 Y;l 50,14 50,98 O 2;r 42,58 58,64 R
beachumbrella||coast,island,boardwalk,dunes|陽傘,海灘,沙灘椅,度假,vacation,beach|l 50,100 50,30 W 2;p 6,40 50,6 94,40 R;p 28,40 50,6 40,40 W;p 60,40 50,6 72,40 W;r 62,84 96,90 B 1;l 66,90 62,100 I 1.5;l 92,90 96,100 I 1.5;l 62,84 54,68 B 2
hammock||coast,island,grass,woods,park,lake,orchard,bamboo|吊床,午睡,hammock|l 10,100 10,30 N 4;l 90,100 90,30 N 4;e 10,24 16 14 F;e 90,24 16 14 F;p 10,48 90,48 76,70 50,76 24,70 Y;l 10,48 50,76 90,48 O 1
palmtree||coast,island,dunes,boardwalk,harbor,savanna|椰子樹,椰林,棕櫚,熱帶,palm|l 52,100 48,60 54,24 N 4;p 54,24 20,14 4,30 30,22 F;p 54,24 88,12 100,30 76,22 F;p 54,24 30,0 14,6 36,12 F;p 54,24 76,-2 94,4 70,10 F;e 50,28 4 4 N;e 58,28 4 4 N
pinetree|||松樹,青松,蒼松,pine|r 46,80 54,100 N;p 20,82 50,50 80,82 F;p 26,58 50,30 74,58 F;p 32,36 50,8 68,36 F
willow||river,lake,reeds,park,oldtown,grass,town|柳樹,楊柳,垂柳,柳絮,willow|l 50,100 50,40 N 5;e 50,30 34 22 F;l 22,30 18,78 F 3;l 32,34 30,86 F 3;l 42,36 42,80 G 3;l 58,36 58,84 F 3;l 68,34 70,88 G 3;l 78,30 82,76 F 3
baretree|||枯樹,枯枝,凋零,乾枯,光禿|l 50,100 50,50 N 5;l 50,60 30,34 18,30 N 3;l 50,50 66,26 82,24 N 3;l 50,50 48,20 N 3;l 30,34 28,14 N 2;l 66,26 62,8 N 2;l 48,20 38,6 N 1.5
appletree||grass,orchard,park,wheat,town,lake|蘋果樹,果樹|r 45,60 55,100 N;e 50,36 40 32 F;e 30,34 4 4 R;e 50,20 4 4 R;e 68,36 4 4 R;e 42,50 4 4 R;e 62,52 4 4 R
ginkgo|||銀杏,杏樹|r 46,56 54,100 N;e 50,34 36 34 D;e 32,44 16 14 Y;e 68,26 16 14 Y;e 20,98 8 2 D;e 76,97 10 2 D
flowerbed|||花壇,花圃,花叢,百花|p 6,100 12,84 88,84 94,100 N;e 20,80 8 8 P;e 36,76 9 9 Y;e 52,80 8 8 R;e 68,76 9 9 V;e 82,80 8 8 P;e 28,84 6 5 F;e 60,84 6 5 F
boulder|||巨石,岩石,石頭,磐石|p 8,100 14,62 36,44 66,40 88,60 94,100 A;l 36,44 44,66 30,84 I 1;l 66,40 62,60 I 1;e 26,98 10 3 F
cave||peaks,cliff,canyon,woods,waterfall,snow,coast|山洞,洞穴,洞口,cave|p 0,100 6,50 30,26 64,20 92,46 100,100 A;p 30,100 32,66 42,50 58,50 68,66 70,100 K;l 30,26 38,40 I 1
pond||grass,park,woods,oldtown,bamboo,orchard,wheat|池塘,荷花,蓮花,荷塘,水塘,pond,lotus|e 50,92 50 9 U;e 26,90 10 3 F;e 64,94 12 3 F;l 44,90 44,84 G 1;e 44,86 5 5 Q;e 76,88 4 4 Q;e 84,92 6 2 F
tram|w|town,skyline,plaza,oldtown,harbor,park,tracks|路面電車,叮叮車,tram|l -80,40 180,40 I 1;l 50,56 60,40 I 1.5;r -30,56 130,94 G 4;r -30,56 130,66 C 3;w -22,68 -4,82;w 2,68 20,82;w 26,68 44,82;w 50,68 68,82;w 74,68 92,82;w 98,68 116,82;e 0,96 5 5 K;e 100,96 5 5 K
truck|||卡車,貨車,搬家,truck|r 4,50 64,92 W 2;r 64,62 96,92 B 3;w 70,66 86,78;e 20,94 8 8 K;e 50,94 8 8 K;e 82,94 8 8 K
caravan|||露營車,旅行車,房車,公路旅行|r 6,50 94,92 W 8;r 6,74 94,80 O;w 16,58 34,70;w 44,58 62,70;r 70,58 84,92 L 2;e 26,94 8 8 K;e 70,94 8 8 K
tractor||wheat,grass,orchard,terraces,savanna|拖拉機,農夫,耕田,耕耘,豐收,tractor|r 30,50 60,82 R 2;r 60,62 90,82 R 2;r 34,36 56,52 L 1;l 30,36 60,36 K 2;e 36,84 16 16 K;e 36,84 7 7 Y;e 80,88 10 10 K;e 80,88 4 4 Y;l 84,62 84,46 K 2
helicopter|w||直升機,helicopter|e 50,-30 22 12 R;p 68,-32 110,-36 110,-30 70,-24 R;l 104,-42 104,-26 K 2;w 36,-36 50,-26;l 20,-46 80,-46 K 2;l 50,-46 50,-42 K 2;l 40,-16 62,-16 K 1.5;l 44,-18 44,-16 K 1;l 58,-18 58,-16 K 1
airship|w||飛船,飛艇,airship|e 50,-40 46 16 W;p 90,-48 108,-58 108,-22 90,-32 R;r 36,-24 64,-16 B 2;l 20,-40 80,-40 R 2
cablecar|w|peaks,snow,cliff,woods,canyon,cloudsea,waterfall,terraces|纜車,索道,cable car|l -200,-60 300,10 I 1;l 46,-14 46,-26 I 1.5;r 30,-14 62,14 R 4;w 34,-8 44,2;w 48,-8 58,2;l 163,-2 163,-10 I 1.5;r 150,-2 176,22 Y 4
foodcart|||小吃攤,路邊攤,攤販,宵夜,消夜,攤子|g 50,50 26;r 14,60 86,90 J 2;p 6,40 94,40 86,26 14,26 R;p 30,40 34,26 42,26 42,40 W;p 58,40 58,26 66,26 70,40 W;l 18,40 18,60 I 2;l 82,40 82,60 I 2;e 28,94 7 7 K;e 72,94 7 7 K;e 40,56 6 4 W;e 60,56 6 4 W
flowershop||town,skyline,plaza,oldtown,park,harbor|花店,買花,花舖,florist|r 14,36 86,100 C;p 8,36 92,36 86,22 14,22 P;w 20,48 50,74;r 58,48 78,100 G 1;r 18,90 50,100 N 1;e 22,90 6 6 R;e 34,88 6 6 Y;e 46,90 6 6 V
bookshop||town,skyline,plaza,oldtown,park|書店,舊書,書攤,bookstore|r 14,36 86,100 T;r 10,28 90,38 N 1;w 20,48 54,78;r 62,50 80,100 N 1;l 24,56 50,56 R 3;l 24,64 50,64 Y 3;l 24,72 50,72 B 3
bakery||town,skyline,plaza,oldtown,park|麵包店,烘焙,出爐,bakery|r 14,36 86,100 J;p 8,38 92,38 86,24 14,24 O;p 22,38 24,24 34,24 34,38 W;p 50,38 50,24 60,24 62,38 W;g 37,62 20;w 20,48 54,76;r 62,50 80,100 N 1;e 30,68 6 4 D;e 44,68 6 4 D
seesaw||grass,park,plaza,town,coast|蹺蹺板,翹翹板,此起彼落,seesaw|p 44,100 50,80 56,100 R;l 6,92 94,68 B 4;l 12,90 12,82 K 2;l 88,70 88,62 K 2
hoop||plaza,town,skyline,park,grass,rooftops|籃球場,籃框,球場上,三分球|l 70,100 70,10 I 4;l 70,20 46,20 I 3;r 30,4 50,34 W 1;r 36,16 44,26 R;e 40,34 9 3 O;l 32,36 36,50 W 1;l 48,36 44,50 W 1;l 40,36 40,50 W 1
goal||grass,park,plaza|球門,射門,足球場,goal|l 10,40 24,56 24,100 A 1;l 90,40 76,56 76,100 A 1;l 24,56 76,56 A 1;l 24,70 76,70 A 1;l 24,84 76,84 A 1;l 40,56 40,100 A 1;l 60,56 60,100 A 1;l 10,100 10,40 W 3;l 90,100 90,40 W 3;l 10,40 90,40 W 3
pool|||游泳池,泳池,跳水,pool|r 0,84 100,100 U 4;r 4,88 96,100 L 3;l 20,80 20,96 A 2;l 30,80 30,96 A 2;l 20,84 30,84 A 1.5;l 60,92 76,92 W 2;l 84,94 94,94 W 2;r 70,70 96,76 W 1;l 92,76 92,86 A 2
picnic||grass,park,lake,orchard,coast,woods,lavender|野餐,郊遊,踏青,picnic|p 4,100 16,86 84,86 96,100 R;l 28,86 20,100 W 2;l 52,86 52,100 W 2;l 74,86 82,100 W 2;r 36,70 56,88 J 2;l 38,70 46,60 54,70 J 2;e 70,84 6 4 Y;r 20,78 26,88 G 2
bbq|||烤肉,燒烤,中秋,bbq|g 50,60 20;l 34,100 44,70 I 2;l 66,100 56,70 I 2;p 26,58 74,58 68,72 32,72 K;l 34,56 34,50 N 2;l 46,56 46,48 N 2;l 58,56 58,50 N 2;e 40,40 5 7 A;e 54,34 6 8 A
easel|||畫架,畫布,寫生,素描,easel|l 30,100 46,14 N 2.5;l 70,100 54,14 N 2.5;l 50,100 50,60 N 2;r 26,22 74,66 W 1;r 22,66 78,70 N;e 40,38 8 6 U;p 30,62 46,44 58,56 66,48 72,62 G
weddingarch|||花拱門,紅毯,新娘,新郎,結婚,婚紗|p 40,100 60,100 56,60 44,60 R;l 22,100 22,40 W 3;l 78,100 78,40 W 3;l 22,40 34,16 50,8 66,16 78,40 W 3;e 22,40 7 7 P;e 30,24 7 7 Q;e 50,8 8 8 P;e 70,24 7 7 Q;e 78,40 7 7 P;e 40,12 6 6 W;e 60,12 6 6 W
skylanterns|w||天燈,孔明燈,放天燈,祈福|g -100,-18 14;p -106,-10 -108,-28 -92,-28 -94,-10 O;g -40,-58 14;p -46,-50 -48,-68 -32,-68 -34,-50 X;g 10,-28 14;p 4,-20 2,-38 18,-38 16,-20 O;g 69,-72 12;p 64,-64 62,-80 76,-80 74,-64 X;g 120,-38 14;p 114,-30 112,-48 128,-48 126,-30 O;g 179,-66 12;p 174,-58 172,-74 186,-74 184,-58 X;g 47,0 16;p 40,10 38,-10 56,-10 54,10 O
sled||snow,aurora,peaks|雪橇,滑雪,sled|l 10,96 90,96 96,88 R 3;l 24,96 24,80 N 2;l 70,96 70,80 N 2;r 16,74 80,82 J 2;l 80,78 96,66 N 1.5
postoffice||town,skyline,plaza,oldtown,park,harbor|郵局,寄信,郵差,post office|r 14,40 86,100 C;p 8,42 50,20 92,42 G;r 40,70 60,100 G 1;w 20,54 34,68;w 66,54 80,68;r 6,80 16,100 R 3;r 4,76 18,82 R 2
museum|||博物館,美術館,展覽,畫展,museum,gallery|r 10,50 90,100 C;p 4,50 50,24 96,50 C;r 4,48 96,54 A;l 22,56 22,96 A 4;l 38,56 38,96 A 4;l 62,56 62,96 A 4;l 78,56 78,96 A 4;r 44,72 56,100 N 1;r 6,96 94,100 A
stadium|w||體育場,球場,演唱會,stadium|g -78,17 20;g 178,17 20;p -80,100 -100,56 200,56 180,100 A;e 50,56 150 14 Z;e 50,56 130 9 G;l -70,56 -78,20 I 2;l 170,56 178,20 I 2;r -90,12 -66,22 W 1;r 166,12 190,22 W 1
crane||skyline,town,harbor,plaza,rooftops,tracks|工地,吊車,起重機,蓋房子|l 44,100 44,-30 Y 3;l 56,100 56,-30 Y 3;l 44,80 56,60 Y 1.5;l 56,80 44,60 Y 1.5;l 44,40 56,20 Y 1.5;l 56,40 44,20 Y 1.5;l 44,0 56,-20 Y 1.5;l 10,-30 120,-30 Y 3;l 50,-46 10,-30 Y 1.5;l 50,-46 120,-30 Y 1.5;l 100,-30 100,10 I 1;r 94,10 106,18 I
windturbine||grass,coast,wheat,peaks,cliff,dunes,savanna,island,highway,terraces,cloudsea,lavender|風力發電,風機,風車群,turbine|l 50,100 50,10 W 3;p 50,10 46,-40 54,-40 W;p 50,10 92,30 88,38 W;p 50,10 8,30 12,38 W;e 50,10 4 4 A
powerpole|||電線桿,電線,電塔|l 50,100 50,0 N 3;l 26,10 74,10 N 3;l 32,24 68,24 N 2.5;l -40,22 26,10 I 0.8;l 74,10 140,22 I 0.8;l -40,34 32,24 I 0.8;l 68,24 140,34 I 0.8
dish|||衛星,天線,訊號,收訊,satellite,signal|r 38,92 62,100 A 1;l 50,100 50,60 I 4;p 20,30 80,50 62,70 28,60 W;e 50,48 24 12 L;l 50,48 68,22 I 1.5;e 68,22 3 3 R
buoy||coast,island,harbor,cliff,lake,boardwalk|浮標,浮球,buoy|e 50,100 30 4 L;p 30,100 38,66 62,66 70,100 R;r 38,74 62,84 W;l 50,66 50,36 I 2;g 50,30 14;e 50,30 6 6 Y
stump||woods,grass,park,orchard,bamboo,peaks,lake|樹樁,年輪,砍伐|l 30,96 20,100 N 3;l 70,96 80,100 N 3;r 30,70 70,100 N 3;e 50,70 20 7 J;e 50,70 12 4 N;e 50,70 5 2 J;l 62,66 70,54 G 1.5;e 72,52 4 3 G
beehive|||蜂巢,蜂蜜,蜜蜂,beehive|l 50,36 50,22 N 2;e 50,84 24 14 D;e 50,70 22 12 D;e 50,56 18 11 D;e 50,44 12 8 D;e 50,84 5 5 K;e 76,50 3 2 K;e 22,62 3 2 K
doghouse|||狗屋,小狗,忠實,忠心|r 24,60 76,100 E;p 16,62 50,34 84,62 I;p 40,100 40,78 50,68 60,78 60,100 K;e 82,96 8 4 A
haystack||wheat,grass,savanna,orchard,terraces|乾草堆,稻草堆,草堆,穀堆,秋收|p 10,100 16,62 34,44 66,44 84,62 90,100 D;l 20,70 80,70 O 1.5;l 16,84 84,84 O 1.5;l 40,46 36,100 O 1;l 62,46 66,100 O 1
wishtree|||許願樹,祈願,紅絲帶,繫上,wishing tree|r 45,58 55,100 N;e 50,34 40 32 F;l 26,40 24,62 R 1.5;l 38,48 37,70 R 1.5;l 52,50 52,74 R 1.5;l 64,46 66,68 R 1.5;l 76,38 78,58 R 1.5;l 32,30 31,46 R 1.5;l 70,26 71,44 R 1.5
moongate||oldtown,park,bamboo,town,lake,grass|月洞門,圓門,園林,庭院,院子|r 4,20 96,100 W;r 0,12 100,22 I 1;e 50,66 30 30 K;e 50,66 26 26 F;p 40,90 60,90 56,76 44,76 H
stonelantern|||石燈籠,石燈,庭園|g 50,56 14;r 40,90 60,100 A 1;r 46,66 54,90 A;r 36,46 64,66 A 1;w 44,50 56,62;p 28,46 50,28 72,46 A;e 50,26 4 4 A
koiflags|||鯉魚旗,端午,兒童節|l 20,100 20,-30 I 2;p 20,-26 70,-22 80,-14 70,-6 20,-10 K;e 30,-18 3 3 W;p 20,-2 66,2 76,10 66,18 20,14 R;e 30,6 3 3 W;p 20,22 60,26 68,33 60,40 20,36 B;e 30,29 3 3 W;e 20,-32 4 4 D
dragonboat|w|river,lake,harbor,reeds,coast,oldtown|龍舟,划龍舟,賽龍舟|p -60,84 150,84 140,96 -50,96 R;p 150,84 172,62 180,70 164,84 G;e 174,62 5 5 G;p -60,84 -80,66 -70,64 -52,80 G;e -30,76 5 5 S;e -5,76 5 5 S;e 20,76 5 5 S;e 45,76 5 5 S;e 70,76 5 5 S;e 95,76 5 5 S;e 120,76 5 5 S;l -60,90 150,90 Y 1.5
teahouse|||茶館,茶樓,喝茶,品茶,茶香|g 12,58 10;g 88,58 10;r 16,50 84,100 J;p 4,52 20,32 80,32 96,52 I;r 22,56 28,100 E;r 72,56 78,100 E;w 34,62 46,78;w 54,62 66,78;r 44,82 56,100 N 1;e 12,58 4 6 R;e 88,58 4 6 R
archway|||牌坊,牌樓,山門|l 22,100 22,24 E 4;l 78,100 78,24 E 4;p 6,26 94,26 98,16 2,16 I;r 26,36 74,46 D 1;p 30,16 70,16 74,6 26,6 I
hotspring|||溫泉,泡湯|e 50,90 46 10 A;e 50,90 38 7 U;p 4,90 10,76 22,84 A;p 96,90 88,74 78,84 A;l 36,76 32,62 38,50 W 2;l 52,74 48,58 54,44 W 2;l 66,76 62,62 68,50 W 2
sandcastle||coast,island,dunes,boardwalk|沙堡,沙雕,堆沙|r 20,70 80,100 D;r 12,56 30,100 D;r 70,56 88,100 D;r 40,50 60,76 D;p 10,56 21,40 32,56 Y;p 68,56 79,40 90,56 Y;p 38,50 50,32 62,50 Y;p 44,100 44,86 50,80 56,86 56,100 N;l 50,32 50,22 I 1;p 50,22 58,25 50,28 R
raft||river,lake,reeds,coast,island|木筏,竹筏,漂泊|e 50,100 46 3 L;r 8,88 92,96 J 3;l 8,84 92,84 N 3;l 8,92 92,92 N 1;l 50,84 50,34 N 2;p 50,36 50,70 80,66 W
launchpad|||發射台,太空船,升空,launch|r 20,96 80,100 A;r 60,20 68,100 I;l 60,30 52,36 I 1.5;l 60,56 52,62 I 1.5;p 42,84 50,84 46,98 O;p 40,84 40,26 46,10 52,26 52,84 W;p 40,84 32,96 40,90 R;p 52,84 60,96 52,90 R;e 46,40 4 4 B
robot|||機器人,機械,robot|l 50,14 50,6 I 1.5;e 50,4 2 2 R;r 34,40 66,78 Z 3;r 38,14 62,36 Z 3;e 45,24 3 3 Y;e 55,24 3 3 Y;r 24,44 32,70 Z 3;r 68,44 76,70 Z 3;r 38,78 46,100 Z 2;r 54,78 62,100 Z 2;r 42,50 58,62 L 1
dinosaur|||恐龍,侏羅紀,dinosaur|p 22,66 0,84 2,90 26,76 G;r 34,78 42,100 G 2;r 54,78 62,100 G 2;e 46,66 28 18 G;p 62,56 76,22 86,20 84,34 70,64 G;e 86,20 10 7 G;e 90,18 1.5 1.5 K;p 40,50 46,42 52,50 F;p 52,50 58,42 64,52 F
pirateship||plaza,grass,park,skyline,coast,harbor|海盜船,遊樂設施|l 50,10 20,100 I 3;l 50,10 80,100 I 3;l 50,10 50,60 I 2;p 14,60 86,60 76,82 50,90 24,82 N;p 14,60 6,48 18,54 N;p 86,60 94,48 82,54 N;r 20,56 80,62 R 1
ticketbooth|||售票亭,售票口,門票|r 26,36 74,100 Y 2;p 18,38 50,16 82,38 R;w 34,48 66,70;r 34,70 66,76 W;r 30,24 70,34 W 2
tunnel||peaks,woods,cliff,canyon,tracks,highway,snow|隧道,盡頭的光,tunnel|p -20,100 -10,40 30,14 70,14 110,40 120,100 A;p 22,100 22,60 34,42 66,42 78,60 78,100 K;g 50,74 24;e 50,74 10 14 Y;l 22,60 34,42 66,42 78,60 I 2
crossing|w|town,tracks,grass,wheat,highway,oldtown,park|平交道,柵欄,鐵道口|g 10,56 14;l 10,100 10,36 K 4;l -2,26 22,44 W 4;l 22,26 -2,44 W 4;e 4,56 5 5 R;e 16,56 5 5 R;l 10,72 120,58 W 4;l 30,69.5 44,67.7 R 4;l 58,65.9 72,64.1 R 4;l 86,62.3 100,60.5 R 4;l 190,100 190,36 K 4;l 178,26 202,44 W 4;l 202,26 178,44 W 4;e 184,56 5 5 R;e 196,56 5 5 R
gasstation||highway,town,skyline,plaza,dunes,grass|加油站,gas station|g 50,44 30;r 4,30 96,40 R 2;l 16,40 16,100 W 3;l 84,40 84,100 W 3;r 36,66 48,100 W 2;r 52,66 64,100 W 2;w 38,70 46,78;w 54,70 62,78;r 30,96 70,100 A
hotel||town,skyline,plaza,harbor,coast,oldtown,park|旅館,旅店,飯店,酒店,hotel|r 22,-10 78,100 H;r 18,-16 82,-8 E 1;r 30,-30 70,-18 R 2;w 28,0 38,12;w 45,0 55,12;w 62,0 72,12;w 28,20 38,32;w 45,20 55,32;w 62,20 72,32;w 28,40 38,52;w 45,40 55,52;w 62,40 72,52;w 28,60 38,72;w 62,60 72,72;r 42,76 58,100 N 2;p 36,76 64,76 60,68 40,68 R
apartment||town,skyline,plaza,oldtown,park,harbor|公寓,老公寓,陽台,樓下,窗台,鄰居|r 18,0 82,100 C;r 14,-6 86,2 A 1;w 24,10 40,24;w 60,10 76,24;w 24,38 40,52;w 60,38 76,52;w 24,66 40,80;w 60,66 76,80;r 22,24 42,28 I;r 58,24 78,28 I;r 22,52 42,56 I;r 58,52 78,56 I;r 44,78 56,100 N 1;e 32,22 3 3 R;e 68,50 3 3 P
porchswing|||搖椅,鞦韆椅,門廊,老夫老妻|l 10,100 10,20 W 3;l 90,100 90,20 W 3;l 6,20 94,20 W 3;l 28,20 28,64 I 1;l 72,20 72,64 I 1;r 22,46 78,64 J 2;r 22,64 78,72 J 2;l 22,72 22,80 J 2;l 78,72 78,80 J 2
lovelocks|w|river,lake,harbor,boardwalk,coast,skyline,town,plaza,oldtown,cliff|同心鎖,愛情鎖,鎖住,情人橋|l -150,50 250,50 I 2;l -150,86 250,86 I 2;l -100,50 -100,100 I 2;l 0,50 0,100 I 2;l 100,50 100,100 I 2;l 200,50 200,100 I 2;r -70,60 -62,70 D 1;r -40,66 -32,76 R 1;r -14,58 -6,68 P 1;r 22,64 30,74 D 1;r 44,58 52,68 B 1;r 66,66 74,76 R 1;r 120,60 128,70 P 1;r 150,66 158,76 D 1;r 176,58 184,68 R 1
heartsign|||愛心裝置,情人節,告白,valentine|g 50,50 40;l 50,84 50,100 I 3;r 34,96 66,100 A;e 36,40 20 20 R;e 64,40 20 20 R;p 18,48 82,48 50,86 R;e 36,40 11 11 P;e 64,40 11 11 P;p 28,50 72,50 50,72 P
terrace|||露天咖啡,露天,咖啡座,午後時光|l 50,100 50,20 I 2;p 14,30 50,8 86,30 R;p 32,30 50,8 44,30 W;p 56,30 50,8 68,30 W;l 30,100 30,70 I 2;e 30,68 14 4 W;l 70,100 70,70 I 2;e 70,68 14 4 W;r 8,80 18,100 J 1;r 82,80 92,100 J 1;e 30,62 3 3 W;e 70,62 3 3 W
icestand|||冰店,冰淇淋車,剉冰,夏日,暑假|r 16,50 84,92 Q 3;p 10,50 90,50 84,36 16,36 W;p 28,50 30,36 42,36 42,50 P;p 58,50 58,36 70,36 72,50 P;w 26,58 60,76;e 30,94 7 7 K;e 70,94 7 7 K;p 70,30 76,12 82,30 D;e 76,10 7 7 P
fruitstand|||水果攤,水果,果攤,市場|r 10,70 90,100 J 2;p 4,44 96,44 88,30 12,30 G;l 14,44 14,70 N 2;l 86,44 86,70 N 2;e 24,66 6 6 R;e 38,66 6 6 O;e 52,66 6 6 Y;e 66,66 6 6 G;e 78,66 6 6 V;e 31,58 6 6 O;e 45,58 6 6 R;e 59,58 6 6 Y
balloonstand|||賣氣球,氣球攤,園遊|l 50,70 30,30 I 0.8;l 50,70 44,22 I 0.8;l 50,70 58,24 I 0.8;l 50,70 72,32 I 0.8;l 50,70 52,14 I 0.8;e 30,24 9 11 R;e 44,14 9 11 Y;e 58,16 9 11 B;e 72,26 9 11 P;e 52,4 9 11 G;r 34,70 66,96 J 2;e 40,98 5 5 K;e 60,98 5 5 K
aquarium|||水族館,海洋館,水母,aquarium|r 8,30 92,100 U 6;r 14,38 86,84 L 3;e 34,56 8 5 O;p 42,56 50,50 50,62 O;e 66,68 6 4 Y;p 72,68 78,64 78,72 Y;e 56,46 5 4 W;l 52,50 52,60 W 1;l 56,50 56,62 W 1;l 60,50 60,60 W 1;r 40,86 60,100 I 1
""".strip()


def _load():
    table: Dict[str, Tuple[bool, Tuple[str, ...], Tuple[str, ...], list]] = {}
    for line in LANDMARKS.splitlines():
        try:
            name, flags, only, words, shapes = line.split("|")
            assert name not in table
            table[name] = ("w" in flags, tuple(t for t in only.split(",") if t), tuple(w for w in words.split(",") if w), card_icons.parse_shapes(shapes))
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"landmark line: {line!r}: {e!r}") from e
    return table


TABLE = _load()


def _painter(prims) -> Callable:
    def paint(k, x, y, s):
        z = 4.0 * s
        card_icons.draw_shapes(k, prims, x - 50 * z, y - 100 * z, z, shine=False, lit=k.dark or k.light == "overcast")
    return paint


LANDMARK_FN: Dict[str, Callable] = {name: _painter(row[3]) for name, row in TABLE.items()}
ONLY_ON = {name: row[1] for name, row in TABLE.items() if row[1]}
WIDE = tuple(name for name, row in TABLE.items() if row[0])
LANDMARK_WORDS = {name: row[2] for name, row in TABLE.items()}
