"""Picture cards put together from parts (the second generation of app/mvstudio/cards.py's cards).

A song gets a world of its own: a few places where it happens, the lights it moves through, a palette, a way
of drawing lines, and the two people in it. choose_world() makes it from the song's seed and keeps away from
what the songs before it used. plan() then gives every part of the timeline a card: a place, a light and
weather, who is in the picture and how, a small thing that goes with the words, and how close the picture
is. draw() paints a card. Nothing is fetched; everything is Pillow shapes at twice the size, scaled down.

A card is written as one string, "w2|place|light|weather|subject|prop|frame|pos|n", so that it can be kept
in the project's cards.json and drawn again later (in another tone, say).
"""
from __future__ import annotations

import colorsys
import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

W, H, S = 1920, 1080, 2
SKIN = (255, 224, 204)


def P(v):
    return int(round(v * S))


# sky top / middle / horizon, the colour everything leans to and how much, what is in the sky, cloud colour
LIGHTS: Dict[str, Dict[str, Any]] = {
    "dawn": {"sky": [(250, 196, 190), (255, 228, 206), (220, 236, 250)], "amb": ((255, 208, 196), 0.16), "orb": "low", "cloud": (255, 240, 232)},
    "day": {"sky": [(112, 190, 248), (172, 220, 255), (230, 246, 255)], "amb": ((255, 255, 255), 0.0), "orb": "sun", "cloud": (255, 255, 255)},
    "golden": {"sky": [(255, 190, 112), (255, 218, 156), (255, 240, 208)], "amb": ((255, 196, 120), 0.22), "orb": "low", "cloud": (255, 236, 206)},
    "sunset": {"sky": [(240, 124, 112), (255, 170, 128), (255, 218, 170)], "amb": ((250, 140, 110), 0.30), "orb": "set", "cloud": (255, 200, 180)},
    "dusk": {"sky": [(92, 88, 168), (186, 128, 178), (248, 188, 170)], "amb": ((132, 104, 178), 0.36), "orb": "thin", "cloud": (214, 160, 196)},
    "night": {"sky": [(16, 24, 68), (38, 52, 114), (82, 88, 150)], "amb": ((36, 46, 108), 0.52), "orb": "moon", "cloud": (70, 82, 140)},
    "overcast": {"sky": [(132, 154, 182), (172, 190, 210), (208, 220, 230)], "amb": ((150, 168, 190), 0.30), "orb": "", "cloud": (196, 208, 222)},
}
PLACES = ("meadow", "sea", "rooftop", "street", "school", "classroom", "station", "park", "bridge", "forest", "lake", "room",
          "flowers", "road", "pier", "hill")
INDOOR = ("classroom", "room")
WEATHERS = ("clear", "rain", "snow")
SUBJECTS = ("none", "solo_front", "solo_back", "solo_walk", "solo_sit", "solo_reach", "solo_open", "solo_wave", "duo_front",
            "duo_back", "duo_sit", "duo_apart", "duo_hands", "duo_face", "other_back")
PROPS = ("none", "stars", "shooting", "bigmoon", "hearts", "letter", "plane", "birds", "balloons", "clover", "petals", "leaves",
         "tears", "dots", "ask", "call", "notes", "lantern", "kite", "rainbow", "fireflies", "umbrella", "bike", "thread", "wings",
         "frames", "clock", "bubbles")
FRAMES = ("wide", "mid", "close")
# The standard grade (world["grade"] == "standard") has more of everything: places, ways to stand, and shots
# that are not "people in front of a view": against the light, over a shoulder, two hands, things on a table.
PLACES_STD = ("cafe", "busstop", "library", "train", "market", "snowtown", "garden", "alley", "field", "fair", "stairs", "riverbank")
SUBJECTS_STD = ("solo_run", "duo_hug")
FRAMES_STD = ("sil", "over", "hands", "still")
INDOOR_STD = ("cafe", "library", "train")
POSES = ("l", "c", "r")
LINES = {"ink": ((50, 60, 92), 4), "brown": ((96, 68, 60), 5), "soft": (None, 3), "fine": ((74, 80, 100), 3)}
HAIR_COLORS = ((92, 70, 70), (52, 48, 62), (134, 88, 62), (182, 134, 88), (116, 62, 70), (70, 84, 110))
CLOTH = ((232, 120, 140), (92, 170, 176), (88, 104, 160), (228, 172, 86), (160, 132, 204), (120, 176, 120), (224, 108, 88),
         (72, 82, 104), (240, 196, 206), (150, 128, 96))
LIGHT_CLOTH = ((255, 255, 255), (255, 246, 226), (228, 240, 255), (255, 232, 236), (232, 246, 232))
GIRL_CUTS = ("long", "bob", "ponytail", "twin", "bun")
BOY_CUTS = ("short", "fringe", "spiky")
GIRL_WEAR = ("skirt", "dress", "shorts")
BOY_WEAR = ("tee", "hoodie", "jacket")
EXTRAS = ("none", "none", "scarf", "hat", "ribbon", "glasses")
AMBIENT = ("none", "birds", "petals", "leaves", "fireflies", "bubbles")
BORDERS = ("comic", "plain", "round", "film")
PALETTES = ((0, 1.0), (-16, 0.92), (14, 1.08), (26, 0.8), (-28, 1.0), (8, 0.68), (-8, 1.2))   # hue turn, colour strength
LIGHT_ARCS = (("day", "golden", "sunset", "dusk"), ("dawn", "day", "golden"), ("golden", "sunset", "night"), ("day", "golden", "dusk"),
              ("dusk", "night", "dawn"), ("day", "sunset", "night"), ("dawn", "day", "dusk", "night"), ("dawn", "golden", "sunset"))


# ---------------------------------------------------------------------------------------------- the world
def make_world(seed: int, grade: str = "simple") -> Dict[str, Any]:
    std = grade == "standard"
    r = random.Random(f"world:{int(seed)}:{grade}" if std else f"world:{int(seed)}")
    indoor = INDOOR + (INDOOR_STD if std else ())
    out_places = [p for p in PLACES + (PLACES_STD if std else ()) if p not in indoor]
    places = (r.sample(out_places, 6) + r.sample(indoor, 2)) if std else (r.sample(out_places, 4) + [r.choice(INDOOR)])
    hue, sat = r.choice(PALETTES)

    def person(cuts, wears):
        return {"hair": list(r.choice(HAIR_COLORS)), "cut": r.choice(cuts), "wear": r.choice(wears), "top": list(r.choice(LIGHT_CLOTH)),
                "low": list(r.choice(CLOTH)), "extra": r.choice(EXTRAS), "extra_col": list(r.choice(CLOTH))}
    wd = {"v": 2, "places": places, "lights": list(r.choice(LIGHT_ARCS)), "hue": hue, "sat": sat, "line": r.choice(sorted(LINES)),
          "border": r.choice(BORDERS), "lead": r.choice(("girl", "boy")), "girl": person(GIRL_CUTS, GIRL_WEAR),
          "boy": person(BOY_CUTS, BOY_WEAR), "head": r.choice((1.0, 1.12, 1.24)), "ambient": r.choice(AMBIENT),
          "subjects": r.sample(SUBJECTS[1:14], 13), "frames": r.sample(["wide", "wide", "mid", "mid", "mid", "close"], 6)}
    if std:      # taller people with smaller heads, and the extra ways to stand among the others
        wd.update(grade="standard", head=r.choice((0.8, 0.86, 0.92)), tall=r.choice((38, 46, 54)),
                  subjects=r.sample(SUBJECTS[1:14] + SUBJECTS_STD, 15), border=r.choice(("plain", "plain", "round", "film", "comic")))
    return wd


def world_distance(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """How unlike two songs' worlds are (larger: more unlike)."""
    d = 0.0
    d += 3.0 * (min(len(a.get("places", [])), len(b.get("places", []))) - len(set(a.get("places", [])) & set(b.get("places", []))))
    d += 2.5 if a.get("line") != b.get("line") else 0
    d += 2.0 if (a.get("hue"), a.get("sat")) != (b.get("hue"), b.get("sat")) else 0
    d += 1.5 if a.get("lights") != b.get("lights") else 0
    d += 1.0 if a.get("border") != b.get("border") else 0
    d += 1.0 if a.get("lead") != b.get("lead") else 0
    for who in ("girl", "boy"):
        pa, pb = a.get(who) or {}, b.get(who) or {}
        d += sum(0.6 for k in ("hair", "cut", "wear", "low") if pa.get(k) != pb.get(k))
    return d


def choose_world(seed: int, recent: Sequence[Dict[str, Any]] = (), grade: str = "simple") -> Dict[str, Any]:
    """The song's world: of two dozen that its seed gives, the one least like the worlds of the songs before
    it (the nearest of them counts most), so a new song does not look like the last one."""
    recent = [w for w in recent if isinstance(w, dict) and w.get("v") == 2][-6:]
    cands = [make_world(int(seed) * 32 + i, grade) for i in range(24)]
    if not recent:
        return cands[0]

    def score(wd):
        ds = [world_distance(wd, old) for old in recent]
        return min(ds) * 2 + ds[-1] + sum(ds) / len(ds)
    return max(cands, key=score)


def valid_world(wd: Any) -> bool:
    try:
        return (wd.get("v") == 2 and len(wd["places"]) >= 1 and all(p in PLACES + PLACES_STD for p in wd["places"])
                and all(x in LIGHTS for x in wd["lights"]) and wd["line"] in LINES and wd["border"] in BORDERS
                and wd.get("grade", "simple") in ("simple", "standard") and float(wd.get("tall", 0)) >= 0
                and wd["lead"] in ("girl", "boy") and all(s in SUBJECTS + SUBJECTS_STD for s in wd["subjects"]) and all(f in FRAMES for f in wd["frames"])
                and wd["girl"]["cut"] in GIRL_CUTS and wd["boy"]["cut"] in BOY_CUTS and float(wd["head"]) > 0)
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------------------------------------ the plan
# words in a line -> what the card takes from them. Chinese first (matched after Traditional -> Simplified),
# then a few English words (whole words, lower case). Later rows do not undo earlier ones.
def _row(words, **what):
    return (tuple(words), what)


HINTS = (
    _row(("流星",), light="night", prop="shooting"),
    _row(("月光", "月亮", "明月", "moon"), light="night", prop="bigmoon"),
    _row(("星", "銀河", "star", "stars"), light="night", prop="stars"),
    _row(("螢火",), light="night", prop="fireflies"),
    _row(("夜", "晚", "夢", "night", "dream", "tonight"), light="night"),
    _row(("夕陽", "黃昏", "日落", "晚霞", "落日", "sunset"), light="sunset"),
    _row(("清晨", "早晨", "黎明", "天亮", "日出", "晨", "morning", "dawn"), light="dawn"),
    _row(("陽光", "晴", "太陽", "燦爛", "sun", "sunshine"), light="day"),
    _row(("雨", "淋", "rain", "raining"), weather="rain", light="overcast"),
    _row(("雪", "冬", "snow", "winter"), weather="snow"),
    _row(("傘",), prop="umbrella", weather="rain", light="overcast"),
    _row(("海", "浪", "沙灘", "sea", "ocean", "beach", "waves"), place="sea"),
    _row(("港", "船", "碼頭", "harbor", "ship"), place="pier"),
    _row(("城市", "霓虹", "高樓", "city"), place="rooftop"),
    _row(("街", "路燈", "巷", "street"), place="street"),
    _row(("學校", "校園", "鐘聲", "操場", "school"), place="school"),
    _row(("教室", "下課", "上課", "課堂", "黑板"), place="classroom"),
    _row(("車站", "列車", "火車", "月台", "站台", "train", "station"), place="station"),
    _row(("窗", "房間", "屋", "window", "room", "home"), place="room"),
    _row(("山", "mountain"), place="hill"),
    _row(("湖", "lake"), place="lake"),
    _row(("森林", "樹", "林", "forest", "tree", "trees"), place="forest"),
    _row(("花", "flower", "flowers"), place="flowers"),
    _row(("橋", "河", "river", "bridge"), place="bridge"),
    _row(("公園", "長椅", "park"), place="park"),
    _row(("路", "走", "旅", "遠方", "road", "walk", "away"), place="road"),
    _row(("我們", "一起", "陪", "身邊", "肩", "together", "we", "us"), subject="duo_sit"),
    _row(("牽", "手", "hand", "hands", "hold"), subject="duo_hands"),
    _row(("擁抱", "抱", "靠", "相遇", "遇見", "meet", "hug"), subject="duo_face"),
    _row(("離", "分手", "再見", "告別", "失去", "走了", "goodbye", "bye", "leave", "gone", "lost"), subject="duo_apart"),
    _row(("想你", "想念", "思念", "寂寞", "孤單", "一個人", "等", "miss", "alone", "lonely", "wait", "waiting"), subject="solo_back"),
    _row(("笑", "快樂", "幸福", "開心", "smile", "happy"), subject="solo_wave"),
    _row(("飛", "自由", "未來", "希望", "明天", "fly", "free", "hope", "tomorrow"), subject="solo_open"),
    _row(("願", "祈", "天空", "sky", "wish"), subject="solo_reach"),
    _row(("他", "她", "別人", "祝福", "her", "him"), subject="other_back"),
    _row(("愛", "心", "喜歡", "戀", "love", "heart"), prop="hearts"),
    _row(("信", "寫", "紙", "日記", "千言萬語", "letter", "write"), prop="letter"),
    _row(("淚", "哭", "傷", "痛", "苦", "cry", "tears", "tear", "hurt", "pain"), prop="tears"),
    _row(("幸運", "奇蹟", "lucky", "luck", "miracle"), prop="clover"),
    _row(("翅膀", "wings"), prop="wings"),
    _row(("鳥", "bird", "birds"), prop="birds"),
    _row(("氣球", "生日", "慶祝", "birthday", "party"), prop="balloons"),
    _row(("歌", "唱", "旋律", "音樂", "song", "sing", "music"), prop="notes"),
    _row(("風", "wind"), prop="leaves"),
    _row(("彩虹", "rainbow"), prop="rainbow"),
    _row(("註定", "命運", "緣", "fate", "destiny"), prop="thread"),
    _row(("回憶", "記憶", "照片", "從前", "曾經", "一幕", "remember", "memory", "memories"), prop="frames"),
    _row(("時間", "歲月", "永遠", "一生", "今生", "time", "forever"), prop="clock"),
    _row(("單車", "腳踏車", "騎"), prop="bike"),
    _row(("問", "為什麼", "why"), prop="ask"),
    _row(("說", "告訴", "話", "言語", "say", "tell", "said"), prop="dots"),
    _row(("喊", "呼喚", "名字", "call", "name"), prop="call"),
    _row(("燈", "light"), prop="lantern"),
    _row(("紙飛機",), prop="plane"),
)
SOLO_ONLY = ("tears", "umbrella", "bike", "wings", "dots", "ask", "call")   # things that belong to one person
DUO_ONLY = ("thread",)


def _simple(text: str) -> str:
    try:
        from ..lyric_align import _t2s
        table = _t2s()
    except Exception:  # noqa: BLE001
        table = {}
    return "".join(table.get(ch, ch) for ch in str(text or "").replace("妳", "你").replace("星期", "")).lower()


def _hints(line: str, rows) -> Dict[str, str]:
    got: Dict[str, str] = {}
    if not line:
        return got
    words = set("".join(ch if ch.isalpha() and ch.isascii() else " " for ch in line).split())
    for ws, what in rows:
        if any((w in words) if w.isascii() else (w in line) for w in ws):
            for k, v in what.items():
                got.setdefault(k, v)
    return got


def card(place, light, weather, subject, prop, frame, pos, n) -> str:
    return "|".join(("w2", place, light, weather, subject, prop, frame, pos, str(int(n))))


def parse(spec: str) -> Optional[Tuple[str, str, str, str, str, str, str, int]]:
    p = str(spec or "").split("|")
    if (len(p) == 9 and p[0] == "w2" and p[1] in PLACES + PLACES_STD and p[2] in LIGHTS and p[3] in WEATHERS
            and p[4] in SUBJECTS + SUBJECTS_STD and p[5] in PROPS and p[6] in FRAMES + FRAMES_STD and p[7] in POSES
            and p[8].isdigit() and len(p[8]) <= 4):
        return p[1], p[2], p[3], p[4], p[5], p[6], p[7], int(p[8])
    return None


def plan(parts: Sequence[Tuple[str, str]], seed: int, world: Dict[str, Any]) -> List[str]:
    """A card for every part of the timeline ((kind, text), kind "intro" | "outro" | "interlude" | other).
    The song stays in its places, two or three lines at a time, and moves through its lights; a line's own
    words can take it somewhere else or put something in the picture. No two cards of a song are the same."""
    r = random.Random(f"plan:{int(seed)}")
    rows = [(tuple(_simple(w) for w in ws), what) for ws, what in HINTS]
    places, lights = list(world["places"]), list(world["lights"])
    outdoor = [p for p in places if p not in INDOOR] or ["meadow"]
    subjects, frames = list(world["subjects"]), list(world["frames"])
    n_lines = max(1, sum(1 for k, _ in parts if k not in ("intro", "outro")))
    out: List[str] = []
    seen = set()
    li = 0
    stay, place = 0, outdoor[0]
    order = places[:]
    for kind, text in parts:
        if kind == "intro":
            spec = card(outdoor[0], lights[0], "clear", "none", "none" if world["ambient"] in ("none", "bubbles") else world["ambient"], "wide", "c", 0)
        elif kind == "outro":
            spec = card(outdoor[-1], "night" if lights[-1] in ("dusk", "night", "sunset") else "dusk", "clear", "duo_back", "stars" if lights[-1] in ("dusk", "night", "sunset") else "birds", "wide", "c", 0)
        else:
            h = {} if kind == "interlude" else _hints(_simple(text), rows)
            if stay <= 0:                 # move on to the song's next place
                order = order[1:] + order[:1]
                place, stay = order[0], r.choice((2, 2, 3))
            stay -= 1
            pl = h.get("place", place)
            light = h.get("light") or lights[min(len(lights) - 1, li * len(lights) // n_lines)]
            weather = h.get("weather", "clear")
            if pl in INDOOR and weather != "clear":
                weather = "clear" if h.get("place") else weather
                pl = pl if h.get("place") else outdoor[li % len(outdoor)]
            subject = h.get("subject") or subjects[li % len(subjects)]
            prop = h.get("prop", "none")
            if kind == "interlude":
                subject, prop = ("none" if li % 2 else "solo_back"), (world["ambient"] if world["ambient"] != "none" else "birds")
            if prop == "none" and world["ambient"] != "none" and r.random() < 0.3:
                prop = world["ambient"]
            if prop in SOLO_ONLY and subject.startswith("duo"):
                subject = "solo_front" if prop in ("dots", "ask", "call", "tears") else "solo_walk"
            if prop in DUO_ONLY and not subject.startswith("duo"):
                subject = "duo_apart" if h.get("subject") == "duo_apart" else "duo_face"
            if prop in SOLO_ONLY and subject in ("none", "solo_back", "other_back") and prop in ("tears", "dots", "ask", "call"):
                subject = "solo_front"
            if prop == "bike":
                subject = "solo_walk"
            if prop == "umbrella" and subject in ("solo_reach", "solo_open", "solo_wave", "solo_sit"):
                subject = "solo_front"
            frame = frames[li % len(frames)]
            if subject in ("solo_sit", "duo_sit", "duo_apart", "none") and frame == "close":
                frame = "mid"
            if prop in ("bike", "wings", "thread", "frames", "kite", "rainbow") and frame == "close":
                frame = "mid"
            pos = "c" if subject.startswith("duo") else POSES[(li + (seed % 3)) % 3]
            spec, n = card(pl, light, weather, subject, prop, frame, pos, 0), 0
            while spec in seen or (out and spec.split("|")[1:6] == out[-1].split("|")[1:6]):
                n += 1                    # the same words again: the same idea from another side
                frame = FRAMES[(FRAMES.index(frame) + n) % 3] if subject not in ("solo_sit", "duo_sit", "duo_apart", "none") else ("wide" if n % 2 else "mid")
                pos = "c" if subject.startswith("duo") else POSES[(li + n) % 3]
                if n % 3 == 0:
                    pl = outdoor[(outdoor.index(pl) + 1) % len(outdoor)] if pl in outdoor else outdoor[n % len(outdoor)]
                spec = card(pl, light, weather, subject, prop, frame, pos, n)
                if n > 40:
                    break
            li += 1
        seen.add(spec)
        out.append(spec)
    return out


# --------------------------------------------------------------------------------------------- the canvas
def _mix(a, b, k):
    return tuple(int(round(x + (y - x) * k)) for x, y in zip(a[:3], b[:3]))


class K:
    """The picture being painted. Colours are given as they would be at noon in the plain palette; c() turns
    them into the song's palette under the card's light (e=True: something that shines, left as it is)."""

    def __init__(self, world, light, seed):
        self.w, self.light, self.L = world, light, LIGHTS[light]
        self.im = Image.new("RGB", (W * S, H * S), "white")
        self.d = ImageDraw.Draw(self.im, "RGBA")
        self.r = random.Random(seed)
        self.ink, self.lw = LINES[world["line"]]
        self.hue, self.sat = float(world["hue"]), float(world["sat"])
        self.dark = light in ("night", "dusk")
        self.sky3 = [self.pal(col) for col in self.L["sky"]]
        self.flat = None      # set: everything is painted in this one colour (people against the light)
        self.mood = "smile"   # the faces: smile | sad | closed | wow
        self.rim = 0          # -1 / 1: light from the left / right draws a bright edge on people
        self.std = world.get("grade") == "standard"

    def pal(self, col):
        r, g, b = col[:3]
        if self.hue or self.sat != 1.0:
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            r, g, b = (v * 255 for v in colorsys.hls_to_rgb((h + self.hue / 360) % 1.0, l, min(1.0, s * self.sat)))
        return (int(round(r)), int(round(g)), int(round(b)))

    def c(self, col, skin=False, e=False):
        if self.flat and len(col) == 3:
            return self.flat
        if e:
            return tuple(col)
        base = tuple(col[:3]) if skin else self.pal(col)
        tint, k = self.L["amb"]
        return _mix(base, self.pal(tint), k * (0.55 if skin else 1.0)) + tuple(col[3:])

    def far(self, col, k=0.55):
        """A colour for something far away: it fades into the horizon."""
        return _mix(self.c(col), self.sky3[2], k)

    def edge(self, fill):
        if self.flat:
            return self.flat
        return self.ink if self.ink else tuple(int(v * 0.6) for v in fill[:3])

    def blur(self, radius=7):
        """Put what is painted so far out of focus (what comes after it stays sharp)."""
        small = self.im.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius))
        self.im.paste(small.resize((W * S, H * S), Image.BILINEAR))

    def ell(self, x, y, rx, ry, fill, line=True, skin=False, e=False, raw=False):
        f = tuple(fill) if raw else self.c(fill, skin, e)
        self.d.ellipse([P(x - rx), P(y - ry), P(x + rx), P(y + ry)], fill=f, outline=self.edge(f) if line else None, width=P(self.lw) if line else 0)

    def rect(self, x0, y0, x1, y1, fill, line=True, r=0, e=False, raw=False):
        f = tuple(fill) if raw else self.c(fill, e=e)
        x0, x1 = min(x0, x1), max(x0, x1); y0, y1 = min(y0, y1), max(y0, y1)
        self.d.rounded_rectangle([P(x0), P(y0), P(x1), P(y1)], radius=P(min(r, (x1 - x0) / 2, (y1 - y0) / 2)), fill=f,
                                 outline=self.edge(f) if line else None, width=P(self.lw) if line else 0)

    def poly(self, pts, fill, line=True, skin=False, e=False, raw=False):
        f = tuple(fill) if raw else self.c(fill, skin, e)
        q = [(P(x), P(y)) for x, y in pts]
        self.d.polygon(q, fill=f)
        if line:
            self.d.line(q + [q[0], q[1]], fill=self.edge(f), width=P(self.lw), joint="curve")

    def stroke(self, pts, col=None, w=4, e=False, raw=False):
        f = (self.ink or (70, 76, 100)) if col is None else (tuple(col) if raw else self.c(col, e=e))
        self.d.line([(P(x), P(y)) for x, y in pts], fill=f, width=max(1, P(w)), joint="curve")

    def limb(self, pts, fill, w, skin=False):
        """A rounded bar with an outline (arms, legs)."""
        f = self.c(fill, skin)
        q = [(P(x), P(y)) for x, y in pts]
        self.d.line(q, fill=self.edge(f), width=P(w + self.lw * 1.6), joint="curve")
        for x, y in (q[0], q[-1]):
            rr = P(w + self.lw * 1.6) / 2
            self.d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=self.edge(f))
        self.d.line(q, fill=f, width=P(w), joint="curve")
        for x, y in (q[0], q[-1]):
            rr = P(w) / 2
            self.d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=f)

    # ---- sky
    def sky(self):
        a, b, c = self.sky3
        hh = H * S
        for y in range(hh):
            t = y / (hh - 1)
            col = _mix(a, b, t / 0.5) if t < 0.5 else _mix(b, c, min(1.0, (t - 0.5) / 0.35))
            self.d.line([(0, y), (W * S, y)], fill=col)
        if self.light == "night":
            for _ in range(150):
                x, y, rr = self.r.uniform(0, W), self.r.uniform(0, 640), self.r.choice((1.5, 2, 2, 3))
                self.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 255, 255, self.r.randint(120, 255)))
        elif self.light == "dusk":
            for _ in range(40):
                x, y = self.r.uniform(0, W), self.r.uniform(0, 300)
                self.d.ellipse([P(x - 2), P(y - 2), P(x + 2), P(y + 2)], fill=(255, 255, 255, self.r.randint(80, 190)))

    def orb(self, horizon=700, side=None):
        kind = self.L["orb"]
        if not kind:
            return None
        x = self.r.uniform(260, 700) if (side or self.r.choice("lr")) == "l" else self.r.uniform(1220, 1660)
        if kind in ("moon", "thin"):
            y, rr = self.r.uniform(130, 300), 62
            for g in range(5, 0, -1):
                self.d.ellipse([P(x - rr - g * 14), P(y - rr - g * 14), P(x + rr + g * 14), P(y + rr + g * 14)], fill=(255, 250, 220, 10))
            self.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 248, 214))
            if kind == "thin" or self.r.random() < 0.6:
                self.d.ellipse([P(x - rr + 30), P(y - rr - 12), P(x + rr + 30), P(y + rr - 12)], fill=self.sky3[0])
            return x, y
        y = {"sun": self.r.uniform(150, 280), "low": horizon - self.r.uniform(170, 260), "set": horizon - self.r.uniform(30, 90)}[kind]
        rr = {"sun": 74, "low": 92, "set": 120}[kind]
        col = {"sun": (255, 244, 170), "low": (255, 232, 150), "set": (255, 206, 130)}[kind]
        for g in range(7, 0, -1):
            self.d.ellipse([P(x - rr - g * 22), P(y - rr - g * 22), P(x + rr + g * 22), P(y + rr + g * 22)], fill=col + (16,))
        self.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=col)
        return x, y

    def cloud(self, x, y, s=1.0, col=None):
        col = self.pal(col or self.L["cloud"])
        shade = _mix(col, self.sky3[1], 0.45)
        blobs = ((-70, 12, 58), (-18, -22, 74), (48, -4, 64), (96, 18, 46), (0, 22, 70))
        for dx, dy, rr in blobs:
            self.d.ellipse([P(x + (dx - rr) * s), P(y + (dy - rr * 0.72 + 14) * s), P(x + (dx + rr) * s), P(y + (dy + rr * 0.72 + 14) * s)], fill=shade)
        for dx, dy, rr in blobs:
            self.d.ellipse([P(x + (dx - rr) * s), P(y + (dy - rr * 0.72) * s), P(x + (dx + rr) * s), P(y + (dy + rr * 0.72) * s)], fill=col)

    def clouds(self, n=None, y0=70, y1=360):
        n = self.r.randint(2, 5) if n is None else n
        if self.L is LIGHTS["overcast"]:
            n += 4
        for _ in range(n):
            self.cloud(self.r.uniform(60, W - 60), self.r.uniform(y0, y1), self.r.uniform(0.7, 1.7))

    def band(self, y0, y1, top, bottom, e=False):
        """A stretch of ground or water, lighter towards the horizon."""
        a, b = self.c(top, e=e), self.c(bottom, e=e)
        for y in range(P(y0), P(y1)):
            self.d.line([(0, y), (W * S, y)], fill=_mix(a, b, (y - P(y0)) / max(1, P(y1) - P(y0))))

    def ridge(self, y, amp, col, step=24, rough=0.3, far=0.0, line=False):
        ph, ph2 = self.r.uniform(0, 6), self.r.uniform(0, 6)
        pts = [(x, y + math.sin(x / 300 + ph) * amp + math.sin(x / 110 + ph2) * amp * rough) for x in range(-30, W + 60, step)]
        f = self.far(col, far) if far else self.c(col)
        self.poly(pts + [(W + 30, H + 30), (-30, H + 30)], f, line=line, raw=True)
        return pts

    def tree(self, x, y, s=1.0, col=(118, 190, 132), trunk=(150, 112, 92), far=0.0, kind="round"):
        f = (lambda q: self.far(q, far)) if far else self.c
        ln = far < 0.3
        self.poly([(x - 16 * s, y), (x - 10 * s, y - 170 * s), (x + 10 * s, y - 170 * s), (x + 16 * s, y)], f(trunk), line=ln, raw=True)
        if kind == "pine":
            for i in range(3):
                yy = y - (110 + i * 80) * s
                self.poly([(x - (110 - i * 22) * s, yy), (x, yy - 150 * s), (x + (110 - i * 22) * s, yy)], f(col), line=ln, raw=True)
            return
        dark = _mix(f(col), (20, 40, 60), 0.14)
        for dx, dy, rr in ((-70, -200, 78), (64, -206, 84), (0, -280, 100), (-10, -190, 80)):
            self.ell(x + dx * s, y + (dy + 12) * s, rr * s, rr * s * 0.88, dark, line=False, raw=True)
        for dx, dy, rr in ((-70, -200, 78), (64, -206, 84), (0, -280, 100), (-10, -190, 80)):
            self.ell(x + dx * s, y + dy * s, rr * s, rr * s * 0.88, f(col), line=ln, raw=True)
        self.ell(x, y - 228 * s, 112 * s, 84 * s, f(col), line=False, raw=True)

    def lamp(self, x, y, h=380, s=1.0):
        self.stroke([(x, y), (x, y - h * s)], (84, 92, 120), 9 * s)
        self.stroke([(x, y - h * s), (x + 44 * s, y - h * s)], (84, 92, 120), 9 * s)
        on = self.dark or self.light == "overcast"
        if on:
            self.d.polygon([(P(x + 44 * s), P(y - h * s + 8)), (P(x - 80 * s), P(y)), (P(x + 180 * s), P(y))], fill=(255, 238, 170, 46))
        self.ell(x + 44 * s, y - h * s + 10 * s, 20 * s, 13 * s, (255, 240, 170) if on else (236, 238, 244), e=on)

    def windows(self, x0, y0, x1, y1, cw=30, ch=38, gap=18, lit=0.5):
        on = self.dark
        y = y0
        while y + ch <= y1:
            x = x0
            while x + cw <= x1:
                if on and self.r.random() < lit:
                    self.rect(x, y, x + cw, y + ch, (255, 232, 150), line=False, r=3, e=True)
                elif not on:
                    self.rect(x, y, x + cw, y + ch, (214, 236, 250), line=False, r=3)
                x += cw + gap
            y += ch + gap

    def shadow(self, x, y, s):
        self.d.ellipse([P(x - 78 * s), P(y - 12 * s), P(x + 78 * s), P(y + 12 * s)], fill=(20, 30, 60, 46))


# --------------------------------------------------------------------------------------------- the places
# Each paints its back (far to near) and returns where people stand: {"ground": y}; called again with
# front=True it paints what is in front of them.
def pl_meadow(k, front=False):
    if front:
        for _ in range(70):
            x, y = k.r.uniform(0, W), k.r.uniform(980, H + 10)
            k.stroke([(x, y), (x + k.r.uniform(-10, 10), y - k.r.uniform(30, 70))], (84, 164, 110), 4)
        for _ in range(16):
            x, y, col = k.r.uniform(0, W), k.r.uniform(990, H - 10), k.r.choice(((255, 196, 212), (255, 240, 150), (255, 255, 255)))
            for a in range(5):
                k.ell(x + math.cos(a * 1.257) * 11, y + math.sin(a * 1.257) * 11, 9, 9, col, line=False)
            k.ell(x, y, 6, 6, (255, 200, 90), line=False)
        return None
    k.ridge(650, 46, (140, 200, 170), far=0.6); k.ridge(720, 40, (134, 204, 158), far=0.3)
    k.band(790, H, (170, 224, 160), (128, 196, 132)); k.ridge(790, 16, (170, 224, 160), rough=0.6)
    k.tree(k.r.choice((250, 1680)), 850, 1.25)
    return {"ground": 880}


def pl_sea(k, front=False):
    if front:
        return None
    k.band(620, 880, (150, 214, 236), (86, 170, 214))
    for i in range(16):
        y = 640 + i * 15
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, y), (x + k.r.uniform(120, 360), y)], (255, 255, 255, 110), 3)
    k.poly([(k.r.uniform(200, 1500) + dx, 618 + dy) for dx, dy in ((0, 0), (60, -34), (150, -40), (230, -10), (260, 2))], k.far((120, 150, 150), 0.5), line=False, raw=True)
    pts = [(x, 872 + math.sin(x / 170 + 1.3) * 20) for x in range(-30, W + 60, 30)]
    k.poly([(x, y - 14) for x, y in pts] + [(W + 30, H + 30), (-30, H + 30)], (255, 255, 255), line=False)
    k.poly(pts + [(W + 30, H + 30), (-30, H + 30)], (250, 230, 190), line=False)
    for _ in range(40):
        x, y = k.r.uniform(0, W), k.r.uniform(910, H)
        k.ell(x, y, 3, 2, (226, 200, 156), line=False)
    return {"ground": 930}


def pl_rooftop(k, front=False):
    if front:
        return None
    for i in range(16):
        x, h = i * 128 - 30 + k.r.uniform(-14, 14), k.r.uniform(150, 380)
        k.rect(x, 760 - h, x + 112, 800, k.far((120, 132, 170), 0.62), line=False, raw=True)
    for i in range(9):
        x, h = i * 226 - 40 + k.r.uniform(-20, 20), k.r.uniform(200, 470)
        k.rect(x, 830 - h, x + 190, 860, k.far((104, 116, 160), 0.25), line=False, raw=True)
        k.windows(x + 22, 850 - h + 10, x + 172, 820, lit=0.55)
    k.band(840, H, (214, 210, 214), (182, 180, 192))
    k.stroke([(0, 840), (W, 840)], None, k.lw)
    for x in range(0, W + 1, 96):
        k.stroke([(x, 840), (x, 770)], (120, 126, 150), 7)
    k.stroke([(0, 770), (W, 770)], (120, 126, 150), 9)
    return {"ground": 930}


def pl_street(k, front=False):
    if front:
        return None
    cols = ((246, 214, 190), (212, 230, 240), (250, 232, 180), (226, 206, 236), (206, 232, 208), (248, 200, 196))
    x = -40
    while x < W + 40:
        wd, h, col = k.r.uniform(230, 330), k.r.uniform(330, 560), k.r.choice(cols)
        k.rect(x, 820 - h, x + wd, 824, col)
        k.windows(x + 30, 820 - h + 34, x + wd - 30, 600, cw=44, ch=56, gap=30, lit=0.6)
        k.rect(x + 30, 660, x + wd - 30, 822, (255, 248, 236) if not k.dark else (255, 226, 160), r=6, e=k.dark)
        k.poly([(x + 12, 660), (x + wd - 12, 660), (x + wd - 34, 610), (x + 34, 610)], k.r.choice(((232, 120, 130), (96, 170, 176), (232, 180, 90), (140, 150, 210))))
        x += wd
    k.band(822, 900, (226, 224, 226), (204, 202, 210)); k.band(900, H, (150, 154, 170), (124, 128, 150))
    k.stroke([(0, 822), (W, 822)], None, k.lw); k.stroke([(0, 900), (W, 900)], None, k.lw)
    for x in range(60, W, 260):
        k.rect(x, 984, x + 120, 996, (240, 240, 244), line=False)
    for x in (k.r.uniform(200, 500), k.r.uniform(1400, 1700)):
        k.lamp(x, 880, 400)
    return {"ground": 880}


def pl_school(k, front=False):
    if front:
        return pl_meadow(k, True)
    k.ridge(700, 36, (140, 200, 170), far=0.55)
    x = k.r.choice((520, 1400))
    k.rect(x - 380, 470, x + 380, 800, (252, 244, 228)); k.rect(x - 110, 350, x + 110, 800, (255, 250, 238))
    k.poly([(x - 130, 350), (x, 270), (x + 130, 350)], (226, 120, 116))
    k.ell(x, 420, 44, 44, (255, 255, 255)); k.stroke([(x, 420), (x, 392)], None, 5); k.stroke([(x, 420), (x + 20, 428)], None, 5)
    k.windows(x - 350, 510, x - 130, 760, cw=50, ch=58, gap=26, lit=0.4); k.windows(x + 130, 510, x + 350, 760, cw=50, ch=58, gap=26, lit=0.4)
    k.rect(x - 44, 690, x + 44, 800, (176, 132, 108), r=6)
    k.band(800, H, (232, 214, 180), (212, 190, 156)); k.stroke([(0, 800), (W, 800)], None, k.lw)
    k.tree(W - x + k.r.uniform(-160, 160), 850, 1.2, col=k.r.choice(((118, 190, 132), (255, 196, 214))))
    return {"ground": 890}


def pl_classroom(k, front=False):
    if front:
        for x in (140, 760, 1380):
            k.rect(x, 1000, x + 400, 1030, (224, 184, 140), r=6); k.rect(x + 20, 1030, x + 380, H + 20, (206, 164, 124), line=False)
        return None
    wall, trim = (250, 240, 222), (236, 222, 198)
    k.rect(-10, -10, W + 10, 150, wall, line=False); k.rect(-10, 700, W + 10, 880, wall, line=False)
    for x in (-10, 610, 1250, 1870):
        k.rect(x, 140, x + 60, 710, wall, line=False)
    for x0, x1 in ((50, 610), (670, 1250), (1310, 1870)):
        k.rect(x0, 150, x1, 700, (255, 255, 255, 34), r=0); k.stroke([((x0 + x1) / 2, 150), ((x0 + x1) / 2, 700)], None, k.lw); k.stroke([(x0, 420), (x1, 420)], None, k.lw)
    k.rect(-10, 700, W + 10, 730, trim); k.band(880, H, (226, 196, 160), (204, 170, 134)); k.stroke([(0, 880), (W, 880)], None, k.lw)
    return {"ground": 950}


def pl_station(k, front=False):
    if front:
        return None
    k.ridge(690, 30, (140, 196, 176), far=0.55)
    k.band(780, 850, (176, 168, 160), (150, 144, 140))
    for y in (800, 832):
        k.stroke([(0, y), (W, y)], (110, 112, 128), 6)
    for x in range(0, W, 70):
        k.stroke([(x, 792), (x + 14, 842)], (146, 124, 108), 6)
    if k.r.random() < 0.7:
        x = k.r.uniform(-200, 900)
        k.rect(x, 560, x + 1000, 800, (240, 244, 248), r=28); k.rect(x, 700, x + 1000, 740, k.r.choice(((232, 120, 130), (96, 150, 210), (110, 180, 140))), line=False)
        for i in range(6):
            k.rect(x + 50 + i * 156, 600, x + 170 + i * 156, 690, (255, 236, 170) if k.dark else (196, 226, 246), r=8, e=k.dark)
    k.band(850, H, (228, 224, 220), (200, 196, 198)); k.stroke([(0, 850), (W, 850)], None, k.lw)
    k.rect(-10, 868, W + 10, 884, (250, 214, 96), line=False)
    for x in (300, 960, 1620):
        k.rect(x - 12, 250, x + 12, 860, (120, 128, 150))
    k.poly([(-20, 250), (W + 20, 250), (W + 20, 190), (-20, 220)], (150, 160, 184))
    xs = k.r.choice((630, 1290)); k.rect(xs - 150, 290, xs + 150, 370, (255, 255, 255), r=8); k.rect(xs - 110, 318, xs + 110, 342, (96, 150, 210), line=False, r=6)
    return {"ground": 940}


def pl_park(k, front=False):
    if front:
        return pl_meadow(k, True)
    for i in range(9):
        k.tree(i * 250 - 40 + k.r.uniform(-50, 50), 760, k.r.uniform(0.8, 1.1), far=0.5)
    k.band(760, H, (176, 226, 164), (132, 198, 136)); k.stroke([(0, 760), (W, 760)], None, max(2, k.lw - 1))
    k.poly([(k.r.uniform(600, 1300), 760), (-60, H + 20), (520, H + 20), (k.r.uniform(600, 1300) + 60, 760)], (244, 228, 196), line=False)
    k.lamp(k.r.choice((330, 1590)), 860, 380)
    k.tree(k.r.choice((140, 1780)), 880, 1.35, col=k.r.choice(((118, 190, 132), (255, 196, 214), (250, 190, 110))))
    return {"ground": 900}


def pl_bridge(k, front=False):
    if front:
        for x in range(30, W, 150):
            k.stroke([(x, 800), (x, 700)], (150, 110, 96), 10)
        k.stroke([(0, 700), (W, 700)], (150, 110, 96), 12); k.stroke([(0, 750), (W, 750)], (150, 110, 96), 7)
        return None
    k.ridge(640, 34, (130, 190, 170), far=0.6)
    for i in range(10):
        x, h = i * 200 + k.r.uniform(-30, 30), k.r.uniform(60, 190)
        k.rect(x, 690 - h, x + 120, 700, k.far((130, 140, 176), 0.6), line=False, raw=True)
    k.band(690, H, (150, 206, 232), (96, 160, 206))
    for i in range(14):
        y, x = 860 + i * 15, k.r.uniform(0, W - 300)
        k.stroke([(x, y), (x + k.r.uniform(100, 320), y)], (255, 255, 255, 100), 3)
    k.rect(-10, 850, W + 10, H + 10, (190, 138, 118), line=False)
    for x in (-200, 440, 1080, 1720):
        k.d.pieslice([P(x), P(900), P(x + 520), P(900 + 620)], 180, 360, fill=k.c((104, 164, 206)), outline=k.edge(k.c((190, 138, 118))), width=P(k.lw))
    k.rect(-10, 800, W + 10, 852, (214, 160, 136))
    return {"ground": 800}


def pl_forest(k, front=False):
    if front:
        for x in (k.r.uniform(-60, 80), k.r.uniform(W - 120, W + 20)):
            k.poly([(x - 70, H + 20), (x - 44, -20), (x + 60, -20), (x + 84, H + 20)], (104, 82, 76))
        for _ in range(26):
            x, y = k.r.uniform(0, W), k.r.uniform(990, H + 10)
            k.ell(x, y, k.r.uniform(26, 50), k.r.uniform(14, 24), (86, 160, 112), line=False)
        return None
    k.rect(-10, -10, W + 10, 700, k.far((96, 160, 130), 0.35), line=False, raw=True)
    for i in range(22):
        x, wd = k.r.uniform(0, W), k.r.uniform(18, 40)
        k.rect(x, -10, x + wd, 760, k.far((120, 110, 110), 0.5), line=False, raw=True)
    if k.light in ("day", "dawn", "golden"):
        for _ in range(5):
            x = k.r.uniform(100, W - 300)
            k.d.polygon([(P(x), 0), (P(x + 150), 0), (P(x - 150), P(900)), (P(x - 420), P(900))], fill=(255, 250, 210, 34))
    k.band(740, H, (150, 204, 150), (104, 164, 116))
    for i in range(7):
        x, s = i * 290 + k.r.uniform(-60, 60), k.r.uniform(1.0, 1.5)
        k.poly([(x - 30 * s, 800 + s * 40), (x - 20 * s, -20), (x + 20 * s, -20), (x + 30 * s, 800 + s * 40)], (132, 104, 92))
    k.poly([(900, 740), (1010, 740), (1500, H + 20), (420, H + 20)], (226, 208, 170), line=False)
    return {"ground": 900}


def pl_lake(k, front=False):
    if front:
        return None
    peaks = [(k.r.uniform(200, 600), k.r.uniform(330, 420)), (k.r.uniform(800, 1150), k.r.uniform(260, 360)), (k.r.uniform(1350, 1750), k.r.uniform(340, 430))]
    for x, top in peaks:
        f = k.far((120, 160, 196), 0.42)
        k.poly([(x - 560, 650), (x, top), (x + 560, 650)], f, line=False, raw=True)
        k.poly([(x - 74, top + 62), (x, top), (x + 74, top + 62), (x + 26, top + 48), (x - 18, top + 70)], (255, 255, 255), line=False)
    k.band(650, 830, (170, 216, 238), (112, 176, 216))
    for x, top in peaks:
        k.d.polygon([(P(x - 560), P(650)), (P(x), P(650 + (650 - top) * 0.5)), (P(x + 560), P(650))], fill=k.far((120, 160, 196), 0.42) + (70,))
    for i in range(10):
        y, x = 670 + i * 16, k.r.uniform(0, W - 300)
        k.stroke([(x, y), (x + k.r.uniform(100, 300), y)], (255, 255, 255, 110), 3)
    k.band(830, H, (176, 220, 164), (130, 190, 134)); k.ridge(830, 10, (176, 220, 164), rough=0.8)
    for x in (k.r.uniform(60, 240), k.r.uniform(1680, 1860)):
        k.tree(x, 890, 1.2, col=(88, 160, 126), kind="pine")
    return {"ground": 900}


def pl_room(k, front=False):
    if front:
        return None
    wall = k.r.choice(((250, 238, 224), (232, 240, 246), (244, 232, 240), (236, 244, 230)))
    x0 = k.r.choice((240, 880))
    x1 = x0 + 800
    k.rect(-10, -10, x0, 890, wall, line=False); k.rect(x1, -10, W + 10, 890, wall, line=False)
    k.rect(x0 - 10, -10, x1 + 10, 170, wall, line=False); k.rect(x0 - 10, 690, x1 + 10, 890, wall, line=False)
    k.rect(x0, 170, x1, 690, (255, 255, 255, 30)); k.stroke([((x0 + x1) / 2, 170), ((x0 + x1) / 2, 690)], None, k.lw); k.stroke([(x0, 430), (x1, 430)], None, k.lw)
    k.rect(x0 - 30, 690, x1 + 30, 716, (255, 252, 244))
    cur = k.r.choice(((250, 200, 196), (190, 220, 236), (250, 232, 170), (206, 196, 236)))
    k.poly([(x0 - 40, 150), (x0 + 110, 150), (x0 + 60, 700), (x0 - 40, 700)], cur); k.poly([(x1 + 40, 150), (x1 - 110, 150), (x1 - 60, 700), (x1 + 40, 700)], cur)
    k.band(880, H, (228, 196, 160), (206, 172, 136)); k.stroke([(0, 880), (W, 880)], None, k.lw)
    px = 1560 if x0 < 500 else 250
    k.rect(px - 150, 700, px + 150, 720, (204, 160, 124)); k.rect(px - 130, 720, px - 110, 880, (184, 142, 110)); k.rect(px + 110, 720, px + 130, 880, (184, 142, 110))
    k.rect(px - 40, 640, px + 40, 700, (240, 150, 130), r=10)
    for a in (-0.5, 0, 0.5):
        k.ell(px + math.sin(a) * 60, 600 - math.cos(a) * 20, 26, 52, (110, 186, 130))
    if k.dark:
        k.d.ellipse([P(px - 260), P(430), P(px + 260), P(950)], fill=(255, 236, 170, 30))
    return {"ground": 950}


def pl_flowers(k, front=False):
    if front:
        cols = ((255, 150, 170), (255, 222, 110), (255, 255, 255), (200, 160, 240))
        for _ in range(26):
            x, y, col, rr = k.r.uniform(0, W), k.r.uniform(970, H), k.r.choice(cols), k.r.uniform(12, 20)
            k.stroke([(x, y), (x, y + 90)], (84, 160, 104), 5)
            for a in range(6):
                k.ell(x + math.cos(a * 1.047) * rr, y + math.sin(a * 1.047) * rr, rr * 0.8, rr * 0.8, col, line=False)
            k.ell(x, y, rr * 0.6, rr * 0.6, (255, 196, 80), line=False)
        return None
    k.ridge(650, 40, (150, 200, 180), far=0.6)
    hx = k.r.uniform(300, 1600)
    k.rect(hx - 50, 580, hx + 50, 660, k.far((250, 240, 226), 0.3), line=False, raw=True); k.poly([(hx - 66, 580), (hx, 530), (hx + 66, 580)], k.far((226, 120, 116), 0.3), line=False, raw=True)
    k.band(700, H, (182, 226, 160), (120, 190, 124))
    cols = ((255, 150, 170), (255, 222, 110), (255, 255, 255), (200, 160, 240), (255, 180, 120))
    for row in range(11):
        y = 716 + row * row * 3.4
        col, rr = cols[row % len(cols)], 3 + row * 0.9
        for i in range(int(90 - row * 5)):
            x = k.r.uniform(0, W)
            k.ell(x, y + k.r.uniform(-8, 8), rr, rr * 0.8, col, line=False)
    return {"ground": 900}


def pl_road(k, front=False):
    if front:
        return pl_meadow(k, True)
    k.ridge(660, 38, (136, 196, 176), far=0.6)
    k.band(720, H, (186, 226, 150), (136, 196, 126)); k.stroke([(0, 720), (W, 720)], None, max(2, k.lw - 1))
    vx = k.r.uniform(700, 1220)
    k.poly([(vx - 14, 720), (vx + 14, 720), (1560, H + 20), (360, H + 20)], (214, 208, 204), line=False)
    for i in range(7):
        t = (i / 7) ** 1.8
        y = 730 + t * 340
        k.rect(vx - 3 - t * 10 + (960 - vx) * t, y, vx + 3 + t * 10 + (960 - vx) * t, y + 10 + t * 40, (255, 255, 255), line=False)
    side = k.r.choice((-1, 1))
    prev = None
    for i in range(6):
        t = (i / 5) ** 1.6
        x, y, h = vx + side * (40 + t * 720), 724 + t * 250, 70 + t * 420
        k.stroke([(x, y), (x, y - h)], (120, 104, 100), 4 + t * 10); k.stroke([(x - h * 0.16, y - h * 0.9), (x + h * 0.16, y - h * 0.9)], (120, 104, 100), 3 + t * 7)
        if prev:
            k.stroke([(prev[0], prev[1]), ((prev[0] + x) / 2, (prev[1] + y - h * 0.9) / 2 + 16 + t * 30), (x, y - h * 0.9)], (90, 90, 104), 2)
        prev = (x, y - h * 0.9)
    return {"ground": 910}


def pl_pier(k, front=False):
    if front:
        return None
    k.band(600, H, (150, 214, 236), (70, 150, 200))
    for i in range(26):
        y, x = 620 + i * 17, k.r.uniform(0, W - 300)
        k.stroke([(x, y), (x + k.r.uniform(100, 340), y)], (255, 255, 255, 100), 3)
    lx = k.r.choice((260, 1660))
    k.poly([(lx - 150, 604), (lx - 60, 570), (lx + 150, 604)], k.far((120, 150, 150), 0.4), line=False, raw=True)
    k.poly([(lx - 16, 596), (lx - 10, 470), (lx + 10, 470), (lx + 16, 596)], (255, 252, 244)); k.rect(lx - 16, 450, lx + 16, 474, (232, 110, 110))
    if k.dark:
        k.d.polygon([(P(lx), P(460)), (P(lx + (700 if lx < 900 else -700)), P(380)), (P(lx + (700 if lx < 900 else -700)), P(520))], fill=(255, 244, 180, 50))
    bx = W - lx + k.r.uniform(-200, 200)
    k.poly([(bx - 80, 650), (bx + 80, 650), (bx + 56, 676), (bx - 56, 676)], (255, 255, 255)); k.poly([(bx, 650), (bx, 560), (bx + 60, 640)], (255, 236, 200))
    k.poly([(620, 840), (1300, 840), (1640, H + 20), (280, H + 20)], (214, 172, 132))
    for i in range(6):
        y = 860 + i * i * 7
        k.stroke([(620 - (y - 840) * 1.42, y), (1300 + (y - 840) * 1.42, y)], (176, 134, 104), 4)
    for x, y in ((600, 850), (1320, 850), (420, 980), (1500, 980)):
        k.rect(x - 16, y - 90, x + 16, y + 30, (160, 120, 96), r=6)
    return {"ground": 930}


def pl_hill(k, front=False):
    if front:
        return pl_meadow(k, True)
    k.ridge(700, 30, (140, 196, 180), far=0.65)
    for i in range(14):
        x = k.r.uniform(0, W)
        f = k.far(k.r.choice(((250, 236, 220), (236, 214, 200), (226, 232, 240))), 0.45)
        k.rect(x, 716, x + 46, 752, f, line=False, raw=True); k.poly([(x - 8, 716), (x + 23, 692), (x + 54, 716)], k.far((214, 120, 110), 0.45), line=False, raw=True)
    pts = [(x, 800 + ((x - 960) / 960) ** 2 * 190) for x in range(-30, W + 60, 30)]
    k.poly(pts + [(W + 30, H + 30), (-30, H + 30)], (160, 216, 150))
    k.tree(k.r.choice((430, 1500)), 850, 1.5, col=k.r.choice(((118, 190, 132), (255, 196, 214), (250, 196, 110))))
    return {"ground": 860}


PLACE_FN = {"meadow": pl_meadow, "sea": pl_sea, "rooftop": pl_rooftop, "street": pl_street, "school": pl_school,
            "classroom": pl_classroom, "station": pl_station, "park": pl_park, "bridge": pl_bridge, "forest": pl_forest,
            "lake": pl_lake, "room": pl_room, "flowers": pl_flowers, "road": pl_road, "pier": pl_pier, "hill": pl_hill}


# --------------------------------------------------------------------------------------------- the people
ARMS = {"down": ((-52, -150), (52, -150)), "up": ((-70, -292), (52, -150)), "both": ((-80, -292), (80, -292)),
        "wave": ((-52, -150), (88, -300)), "out": ((-124, -204), (124, -204)), "hold_r": ((-52, -150), (86, -146)),
        "hold_l": ((-86, -146), (52, -150)), "fwd_r": ((-52, -150), (104, -196)), "fwd_l": ((-104, -196), (52, -150))}


def figure(k, who, x, y, s, face="front", arms="down", sit=False, walk=False):
    """One of the song's two people, feet at (x, y). Returns where the head and hands are."""
    p = k.w[who]
    girl = who == "girl"
    hd = float(k.w["head"])
    hair, top, low, ecol = tuple(p["hair"]), tuple(p["top"]), tuple(p["low"]), tuple(p["extra_col"])
    cut, wear, extra = p["cut"], p["wear"], p["extra"]
    tall = float(k.w.get("tall", 0) or 0)
    b = y + (48 * s if sit else -tall * s)     # where the feet would be standing: the body hangs from here
    hy, hr = b - (222 + 38 * hd) * s, 46 * hd * s
    back = face == "back"
    if wear == "hoodie":
        top = ecol
    k.shadow(x, y, s)
    if not back:                               # hair behind the head and shoulders
        if girl and cut == "long": k.poly([(x - hr * 1.12, hy - 6 * s), (x + hr * 1.12, hy - 6 * s), (x + hr, hy + hr * 2.5), (x - hr, hy + hr * 2.5)], hair)
        elif girl and cut == "bob": k.poly([(x - hr * 1.16, hy - 6 * s), (x + hr * 1.16, hy - 6 * s), (x + hr * 1.26, hy + hr * 1.2), (x - hr * 1.26, hy + hr * 1.2)], hair)
        elif girl and cut == "ponytail": k.ell(x + hr * 1.2, hy + hr * 0.8, hr * 0.38, hr * 1.14, hair)
        elif girl and cut == "twin":
            for sx in (-1, 1): k.ell(x + sx * hr * 1.3, hy + hr, hr * 0.36, hr * 1.1, hair)
        if wear == "hoodie": k.ell(x, b - 214 * s, 54 * s, 30 * s, top)
    # legs
    fl, fr = (x - 24 * s, y), (x + 24 * s, y)
    if walk:
        fl, fr = (x - 52 * s, y - 4 * s), (x + 46 * s, y)
        if walk > 1:
            fl, fr = (x - 88 * s, y - 30 * s), (x + 70 * s, y)
    leg = SKIN if girl else low
    k.limb([(x - 22 * s, b - 112 * s), fl], leg, 13 * s, skin=girl); k.limb([(x + 22 * s, b - 112 * s), fr], leg, 13 * s, skin=girl)
    for fx, fy in (fl, fr):
        k.ell(fx + (6 * s if not back else 0), fy, 17 * s, 9 * s, (250, 250, 252) if girl else (84, 90, 110))
    # clothes
    if girl and wear == "dress":
        k.poly([(x - 42 * s, b - 222 * s), (x + 42 * s, b - 222 * s), (x + 70 * s, b - 76 * s), (x - 70 * s, b - 76 * s)], low)
        top = low
    else:
        if girl and wear == "skirt": k.poly([(x - 40 * s, b - 152 * s), (x + 40 * s, b - 152 * s), (x + 64 * s, b - 84 * s), (x - 64 * s, b - 84 * s)], low)
        else: k.rect(x - 40 * s, b - 152 * s, x + 40 * s, b - 100 * s, low, r=8 * s)
        k.rect(x - 42 * s, b - 222 * s, x + 42 * s, b - 140 * s, top, r=16 * s)
        if wear == "jacket" and not back:
            k.rect(x - 42 * s, b - 222 * s, x - 12 * s, b - 140 * s, ecol, r=10 * s); k.rect(x + 12 * s, b - 222 * s, x + 42 * s, b - 140 * s, ecol, r=10 * s)
        elif wear == "jacket":
            k.rect(x - 42 * s, b - 222 * s, x + 42 * s, b - 140 * s, ecol, r=16 * s)
        if wear == "hoodie" and not back: k.stroke([(x - 20 * s, b - 160 * s), (x + 20 * s, b - 160 * s)], None, 3)
    sleeve = ecol if wear == "jacket" else top
    hands = []
    for sx, (ax, ay) in zip((-1, 1), ARMS[arms]):
        hx_, hy_ = x + ax * s, b + ay * s
        k.limb([(x + sx * 40 * s, b - 208 * s), (hx_, hy_)], sleeve, 12 * s)
        k.ell(hx_, hy_, 10 * s, 10 * s, SKIN, skin=True)
        hands.append((hx_, hy_))
    if extra == "scarf":
        k.rect(x - 40 * s, b - 232 * s, x + 40 * s, b - 204 * s, ecol, r=10 * s); k.rect(x + 14 * s, b - 214 * s, x + 36 * s, b - 150 * s, ecol, r=8 * s)
    # head
    k.ell(x, hy, hr, hr, SKIN, skin=True)
    hc = k.c(hair)
    if back:
        k.ell(x, hy - hr * 0.06, hr * 1.06, hr * 1.02, hair)
        if girl and cut == "long": k.poly([(x - hr * 1.04, hy), (x + hr * 1.04, hy), (x + hr * 0.96, hy + hr * 2.6), (x - hr * 0.96, hy + hr * 2.6)], hair)
        elif girl and cut == "bob": k.poly([(x - hr * 1.04, hy), (x + hr * 1.04, hy), (x + hr * 1.2, hy + hr * 1.26), (x - hr * 1.2, hy + hr * 1.26)], hair)
        elif girl and cut == "ponytail": k.poly([(x - hr * 0.32, hy + hr * 0.6), (x + hr * 0.32, hy + hr * 0.6), (x + hr * 0.44, hy + hr * 2.8), (x - hr * 0.44, hy + hr * 2.8)], hair)
        elif girl and cut == "twin":
            for sx in (-1, 1): k.poly([(x + sx * hr * 0.6, hy + hr * 0.5), (x + sx * hr * 1.14, hy + hr * 0.5), (x + sx * hr * 1.3, hy + hr * 2.6), (x + sx * hr * 0.74, hy + hr * 2.6)], hair)
    else:
        k.d.pieslice([P(x - hr * 1.05), P(hy - hr * 1.09), P(x + hr * 1.05), P(hy + hr * 0.86)], 180, 360, fill=hc, outline=k.edge(hc), width=P(k.lw))
        if not girl and cut == "fringe": k.poly([(x - hr * 0.9, hy - hr * 0.1), (x + hr * 0.2, hy - hr * 0.1), (x - hr * 0.5, hy + hr * 0.3)], hair, line=False)
        dx = {"front": 0, "left": -9, "right": 9}[face] * hd * s
        mood = k.mood
        for e in (-16, 16):
            if mood == "closed": k.d.arc([P(x + e * hd * s + dx - 8 * hd * s), P(hy + hr * 0.02), P(x + e * hd * s + dx + 8 * hd * s), P(hy + hr * 0.26)], 20, 160, fill=(46, 50, 74), width=P(max(2, 3 * s)))
            else: k.ell(x + e * hd * s + dx, hy + hr * 0.14, (6.5 if mood == "wow" else 5) * hd * s, (9 if mood == "wow" else 7) * hd * s, (46, 50, 74), line=False)
        if not k.flat:
            for e in (-27, 27): k.ell(x + e * hd * s + dx, hy + hr * 0.44, 9 * hd * s, 6 * hd * s, (255, 168, 168, 150), line=False, e=True)
            if mood == "sad": k.d.arc([P(x - 8 * hd * s + dx), P(hy + hr * 0.5), P(x + 8 * hd * s + dx), P(hy + hr * 0.76)], 200, 340, fill=(120, 70, 80), width=P(max(2, 3 * s)))
            elif mood == "wow": k.ell(x + dx, hy + hr * 0.56, 5 * hd * s, 6 * hd * s, (150, 80, 90), line=False)
            else: k.d.arc([P(x - 8 * hd * s + dx), P(hy + hr * 0.36), P(x + 8 * hd * s + dx), P(hy + hr * 0.62)], 20, 160, fill=(120, 70, 80), width=P(max(2, 3 * s)))
        if extra == "glasses":
            for e in (-16, 16): k.d.ellipse([P(x + e * hd * s + dx - 13 * hd * s), P(hy + hr * 0.14 - 12 * hd * s), P(x + e * hd * s + dx + 13 * hd * s), P(hy + hr * 0.14 + 12 * hd * s)], outline=(60, 66, 90), width=P(3))
            k.stroke([(x - 3 * hd * s + dx, hy + hr * 0.14), (x + 3 * hd * s + dx, hy + hr * 0.14)], (60, 66, 90), 3, raw=True)
    if girl and cut == "bun": k.ell(x, hy - hr * 1.12, hr * 0.44, hr * 0.4, hair)
    if not girl and cut == "spiky":
        for i in (-2, -1, 0, 1, 2): k.poly([(x + i * hr * 0.36 - hr * 0.24, hy - hr * 0.84), (x + i * hr * 0.42, hy - hr * (1.3 - abs(i) * 0.08)), (x + i * hr * 0.36 + hr * 0.24, hy - hr * 0.84)], hair, line=False)
    if extra == "hat":
        k.ell(x, hy - hr * 0.62, hr * 1.36, hr * 0.26, ecol); k.d.pieslice([P(x - hr * 0.92), P(hy - hr * 1.5), P(x + hr * 0.92), P(hy + hr * 0.2)], 180, 360, fill=k.c(ecol), outline=k.edge(k.c(ecol)), width=P(k.lw))
    elif extra == "ribbon" and girl:
        rx, ry = x + hr * 0.62, hy - hr * 0.9
        k.poly([(rx, ry), (rx - 26 * s, ry - 18 * s), (rx - 26 * s, ry + 18 * s)], ecol); k.poly([(rx, ry), (rx + 26 * s, ry - 18 * s), (rx + 26 * s, ry + 18 * s)], ecol)
    if k.rim:                                  # the light behind: a bright edge on that side
        a0, a1 = (-70, 70) if k.rim > 0 else (110, 250)
        k.d.arc([P(x - hr * 1.04), P(hy - hr * 1.06), P(x + hr * 1.04), P(hy + hr * 1.0)], a0, a1, fill=(255, 244, 214, 230), width=P(max(3, 5 * s)))
        k.d.line([(P(x + k.rim * 43 * s), P(b - 214 * s)), (P(x + k.rim * 43 * s), P(b - 150 * s))], fill=(255, 244, 214, 210), width=P(max(3, 5 * s)))
    return {"x": x, "y": y, "s": s, "head": (x, hy, hr), "hands": hands, "top": b - 222 * s}


def bench(k, x, y, s, wide=True):
    w = (190 if wide else 110) * s
    for sx in (-1, 1): k.rect(x + sx * (w - 24 * s) - 8 * s, y - 60 * s, x + sx * (w - 24 * s) + 8 * s, y + 4 * s, (150, 110, 92))
    k.rect(x - w, y - 72 * s, x + w, y - 56 * s, (206, 156, 122), r=5 * s)
    k.rect(x - w, y - 150 * s, x + w, y - 132 * s, (206, 156, 122), r=5 * s)


def people(k, subject, pos, frame, ground, n):
    """Put the people of the subject in the picture. Returns [lead, other] (either can be None)."""
    lead = k.w["lead"]
    other = "boy" if lead == "girl" else "girl"
    s = {"wide": 0.82, "mid": 1.14, "close": 2.2}[frame]
    y = 1130 if frame == "close" else ground + (6 if frame == "wide" else 28)
    x = {"l": 560, "c": 960, "r": 1360}[pos]
    flip = n % 2 == 1
    if subject == "none":
        return [None, None]
    if subject == "solo_front": return [figure(k, lead, x, y, s, "front"), None]
    if subject == "solo_back": return [figure(k, lead, x, y, s, "back"), None]
    if subject == "other_back": return [None, figure(k, other, x, y, s, "back")]
    if subject == "solo_walk": return [figure(k, lead, x, y, s, "left" if pos == "r" else "right", "fwd_l" if pos == "r" else "fwd_r", walk=True), None]
    if subject == "solo_run": return [figure(k, lead, x, y, s, "left" if pos == "r" else "right", "out", walk=2), None]
    if subject == "duo_hug":
        return [figure(k, lead, 960 - 52 * s, y, s, "right", "hold_r"), figure(k, other, 960 + 52 * s, y, s, "left", "hold_l")]
    if subject == "solo_reach": return [figure(k, lead, x, y, s, "front" if flip else "back", "up"), None]
    if subject == "solo_open": return [figure(k, lead, x, y, s, "front" if flip else "back", "out"), None]
    if subject == "solo_wave": return [figure(k, lead, x, y, s, "front", "wave"), None]
    if subject == "solo_sit":
        bench(k, x, y, s, wide=False)
        return [figure(k, lead, x, y, s, "front" if flip else "back", sit=True), None]
    x = 960
    if subject == "duo_sit":
        bench(k, x, y, s)
        f = "front" if flip else "back"
        return [figure(k, lead, x - 86 * s, y, s, f, sit=True), figure(k, other, x + 86 * s, y, s, f, sit=True)]
    if subject == "duo_apart":
        g = min(560, 420 / s + 200)
        return [figure(k, lead, x - g, y, s, "left" if not flip else "back"), figure(k, other, x + g, y, s, "right" if not flip else "back")]
    if subject == "duo_hands":
        f = "front" if flip else "back"
        return [figure(k, lead, x - 80 * s, y, s, f, "hold_r"), figure(k, other, x + 80 * s, y, s, f, "hold_l")]
    if subject == "duo_face":
        return [figure(k, lead, x - 120 * s, y, s, "right", "fwd_r"), figure(k, other, x + 120 * s, y, s, "left", "fwd_l")]
    f = "back" if subject == "duo_back" else "front"
    return [figure(k, lead, x - 84 * s, y, s, f), figure(k, other, x + 84 * s, y, s, f, "wave" if f == "front" and flip else "down")]


# --------------------------------------------------------------------------------------------- the things
def _heart(k, x, y, s, col=(255, 120, 144)):
    k.ell(x - 14 * s, y - 8 * s, 16 * s, 16 * s, col, line=False, e=True); k.ell(x + 14 * s, y - 8 * s, 16 * s, 16 * s, col, line=False, e=True)
    k.poly([(x - 29 * s, y - 2 * s), (x + 29 * s, y - 2 * s), (x, y + 32 * s)], col, line=False, e=True)


def _star(k, x, y, rr, col=(255, 240, 160)):
    k.poly([(x + math.cos(-math.pi / 2 + i * math.pi / 5) * (rr if i % 2 == 0 else rr * 0.45), y + math.sin(-math.pi / 2 + i * math.pi / 5) * (rr if i % 2 == 0 else rr * 0.45)) for i in range(10)], col, line=False, e=True)


def _bubble(k, x, y, mark, side=1):
    k.rect(x - 110, y - 70, x + 110, y + 70, (255, 255, 255), r=56, e=True)
    k.poly([(x - side * 60, y + 62), (x - side * 16, y + 62), (x - side * 84, y + 124)], (255, 255, 255), e=True)
    k.rect(x - side * 66 - 4, y + 44, x - side * 12 + 4, y + 64, (255, 255, 255), line=False, e=True)
    ink = (60, 68, 100)
    if mark == "dots":
        for i in (-1, 0, 1): k.ell(x + i * 46, y, 12, 12, ink, line=False, e=True)
    elif mark == "call":
        k.rect(x - 9, y - 42, x + 9, y + 12, (255, 120, 136), line=False, r=8, e=True); k.ell(x, y + 34, 11, 11, (255, 120, 136), line=False, e=True)
    else:
        k.d.arc([P(x - 26), P(y - 46), P(x + 26), P(y + 6)], 200, 80, fill=ink, width=P(9)); k.stroke([(x + 4, y + 2), (x, y + 18)], ink, 9, raw=True); k.ell(x, y + 38, 8, 8, ink, line=False, e=True)


def thing(k, prop, phase, who, ground):
    """Paint the card's small thing. phase "back": behind the place (sky); "mid": on the ground behind the
    people; "front": in front of everything. who: [lead, other] from people() (None in the back phase)."""
    r = k.r
    one = next((f for f in (who or []) if f), None)
    if phase == "back":
        if prop == "stars":
            for _ in range(60):
                x, y, rr = r.uniform(0, W), r.uniform(0, 600), r.choice((2, 3, 3, 4))
                k.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 255, 255, 230))
            for _ in range(7): _star(k, r.uniform(80, W - 80), r.uniform(60, 480), r.uniform(14, 28))
        elif prop == "shooting":
            for _ in range(r.choice((1, 2, 2))):
                x, y, ln = r.uniform(500, W - 200), r.uniform(120, 380), r.uniform(320, 520)
                for i in range(24):
                    t = i / 24
                    k.d.line([(P(x - ln * t), P(y - ln * 0.42 * t)), (P(x - ln * (t + 0.05)), P(y - ln * 0.42 * (t + 0.05)))], fill=(255, 255, 255, int(235 * (1 - t))), width=P(7 * (1 - t) + 1))
                _star(k, x, y, 22)
        elif prop == "bigmoon":
            x, y, rr = r.choice((440, 1480)), r.uniform(250, 340), 190
            for g in range(6, 0, -1): k.d.ellipse([P(x - rr - g * 22), P(y - rr - g * 22), P(x + rr + g * 22), P(y + rr + g * 22)], fill=(255, 250, 214, 12))
            k.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 248, 214))
            for dx, dy, cr in ((-60, -40, 34), (50, 30, 46), (-20, 80, 22), (80, -70, 20)): k.d.ellipse([P(x + dx - cr), P(y + dy - cr), P(x + dx + cr), P(y + dy + cr)], fill=(244, 232, 190))
        elif prop == "rainbow":
            cx, cy = r.uniform(700, 1220), 900
            for i, col in enumerate(((255, 130, 130), (255, 190, 120), (255, 236, 140), (150, 220, 150), (140, 190, 250), (190, 160, 240))):
                rr = 760 - i * 26
                k.d.arc([P(cx - rr), P(cy - rr), P(cx + rr), P(cy + rr)], 180, 360, fill=col + (150,), width=P(27))
        elif prop == "birds":
            bx, by = r.uniform(300, W - 500), r.uniform(120, 320)
            for i in range(r.randint(5, 9)):
                x, y, sz = bx + r.uniform(-40, 420), by + r.uniform(-70, 120), r.uniform(12, 22)
                k.stroke([(x - sz, y - sz * 0.5), (x, y), (x + sz, y - sz * 0.5)], None, 4)
        elif prop == "lantern":
            for _ in range(9):
                x, y, sz = r.uniform(100, W - 100), r.uniform(60, 560), r.uniform(0.5, 1.3)
                k.d.ellipse([P(x - 70 * sz), P(y - 70 * sz), P(x + 70 * sz), P(y + 70 * sz)], fill=(255, 210, 120, 40))
                k.poly([(x - 26 * sz, y - 34 * sz), (x + 26 * sz, y - 34 * sz), (x + 20 * sz, y + 30 * sz), (x - 20 * sz, y + 30 * sz)], (255, 190, 110), e=True)
                k.rect(x - 12 * sz, y + 30 * sz, x + 12 * sz, y + 38 * sz, (255, 236, 170), line=False, e=True)
        elif prop == "frames":
            xs = [r.uniform(260, 520), r.uniform(840, 1080), r.uniform(1400, 1660)]
            k.stroke([(0, 150), (W / 2, 210), (W, 150)], (150, 130, 120), 4)
            for i, x in enumerate(xs):
                y = 250 + r.uniform(-20, 40)
                k.stroke([(x, 190), (x, y - 70)], (150, 130, 120), 3)
                k.rect(x - 120, y - 80, x + 120, y + 110, (255, 255, 255), r=6, e=True)
                k.rect(x - 100, y - 62, x + 100, y + 60, ((190, 226, 250), (255, 214, 190), (206, 236, 206))[i], line=False, e=True)
                k.ell(x + (i - 1) * 30, y + 6, 24, 24, ((255, 240, 160), (255, 150, 150), (255, 255, 255))[i], line=False, e=True)
        elif prop == "clock":
            x, y, rr = r.choice((480, 1440)), 320, 190
            k.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 255, 255, 120), outline=(255, 255, 255, 220), width=P(10))
            for i in range(12):
                a = i * math.pi / 6
                k.d.line([(P(x + math.cos(a) * rr * 0.84), P(y + math.sin(a) * rr * 0.84)), (P(x + math.cos(a) * rr * 0.94), P(y + math.sin(a) * rr * 0.94))], fill=(255, 255, 255, 230), width=P(6))
            a1, a2 = r.uniform(0, 6.28), r.uniform(0, 6.28)
            k.d.line([(P(x), P(y)), (P(x + math.cos(a1) * rr * 0.5), P(y + math.sin(a1) * rr * 0.5))], fill=(255, 255, 255, 240), width=P(12))
            k.d.line([(P(x), P(y)), (P(x + math.cos(a2) * rr * 0.76), P(y + math.sin(a2) * rr * 0.76))], fill=(255, 255, 255, 240), width=P(7))
        elif prop == "plane":
            x, y, sz = r.uniform(500, 1400), r.uniform(150, 330), r.uniform(1.0, 1.6)
            pts = [(x - 300 * sz + i * 30 * sz, y + 90 * sz - math.sin(i / 3) * 30 * sz - i * 8 * sz) for i in range(10)]
            for a, b_ in zip(pts[::2], pts[1::2]): k.stroke([a, b_], (255, 255, 255), 4, e=True)
            k.poly([(x - 70 * sz, y + 10 * sz), (x + 80 * sz, y - 40 * sz), (x - 10 * sz, y + 44 * sz)], (255, 255, 255), e=True); k.poly([(x - 10 * sz, y + 44 * sz), (x + 80 * sz, y - 40 * sz), (x + 6 * sz, y + 12 * sz)], (226, 234, 246), e=True)
        elif prop == "kite" and not who:
            pass
        return
    if phase == "mid":
        if prop == "bike" and one:
            x, y, s = one["x"] - 150 * one["s"], one["y"], one["s"]
            for dx in (-80, 80): k.d.ellipse([P(x + (dx - 58) * s), P(y - 116 * s), P(x + (dx + 58) * s), P(y)], outline=k.ink or (70, 76, 100), width=P(6))
            k.stroke([(x - 80 * s, y - 58 * s), (x - 10 * s, y - 58 * s), (x + 50 * s, y - 136 * s), (x - 40 * s, y - 136 * s), (x - 80 * s, y - 58 * s)], (232, 120, 130), 7)
            k.stroke([(x + 50 * s, y - 136 * s), (x + 80 * s, y - 58 * s)], (232, 120, 130), 7); k.stroke([(x + 36 * s, y - 170 * s), (x + 74 * s, y - 166 * s)], None, 7); k.stroke([(x - 56 * s, y - 146 * s), (x - 24 * s, y - 146 * s)], None, 9)
        elif prop == "wings" and one:
            x, s = one["x"], one["s"]
            y = one["top"] + 30 * s
            for sx in (-1, 1):
                for i in range(5):
                    a = -0.5 + i * 0.32
                    k.poly([(x + sx * 20 * s, y), (x + sx * (230 - i * 26) * s, y - (150 - i * 74) * s * math.cos(a)), (x + sx * (150 - i * 14) * s, y + (30 + i * 22) * s)], (255, 255, 255), e=True)
        elif prop == "clover":
            x = (one["x"] + 230 * one["s"]) if one else 960
            y, s = ground, (one["s"] if one else 1.0) * 1.3
            k.stroke([(x, y), (x - 10 * s, y - 110 * s)], (84, 160, 100), 6 * s)
            for a in range(4):
                ang = a * math.pi / 2 + math.pi / 4
                cx, cy = x - 10 * s + math.cos(ang) * 30 * s, y - 120 * s + math.sin(ang) * 30 * s
                for b_ in (-0.45, 0.45): k.ell(cx + math.cos(ang + b_) * 14 * s, cy + math.sin(ang + b_) * 14 * s, 20 * s, 20 * s, (112, 200, 126), line=False)
        return
    # front
    if prop == "hearts":
        bx, by = (one["head"][0], one["head"][1] - one["head"][2] * 1.6) if one else (960, 420)
        if who and who[0] and who[1]: bx = (who[0]["x"] + who[1]["x"]) / 2
        _heart(k, bx, by - 60, 2.0)
        for _ in range(6): _heart(k, bx + r.uniform(-260, 260), by - r.uniform(40, 330), r.uniform(0.6, 1.2), r.choice(((255, 150, 170), (255, 120, 144), (255, 190, 200))))
    elif prop == "letter":
        x, y, s = r.choice((430, 1490)), r.uniform(280, 380), r.uniform(1.3, 1.7)
        k.rect(x - 130 * s, y - 84 * s, x + 130 * s, y + 84 * s, (255, 252, 242), r=8, e=True)
        k.stroke([(x - 130 * s, y - 84 * s), (x, y + 6 * s), (x + 130 * s, y - 84 * s)], None, k.lw); _heart(k, x, y + 2 * s, 1.0 * s)
        for _ in range(4): k.rect(*(lambda px, py: (px, py, px + 44, py + 56))(r.uniform(200, W - 240), r.uniform(120, 520)), (255, 255, 255, 190), line=False, r=4, e=True)
    elif prop == "balloons":
        hx, hy_ = one["hands"][1] if one else (960, ground - 200)
        for i, col in enumerate(((255, 150, 160), (255, 220, 120), (150, 214, 190), (170, 190, 255), (255, 190, 220))):
            x, y = hx + (i - 2) * 86 + r.uniform(-20, 20), hy_ - r.uniform(300, 460)
            k.stroke([(hx, hy_), (x, y + 80)], None, 2); k.ell(x, y, 60, 76, col, e=True); k.ell(x - 20, y - 26, 12, 18, (255, 255, 255, 150), line=False, e=True)
    elif prop == "tears" and one:
        hx, hy_, hr = one["head"]
        for dx, dy in ((-0.42, 0.5), (0.5, 0.74)):
            x, y = hx + dx * hr, hy_ + dy * hr
            k.poly([(x, y - hr * 0.3), (x + hr * 0.17, y + hr * 0.08), (x, y + hr * 0.24), (x - hr * 0.17, y + hr * 0.08)], (150, 212, 255), e=True)
    elif prop in ("dots", "ask", "call") and one:
        hx, hy_, hr = one["head"]
        side = 1 if hx < 960 else -1
        _bubble(k, hx + side * (hr + 150), max(110, hy_ - hr - 110), prop, side)
    elif prop == "notes":
        bx, by = (one["head"][0], one["head"][1]) if one else (960, 500)
        for i in range(6):
            x, y, s = bx + r.uniform(-330, 330), by - r.uniform(110, 420), r.uniform(0.8, 1.5)
            col = r.choice(((255, 255, 255), (255, 236, 150), (255, 190, 210)))
            k.ell(x, y, 16 * s, 12 * s, col, line=False, e=True); k.stroke([(x + 14 * s, y), (x + 14 * s, y - 62 * s)], col, 5 * s, e=True); k.stroke([(x + 14 * s, y - 62 * s), (x + 40 * s, y - 50 * s)], col, 7 * s, e=True)
    elif prop == "kite":
        x, y = r.uniform(500, 1400), r.uniform(150, 300)
        hx, hy_ = one["hands"][1] if one else (960, ground - 100)
        k.stroke([(hx, hy_), ((hx + x) / 2, (hy_ + y) / 2 + 80), (x, y + 70)], None, 2)
        k.poly([(x, y - 80), (x + 56, y), (x, y + 70), (x - 56, y)], (255, 150, 130), e=True); k.stroke([(x, y - 80), (x, y + 70)], None, 3); k.stroke([(x - 56, y), (x + 56, y)], None, 3)
    elif prop == "umbrella" and one:
        hx, hy_, hr = one["head"]
        s, col = one["s"], r.choice(((255, 150, 160), (255, 214, 110), (140, 190, 250), (160, 220, 180)))
        k.stroke([(hx + hr * 0.9, hy_ + hr * 2.4), (hx + hr * 0.9, hy_ - hr * 1.6)], None, 5 * s)
        k.d.pieslice([P(hx + hr * 0.9 - 170 * s), P(hy_ - hr * 1.6 - 120 * s), P(hx + hr * 0.9 + 170 * s), P(hy_ - hr * 1.6 + 120 * s)], 180, 360, fill=col, outline=k.edge(col), width=P(k.lw))
    elif prop == "thread" and who and who[0] and who[1]:
        (ax, ay), (bx, by) = who[0]["hands"][1], who[1]["hands"][0]
        pts = [(ax + (bx - ax) * t, ay + (by - ay) * t + math.sin(t * math.pi) * 60 + math.sin(t * math.pi * 3) * 16) for t in [i / 30 for i in range(31)]]
        k.stroke(pts, (232, 70, 90), 5, e=True)
    elif prop in ("petals", "leaves", "fireflies", "bubbles"):
        for _ in range({"petals": 70, "leaves": 44, "fireflies": 46, "bubbles": 26}[prop]):
            x, y = r.uniform(0, W), r.uniform(0, H)
            if prop == "petals": k.ell(x, y, r.uniform(7, 13), r.uniform(4, 7), r.choice(((255, 200, 216), (255, 226, 232), (255, 180, 200))), line=False)
            elif prop == "leaves":
                a, col = r.uniform(0, 3.14), r.choice(((240, 170, 90), (226, 120, 90), (250, 210, 110), (150, 200, 120)))
                k.poly([(x - math.cos(a) * 20, y - math.sin(a) * 20), (x - math.sin(a) * 8, y + math.cos(a) * 8), (x + math.cos(a) * 20, y + math.sin(a) * 20), (x + math.sin(a) * 8, y - math.cos(a) * 8)], col, line=False)
            elif prop == "fireflies":
                y = r.uniform(300, H)
                k.d.ellipse([P(x - 16), P(y - 16), P(x + 16), P(y + 16)], fill=(236, 255, 150, 50)); k.d.ellipse([P(x - 5), P(y - 5), P(x + 5), P(y + 5)], fill=(246, 255, 190))
            else:
                rr = r.uniform(14, 44)
                k.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 255, 255, 36), outline=(255, 255, 255, 190), width=P(3)); k.d.ellipse([P(x - rr * 0.5), P(y - rr * 0.6), P(x - rr * 0.2), P(y - rr * 0.3)], fill=(255, 255, 255, 200))


def weather(k, kind):
    if kind == "rain":
        for _ in range(300):
            x, y, ln = k.r.uniform(-60, W), k.r.uniform(-40, H), k.r.uniform(24, 60)
            k.d.line([(P(x), P(y)), (P(x + ln * 0.25), P(y + ln))], fill=(255, 255, 255, k.r.randint(90, 180)), width=P(3))
    elif kind == "snow":
        for _ in range(200):
            x, y, rr = k.r.uniform(0, W), k.r.uniform(0, H), k.r.uniform(3, 9)
            k.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 255, 255, k.r.randint(170, 250)))


# ------------------------------------------------------------------------------------------------ the card
def _finish(k, border):
    im = k.im.resize((W, H), Image.LANCZOS)
    im = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.1)).enhance(1.14)     # the mixing of lights leaves it a little pale
    # the corners a little darker, so the middle of the card holds the eye
    small = Image.new("L", (96, 54))
    px = small.load()
    for yy in range(54):
        for xx in range(96):
            dd = math.hypot((xx - 47.5) / 47.5, (yy - 26.5) / 26.5)
            px[xx, yy] = int(max(0.0, min(1.0, (dd - 0.78) / 0.7)) * 56)
    im = Image.composite(Image.new("RGB", (W, H), (20, 24, 50)), im, small.resize((W, H), Image.BILINEAR))
    d = ImageDraw.Draw(im, "RGBA")
    ink = k.ink or (70, 76, 100)
    if border == "comic":
        d.rounded_rectangle([14, 14, W - 15, H - 15], radius=26, outline=(255, 255, 255), width=18); d.rounded_rectangle([24, 24, W - 25, H - 25], radius=20, outline=ink, width=4)
    elif border == "round":
        d.rounded_rectangle([-40, -40, W + 39, H + 39], radius=110, outline=(255, 252, 244), width=76)
    elif border == "film":
        d.rectangle([0, 0, W, 46], fill=(24, 26, 40)); d.rectangle([0, H - 46, W, H], fill=(24, 26, 40))
        for x in range(30, W, 96):
            d.rounded_rectangle([x, 12, x + 40, 34], radius=6, fill=(236, 236, 228)); d.rounded_rectangle([x, H - 34, x + 40, H - 12], radius=6, fill=(236, 236, 228))
    return im


def draw(spec: str, world: Dict[str, Any], seed: int = 0) -> Image.Image:
    """The card as a 1920x1080 picture (the same spec, world and seed always give the same picture)."""
    got = parse(spec)
    if not got or not valid_world(world):
        raise KeyError(spec)
    place, light, wth, subject, prop, frame, pos, n = got
    import zlib
    k = K(world, light, zlib.crc32(spec.encode()) + int(seed) % 999983)
    std = k.std
    if frame in FRAMES_STD and not std:
        frame = "mid"
    k.sky()
    sun = None
    if wth == "clear" and place != "forest":
        sun = k.orb(horizon=680, side=("l" if pos == "r" else "r") if frame == "sil" else None)
    if place != "forest":
        k.clouds()
    thing(k, prop, "back", None, 0)
    info = PLACE_FN[place](k) or {}
    ground = float(info.get("ground", 900))
    if std:
        k.mood = MOODS.get(prop, "sad" if subject in SAD_SUBJECTS else "smile")
        if sun and place not in INDOOR + INDOOR_STD and light in ("golden", "sunset", "dawn", "dusk", "night"):
            k.rim = 1 if sun[0] > 960 else -1
    if frame == "still":
        k.blur(9)
        shot_still(k, prop, n)
        thing(k, prop if prop in ("petals", "leaves", "fireflies", "bubbles", "notes") else "none", "front", [None, None], ground)
    elif frame == "hands":
        k.blur(9)
        shot_hands(k, subject, prop, n)
        thing(k, prop if prop in ("petals", "leaves", "fireflies", "bubbles") else "none", "front", [None, None], ground)
    else:
        shot = "mid" if frame in ("sil", "over") else frame
        probe = {"l": 560, "c": 960, "r": 1360}[pos]
        who = None
        if prop in ("bike", "wings", "clover") and subject != "none":
            # these go behind the person, who is not there yet: work out where the person will be
            s = {"wide": 0.82, "mid": 1.14, "close": 2.2}[shot]
            y = 1130 if shot == "close" else ground + (6 if shot == "wide" else 28)
            b = y + (48 * s if subject.endswith("sit") else -float(world.get("tall", 0) or 0) * s)
            who = [{"x": probe if not subject.startswith("duo") else 960 - 84 * s, "y": y, "s": s, "top": b - 222 * s}, None]
        thing(k, prop, "mid", who, ground)
        if frame == "sil":       # against the light: the ground and the people are dark shapes
            k.d.rectangle([0, P(ground - 40), W * S, H * S], fill=(24, 22, 46, 150))
            k.flat = _mix((26, 24, 48), k.sky3[0], 0.12)
        if shot == "close" or frame == "over":
            PLACE_FN[place](k, True)
        if frame == "over":
            k.blur(5)
        who = people(k, subject, pos, shot, ground, n)
        if shot != "close" and frame != "over":
            PLACE_FN[place](k, True)
        k.flat = None
        if frame == "over":      # someone's shoulder and head in front, looking on
            k.blur(3)
            watcher = "boy" if world["lead"] == "girl" else "girl"
            rim, k.rim = k.rim, 0
            figure(k, watcher, 330 if pos != "l" else 1590, 1900, 4.2, "back")
            k.rim = rim
        thing(k, prop, "front", who, ground)
    weather(k, wth)
    im = _finish(k, world["border"])
    return _finish_standard(im, zlib.crc32(spec.encode())) if std else im


# ------------------------------------------------------------------------- the standard grade: more places
def pl_cafe(k, front=False):
    if front:
        k.rect(-10, 990, W + 10, H + 20, (176, 128, 100)); k.rect(-10, 968, W + 10, 996, (206, 156, 122), r=6)
        return None
    wall = k.r.choice(((250, 236, 214), (236, 226, 214), (240, 232, 226)))
    k.rect(-10, -10, W + 10, 120, wall, line=False); k.rect(-10, 700, W + 10, 880, wall, line=False)
    for x in (-10, 930, 1870):
        k.rect(x, 110, x + 60, 710, wall, line=False)
    for x0, x1 in ((50, 930), (990, 1870)):
        k.rect(x0, 120, x1, 700, (255, 255, 255, 26)); k.stroke([(x0, 250), (x1, 250)], None, k.lw)
    k.rect(-10, 700, W + 10, 726, (206, 156, 122))
    for x in (300, 760, 1220, 1680):
        k.stroke([(x, -10), (x, 150)], (90, 84, 96), 4)
        k.d.ellipse([P(x - 120), P(120), P(x + 120), P(360)], fill=(255, 232, 170, 30))
        k.poly([(x - 46, 210), (x + 46, 210), (x + 24, 150), (x - 24, 150)], (240, 190, 120)); k.ell(x, 214, 22, 12, (255, 244, 190), e=True)
    k.band(880, H, (214, 180, 150), (190, 152, 124)); k.stroke([(0, 880), (W, 880)], None, k.lw)
    for x in (k.r.uniform(160, 330), k.r.uniform(1560, 1740)):
        k.rect(x - 110, 760, x + 110, 782, (206, 156, 122), r=6); k.rect(x - 10, 782, x + 10, 900, (150, 110, 92))
        k.rect(x - 34, 716, x - 6, 760, (255, 255, 255), r=6); k.rect(x + 20, 728, x + 60, 760, (240, 150, 130), r=6)
    return {"ground": 950}


def pl_busstop(k, front=False):
    if front:
        return None
    k.ridge(690, 34, (140, 196, 176), far=0.55)
    for i in range(7):
        k.tree(i * 320 - 60 + k.r.uniform(-60, 60), 800, k.r.uniform(0.8, 1.1), far=0.45)
    k.band(800, 880, (226, 224, 226), (204, 202, 210)); k.band(880, H, (150, 154, 170), (122, 126, 150))
    k.stroke([(0, 800), (W, 800)], None, k.lw); k.stroke([(0, 880), (W, 880)], None, k.lw)
    for x in range(40, W, 280):
        k.rect(x, 976, x + 130, 990, (240, 240, 244), line=False)
    x = k.r.choice((520, 1400))
    k.rect(x - 250, 470, x + 250, 500, (120, 150, 190), r=8)
    for sx in (-236, 236):
        k.rect(x + sx - 8, 500, x + sx + 8, 860, (120, 128, 150))
    k.rect(x - 228, 520, x + 228, 760, (220, 240, 250, 90), r=4); k.rect(x - 180, 800, x + 180, 818, (206, 156, 122), r=5)
    sx = x + (330 if x < 960 else -330)
    k.rect(sx - 6, 520, sx + 6, 860, (120, 128, 150)); k.ell(sx, 500, 44, 44, (250, 214, 96)); k.rect(sx - 22, 492, sx + 22, 508, (96, 110, 150), line=False)
    k.lamp(W - x + k.r.uniform(-120, 120), 860, 400)
    return {"ground": 866}


def pl_library(k, front=False):
    if front:
        return None
    k.rect(-10, -10, W + 10, 890, (238, 226, 208), line=False)
    wx = k.r.choice((660, 960, 1260))
    cols = ((214, 110, 104), (96, 150, 190), (232, 180, 90), (120, 176, 130), (150, 120, 190), (236, 228, 214), (84, 96, 130))
    for x0 in range(-60, W, 300):
        if abs(x0 + 130 - wx) < 200:
            continue
        k.rect(x0, 120, x0 + 260, 880, (176, 128, 100))
        for sh in range(5):
            y1 = 250 + sh * 150
            k.rect(x0 + 14, y1 - 116, x0 + 246, y1, (120, 86, 72), line=False)
            bx = x0 + 18
            while bx < x0 + 232:
                bw, bh = k.r.uniform(12, 26), k.r.uniform(74, 110)
                k.rect(bx, y1 - bh, bx + bw, y1, k.r.choice(cols), line=False, r=2)
                bx += bw + 2
    k.rect(wx - 170, 150, wx + 170, 700, (255, 255, 255, 30)); k.stroke([(wx, 150), (wx, 700)], None, k.lw)
    k.rect(wx - 190, 700, wx + 190, 724, (206, 156, 122))
    k.d.polygon([(P(wx - 170), P(700)), (P(wx + 170), P(700)), (P(wx + 480), P(H)), (P(wx - 480), P(H))], fill=(255, 244, 200, 30))
    k.band(880, H, (206, 170, 134), (176, 140, 110)); k.stroke([(0, 880), (W, 880)], None, k.lw)
    return {"ground": 950}


def pl_train(k, front=False):
    if front:
        return None
    k.ridge(560, 40, (140, 196, 176), far=0.5); k.ridge(640, 26, (150, 206, 150), far=0.25)
    for _ in range(5):
        x = k.r.uniform(0, W)
        k.rect(x, 590, x + 60, 650, k.far((250, 236, 220), 0.3), line=False, raw=True)
    wall = k.r.choice(((236, 238, 240), (240, 232, 220), (226, 236, 232)))
    k.rect(-10, -10, W + 10, 200, wall, line=False); k.rect(-10, 660, W + 10, 900, wall, line=False)
    for x in (-10, 600, 1260, 1880):
        k.rect(x, 190, x + 60, 670, wall, line=False)
    for x0, x1 in ((50, 600), (660, 1260), (1320, 1880)):
        k.rect(x0, 200, x1, 660, (255, 255, 255, 24), r=30)
    k.stroke([(0, 120), (W, 120)], (150, 156, 170), 8)
    for x in range(120, W, 160):
        k.stroke([(x, 120), (x, 190)], (150, 156, 170), 4); k.d.ellipse([P(x - 22), P(190), P(x + 22), P(234)], outline=k.c((240, 240, 244)), width=P(7))
    seat = k.r.choice(((96, 150, 190), (120, 170, 130), (190, 110, 110), (150, 120, 180)))
    k.rect(-10, 700, W + 10, 790, seat, r=20); k.rect(-10, 790, W + 10, 880, _mix(seat, (30, 30, 50), 0.2))
    k.band(880, H, (196, 198, 204), (160, 164, 176)); k.stroke([(0, 880), (W, 880)], None, k.lw)
    return {"ground": 960}


def pl_market(k, front=False):
    if front:
        return None
    for i in range(12):
        x, h = i * 170 - 30, k.r.uniform(200, 420)
        k.rect(x, 720 - h, x + 150, 740, k.far((110, 120, 160), 0.4), line=False, raw=True)
        k.windows(x + 18, 730 - h + 14, x + 132, 700, lit=0.4)
    k.stroke([(0, 300), (480, 380), (960, 300), (1440, 380), (W, 300)], (90, 84, 96), 3)
    for i in range(16):
        x = 60 + i * 120
        y = 300 + (80 if (i // 4) % 2 == 0 else -80) * (((i % 4) + 0.5) / 4 if (i // 4) % 2 == 0 else 1 - ((i % 4) + 0.5) / 4) + (0 if (i // 4) % 2 == 0 else 80)
        col = ((255, 120, 110), (255, 214, 110), (150, 220, 170), (150, 190, 255))[i % 4]
        k.d.ellipse([P(x - 60), P(y - 40), P(x + 60), P(y + 80)], fill=col + (36,))
        k.ell(x, y + 22, 18, 24, col, e=True)
    x = -40
    while x < W:
        wd, col = k.r.uniform(300, 400), k.r.choice(((226, 96, 96), (236, 170, 70), (80, 150, 170), (150, 110, 180)))
        k.rect(x + 20, 560, x + wd - 20, 840, (255, 240, 200), e=True)
        for i in range(int(wd // 50)):
            k.rect(x + 34 + i * 50, 700, x + 70 + i * 50, 740, k.r.choice(((255, 150, 130), (255, 220, 120), (170, 220, 150), (255, 255, 255))), line=False, r=8, e=True)
        k.rect(x + 10, 740, x + wd - 10, 850, (176, 128, 100)); k.poly([(x, 560), (x + wd, 560), (x + wd - 30, 480), (x + 30, 480)], col)
        for i in range(int(wd // 60)):
            k.poly([(x + i * 60, 560), (x + i * 60 + 30, 590), (x + i * 60 + 60, 560)], col, line=False)
        x += wd
    k.band(850, H, (150, 146, 160), (116, 114, 136)); k.stroke([(0, 850), (W, 850)], None, k.lw)
    return {"ground": 930}


def pl_snowtown(k, front=False):
    if front:
        for _ in range(60):
            x, y, rr = k.r.uniform(0, W), k.r.uniform(0, H), k.r.uniform(4, 11)
            k.d.ellipse([P(x - rr), P(y - rr), P(x + rr), P(y + rr)], fill=(255, 255, 255, k.r.randint(150, 240)))
        return None
    k.ridge(650, 44, (226, 236, 246), far=0.3)
    for i in range(6):
        k.tree(i * 400 + k.r.uniform(-80, 80), 790, k.r.uniform(0.7, 1.0), col=(120, 170, 160), far=0.3, kind="pine")
    x = -30
    while x < W:
        wd, h = k.r.uniform(200, 300), k.r.uniform(130, 210)
        col = k.r.choice(((236, 200, 180), (214, 190, 170), (226, 214, 190), (200, 180, 190)))
        k.rect(x + 20, 800 - h, x + wd - 20, 810, col)
        k.poly([(x, 800 - h), (x + wd / 2, 800 - h - 110), (x + wd, 800 - h)], (255, 255, 255))
        k.rect(x + wd / 2 - 24, 800 - h + 40, x + wd / 2 + 24, 800 - h + 96, (255, 232, 150) if k.dark else (190, 220, 240), r=4, e=k.dark)
        k.rect(x + 40, 740, x + 84, 810, (150, 104, 88), r=4)
        x += wd + k.r.uniform(10, 60)
    k.band(800, H, (255, 255, 255), (220, 232, 246)); k.ridge(800, 10, (255, 255, 255), rough=0.9)
    k.lamp(k.r.choice((380, 1540)), 880, 380)
    return {"ground": 900}


def pl_garden(k, front=False):
    if front:
        return pl_flowers(k, True)
    k.ridge(680, 30, (140, 200, 170), far=0.55)
    for i in range(8):
        k.tree(i * 280 - 40 + k.r.uniform(-50, 50), 780, k.r.uniform(0.8, 1.0), far=0.4, col=k.r.choice(((118, 190, 132), (255, 196, 214))))
    k.band(780, H, (176, 226, 164), (130, 196, 134)); k.stroke([(0, 780), (W, 780)], None, max(2, k.lw - 1))
    for x in range(0, W + 1, 70):
        k.rect(x - 9, 720, x + 9, 800, (255, 252, 244), r=6)
    k.rect(-10, 742, W + 10, 756, (255, 252, 244))
    ax = k.r.uniform(700, 1220)
    k.d.arc([P(ax - 240), P(330), P(ax + 240), P(1290)], 180, 360, fill=k.c((150, 110, 92)), width=P(18))
    for i in range(26):
        a = math.pi + i * math.pi / 25
        x, y = ax + math.cos(a) * 240, 810 + math.sin(a) * 480
        k.ell(x, y, 26, 22, (104, 180, 124), line=False); k.ell(x + k.r.uniform(-12, 12), y + k.r.uniform(-12, 12), 13, 13, k.r.choice(((255, 150, 170), (255, 222, 110), (255, 255, 255), (200, 160, 240))), line=False)
    k.poly([(ax - 150, 780), (ax + 150, 780), (ax + 420, H + 20), (ax - 420, H + 20)], (240, 226, 196), line=False)
    return {"ground": 900}


def pl_alley(k, front=False):
    if front:
        return None
    k.rect(700, 300, 1220, 820, k.far((170, 180, 200), 0.5), line=False, raw=True)
    for side in (0, 1):
        x0, x1 = (-10, 620) if side == 0 else (1300, W + 10)
        k.rect(x0, -10, x1, 840, k.r.choice(((236, 220, 200), (220, 226, 232), (240, 228, 214), (226, 214, 226))))
        k.windows(x0 + 70, 110, x1 - 70, 520, cw=96, ch=120, gap=70, lit=0.6)
        dx = x1 - 190 if side == 0 else x0 + 60
        k.rect(dx, 590, dx + 130, 840, (150, 110, 92), r=6); k.poly([(dx - 30, 590), (dx + 160, 590), (dx + 140, 540), (dx - 10, 540)], k.r.choice(((226, 110, 110), (96, 160, 170), (232, 180, 90))))
        px = x0 + 80 if side == 0 else x1 - 150
        k.rect(px, 760, px + 70, 840, (220, 130, 100), r=8)
        for a in (-0.5, 0, 0.5):
            k.ell(px + 35 + math.sin(a) * 40, 720 - math.cos(a) * 10, 22, 46, (110, 186, 130))
    for y in (200, 330):
        k.stroke([(620, y), (960, y + 60), (1300, y - 10)], (90, 84, 96), 3)
    for i in range(6):
        k.rect(700 + i * 86, 262 + (i % 2) * 14 + 20, 760 + i * 86, 340 + (i % 2) * 14 + 20, k.r.choice(((255, 255, 255), (250, 200, 196), (190, 220, 236), (250, 232, 170))), r=4)
    k.band(820, H, (196, 190, 190), (160, 156, 164)); k.stroke([(0, 838), (W, 838)], None, k.lw)
    k.poly([(700, 820), (1220, 820), (1560, H + 20), (360, H + 20)], (214, 208, 204), line=False)
    return {"ground": 920}


def pl_field(k, front=False):
    if front:
        for _ in range(110):
            x, y = k.r.uniform(0, W), k.r.uniform(960, H + 20)
            k.stroke([(x, y), (x + k.r.uniform(-14, 14), y - k.r.uniform(60, 130))], (226, 190, 96), 5)
        return None
    k.ridge(660, 36, (140, 196, 176), far=0.6)
    mx = k.r.choice((380, 1540))
    k.poly([(mx - 34, 720), (mx - 20, 560), (mx + 20, 560), (mx + 34, 720)], k.far((250, 240, 226), 0.25), raw=True)
    for i in range(4):
        a = i * math.pi / 2 + 0.5
        k.poly([(mx, 560), (mx + math.cos(a) * 130 - math.sin(a) * 18, 560 + math.sin(a) * 130 + math.cos(a) * 18), (mx + math.cos(a) * 130 + math.sin(a) * 18, 560 + math.sin(a) * 130 - math.cos(a) * 18)], k.far((236, 226, 214), 0.2), raw=True)
    k.band(720, H, (244, 222, 140), (214, 180, 96))
    for row in range(12):
        y = 730 + row * row * 2.6
        k.stroke([(0, y), (W, y)], (206, 170, 90, 120), 2 + row * 0.5)
    k.poly([(900, 720), (1000, 720), (1300, H + 20), (640, H + 20)], (226, 206, 170), line=False)
    sx = W - mx
    k.stroke([(sx, 880), (sx, 700)], (150, 110, 92), 8); k.stroke([(sx - 70, 740), (sx + 70, 740)], (150, 110, 92), 8)
    k.ell(sx, 690, 26, 26, (250, 232, 190)); k.poly([(sx - 44, 676), (sx + 44, 676), (sx, 630)], (214, 150, 90))
    return {"ground": 900}


def pl_fair(k, front=False):
    if front:
        return None
    fx, fy, rr = k.r.choice((560, 1360)), 430, 300
    k.d.ellipse([P(fx - rr), P(fy - rr), P(fx + rr), P(fy + rr)], outline=k.far((150, 160, 200), 0.2), width=P(10))
    for i in range(12):
        a = i * math.pi / 6
        k.d.line([(P(fx), P(fy)), (P(fx + math.cos(a) * rr), P(fy + math.sin(a) * rr))], fill=k.far((150, 160, 200), 0.3), width=P(5))
        cx, cy = fx + math.cos(a) * rr, fy + math.sin(a) * rr
        k.rect(cx - 30, cy - 6, cx + 30, cy + 44, ((255, 150, 150), (255, 220, 120), (150, 214, 190), (170, 190, 255))[i % 4], r=10, e=k.dark)
    k.poly([(fx - 120, 820), (fx, fy), (fx + 120, 820)], k.far((130, 140, 180), 0.2), line=False, raw=True)
    x = -20
    while x < W:
        wd = k.r.uniform(240, 340)
        if abs(x + wd / 2 - fx) > 260:
            col = k.r.choice(((232, 110, 110), (96, 160, 200), (236, 180, 80), (150, 120, 190)))
            k.rect(x + 30, 660, x + wd - 30, 830, (255, 248, 230))
            for i in range(6):
                k.poly([(x + 10 + i * (wd - 20) / 6, 660), (x + wd / 2, 540), (x + 10 + (i + 1) * (wd - 20) / 6, 660)], col if i % 2 == 0 else (255, 255, 255))
            k.stroke([(x + wd / 2, 540), (x + wd / 2, 500)], None, 4); k.poly([(x + wd / 2, 500), (x + wd / 2 + 40, 512), (x + wd / 2, 524)], col)
        x += wd
    k.stroke([(0, 600), (W / 2, 660), (W, 600)], (90, 84, 96), 3)
    for i in range(20):
        t = i / 19
        x, y = t * W, 600 + math.sin(t * math.pi) * 60
        k.ell(x, y + 14, 12, 16, ((255, 120, 110), (255, 214, 110), (150, 220, 170), (150, 190, 255))[i % 4], line=False, e=True)
    k.band(830, H, (232, 214, 190), (204, 184, 160)); k.stroke([(0, 830), (W, 830)], None, k.lw)
    return {"ground": 910}


def pl_stairs(k, front=False):
    if front:
        return None
    k.ridge(600, 40, (130, 190, 160), far=0.5)
    for i in range(7):
        k.tree(k.r.uniform(-40, 520) if i % 2 else k.r.uniform(1400, W + 40), k.r.uniform(700, 860), k.r.uniform(1.0, 1.5), col=k.r.choice(((104, 176, 124), (118, 190, 132), (250, 190, 110), (232, 120, 110))))
    k.band(860, H, (170, 214, 150), (126, 186, 126))
    for i in range(12):
        t = i / 11
        y, half = 470 + t * t * 520 + t * 90, 120 + t * 420
        k.rect(960 - half, y, 960 + half, y + 30 + t * 60, _mix((226, 222, 216), (190, 186, 190), i % 2 * 0.5 + 0.1))
    for sx in (-1, 1):
        for i in range(4):
            t = (i + 0.5) / 4
            x, y = 960 + sx * (170 + t * 430), 500 + t * t * 500 + t * 90
            sz = 0.5 + t * 0.9
            k.rect(x - 8 * sz, y - 150 * sz, x + 8 * sz, y, (120, 100, 96)); k.rect(x - 34 * sz, y - 210 * sz, x + 34 * sz, y - 150 * sz, (255, 232, 160) if k.dark else (250, 244, 232), r=6, e=k.dark)
            k.poly([(x - 46 * sz, y - 210 * sz), (x + 46 * sz, y - 210 * sz), (x, y - 250 * sz)], (190, 90, 90))
            if k.dark:
                k.d.ellipse([P(x - 110 * sz), P(y - 290 * sz), P(x + 110 * sz), P(y - 70 * sz)], fill=(255, 226, 150, 34))
    return {"ground": 1010}


def pl_riverbank(k, front=False):
    if front:
        return pl_meadow(k, True)
    for i in range(12):
        x, h = i * 170 + k.r.uniform(-30, 30), k.r.uniform(70, 230)
        k.rect(x, 640 - h, x + 130, 650, k.far((130, 140, 176), 0.6), line=False, raw=True)
    k.band(640, 760, (170, 216, 238), (112, 176, 216))
    for i in range(7):
        y, x = 656 + i * 15, k.r.uniform(0, W - 300)
        k.stroke([(x, y), (x + k.r.uniform(100, 300), y)], (255, 255, 255, 110), 3)
    k.rect(-10, 560, W + 10, 584, k.far((150, 150, 170), 0.3), line=False, raw=True)
    for x in range(100, W, 330):
        k.rect(x, 584, x + 30, 660, k.far((150, 150, 170), 0.3), line=False, raw=True)
    pts = [(x, 740 + (x / W) * 130 * (1 if k.r is None else 1)) for x in range(-30, W + 60, 60)]
    k.poly(pts + [(W + 30, H + 30), (-30, H + 30)], (160, 214, 150))
    k.poly([(-30, 930), (W + 30, 990), (W + 30, 1040), (-30, 990)], (226, 214, 196), line=False)
    k.tree(k.r.choice((200, 1700)), 900, 1.2)
    return {"ground": 920}


PLACE_FN.update({"cafe": pl_cafe, "busstop": pl_busstop, "library": pl_library, "train": pl_train, "market": pl_market,
                 "snowtown": pl_snowtown, "garden": pl_garden, "alley": pl_alley, "field": pl_field, "fair": pl_fair,
                 "stairs": pl_stairs, "riverbank": pl_riverbank})
HINTS_STD = (
    _row(("咖啡", "coffee", "cafe"), place="cafe"),
    _row(("公車", "巴士", "站牌", "bus"), place="busstop"),
    _row(("書", "圖書館", "故事", "book", "story"), place="library"),
    _row(("車廂", "電車", "捷運", "地鐵"), place="train"),
    _row(("夜市", "燈火", "熱鬧", "人群", "crowd"), place="market"),
    _row(("雪", "冬", "聖誕", "snow", "winter", "christmas"), place="snowtown", weather="snow"),
    _row(("花園", "玫瑰", "garden", "rose"), place="garden"),
    _row(("巷", "轉角", "角落", "老街", "corner"), place="alley"),
    _row(("田", "稻", "麥", "故鄉", "家鄉", "field"), place="field"),
    _row(("摩天輪", "遊樂", "約會", "煙火", "date"), place="fair"),
    _row(("階梯", "樓梯", "石階", "祈", "廟"), place="stairs"),
    _row(("河岸", "河邊", "堤", "岸"), place="riverbank"),
    _row(("跑", "追", "奔", "run", "running", "chase"), subject="solo_run"),
    _row(("擁抱", "抱", "懷裡", "hug", "arms"), subject="duo_hug"),
)
MOODS = {"tears": "sad", "hearts": "closed", "call": "wow", "ask": "wow", "shooting": "wow", "notes": "closed", "umbrella": "sad"}
SAD_SUBJECTS = ("duo_apart", "solo_back", "other_back")


def plan_standard(parts: Sequence[Tuple[str, str]], seed: int, world: Dict[str, Any]) -> List[str]:
    """plan() for a standard world: the same walk through the song, with the extra places and stances its
    words can call for, and about one card in four as another kind of shot: against the light, over a
    shoulder, two hands, or things on a table."""
    global HINTS
    keep = HINTS
    HINTS = HINTS_STD + HINTS          # the standard words first: they win over the simple ones
    try:
        specs = plan(parts, seed, world)
    finally:
        HINTS = keep
    r = random.Random(f"shots:{int(seed)}")
    out: List[str] = []
    seen = set()
    since = 2
    for (kind, _), spec in zip(parts, specs):
        place, light, wth, subject, prop, frame, pos, n = parse(spec)  # type: ignore[misc]
        if kind not in ("intro", "outro"):
            since += 1
            shot = ""
            outdoor = place not in INDOOR + INDOOR_STD
            if since >= 3 and r.random() < 0.6:
                if subject == "none" or prop in ("letter", "clock", "frames"):
                    shot = "still"
                elif outdoor and place != "forest" and wth == "clear" and light in ("sunset", "golden", "dawn", "dusk") and prop in ("none", "birds", "hearts", "thread", "leaves", "petals"):
                    shot = "sil"
                elif subject.startswith("duo") and subject != "duo_apart" and prop in ("none", "hearts", "thread", "petals", "leaves", "bubbles", "fireflies", "stars"):
                    shot = "hands"
                elif subject.startswith("solo") and subject not in ("solo_sit", "solo_run") and prop in ("none", "stars", "shooting", "bigmoon", "birds", "rainbow", "lantern", "kite", "plane", "balloons"):
                    shot = "over"
            if shot:
                frame, since = shot, 0
        spec = card(place, light, wth, subject, prop, frame, pos, n)
        while spec in seen:
            n += 1
            spec = card(place, light, wth, subject, prop, frame, pos, n)
        seen.add(spec)
        out.append(spec)
    return out


# ---- the other kinds of shot
def _hand(k, x, y, s, direction, sleeve):
    """A forearm coming in from the side (direction 1: from the left) with its hand at (x, y)."""
    k.limb([(x - direction * 900 * s, y + 260 * s), (x - direction * 110 * s, y + 20 * s)], sleeve, 150 * s)
    k.limb([(x - direction * 150 * s, y + 30 * s), (x - direction * 40 * s, y)], SKIN, 104 * s, skin=True)
    k.ell(x, y, 66 * s, 58 * s, SKIN, skin=True)
    for i in range(4):
        k.limb([(x + direction * 30 * s, y - 34 * s + i * 24 * s), (x + direction * (96 - abs(i - 1.5) * 10) * s, y - 30 * s + i * 24 * s)], SKIN, 22 * s, skin=True)
    k.limb([(x - direction * 10 * s, y - 50 * s), (x + direction * 40 * s, y - 78 * s)], SKIN, 24 * s, skin=True)


def shot_hands(k, subject, prop, n):
    lead = k.w["lead"]
    other = "boy" if lead == "girl" else "girl"
    sl = [tuple(k.w[w]["extra_col"]) if k.w[w]["wear"] in ("hoodie", "jacket") else tuple(k.w[w]["top"]) for w in (lead, other)]
    gap = {"duo_hands": 46, "duo_hug": 30, "duo_face": 150, "duo_sit": 60}.get(subject, 110) + (n % 3) * 30
    y = 600 + (n % 2) * 40
    _hand(k, 960 - gap, y, 1.0, 1, sl[0]); _hand(k, 960 + gap, y + 16, 1.0, -1, sl[1])
    if prop == "thread" or n % 4 == 3:
        pts = [(960 - gap + 70 + (2 * gap - 140) * t, y + 60 + math.sin(t * math.pi) * (90 if gap > 80 else 40)) for t in [i / 24 for i in range(25)]]
        k.stroke(pts, (232, 70, 90), 7, e=True)
    if prop == "hearts":
        _heart(k, 960, y - 230, 2.4)
        for dx, dy, sz in ((-210, -150, 1.0), (190, -300, 1.2), (60, -400, 0.8)): _heart(k, 960 + dx, y + dy, sz, (255, 170, 190))


def shot_still(k, prop, n):
    """Things on a table in front of the place (which is out of focus)."""
    wood = k.r.choice(((206, 156, 122), (176, 128, 100), (226, 190, 150)))
    k.band(600, H, wood, _mix(wood, (60, 40, 40), 0.25)); k.stroke([(0, 600), (W, 600)], None, k.lw)
    for i in range(6):
        k.stroke([(0, 660 + i * 80), (W, 660 + i * 80)], _mix(wood, (60, 40, 40), 0.18), 3, raw=True)
    x = 960 + ((n % 3) - 1) * 200
    k.d.ellipse([P(x - 560), P(900), P(x + 560), P(1010)], fill=(40, 24, 30, 40))
    if prop == "letter":
        k.poly([(x - 420, 800), (x + 200, 690), (x + 360, 900), (x - 280, 1020)], (255, 252, 242), e=True)
        k.stroke([(x - 420, 800), (x - 20, 890), (x + 200, 690)], None, k.lw); _heart(k, x - 14, 868, 1.9)
        k.limb([(x + 440, 940), (x + 760, 740)], (84, 96, 130), 30); k.poly([(x + 424, 954), (x + 456, 926), (x + 396, 984)], (60, 60, 70))
    elif prop == "clock":
        y = 700
        for sx in (-1, 1):
            k.ell(x + sx * 170, y - 220, 78, 66, (240, 120, 120)); k.limb([(x + sx * 150, y + 210), (x + sx * 200, y + 270)], (150, 110, 92), 26)
        k.ell(x, y, 250, 250, (240, 120, 120)); k.ell(x, y, 204, 204, (255, 252, 244), e=True)
        for i in range(12):
            a = i * math.pi / 6
            k.stroke([(x + math.cos(a) * 168, y + math.sin(a) * 168), (x + math.cos(a) * 188, y + math.sin(a) * 188)], (60, 68, 100), 9, raw=True)
        a1, a2 = k.r.uniform(0, 6.28), k.r.uniform(0, 6.28)
        k.stroke([(x, y), (x + math.cos(a1) * 100, y + math.sin(a1) * 100)], (60, 68, 100), 18, raw=True); k.stroke([(x, y), (x + math.cos(a2) * 154, y + math.sin(a2) * 154)], (60, 68, 100), 10, raw=True)
        k.ell(x, y, 16, 16, (240, 120, 120), line=False)
    elif prop == "frames":
        k.poly([(x - 290, 960), (x - 250, 420), (x + 270, 420), (x + 310, 960)], (255, 252, 244), e=True)
        k.rect(x - 216, 470, x + 236, 880, k.sky3[1], raw=True); k.ell(x + 130, 560, 44, 44, (255, 240, 160), line=False, e=True)
        k.rect(x - 216, 800, x + 236, 880, (150, 206, 150), line=False)
        for dx, who in ((-90, "girl"), (80, "boy")):
            k.rect(x + dx - 84, 800, x + dx + 84, 880, tuple(k.w[who]["top"]), r=30)
            k.ell(x + dx, 730, 70, 70, SKIN, skin=True); k.d.pieslice([P(x + dx - 74), P(654), P(x + dx + 74), P(790)], 180, 360, fill=k.c(tuple(k.w[who]["hair"])))
            for e in (-24, 24): k.ell(x + dx + e, 742, 7, 10, (46, 50, 74), line=False)
            k.d.arc([P(x + dx - 16), P(756), P(x + dx + 16), P(784)], 20, 160, fill=(120, 70, 80), width=P(4))
    else:
        cx = x - 280
        k.ell(cx, 940, 250, 56, (255, 255, 255), e=True); k.rect(cx - 160, 680, cx + 160, 930, (255, 255, 255), r=70, e=True)
        k.ell(cx, 690, 160, 42, (150, 100, 80), e=True); k.d.arc([P(cx + 110), P(730), P(cx + 280), P(880)], -90, 90, fill=k.edge((255, 255, 255)), width=P(20))
        for i in range(3):
            pts = [(cx - 80 + i * 80 + math.sin(t * 5 + i) * 24, 650 - t * 300) for t in [j / 14 for j in range(15)]]
            k.stroke(pts, (255, 255, 255, 150), 14, e=True)
        bx = x + 330
        cover = k.r.choice(((214, 110, 104), (96, 150, 190), (120, 176, 130), (160, 132, 204)))
        k.poly([(bx - 330, 900), (bx + 310, 800), (bx + 380, 980), (bx - 260, 1080)], cover)
        k.poly([(bx - 306, 924), (bx + 322, 824), (bx + 336, 866), (bx - 292, 966)], (255, 252, 244), line=False, e=True)
        if prop == "hearts": _heart(k, cx, 810, 2.4)


def _finish_standard(im: Image.Image, seed: int) -> Image.Image:
    """Light that spills from the bright parts, and a little grain (the same grain for the same card)."""
    small = im.resize((W // 4, H // 4), Image.BILINEAR).point(lambda v: max(0, v - 176) * 3)
    glow = small.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    im = ImageChops.screen(im, ImageEnhance.Brightness(glow).enhance(0.5))
    noise = Image.frombytes("L", (W // 2, H // 2), random.Random(seed).randbytes((W // 2) * (H // 2)))
    grain = noise.point(lambda v: 128 + (v - 128) // 5).resize((W, H), Image.BILINEAR).convert("RGB")
    return Image.blend(im, ImageChops.overlay(im, grain), 0.16)
