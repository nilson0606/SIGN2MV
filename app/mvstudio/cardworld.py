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

from . import card_icons

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
PROPS_STD = ("hourglass", "calendar", "suitcase", "phone", "key", "candle", "ring", "cranes", "dandelion", "broken", "wine",
             "guitar", "camera", "diary", "footprints", "door", "raincloud", "rays", "fireworks", "paperboat", "butterfly", "cat",
             "thought", "dream")
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
    if std:      # six put-together places, two of the painted ones, two rooms
        terrains, places = r.sample(TERRAINS, 5), []
        for i, lm in enumerate(r.sample(LANDMARKS, 6)):
            t = terrains[i % 5] if fits(lm, terrains[i % 5]) else r.choice([x for x in TERRAINS if fits(lm, x)])
            places.append(f"{t}.{lm}.{r.choice(FRONTS)}")
        places += r.sample(out_places, 2) + r.sample(indoor, 2)
    else:
        places = r.sample(out_places, 4) + [r.choice(INDOOR)]
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
    def parts(wd):      # a put-together place counts by its terrain and its landmark
        return {x for p in wd.get("places", []) for x in (str(p).split(".")[:2] if "." in str(p) else [p])}
    pa, pb = parts(a), parts(b)
    d += 3.0 * (min(len(pa), len(pb)) - len(pa & pb)) * 5.0 / max(5, min(len(pa), len(pb)))
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
        return (wd.get("v") == 2 and len(wd["places"]) >= 1 and all(valid_place(p) for p in wd["places"])
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
    if (len(p) == 9 and p[0] == "w2" and valid_place(p[1]) and p[2] in LIGHTS and p[3] in WEATHERS
            and p[4] in SUBJECTS + SUBJECTS_STD and (p[5] in PROPS + PROPS_STD or p[5] in card_icons.TABLE)
            and p[6] in FRAMES + FRAMES_STD and p[7] in POSES
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
    rooms = INDOOR + INDOOR_STD
    outdoor = [p for p in places if p not in rooms] or ["meadow"]
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
            if (h.get("terrain") or h.get("landmark")) and world.get("grade") == "standard" and h.get("place") not in PLACES_STD + rooms:
                # the standard grade's own words win over the simple grade's place for the same line
                pl = compose(place, h.get("terrain"), h.get("landmark"), world)
            light = h.get("light") or lights[min(len(lights) - 1, li * len(lights) // n_lines)]
            weather = h.get("weather", "clear")
            if pl in rooms and weather != "clear":
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
    if prop in PROPS_STD or prop in card_icons.TABLE:
        thing_standard(k, prop, "back", None, 0)
    info = paint_place(k, place) or {}
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
            paint_place(k, place, True)
        if frame == "over":
            k.blur(5)
        who = people(k, subject, pos, shot, ground, n)
        if shot != "close" and frame != "over":
            paint_place(k, place, True)
        k.flat = None
        if frame == "over":      # someone's shoulder and head in front, looking on
            k.blur(3)
            watcher = "boy" if world["lead"] == "girl" else "girl"
            rim, k.rim = k.rim, 0
            figure(k, watcher, 330 if pos != "l" else 1590, 1900, 4.2, "back")
            k.rim = rim
        thing(k, prop, "front", who, ground)
        if prop in PROPS_STD or prop in card_icons.TABLE:
            thing_standard(k, prop, "front", who, ground)
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
    _row(("公車", "巴士", "bus"), place="busstop"),
    _row(("書", "圖書館", "故事", "book", "story"), place="library"),
    _row(("車廂", "電車", "捷運", "地鐵"), place="train"),
    _row(("夜市", "燈火", "熱鬧", "人群", "crowd"), place="market"),
    _row(("花園", "玫瑰", "garden", "rose"), place="garden"),
    _row(("巷", "轉角", "角落", "老街", "corner"), place="alley"),
    _row(("階梯", "樓梯", "石階"), place="stairs"),
    _row(("河岸", "河邊", "堤", "岸"), place="riverbank"),
    # landmarks
    _row(("燈塔", "lighthouse"), landmark="lighthouse", terrain="cliff"),
    _row(("摩天輪", "約會", "date"), landmark="ferris"),
    _row(("風車",), landmark="windmill"),
    _row(("教堂", "婚禮", "誓言", "承諾", "嫁", "娶", "promise", "wedding"), landmark="chapel"),
    _row(("鐘樓", "鐘聲", "bell"), landmark="clocktower"),
    _row(("電話亭",), landmark="phonebooth"),
    _row(("鞦韆", "童年", "小時候", "長大", "childhood"), landmark="swings"),
    _row(("溜滑梯", "遊樂場", "公園"), landmark="slide"),
    _row(("營火", "露營", "帳篷", "篝火", "camp"), landmark="camp", light="night"),
    _row(("櫻", "春天", "spring"), landmark="cherry"),
    _row(("楓", "秋天", "落葉", "autumn", "fall"), landmark="maple"),
    _row(("噴泉", "廣場", "square"), landmark="fountain", terrain="plaza"),
    _row(("站牌", "等車"), landmark="shelter"),
    _row(("販賣機",), landmark="vending"),
    _row(("郵筒", "寄"), landmark="mailbox"),
    _row(("單車", "腳踏車"), landmark="bicycle"),
    _row(("汽車", "開車", "開往", "公路", "車窗", "drive", "car"), landmark="car"),
    _row(("列車", "火車", "鐵軌", "train"), landmark="trainpass"),
    _row(("橋", "bridge"), landmark="farbridge", terrain="river"),
    _row(("鐵塔", "電波", "廣播", "radio"), landmark="radiotower"),
    _row(("農", "穀倉", "故鄉", "家鄉", "老家", "hometown"), landmark="barn", terrain="wheat"),
    _row(("小屋", "木屋", "炊煙", "回家", "家門", "home"), landmark="cabin"),
    _row(("城堡", "王子", "公主", "童話", "castle", "fairy"), landmark="castle"),
    _row(("熱氣球",), landmark="hotair"),
    _row(("帆", "船", "航", "sail", "boat"), landmark="sailboats", terrain="coast"),
    _row(("天文", "宇宙", "星球", "universe"), landmark="observatory", light="night"),
    _row(("溫室", "栽", "灌溉", "grow"), landmark="greenhouse"),
    _row(("舞台", "演唱", "掌聲", "聚光", "stage"), landmark="stage"),
    _row(("旋轉木馬", "遊樂園", "樂園"), landmark="carousel"),
    _row(("雪人",), landmark="snowman", terrain="snow", weather="snow"),
    _row(("稻草人",), landmark="scarecrow", terrain="wheat"),
    _row(("路口", "方向", "迷路", "選擇", "岔路", "direction", "lost"), landmark="signpost"),
    _row(("井", "許願"), landmark="well"),
    _row(("涼亭",), landmark="gazebo"),
    _row(("鋼琴", "琴聲", "piano"), landmark="piano"),
    _row(("望遠鏡", "眺望", "遠望"), landmark="telescope"),
    _row(("碼頭", "棧橋", "pier"), landmark="jetty"),
    _row(("飛機", "機場", "航班", "plane", "flight"), landmark="jet"),
    _row(("市集", "園遊會", "祭"), landmark="tents"),
    _row(("燈籠", "廟", "祈"), landmark="lanterns"),
    # terrains
    _row(("海", "浪", "沙灘", "sea", "ocean", "beach", "waves"), terrain="coast"),
    _row(("城市", "霓虹", "高樓", "都市", "city"), terrain="skyline"),
    _row(("小鎮", "街", "town", "street"), terrain="town"),
    _row(("山", "湖", "mountain", "lake"), terrain="peaks"),
    _row(("森林", "樹林", "forest"), terrain="woods"),
    _row(("雪", "冬", "聖誕", "snow", "winter", "christmas"), terrain="snow", weather="snow"),
    _row(("田", "稻", "麥", "field"), terrain="wheat"),
    _row(("河", "溪", "river"), terrain="river"),
    _row(("沙漠", "荒漠", "荒野", "desert"), terrain="dunes"),
    _row(("懸崖", "盡頭", "天涯", "海角", "edge"), terrain="cliff"),
    _row(("草原", "原野", "草地"), terrain="grass"),
    # stances
    _row(("跑", "追", "奔", "run", "running", "chase"), subject="solo_run"),
    _row(("擁抱", "抱", "懷裡", "hug", "arms"), subject="duo_hug"),
    # things
    _row(("想你", "想念", "思念", "牽掛", "miss"), prop="thought"),
    _row(("夢", "睡", "dream", "sleep"), prop="dream"),
    _row(("沙漏", "流逝", "來不及"), prop="hourglass"),
    _row(("日子", "那天", "那年", "每天", "明天", "昨天", "紀念", "days", "yesterday"), prop="calendar"),
    _row(("行李", "遠行", "出發", "流浪", "漂泊", "離家", "leave", "leaving"), prop="suitcase"),
    _row(("電話", "手機", "訊息", "簡訊", "已讀", "phone", "text", "message"), prop="phone"),
    _row(("鑰匙", "鎖", "秘密", "心門", "key", "secret"), prop="key"),
    _row(("蠟燭", "燭", "生日", "祈禱", "candle", "pray"), prop="candle"),
    _row(("戒指", "永遠", "一輩子", "ring", "forever"), prop="ring"),
    _row(("紙鶴", "願望", "心願", "wish"), prop="cranes"),
    _row(("蒲公英", "隨風", "飄"), prop="dandelion"),
    _row(("心碎", "碎", "分手", "背叛", "broken", "breakup"), prop="broken"),
    _row(("酒", "醉", "乾杯", "wine", "drunk"), prop="wine"),
    _row(("吉他", "彈", "guitar"), prop="guitar"),
    _row(("相機", "拍", "鏡頭", "camera", "photo"), prop="camera"),
    _row(("日記", "寫下", "diary"), prop="diary"),
    _row(("腳印", "足跡", "走過", "一步", "footprints", "steps"), prop="footprints"),
    _row(("門", "打開", "door", "open"), prop="door"),
    _row(("烏雲", "陰天", "憂鬱", "悲傷", "難過", "sad", "blue"), prop="raincloud"),
    _row(("光芒", "一道光", "曙光", "希望", "勇氣", "相信", "light", "hope", "believe", "brave"), prop="rays"),
    _row(("煙火", "煙花", "慶祝", "新年", "fireworks"), prop="fireworks", light="night"),
    _row(("紙船", "漂流", "drift"), prop="paperboat"),
    _row(("蝴蝶", "butterfly"), prop="butterfly"),
    _row(("貓", "cat"), prop="cat"),
    # a line with no thing to show still has a feeling: it decides the light and how they stand
    _row(("痛", "傷", "哭", "淚", "寂寞", "孤單", "失去", "後悔", "遺憾", "心酸", "錯過", "cry", "hurt", "lonely", "regret"), light="dusk", subject="solo_back"),
    _row(("快樂", "幸福", "開心", "笑", "甜", "美好", "溫暖", "happy", "smile", "sweet", "warm"), light="day", subject="solo_wave"),
    _row(("我們", "一起", "陪", "身邊", "together"), subject="duo_sit"),
)
ICON_HINTS = tuple(_row(words, prop=name) for name, (_fam, words, _shapes) in card_icons.TABLE.items())
MOODS = {"tears": "sad", "hearts": "closed", "call": "wow", "ask": "wow", "shooting": "wow", "notes": "closed", "umbrella": "sad",
         "broken": "sad", "raincloud": "sad", "fireworks": "wow", "thought": "closed", "dream": "closed", "guitar": "closed", "suitcase": "sad"}
SAD_SUBJECTS = ("duo_apart", "solo_back", "other_back")


def plan_standard(parts: Sequence[Tuple[str, str]], seed: int, world: Dict[str, Any]) -> List[str]:
    """plan() for a standard world: the same walk through the song, with the extra places and stances its
    words can call for, and about one card in four as another kind of shot: against the light, over a
    shoulder, two hands, or things on a table."""
    global HINTS
    keep = HINTS
    HINTS = HINTS_STD + ICON_HINTS + HINTS          # the standard words first: they win over the simple ones
    try:
        specs = plan(parts, seed, world)
    finally:
        HINTS = keep
    r = random.Random(f"shots:{int(seed)}")
    rows = [(tuple(_simple(w) for w in ws), what) for ws, what in HINTS_STD + ICON_HINTS + keep if "prop" in what]
    out: List[str] = []
    seen = set()
    sung: Dict[str, int] = {}
    since = 2
    for (kind, text), spec in zip(parts, specs):
        place, light, wth, subject, prop, frame, pos, n = parse(spec)  # type: ignore[misc]
        if kind not in ("intro", "outro", "interlude"):
            # the same line again: another of the things its words name (or, with only one, every other time none)
            line = _simple(text)
            again = sung.get(line, 0)
            sung[line] = again + 1
            if again:
                words = set("".join(ch if ch.isalpha() and ch.isascii() else " " for ch in line).split())
                alts: List[str] = []
                for ws, what in rows:
                    if what["prop"] not in alts and any((w in words) if w.isascii() else (w in line) for w in ws):
                        alts.append(what["prop"])
                duo = subject.startswith("duo")
                alts = [a for a in alts if not (a in SOLO_ONLY and duo) and not (a in DUO_ONLY and not duo) and a not in ("bike", "umbrella", "wings")]
                if len(alts) > 1:
                    prop = alts[again % len(alts)]
                elif again % 2 == 1 and prop not in SOLO_ONLY + DUO_ONLY:
                    prop = "none"
        if kind not in ("intro", "outro"):
            since += 1
            shot = ""
            outdoor = place not in INDOOR + INDOOR_STD
            if since >= 3 and r.random() < 0.6:
                if subject == "none" or prop in ("letter", "clock", "frames", "hourglass", "calendar", "key", "candle", "diary") or (
                        prop in card_icons.TABLE and card_icons.TABLE[prop][0] in ("hold", "side") and r.random() < 0.5):
                    shot = "still"
                elif outdoor and place != "forest" and not place.startswith(("woods.", "skyline.")) and wth == "clear" and light in ("sunset", "golden", "dawn", "dusk") and prop in ("none", "birds", "hearts", "thread", "leaves", "petals"):
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
    if prop in card_icons.TABLE:
        card_icons.draw_icon(k, prop, x, 990, 470)
    elif prop == "letter":
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


# ------------------------------------------------- the standard grade: places put together from parts
# A place of this kind is written "terrain.landmark.front": the lie of the land, the one thing that stands
# in it, and what is nearest to the eye. Twelve terrains, forty landmarks and nine fronts.
def tr_grass(k):
    k.ridge(650, 46, (140, 200, 170), far=0.6); k.ridge(720, 40, (134, 204, 158), far=0.3)
    k.band(790, H, (170, 224, 160), (128, 196, 132)); k.ridge(790, 14, (170, 224, 160), rough=0.6)
    return {"ground": 890, "base": 800}


def tr_coast(k):
    k.band(620, 880, (150, 214, 236), (86, 170, 214))
    for i in range(16):
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, 640 + i * 15), (x + k.r.uniform(120, 360), 640 + i * 15)], (255, 255, 255, 110), 3)
    pts = [(x, 872 + math.sin(x / 170 + 1.3) * 20) for x in range(-30, W + 60, 30)]
    k.poly([(x, y - 14) for x, y in pts] + [(W + 30, H + 30), (-30, H + 30)], (255, 255, 255), line=False)
    k.poly(pts + [(W + 30, H + 30), (-30, H + 30)], (250, 230, 190), line=False)
    return {"ground": 940, "base": 890}


def tr_skyline(k):
    for i in range(16):
        x, h = i * 128 - 30 + k.r.uniform(-14, 14), k.r.uniform(150, 420)
        k.rect(x, 780 - h, x + 112, 800, k.far((120, 132, 170), 0.55), line=False, raw=True)
        k.windows(x + 14, 790 - h + 12, x + 100, 770, cw=18, ch=24, gap=14, lit=0.4)
    k.band(800, H, (220, 216, 220), (186, 184, 196)); k.stroke([(0, 800), (W, 800)], None, k.lw)
    for y in (880, 980):
        k.stroke([(0, y), (W, y)], (200, 198, 206), 3)
    return {"ground": 900, "base": 808}


def tr_town(k):
    k.ridge(680, 30, (140, 196, 176), far=0.6)
    x = -30
    while x < W:
        wd, h = k.r.uniform(150, 230), k.r.uniform(110, 190)
        k.rect(x + 10, 790 - h, x + wd - 10, 800, k.far(k.r.choice(((246, 214, 190), (212, 230, 240), (250, 232, 180), (226, 206, 236))), 0.2), raw=True)
        k.poly([(x, 790 - h), (x + wd / 2, 790 - h - 70), (x + wd, 790 - h)], k.far(k.r.choice(((214, 120, 110), (120, 140, 180), (170, 120, 100))), 0.2), raw=True)
        k.windows(x + 30, 790 - h + 20, x + wd - 30, 780, cw=30, ch=36, gap=24, lit=0.6)
        x += wd + k.r.uniform(0, 30)
    k.band(800, H, (232, 222, 208), (206, 194, 184)); k.stroke([(0, 800), (W, 800)], None, k.lw)
    return {"ground": 900, "base": 810}


def tr_peaks(k):
    for x, top in ((k.r.uniform(200, 600), k.r.uniform(300, 400)), (k.r.uniform(800, 1150), k.r.uniform(240, 340)), (k.r.uniform(1350, 1750), k.r.uniform(320, 420))):
        k.poly([(x - 560, 650), (x, top), (x + 560, 650)], k.far((120, 160, 196), 0.42), line=False, raw=True)
        k.poly([(x - 74, top + 62), (x, top), (x + 74, top + 62), (x + 26, top + 48), (x - 18, top + 70)], (255, 255, 255), line=False)
    k.band(650, 820, (170, 216, 238), (112, 176, 216))
    for i in range(9):
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, 670 + i * 16), (x + k.r.uniform(100, 300), 670 + i * 16)], (255, 255, 255, 110), 3)
    k.band(820, H, (176, 220, 164), (130, 190, 134)); k.ridge(820, 10, (176, 220, 164), rough=0.8)
    return {"ground": 900, "base": 830}


def tr_woods(k):
    for i in range(10):
        k.tree(i * 220 - 40 + k.r.uniform(-50, 50), 770, k.r.uniform(0.9, 1.3), far=0.5, kind="pine" if i % 3 == 0 else "round")
    k.band(770, H, (160, 214, 154), (112, 176, 122)); k.stroke([(0, 770), (W, 770)], None, max(2, k.lw - 1))
    k.poly([(880, 770), (1040, 770), (1500, H + 20), (420, H + 20)], (226, 208, 170), line=False)
    return {"ground": 900, "base": 790}


def tr_snow(k):
    k.ridge(640, 50, (226, 236, 246), far=0.3); k.ridge(720, 34, (240, 246, 252), far=0.15)
    for i in range(5):
        k.tree(i * 480 + k.r.uniform(-90, 90), 800, k.r.uniform(0.7, 1.0), col=(120, 170, 160), far=0.3, kind="pine")
    k.band(800, H, (255, 255, 255), (216, 230, 246)); k.ridge(800, 12, (255, 255, 255), rough=0.9)
    return {"ground": 900, "base": 812}


def tr_wheat(k):
    k.ridge(660, 36, (140, 196, 176), far=0.6)
    k.band(720, H, (244, 222, 140), (214, 180, 96))
    for row in range(12):
        k.stroke([(0, 730 + row * row * 2.6), (W, 730 + row * row * 2.6)], (206, 170, 90, 120), 2 + row * 0.5)
    return {"ground": 900, "base": 790}


def tr_river(k):
    k.ridge(600, 36, (136, 196, 176), far=0.6)
    k.band(640, 770, (170, 216, 238), (112, 176, 216))
    for i in range(7):
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, 656 + i * 15), (x + k.r.uniform(100, 300), 656 + i * 15)], (255, 255, 255, 110), 3)
    k.band(770, H, (166, 218, 152), (124, 188, 128)); k.ridge(770, 10, (166, 218, 152), rough=0.8)
    return {"ground": 900, "base": 800}


def tr_dunes(k):
    k.ridge(620, 60, (236, 200, 150), far=0.45, rough=0.1); k.ridge(700, 50, (240, 206, 150), far=0.2, rough=0.1)
    k.band(780, H, (246, 220, 164), (226, 186, 128)); k.ridge(780, 26, (246, 220, 164), rough=0.1)
    for _ in range(5):
        x = k.r.uniform(60, W - 60)
        k.rect(x - 10, 720, x + 10, 800, (110, 170, 120), r=10); k.rect(x - 34, 740, x - 18, 780, (110, 170, 120), r=8); k.rect(x + 18, 730, x + 34, 770, (110, 170, 120), r=8)
    return {"ground": 900, "base": 810}


def tr_cliff(k):
    k.band(640, H, (150, 214, 236), (70, 150, 200))
    for i in range(22):
        x = k.r.uniform(0, W - 300)
        k.stroke([(x, 660 + i * 18), (x + k.r.uniform(100, 340), 660 + i * 18)], (255, 255, 255, 100), 3)
    side = k.r.choice((0, 1))
    pts = [(-30, 800), (1150, 790), (1260, 830), (1220, 940), (1300, H + 30), (-30, H + 30)]
    if side:
        pts = [(W - x, y) for x, y in pts]
    k.poly(pts, (150, 136, 130)); top = [(-30, 800), (1150, 790), (1260, 830), (1100, 850), (-30, 860)]
    k.poly([(W - x, y) for x, y in top] if side else top, (160, 214, 150))
    return {"ground": 850, "base": 800, "x": 1500 if side else 420}


def tr_plaza(k):
    for i in range(9):
        k.tree(i * 250 - 40 + k.r.uniform(-50, 50), 780, k.r.uniform(0.8, 1.1), far=0.45)
    k.band(780, H, (236, 226, 214), (210, 198, 190)); k.stroke([(0, 780), (W, 780)], None, k.lw)
    for i in range(1, 9):
        y = 780 + i * i * 4.6
        k.stroke([(0, y), (W, y)], (214, 204, 196), 2)
    for i in range(-8, 9):
        k.stroke([(960 + i * 60, 780), (960 + i * 320, H)], (214, 204, 196), 2)
    return {"ground": 900, "base": 800}


TERRAIN_FN = {"grass": tr_grass, "coast": tr_coast, "skyline": tr_skyline, "town": tr_town, "peaks": tr_peaks, "woods": tr_woods,
              "snow": tr_snow, "wheat": tr_wheat, "river": tr_river, "dunes": tr_dunes, "cliff": tr_cliff, "plaza": tr_plaza}
TERRAINS = tuple(TERRAIN_FN)


def _lit(k):
    return k.dark or k.light == "overcast"


def lm_lighthouse(k, x, y, s):
    k.poly([(x - 44 * s, y), (x - 26 * s, y - 330 * s), (x + 26 * s, y - 330 * s), (x + 44 * s, y)], (255, 252, 244))
    for i in (1, 3): k.poly([(x - (44 - i * 4.4) * s, y - i * 66 * s), (x + (44 - i * 4.4) * s, y - i * 66 * s), (x + (40 - i * 4.4) * s, y - (i * 66 + 60) * s), (x - (40 - i * 4.4) * s, y - (i * 66 + 60) * s)], (226, 100, 100), line=False)
    k.rect(x - 34 * s, y - 384 * s, x + 34 * s, y - 330 * s, (255, 240, 170), e=_lit(k)); k.poly([(x - 44 * s, y - 384 * s), (x + 44 * s, y - 384 * s), (x, y - 440 * s)], (226, 100, 100))
    if _lit(k): k.d.polygon([(P(x), P(y - 358 * s)), (P(x + 900 * s), P(y - 470 * s)), (P(x + 900 * s), P(y - 250 * s))], fill=(255, 244, 180, 44))


def lm_ferris(k, x, y, s):
    cy, rr = y - 330 * s, 250 * s
    k.poly([(x - 100 * s, y), (x, cy), (x + 100 * s, y)], (150, 160, 190), line=False)
    k.d.ellipse([P(x - rr), P(cy - rr), P(x + rr), P(cy + rr)], outline=k.c((150, 160, 200)), width=P(9 * s))
    for i in range(12):
        a = i * math.pi / 6
        k.stroke([(x, cy), (x + math.cos(a) * rr, cy + math.sin(a) * rr)], (150, 160, 200), 4 * s)
        k.rect(x + math.cos(a) * rr - 26 * s, cy + math.sin(a) * rr - 4 * s, x + math.cos(a) * rr + 26 * s, cy + math.sin(a) * rr + 40 * s, ((255, 150, 150), (255, 220, 120), (150, 214, 190), (170, 190, 255))[i % 4], r=8 * s, e=k.dark)


def lm_windmill(k, x, y, s):
    k.poly([(x - 60 * s, y), (x - 34 * s, y - 280 * s), (x + 34 * s, y - 280 * s), (x + 60 * s, y)], (250, 240, 226)); k.poly([(x - 44 * s, y - 280 * s), (x + 44 * s, y - 280 * s), (x, y - 340 * s)], (190, 110, 100))
    k.rect(x - 18 * s, y - 70 * s, x + 18 * s, y, (150, 110, 92), r=6 * s)
    a0 = k.r.uniform(0, 1.5)
    for i in range(4):
        a = a0 + i * math.pi / 2
        k.poly([(x, y - 290 * s), (x + math.cos(a) * 230 * s - math.sin(a) * 30 * s, y - 290 * s + math.sin(a) * 230 * s + math.cos(a) * 30 * s), (x + math.cos(a) * 230 * s + math.sin(a) * 30 * s, y - 290 * s + math.sin(a) * 230 * s - math.cos(a) * 30 * s)], (236, 226, 214))
    k.ell(x, y - 290 * s, 14 * s, 14 * s, (150, 110, 92))


def lm_chapel(k, x, y, s):
    k.rect(x - 130 * s, y - 200 * s, x + 130 * s, y, (255, 252, 244)); k.poly([(x - 150 * s, y - 200 * s), (x, y - 310 * s), (x + 150 * s, y - 200 * s)], (120, 150, 190))
    k.rect(x - 44 * s, y - 400 * s, x + 44 * s, y - 250 * s, (255, 252, 244)); k.poly([(x - 56 * s, y - 400 * s), (x, y - 500 * s), (x + 56 * s, y - 400 * s)], (120, 150, 190))
    k.stroke([(x, y - 500 * s), (x, y - 560 * s)], None, 6 * s); k.stroke([(x - 20 * s, y - 536 * s), (x + 20 * s, y - 536 * s)], None, 6 * s)
    k.ell(x, y - 330 * s, 22 * s, 26 * s, (255, 226, 130), e=True); k.rect(x - 34 * s, y - 110 * s, x + 34 * s, y, (150, 110, 92), r=30 * s)
    for sx in (-80, 80): k.rect(x + sx * s - 16 * s, y - 150 * s, x + sx * s + 16 * s, y - 80 * s, (255, 232, 150) if _lit(k) else (190, 220, 240), r=14 * s, e=_lit(k))


def lm_clocktower(k, x, y, s):
    k.rect(x - 60 * s, y - 380 * s, x + 60 * s, y, (236, 214, 190)); k.poly([(x - 76 * s, y - 380 * s), (x, y - 480 * s), (x + 76 * s, y - 380 * s)], (120, 130, 170))
    k.ell(x, y - 300 * s, 44 * s, 44 * s, (255, 255, 255), e=_lit(k)); k.stroke([(x, y - 300 * s), (x, y - 330 * s)], None, 5 * s); k.stroke([(x, y - 300 * s), (x + 22 * s, y - 290 * s)], None, 5 * s)
    k.windows(x - 40 * s, y - 220 * s, x + 40 * s, y - 60 * s, cw=26 * s, ch=36 * s, gap=20 * s, lit=0.5)


def lm_phonebooth(k, x, y, s):
    s *= 0.8
    k.rect(x - 60 * s, y - 250 * s, x + 60 * s, y, (226, 90, 90), r=8 * s); k.rect(x - 44 * s, y - 220 * s, x + 44 * s, y - 40 * s, (255, 240, 180) if _lit(k) else (214, 236, 250), r=4 * s, e=_lit(k))
    k.stroke([(x, y - 220 * s), (x, y - 40 * s)], None, 3); k.stroke([(x - 44 * s, y - 130 * s), (x + 44 * s, y - 130 * s)], None, 3); k.rect(x - 66 * s, y - 270 * s, x + 66 * s, y - 250 * s, (226, 90, 90), r=6 * s)
    if _lit(k): k.d.ellipse([P(x - 170 * s), P(y - 320 * s), P(x + 170 * s), P(y + 40 * s)], fill=(255, 236, 170, 34))


def lm_swings(k, x, y, s):
    k.stroke([(x - 190 * s, y), (x - 150 * s, y - 250 * s), (x + 150 * s, y - 250 * s), (x + 190 * s, y)], (120, 150, 190), 10 * s)
    for dx in (-70, 70):
        sw = k.r.uniform(-24, 24)
        k.stroke([(x + (dx - 22) * s, y - 250 * s), (x + (dx - 22 + sw) * s, y - 60 * s)], None, 3); k.stroke([(x + (dx + 22) * s, y - 250 * s), (x + (dx + 22 + sw) * s, y - 60 * s)], None, 3)
        k.rect(x + (dx - 30 + sw) * s, y - 66 * s, x + (dx + 30 + sw) * s, y - 52 * s, (232, 180, 90), r=4 * s)


def lm_slide(k, x, y, s):
    k.rect(x - 20 * s, y - 220 * s, x + 20 * s, y, (120, 150, 190)); k.rect(x - 60 * s, y - 250 * s, x + 60 * s, y - 220 * s, (232, 110, 110), r=6 * s)
    k.poly([(x + 40 * s, y - 230 * s), (x + 60 * s, y - 250 * s), (x + 330 * s, y - 10 * s), (x + 290 * s, y)], (250, 214, 96))
    for i in range(5): k.stroke([(x - 70 * s, y - i * 44 * s), (x - 24 * s, y - i * 44 * s)], (120, 150, 190), 7 * s)
    k.stroke([(x - 70 * s, y), (x - 70 * s, y - 230 * s)], (120, 150, 190), 7 * s)


def lm_camp(k, x, y, s):
    for dx, col in ((-170, (236, 150, 90)), (150, (110, 170, 150))):
        k.poly([(x + (dx - 130) * s, y), (x + dx * s, y - 180 * s), (x + (dx + 130) * s, y)], col); k.poly([(x + (dx - 30) * s, y), (x + dx * s, y - 110 * s), (x + (dx + 30) * s, y)], (70, 60, 70))
    for a in (-0.5, 0.5): k.limb([(x - 40 * s, y + 20 * s + a * 10), (x + 40 * s, y + 10 * s - a * 10)], (150, 110, 92), 12 * s)
    k.d.ellipse([P(x - 150 * s), P(y - 190 * s), P(x + 150 * s), P(y + 70 * s)], fill=(255, 190, 90, 40))
    k.poly([(x - 34 * s, y + 6 * s), (x - 10 * s, y - 60 * s), (x, y - 30 * s), (x + 14 * s, y - 96 * s), (x + 36 * s, y + 6 * s)], (255, 170, 70), e=True); k.poly([(x - 14 * s, y + 6 * s), (x, y - 40 * s), (x + 16 * s, y + 6 * s)], (255, 236, 150), line=False, e=True)


def lm_bigtree(k, x, y, s):
    k.tree(x, y + 10, 1.7 * s)


def lm_cherry(k, x, y, s):
    k.tree(x, y + 10, 1.6 * s, col=(255, 196, 214))
    for _ in range(26): k.ell(x + k.r.uniform(-260, 260) * s, y - k.r.uniform(-10, 420) * s, 8, 5, (255, 214, 226), line=False)


def lm_maple(k, x, y, s):
    k.tree(x, y + 10, 1.6 * s, col=k.r.choice(((240, 150, 80), (226, 110, 90), (250, 200, 100))))


def lm_gate(k, x, y, s):
    for sx in (-1, 1): k.rect(x + sx * 130 * s - 16 * s, y - 280 * s, x + sx * 130 * s + 16 * s, y, (214, 90, 80))
    k.rect(x - 190 * s, y - 320 * s, x + 190 * s, y - 286 * s, (214, 90, 80), r=6 * s); k.rect(x - 150 * s, y - 250 * s, x + 150 * s, y - 226 * s, (214, 90, 80))
    k.poly([(x - 210 * s, y - 320 * s), (x + 210 * s, y - 320 * s), (x + 190 * s, y - 350 * s), (x - 190 * s, y - 350 * s)], (70, 66, 80))


def lm_fountain(k, x, y, s):
    k.ell(x, y, 220 * s, 44 * s, (200, 206, 216)); k.ell(x, y - 8 * s, 190 * s, 32 * s, (150, 206, 236)); k.rect(x - 18 * s, y - 150 * s, x + 18 * s, y - 6 * s, (200, 206, 216)); k.ell(x, y - 150 * s, 80 * s, 18 * s, (200, 206, 216))
    for sx in (-1, 1):
        pts = [(x + sx * t * 110 * s, y - 150 * s - math.sin(t * math.pi) * 110 * s + t * 140 * s) for t in [i / 12 for i in range(13)]]
        k.stroke(pts, (255, 255, 255, 200), 7 * s, e=True)
    k.stroke([(x, y - 160 * s), (x, y - 270 * s)], (255, 255, 255, 200), 8 * s, e=True)


def lm_busstop(k, x, y, s):
    k.rect(x - 200 * s, y - 300 * s, x + 200 * s, y - 276 * s, (120, 150, 190), r=8)
    for sx in (-188, 188): k.rect(x + sx * s - 7 * s, y - 276 * s, x + sx * s + 7 * s, y, (120, 128, 150))
    k.rect(x - 180 * s, y - 260 * s, x + 180 * s, y - 70 * s, (220, 240, 250, 90), r=4); k.rect(x - 150 * s, y - 60 * s, x + 150 * s, y - 44 * s, (206, 156, 122), r=5)
    k.rect(x + 250 * s, y - 280 * s, x + 262 * s, y, (120, 128, 150)); k.ell(x + 256 * s, y - 300 * s, 38 * s, 38 * s, (250, 214, 96))


def lm_benchlamp(k, x, y, s):
    k.lamp(x - 150 * s, y + 20, 380 * s); bench(k, x + 60 * s, y + 30 * s, s * 1.1)


def lm_vending(k, x, y, s):
    s *= 0.9
    for dx, col in ((-70, (226, 90, 90)), (70, (90, 140, 200))):
        k.rect(x + (dx - 60) * s, y - 250 * s, x + (dx + 60) * s, y, col, r=8 * s); k.rect(x + (dx - 46) * s, y - 230 * s, x + (dx + 46) * s, y - 110 * s, (255, 250, 220), r=4 * s, e=True)
        for i in range(3):
            for j in range(3): k.rect(x + (dx - 38 + i * 28) * s, y - (222 - j * 38) * s, x + (dx - 20 + i * 28) * s, y - (192 - j * 38) * s, ((255, 150, 130), (150, 214, 190), (255, 220, 120))[(i + j) % 3], line=False, r=3, e=True)
        k.rect(x + (dx - 40) * s, y - 60 * s, x + (dx + 40) * s, y - 30 * s, (40, 44, 60), r=4)
    if _lit(k): k.d.ellipse([P(x - 240 * s), P(y - 330 * s), P(x + 240 * s), P(y + 60 * s)], fill=(255, 244, 200, 36))


def lm_mailbox(k, x, y, s):
    k.rect(x - 10 * s, y - 120 * s, x + 10 * s, y, (120, 128, 150)); k.rect(x - 56 * s, y - 230 * s, x + 56 * s, y - 110 * s, (226, 90, 90), r=30 * s)
    k.rect(x - 34 * s, y - 196 * s, x + 34 * s, y - 182 * s, (60, 50, 60), line=False, r=4); k.poly([(x + 56 * s, y - 200 * s), (x + 100 * s, y - 200 * s), (x + 100 * s, y - 170 * s), (x + 56 * s, y - 170 * s)], (250, 214, 96))


def lm_bicycle(k, x, y, s):
    for dx in (-90, 90): k.d.ellipse([P(x + (dx - 64) * s), P(y - 128 * s), P(x + (dx + 64) * s), P(y)], outline=k.ink or (70, 76, 100), width=P(6))
    k.stroke([(x - 90 * s, y - 64 * s), (x - 10 * s, y - 64 * s), (x + 56 * s, y - 150 * s), (x - 44 * s, y - 150 * s), (x - 90 * s, y - 64 * s)], (96, 170, 176), 8 * s)
    k.stroke([(x + 56 * s, y - 150 * s), (x + 90 * s, y - 64 * s)], (96, 170, 176), 8 * s); k.stroke([(x + 40 * s, y - 190 * s), (x + 84 * s, y - 184 * s)], None, 8 * s); k.stroke([(x - 62 * s, y - 162 * s), (x - 26 * s, y - 162 * s)], None, 10 * s)


def lm_car(k, x, y, s):
    col = k.r.choice(((226, 110, 110), (110, 160, 210), (250, 214, 110), (150, 200, 170)))
    k.rect(x - 220 * s, y - 100 * s, x + 220 * s, y - 20 * s, col, r=26 * s); k.poly([(x - 130 * s, y - 100 * s), (x - 90 * s, y - 170 * s), (x + 90 * s, y - 170 * s), (x + 140 * s, y - 100 * s)], col)
    k.poly([(x - 104 * s, y - 104 * s), (x - 78 * s, y - 154 * s), (x - 6 * s, y - 154 * s), (x - 6 * s, y - 104 * s)], (214, 236, 250)); k.poly([(x + 8 * s, y - 104 * s), (x + 8 * s, y - 154 * s), (x + 80 * s, y - 154 * s), (x + 112 * s, y - 104 * s)], (214, 236, 250))
    for dx in (-130, 130): k.ell(x + dx * s, y - 20 * s, 40 * s, 40 * s, (60, 62, 76)); k.ell(x + dx * s, y - 20 * s, 16 * s, 16 * s, (200, 204, 214), line=False)
    if _lit(k): k.d.polygon([(P(x + 220 * s), P(y - 66 * s)), (P(x + 620 * s), P(y - 110 * s)), (P(x + 620 * s), P(y + 10 * s))], fill=(255, 244, 190, 60))


def lm_trainpass(k, x, y, s):
    k.rect(-10, y - 16, W + 10, y, (150, 144, 140), line=False)
    x0 = k.r.uniform(-300, 500)
    for c in range(3):
        cx = x0 + c * 520
        k.rect(cx, y - 180, cx + 500, y - 14, (240, 244, 248), r=24); k.rect(cx, y - 90, cx + 500, y - 60, (96, 150, 210), line=False)
        for i in range(4): k.rect(cx + 40 + i * 112, y - 160, cx + 124 + i * 112, y - 100, (255, 236, 170) if k.dark else (196, 226, 246), r=8, e=k.dark)


def lm_farbridge(k, x, y, s):
    k.rect(-10, y - 130, W + 10, y - 104, (190, 110, 100))
    for tx in (520, 1400):
        k.rect(tx - 16, y - 360, tx + 16, y, (190, 110, 100))
        for i in range(-12, 13): k.stroke([(tx, y - 350), (tx + i * 34, y - 130)], (190, 110, 100), 2)


def lm_radiotower(k, x, y, s):
    k.poly([(x - 80 * s, y), (x, y - 520 * s), (x + 80 * s, y)], (226, 100, 100), line=False); k.poly([(x - 54 * s, y), (x, y - 420 * s), (x + 54 * s, y)], k.sky3[2], line=False, raw=True)
    for i in range(1, 6): k.stroke([(x - (80 - i * 13) * s, y - i * 84 * s), (x + (80 - i * 13) * s, y - i * 84 * s)], (226, 100, 100), 6 * s)
    k.ell(x, y - 524 * s, 9 * s, 9 * s, (255, 90, 90), line=False, e=True)
    if k.dark: k.d.ellipse([P(x - 50 * s), P(y - 574 * s), P(x + 50 * s), P(y - 474 * s)], fill=(255, 90, 90, 60))


def lm_watertower(k, x, y, s):
    for sx in (-70, 70): k.stroke([(x + sx * s, y), (x + sx * 0.6 * s, y - 250 * s)], (120, 128, 150), 9 * s)
    k.stroke([(x - 62 * s, y - 100 * s), (x + 62 * s, y - 100 * s)], (120, 128, 150), 6 * s); k.rect(x - 100 * s, y - 380 * s, x + 100 * s, y - 250 * s, (190, 210, 226), r=10 * s); k.poly([(x - 110 * s, y - 380 * s), (x, y - 440 * s), (x + 110 * s, y - 380 * s)], (150, 110, 100))


def lm_barn(k, x, y, s):
    k.rect(x - 170 * s, y - 180 * s, x + 170 * s, y, (206, 96, 90)); k.poly([(x - 190 * s, y - 180 * s), (x - 110 * s, y - 280 * s), (x + 110 * s, y - 280 * s), (x + 190 * s, y - 180 * s)], (120, 100, 100))
    k.rect(x - 60 * s, y - 120 * s, x + 60 * s, y, (255, 252, 244)); k.stroke([(x - 60 * s, y - 120 * s), (x + 60 * s, y)], (206, 96, 90), 6 * s); k.stroke([(x + 60 * s, y - 120 * s), (x - 60 * s, y)], (206, 96, 90), 6 * s)
    k.rect(x + 210 * s, y - 320 * s, x + 290 * s, y, (226, 226, 230), r=36 * s)


def lm_cabin(k, x, y, s):
    k.rect(x - 150 * s, y - 150 * s, x + 150 * s, y, (176, 128, 100)); k.poly([(x - 180 * s, y - 150 * s), (x, y - 270 * s), (x + 180 * s, y - 150 * s)], (120, 86, 76))
    k.rect(x - 36 * s, y - 96 * s, x + 14 * s, y, (120, 86, 76), r=4); k.rect(x + 50 * s, y - 110 * s, x + 110 * s, y - 50 * s, (255, 232, 150) if _lit(k) else (214, 236, 250), r=4, e=_lit(k))
    k.rect(x + 70 * s, y - 280 * s, x + 110 * s, y - 200 * s, (150, 110, 100))
    for i in range(4): k.ell(x + (90 + i * 22) * s, y - (300 + i * 44) * s, (24 + i * 8) * s, (18 + i * 6) * s, (255, 255, 255, 150), line=False, e=True)


def lm_castle(k, x, y, s):
    k.rect(x - 200 * s, y - 220 * s, x + 200 * s, y, (226, 220, 226))
    for i in range(-4, 5): k.rect(x + i * 46 * s - 14 * s, y - 250 * s, x + i * 46 * s + 14 * s, y - 220 * s, (226, 220, 226))
    for sx in (-200, 0, 200):
        h = 420 if sx == 0 else 330
        k.rect(x + sx * s - 50 * s, y - h * s, x + sx * s + 50 * s, y, (236, 230, 236)); k.poly([(x + sx * s - 64 * s, y - h * s), (x + sx * s, y - (h + 120) * s), (x + sx * s + 64 * s, y - h * s)], k.r.choice(((120, 150, 200), (200, 110, 130), (150, 120, 190))))
        k.rect(x + sx * s - 14 * s, y - (h - 60) * s, x + sx * s + 14 * s, y - (h - 110) * s, (255, 232, 150) if _lit(k) else (120, 130, 160), r=12 * s, e=_lit(k))
    k.rect(x - 40 * s, y - 110 * s, x + 40 * s, y, (150, 110, 92), r=36 * s)


def lm_balloons(k, x, y, s):
    for i in range(3):
        bx, by, sz = x + (i - 1) * 330 * s + k.r.uniform(-60, 60), y - k.r.uniform(330, 600) * s, k.r.uniform(0.6, 1.1) * s
        col = ((255, 150, 130), (250, 214, 110), (130, 190, 230))[i]
        k.ell(bx, by, 100 * sz, 120 * sz, col); k.poly([(bx - 50 * sz, by + 100 * sz), (bx + 50 * sz, by + 100 * sz), (bx + 18 * sz, by + 170 * sz), (bx - 18 * sz, by + 170 * sz)], col, line=False)
        for a in (-0.6, 0, 0.6): k.d.arc([P(bx - 100 * sz * abs(math.cos(a)) - 1), P(by - 120 * sz), P(bx + 100 * sz * abs(math.cos(a)) + 1), P(by + 120 * sz)], 0, 360, fill=(255, 255, 255, 130), width=P(3))
        k.rect(bx - 20 * sz, by + 176 * sz, bx + 20 * sz, by + 206 * sz, (176, 128, 100), r=3)


def lm_sailboats(k, x, y, s):
    for i in range(3):
        bx, by, sz = x + (i - 1) * 300 * s + k.r.uniform(-50, 50), y - k.r.uniform(120, 230), k.r.uniform(0.5, 1.0)
        k.poly([(bx - 90 * sz, by), (bx + 90 * sz, by), (bx + 62 * sz, by + 30 * sz), (bx - 62 * sz, by + 30 * sz)], (255, 255, 255)); k.poly([(bx, by - 4), (bx, by - 130 * sz), (bx + 76 * sz, by - 14 * sz)], k.r.choice(((255, 236, 200), (255, 190, 180), (190, 220, 250))))
        k.poly([(bx - 8 * sz, by - 4), (bx - 8 * sz, by - 100 * sz), (bx - 60 * sz, by - 12 * sz)], (255, 255, 255))


def lm_observatory(k, x, y, s):
    k.rect(x - 130 * s, y - 130 * s, x + 130 * s, y, (236, 236, 240)); k.d.pieslice([P(x - 130 * s), P(y - 260 * s), P(x + 130 * s), P(y)], 180, 360, fill=k.c((214, 220, 232)), outline=k.edge(k.c((214, 220, 232))), width=P(k.lw))
    k.poly([(x - 16 * s, y - 250 * s), (x + 30 * s, y - 256 * s), (x + 50 * s, y - 130 * s), (x - 10 * s, y - 130 * s)], (60, 64, 90)); k.rect(x - 30 * s, y - 80 * s, x + 30 * s, y, (150, 110, 92), r=4)
    k.limb([(x + 20 * s, y - 200 * s), (x + 130 * s, y - 330 * s)], (120, 128, 150), 22 * s)


def lm_greenhouse(k, x, y, s):
    k.poly([(x - 200 * s, y), (x - 200 * s, y - 160 * s), (x, y - 270 * s), (x + 200 * s, y - 160 * s), (x + 200 * s, y)], (220, 244, 236, 150))
    for i in range(-3, 4): k.stroke([(x + i * 66 * s, y), (x + i * 66 * s, y - (270 - abs(i) * 36.6) * s)], (255, 255, 255), 4 * s)
    k.stroke([(x - 200 * s, y - 160 * s), (x + 200 * s, y - 160 * s)], (255, 255, 255), 4 * s)
    for i in range(5): k.ell(x + (i - 2) * 70 * s, y - 40 * s, 30 * s, 44 * s, (110, 186, 130), line=False); k.ell(x + (i - 2) * 70 * s, y - 76 * s, 12 * s, 12 * s, ((255, 150, 170), (255, 222, 110), (255, 255, 255))[i % 3], line=False)


def lm_stage(k, x, y, s):
    k.rect(x - 330 * s, y - 60 * s, x + 330 * s, y, (90, 84, 110)); k.rect(x - 330 * s, y - 380 * s, x - 300 * s, y - 60 * s, (60, 62, 80)); k.rect(x + 300 * s, y - 380 * s, x + 330 * s, y - 60 * s, (60, 62, 80)); k.rect(x - 340 * s, y - 410 * s, x + 340 * s, y - 380 * s, (60, 62, 80))
    for i, col in enumerate(((255, 120, 150), (255, 230, 120), (120, 200, 255), (190, 150, 255), (150, 240, 190))):
        lx = x + (i - 2) * 130 * s
        k.d.polygon([(P(lx), P(y - 376 * s)), (P(lx - 90 * s + (i - 2) * 30 * s), P(y - 60 * s)), (P(lx + 90 * s + (i - 2) * 30 * s), P(y - 60 * s))], fill=col + (60,)); k.ell(lx, y - 372 * s, 18 * s, 14 * s, col, e=True)
    k.stroke([(x, y - 60 * s), (x, y - 190 * s)], (200, 204, 214), 5 * s); k.ell(x, y - 200 * s, 12 * s, 18 * s, (60, 62, 80))


def lm_carousel(k, x, y, s):
    k.rect(x - 220 * s, y - 40 * s, x + 220 * s, y, (240, 150, 160), r=8); k.poly([(x - 250 * s, y - 260 * s), (x, y - 380 * s), (x + 250 * s, y - 260 * s)], (255, 236, 200))
    for i in range(-3, 4): k.poly([(x + (i - 0.5) * 70 * s, y - 260 * s), (x + i * 70 * s, y - 230 * s), (x + (i + 0.5) * 70 * s, y - 260 * s)], ((240, 150, 160), (150, 200, 230))[i % 2])
    for i in range(-2, 3):
        px = x + i * 100 * s
        k.stroke([(px, y - 256 * s), (px, y - 40 * s)], (250, 214, 110), 6 * s); k.ell(px, y - (110 + (i % 2) * 40) * s, 40 * s, 22 * s, (255, 255, 255)); k.ell(px + 36 * s, y - (136 + (i % 2) * 40) * s, 16 * s, 14 * s, (255, 255, 255))
    k.ell(x, y - 386 * s, 14 * s, 14 * s, (250, 214, 110), e=True)


def lm_snowman(k, x, y, s):
    k.ell(x, y - 70 * s, 90 * s, 80 * s, (255, 255, 255)); k.ell(x, y - 190 * s, 64 * s, 60 * s, (255, 255, 255)); k.ell(x, y - 286 * s, 46 * s, 44 * s, (255, 255, 255))
    for e in (-16, 16): k.ell(x + e * s, y - 296 * s, 5 * s, 6 * s, (46, 50, 74), line=False)
    k.poly([(x, y - 286 * s), (x + 50 * s, y - 276 * s), (x, y - 270 * s)], (255, 150, 80)); k.rect(x - 50 * s, y - 250 * s, x + 50 * s, y - 228 * s, (226, 90, 90), r=8 * s)
    k.rect(x - 36 * s, y - 376 * s, x + 36 * s, y - 322 * s, (60, 62, 80)); k.rect(x - 56 * s, y - 330 * s, x + 56 * s, y - 318 * s, (60, 62, 80))
    for sx in (-1, 1): k.stroke([(x + sx * 60 * s, y - 200 * s), (x + sx * 130 * s, y - 250 * s)], (150, 110, 92), 6 * s)


def lm_scarecrow(k, x, y, s):
    k.stroke([(x, y), (x, y - 260 * s)], (150, 110, 92), 9 * s); k.stroke([(x - 100 * s, y - 200 * s), (x + 100 * s, y - 200 * s)], (150, 110, 92), 9 * s)
    k.poly([(x - 60 * s, y - 220 * s), (x + 60 * s, y - 220 * s), (x + 44 * s, y - 90 * s), (x - 44 * s, y - 90 * s)], (110, 150, 200)); k.ell(x, y - 270 * s, 40 * s, 40 * s, (250, 232, 190)); k.poly([(x - 66 * s, y - 290 * s), (x + 66 * s, y - 290 * s), (x, y - 360 * s)], (214, 150, 90))


def lm_signpost(k, x, y, s):
    k.stroke([(x, y), (x, y - 300 * s)], (150, 110, 92), 10 * s)
    for i, (d, col) in enumerate(((1, (255, 252, 244)), (-1, (250, 232, 180)), (1, (226, 240, 250)))):
        yy = y - (270 - i * 62) * s
        k.poly([(x - d * 20 * s, yy - 22 * s), (x + d * 150 * s, yy - 22 * s), (x + d * 180 * s, yy), (x + d * 150 * s, yy + 22 * s), (x - d * 20 * s, yy + 22 * s)], col)


def lm_well(k, x, y, s):
    k.rect(x - 90 * s, y - 90 * s, x + 90 * s, y, (190, 186, 190), r=8)
    for sx in (-76, 76): k.rect(x + sx * s - 8 * s, y - 250 * s, x + sx * s + 8 * s, y - 90 * s, (150, 110, 92))
    k.poly([(x - 120 * s, y - 250 * s), (x, y - 320 * s), (x + 120 * s, y - 250 * s)], (190, 110, 100)); k.stroke([(x, y - 250 * s), (x, y - 150 * s)], None, 3); k.rect(x - 22 * s, y - 150 * s, x + 22 * s, y - 110 * s, (176, 128, 100), r=4)


def lm_gazebo(k, x, y, s):
    k.rect(x - 190 * s, y - 30 * s, x + 190 * s, y, (236, 230, 226), r=6)
    for i in range(-2, 3): k.rect(x + i * 86 * s - 9 * s, y - 250 * s, x + i * 86 * s + 9 * s, y - 30 * s, (255, 252, 244))
    k.poly([(x - 230 * s, y - 250 * s), (x, y - 390 * s), (x + 230 * s, y - 250 * s)], (120, 170, 160)); k.ell(x, y - 396 * s, 12 * s, 12 * s, (250, 214, 110))
    k.rect(x - 180 * s, y - 100 * s, x + 180 * s, y - 86 * s, (255, 252, 244), r=4)


def lm_piano(k, x, y, s):
    k.poly([(x - 170 * s, y - 130 * s), (x + 90 * s, y - 130 * s), (x + 170 * s, y - 200 * s), (x + 170 * s, y - 100 * s), (x - 170 * s, y - 100 * s)], (50, 50, 64))
    k.rect(x - 170 * s, y - 104 * s, x + 30 * s, y - 80 * s, (255, 255, 255))
    for i in range(9): k.stroke([(x - 170 * s + i * 22 * s, y - 104 * s), (x - 170 * s + i * 22 * s, y - 80 * s)], (50, 50, 64), 2)
    for sx in (-150, 150, 0): k.rect(x + sx * s - 7 * s, y - 100 * s, x + sx * s + 7 * s, y, (50, 50, 64))
    k.poly([(x + 60 * s, y - 130 * s), (x + 170 * s, y - 200 * s), (x + 150 * s, y - 300 * s)], (70, 70, 88)); k.rect(x - 240 * s, y - 60 * s, x - 190 * s, y - 46 * s, (120, 86, 76)); k.rect(x - 222 * s, y - 46 * s, x - 208 * s, y, (120, 86, 76))


def lm_telescope(k, x, y, s):
    for a in (-0.4, 0, 0.4): k.stroke([(x, y - 170 * s), (x + math.sin(a) * 110 * s, y)], (120, 128, 150), 7 * s)
    k.limb([(x - 70 * s, y - 150 * s), (x + 120 * s, y - 260 * s)], (236, 236, 240), 34 * s); k.limb([(x + 110 * s, y - 254 * s), (x + 150 * s, y - 278 * s)], (120, 128, 150), 44 * s)


def lm_lifeguard(k, x, y, s):
    for sx in (-1, 1): k.stroke([(x + sx * 90 * s, y), (x + sx * 50 * s, y - 250 * s)], (255, 252, 244), 10 * s)
    for i in range(1, 4): k.stroke([(x - (90 - i * 10) * s, y - i * 60 * s), (x + (90 - i * 10) * s, y - i * 60 * s)], (255, 252, 244), 7 * s)
    k.rect(x - 70 * s, y - 280 * s, x + 70 * s, y - 250 * s, (226, 100, 100), r=4); k.rect(x - 70 * s, y - 380 * s, x - 56 * s, y - 280 * s, (226, 100, 100)); k.poly([(x - 110 * s, y - 380 * s), (x + 110 * s, y - 400 * s), (x + 110 * s, y - 380 * s)], (255, 236, 200))


def lm_jetty(k, x, y, s):
    k.poly([(x - 60, y - 10), (x + 60, y - 10), (x + 30, y - 190), (x - 30, y - 190)], (214, 172, 132))
    for i in range(5): k.stroke([(x - 60 + i * 6, y - 14 - i * 40), (x + 60 - i * 6, y - 14 - i * 40)], (176, 134, 104), 3)
    for sx in (-1, 1): k.rect(x + sx * 62 - 8, y - 70, x + sx * 62 + 8, y, (160, 120, 96), r=4)


def lm_plane(k, x, y, s):
    bx, by = x + k.r.uniform(-100, 100), y - k.r.uniform(420, 560)
    k.limb([(bx - 160 * s, by + 20 * s), (bx + 150 * s, by - 30 * s)], (255, 255, 255), 44 * s)
    k.poly([(bx - 30 * s, by - 6 * s), (bx - 110 * s, by + 110 * s), (bx - 50 * s, by + 110 * s), (bx + 50 * s, by - 16 * s)], (226, 232, 244)); k.poly([(bx - 150 * s, by + 14 * s), (bx - 200 * s, by - 60 * s), (bx - 160 * s, by - 60 * s), (bx - 110 * s, by + 6 * s)], (226, 100, 100))
    for i in range(7): k.ell(bx - (230 + i * 70) * s, by + (34 + i * 12) * s, (26 + i * 6) * s, (14 + i * 3) * s, (255, 255, 255, 150 - i * 18), line=False, e=True)


def lm_tents(k, x, y, s):
    for i in range(3):
        tx, col = x + (i - 1) * 250 * s, ((232, 110, 110), (96, 160, 200), (236, 180, 80))[i]
        k.rect(tx - 100 * s, y - 150 * s, tx + 100 * s, y, (255, 248, 230))
        for j in range(6): k.poly([(tx - 110 * s + j * 36.7 * s, y - 150 * s), (tx, y - 270 * s), (tx - 110 * s + (j + 1) * 36.7 * s, y - 150 * s)], col if j % 2 == 0 else (255, 255, 255))
        k.poly([(tx, y - 270 * s), (tx + 40 * s, y - 290 * s), (tx, y - 310 * s)], col)


def lm_torch(k, x, y, s):
    for dx in (-200, 0, 200):
        k.rect(x + dx * s - 8 * s, y - 220 * s, x + dx * s + 8 * s, y, (120, 100, 96)); k.rect(x + dx * s - 40 * s, y - 290 * s, x + dx * s + 40 * s, y - 220 * s, (255, 232, 160) if _lit(k) else (250, 244, 232), r=6, e=_lit(k)); k.poly([(x + dx * s - 54 * s, y - 290 * s), (x + dx * s + 54 * s, y - 290 * s), (x + dx * s, y - 340 * s)], (190, 90, 90))
        if _lit(k): k.d.ellipse([P(x + dx * s - 130 * s), P(y - 390 * s), P(x + dx * s + 130 * s), P(y - 130 * s)], fill=(255, 226, 150, 36))


LANDMARK_FN = {"lighthouse": lm_lighthouse, "ferris": lm_ferris, "windmill": lm_windmill, "chapel": lm_chapel, "clocktower": lm_clocktower,
               "phonebooth": lm_phonebooth, "swings": lm_swings, "slide": lm_slide, "camp": lm_camp, "bigtree": lm_bigtree, "cherry": lm_cherry,
               "maple": lm_maple, "gate": lm_gate, "fountain": lm_fountain, "shelter": lm_busstop, "benchlamp": lm_benchlamp,
               "vending": lm_vending, "mailbox": lm_mailbox, "bicycle": lm_bicycle, "car": lm_car, "trainpass": lm_trainpass,
               "farbridge": lm_farbridge, "radiotower": lm_radiotower, "watertower": lm_watertower, "barn": lm_barn, "cabin": lm_cabin,
               "castle": lm_castle, "hotair": lm_balloons, "sailboats": lm_sailboats, "observatory": lm_observatory,
               "greenhouse": lm_greenhouse, "stage": lm_stage, "carousel": lm_carousel, "snowman": lm_snowman, "scarecrow": lm_scarecrow,
               "signpost": lm_signpost, "well": lm_well, "gazebo": lm_gazebo, "piano": lm_piano, "telescope": lm_telescope,
               "lifeguard": lm_lifeguard, "jetty": lm_jetty, "jet": lm_plane, "tents": lm_tents, "lanterns": lm_torch}
LANDMARKS = tuple(LANDMARK_FN)
# a landmark that only makes sense on some terrains
ONLY_ON = {"lighthouse": ("coast", "cliff", "peaks"), "sailboats": ("coast", "cliff", "peaks", "river"), "lifeguard": ("coast",),
           "jetty": ("coast", "peaks", "river"), "snowman": ("snow",), "scarecrow": ("wheat", "grass"), "barn": ("wheat", "grass"),
           "farbridge": ("river", "coast", "skyline"), "trainpass": ("grass", "wheat", "town", "snow", "river", "plaza"),
           "vending": ("town", "skyline", "plaza"), "phonebooth": ("town", "skyline", "plaza", "snow"), "shelter": ("town", "skyline", "plaza", "grass"),
           "stage": ("plaza", "skyline", "grass"), "carousel": ("plaza", "grass", "skyline"), "ferris": ("plaza", "skyline", "coast", "grass", "town")}
NOT_ON = {"dunes": ("cherry", "maple", "bigtree", "greenhouse", "gazebo", "fountain", "swings", "slide", "castle", "chapel", "cabin", "mailbox", "benchlamp", "piano", "clocktower")}
WIDE_LANDMARKS = ("trainpass", "farbridge", "hotair", "sailboats", "jet", "tents", "lanterns")


def fits(landmark: str, terrain: str) -> bool:
    return terrain in ONLY_ON.get(landmark, TERRAINS) and landmark not in NOT_ON.get(terrain, ())


def fr_none(k, front):
    return None


def fr_flowers(k, front):
    if front: pl_flowers(k, True)


def fr_grass(k, front):
    if front: pl_meadow(k, True)


def fr_fence(k, front):
    if not front:
        for x in range(0, W + 1, 70): k.rect(x - 9, 760, x + 9, 850, (255, 252, 244), r=6)
        k.rect(-10, 786, W + 10, 800, (255, 252, 244))


def fr_railing(k, front):
    if not front:
        for x in range(0, W + 1, 96): k.stroke([(x, 850), (x, 770)], (120, 126, 150), 7)
        k.stroke([(0, 770), (W, 770)], (120, 126, 150), 9)


def fr_lamps(k, front):
    if not front:
        for x in (k.r.uniform(120, 300), k.r.uniform(1620, 1800)): k.lamp(x, 880, 400)


def fr_branches(k, front):
    if front:
        col = k.r.choice(((104, 176, 124), (255, 196, 214), (240, 160, 90)))
        for side in (0, 1):
            x0 = -40 if side == 0 else W + 40
            k.stroke([(x0, 60), (x0 + (420 if side == 0 else -420), 150)], (120, 86, 76), 16)
            for _ in range(36):
                x, y = x0 + (k.r.uniform(0, 520) if side == 0 else -k.r.uniform(0, 520)), k.r.uniform(-20, 260)
                k.ell(x, y, k.r.uniform(26, 50), k.r.uniform(18, 34), col, line=False)


def fr_rocks(k, front):
    if front:
        for _ in range(7):
            x, sz = k.r.uniform(0, W), k.r.uniform(40, 110)
            k.poly([(x - sz, H + 10), (x - sz * 0.6, H - sz * 0.7), (x + sz * 0.2, H - sz), (x + sz, H - sz * 0.4), (x + sz * 1.1, H + 10)], k.r.choice(((170, 170, 180), (150, 150, 164), (190, 184, 180))))


def fr_puddles(k, front):
    if not front:
        for _ in range(5):
            x, y, rx = k.r.uniform(100, W - 100), k.r.uniform(930, 1040), k.r.uniform(90, 220)
            k.d.ellipse([P(x - rx), P(y - rx * 0.16), P(x + rx), P(y + rx * 0.16)], fill=k.sky3[1] + (150,)); k.d.arc([P(x - rx * 0.6), P(y - rx * 0.09), P(x + rx * 0.6), P(y + rx * 0.09)], 0, 360, fill=(255, 255, 255, 120), width=P(3))


FRONT_FN = {"none": fr_none, "flowers": fr_flowers, "grass": fr_grass, "fence": fr_fence, "railing": fr_railing, "lamps": fr_lamps,
            "branches": fr_branches, "rocks": fr_rocks, "puddles": fr_puddles}
FRONTS = tuple(FRONT_FN)


def composite(place: str) -> Optional[Tuple[str, str, str]]:
    p = str(place).split(".")
    if len(p) == 3 and p[0] in TERRAIN_FN and p[1] in LANDMARK_FN and p[2] in FRONT_FN:
        return p[0], p[1], p[2]
    return None


def valid_place(place: object) -> bool:
    return isinstance(place, str) and (place in PLACE_FN or composite(place) is not None)


def paint_place(k, place: str, front: bool = False):
    """Paint a place of either kind (one of PLACE_FN, or "terrain.landmark.front")."""
    parts = composite(place)
    if not parts:
        return PLACE_FN[place](k, front)
    t, l, f = parts
    if front:
        FRONT_FN[f](k, True)
        return None
    info = TERRAIN_FN[t](k)
    x = 960 if l in WIDE_LANDMARKS else info.get("x") or k.r.choice((400, 1520))
    LANDMARK_FN[l](k, x, info["base"], 1.0 if l in WIDE_LANDMARKS else 1.4)
    FRONT_FN[f](k, False)
    return {"ground": info["ground"]}


def compose(base: str, terrain: Optional[str], landmark: Optional[str], world: Dict[str, Any]) -> str:
    """The place a line's words ask for: this terrain and/or this landmark, the rest from where the song is."""
    parts = composite(base) or next((composite(p) for p in world.get("places", []) if composite(p)), None) or ("grass", "bigtree", "none")
    t, l, f = parts
    if landmark:
        l = landmark
        t = terrain or t
        if not fits(l, t):
            t = next(x for x in TERRAINS if fits(l, x))
    elif terrain:
        t = terrain
        if not fits(l, t):
            l = next(x for x in ("bigtree", "signpost", "bicycle", "hotair") if fits(x, t))
    return f"{t}.{l}.{f}"


# ------------------------------------------------------------------ the standard grade: more small things
def thing_standard(k, prop, phase, who, ground):
    """The things only the standard grade has (PROPS_STD); phases as in thing()."""
    r = k.r
    one = next((f for f in (who or []) if f), None)
    hx, hy, hr = one["head"] if one else (960, 520, 50)
    sc = one["s"] if one else 1.0
    side = 1 if hx < 960 else -1
    bx, by = hx + side * (150 + 130 * sc), ground - 10       # a spot on the ground beside the person
    icon = card_icons.TABLE.get(prop)
    if icon:
        fam = icon[0]
        if not one and fam in ("hold", "bubble", "side"):
            fam = "sky" if fam != "side" else "ground"       # nobody to hold it or think of it
        if phase == "back" and fam == "sky" and icon[0] == "sky":
            x, y = r.choice((430, 1490)), r.uniform(330, 430)
            k.d.ellipse([P(x - 230), P(y - 380), P(x + 230), P(y + 80)], fill=(255, 255, 255, 34))
            card_icons.draw_icon(k, prop, x, y, 300)
        elif phase == "front" and fam == "sky" and icon[0] != "sky":
            x, y = r.choice((430, 1490)), r.uniform(380, 460)
            k.d.ellipse([P(x - 210), P(y - 350), P(x + 210), P(y + 70)], fill=(255, 255, 255, 60))
            card_icons.draw_icon(k, prop, x, y, 270)
        elif phase == "front" and fam == "ground":
            card_icons.draw_icon(k, prop, 960 + r.choice((-1, 1)) * 330, ground + 40, 280, shine=False)
        elif phase == "front" and fam == "side":
            card_icons.draw_icon(k, prop, bx, by + 20, max(170, 250 * sc), shine=False)
        elif phase == "front" and fam == "hold":
            x, y = one["hands"][1] if side > 0 else one["hands"][0]
            card_icons.draw_icon(k, prop, x, y + 30 * sc, max(110, 130 * sc))
        elif phase == "front" and fam == "bubble":
            x, y = hx + side * (hr + 210), max(190, hy - hr - 150)
            for i, rr in enumerate((14, 22)): k.ell(x - side * (150 - i * 34), y + 150 - i * 38, rr, rr, (255, 255, 255), e=True)
            for dx, dy, rr in ((-90, 10, 86), (0, -36, 104), (96, 6, 88), (0, 46, 96)): k.ell(x + dx, y + dy, rr, rr * 0.82, (255, 255, 255), line=False, e=True)
            card_icons.draw_icon(k, prop, x, y + 74, 150)
        elif phase == "front" and fam == "rain":
            for _ in range(16):
                card_icons.draw_icon(k, prop, r.uniform(60, W - 60), r.uniform(120, H - 40), r.uniform(46, 110))
        return
    if phase == "back":
        if prop == "rays":
            cx = r.uniform(500, 1400)
            for i in range(9):
                a = math.pi * (0.12 + i * 0.095)
                k.d.polygon([(P(cx), P(-60)), (P(cx + math.cos(a) * 1900), P(-60 + math.sin(a) * 1900)), (P(cx + math.cos(a + 0.045) * 1900), P(-60 + math.sin(a + 0.045) * 1900))], fill=(255, 250, 210, 46))
        elif prop == "fireworks":
            for _ in range(4):
                cx, cy, rr = r.uniform(250, W - 250), r.uniform(120, 420), r.uniform(110, 220)
                col = r.choice(((255, 130, 150), (255, 226, 120), (140, 220, 255), (190, 160, 255), (150, 240, 190)))
                for i in range(22):
                    a = i * math.pi / 11
                    k.d.line([(P(cx + math.cos(a) * rr * 0.25), P(cy + math.sin(a) * rr * 0.25)), (P(cx + math.cos(a) * rr), P(cy + math.sin(a) * rr))], fill=col + (230,), width=P(5))
                    k.d.ellipse([P(cx + math.cos(a) * rr - 7), P(cy + math.sin(a) * rr - 7), P(cx + math.cos(a) * rr + 7), P(cy + math.sin(a) * rr + 7)], fill=(255, 255, 255, 240))
                k.d.ellipse([P(cx - rr * 1.2), P(cy - rr * 1.2), P(cx + rr * 1.2), P(cy + rr * 1.2)], fill=col + (22,))
        elif prop == "cranes":
            for i in range(7):
                x, y, z = r.uniform(150, W - 150), r.uniform(80, 480), r.uniform(0.7, 1.4)
                col = r.choice(((255, 190, 200), (255, 236, 160), (190, 226, 250), (210, 190, 250), (255, 255, 255)))
                k.poly([(x - 60 * z, y), (x, y - 14 * z), (x + 70 * z, y - 30 * z), (x + 10 * z, y + 16 * z)], col, e=True); k.poly([(x - 6 * z, y - 10 * z), (x - 30 * z, y - 76 * z), (x + 24 * z, y - 12 * z)], col, e=True)
        return
    if phase != "front":
        return
    if prop == "door":
        x = 1500 if hx < 960 else 420
        k.rect(x - 110, ground - 400, x + 110, ground, (255, 250, 220), e=True); k.d.polygon([(P(x - 110), P(ground)), (P(x + 110), P(ground)), (P(x + 330), P(ground + 190)), (P(x - 330), P(ground + 190))], fill=(255, 250, 210, 70))
        k.poly([(x + 110, ground - 400), (x + 230, ground - 440), (x + 230, ground + 30), (x + 110, ground)], (176, 128, 100)); k.ell(x + 130, ground - 190, 9, 9, (250, 214, 110), e=True)
    elif prop == "hourglass":
        x, y, z = bx, by, 1.5 * sc
        k.rect(x - 60 * z, y - 190 * z, x + 60 * z, y - 176 * z, (176, 128, 100), r=4); k.rect(x - 60 * z, y - 14 * z, x + 60 * z, y, (176, 128, 100), r=4)
        k.poly([(x - 48 * z, y - 176 * z), (x + 48 * z, y - 176 * z), (x + 6 * z, y - 95 * z), (x + 48 * z, y - 14 * z), (x - 48 * z, y - 14 * z), (x - 6 * z, y - 95 * z)], (230, 244, 250, 170))
        k.poly([(x - 30 * z, y - 150 * z), (x + 30 * z, y - 150 * z), (x, y - 100 * z)], (250, 214, 110), line=False, e=True); k.poly([(x - 40 * z, y - 16 * z), (x + 40 * z, y - 16 * z), (x, y - 56 * z)], (250, 214, 110), line=False, e=True)
        k.stroke([(x, y - 100 * z), (x, y - 40 * z)], (250, 214, 110), 3, e=True)
    elif prop == "calendar":
        x, y = hx + side * (hr + 200), max(150, hy - hr - 60)
        mark = (r.randrange(4), r.randrange(3))
        k.rect(x - 110, y - 100, x + 110, y + 120, (255, 255, 255), r=10, e=True); k.rect(x - 110, y - 100, x + 110, y - 50, (232, 110, 110), r=10, e=True)
        for i in range(4):
            for j in range(3): k.rect(x - 86 + i * 46, y - 26 + j * 44, x - 54 + i * 46, y + 6 + j * 44, (255, 150, 150) if (i, j) == mark else (226, 232, 240), line=False, r=5, e=True)
        for dx in (-60, 60): k.rect(x + dx - 7, y - 122, x + dx + 7, y - 80, (120, 128, 150), r=5)
    elif prop == "suitcase":
        x, y, z = bx, by, 1.2 * sc
        k.rect(x - 70 * z, y - 150 * z, x + 70 * z, y - 10 * z, r.choice(((214, 150, 90), (120, 160, 200), (226, 110, 110))), r=14 * z)
        k.d.arc([P(x - 30 * z), P(y - 190 * z), P(x + 30 * z), P(y - 130 * z)], 180, 360, fill=k.ink or (70, 76, 100), width=P(8 * z))
        for dx in (-34, 34): k.stroke([(x + dx * z, y - 150 * z), (x + dx * z, y - 10 * z)], (255, 255, 255, 170), 6 * z, e=True)
        for dx in (-44, 44): k.ell(x + dx * z, y - 4 * z, 12 * z, 12 * z, (60, 62, 76))
    elif prop == "phone":
        x, y = (one["hands"][1] if one else (960, 600))
        z = 1.1 * sc
        k.d.ellipse([P(x - 110 * z), P(y - 150 * z), P(x + 110 * z), P(y + 70 * z)], fill=(190, 226, 255, 60))
        k.rect(x - 30 * z, y - 96 * z, x + 30 * z, y + 16 * z, (50, 54, 70), r=10 * z); k.rect(x - 24 * z, y - 86 * z, x + 24 * z, y + 4 * z, (200, 232, 255), line=False, r=5 * z, e=True)
        _bubble(k, hx + side * (hr + 150), max(110, hy - hr - 110), "dots", side)
    elif prop == "key":
        x, y = hx + side * (hr + 170), max(150, hy - hr - 40)
        k.d.ellipse([P(x - 110), P(y - 110), P(x + 110), P(y + 110)], fill=(255, 236, 150, 44))
        k.d.ellipse([P(x - 56), P(y - 86), P(x + 4), P(y - 26)], outline=(250, 206, 96), width=P(16)); k.limb([(x - 4, y - 36), (x + 70, y + 60)], (250, 206, 96), 16)
        for d in (0.55, 0.8): k.limb([(x - 4 + 74 * d, y - 36 + 96 * d), (x + 22 + 74 * d, y - 54 + 96 * d)], (250, 206, 96), 12)
    elif prop == "candle":
        for i in range(3):
            x, y, h = bx + (i - 1) * 76 * sc, by, (90 + (i % 2) * 50) * sc
            k.d.ellipse([P(x - 100 * sc), P(y - h - 150 * sc), P(x + 100 * sc), P(y - h + 50 * sc)], fill=(255, 220, 130, 40))
            k.rect(x - 20 * sc, y - h, x + 20 * sc, y, (255, 250, 236), r=6); k.poly([(x - 12 * sc, y - h - 6 * sc), (x, y - h - 56 * sc), (x + 12 * sc, y - h - 6 * sc)], (255, 190, 80), e=True); k.ell(x, y - h - 14 * sc, 6 * sc, 10 * sc, (255, 244, 190), line=False, e=True)
    elif prop == "ring":
        x, y = (((who[0]["x"] + who[1]["x"]) / 2, hy - hr * 2.4) if who and who[0] and who[1] else (hx + side * (hr + 160), hy - hr - 30))
        y = max(170, y)
        k.d.ellipse([P(x - 120), P(y - 120), P(x + 120), P(y + 120)], fill=(255, 244, 190, 50))
        k.d.ellipse([P(x - 54), P(y - 30), P(x + 54), P(y + 78)], outline=(250, 214, 110), width=P(16)); k.poly([(x - 30, y - 46), (x, y - 86), (x + 30, y - 46), (x, y - 16)], (190, 236, 255), e=True)
        for a in range(4): _star(k, x + math.cos(a * 1.57 + 0.6) * 110, y - 30 + math.sin(a * 1.57 + 0.6) * 100, 12, (255, 255, 255))
    elif prop == "dandelion":
        x, y, z = bx, by, 1.3 * sc
        k.stroke([(x, y), (x + 14 * z, y - 190 * z)], (110, 176, 120), 5 * z)
        for i in range(14):
            a = i * 0.449
            k.stroke([(x + 14 * z, y - 190 * z), (x + 14 * z + math.cos(a) * 50 * z, y - 190 * z + math.sin(a) * 50 * z)], (255, 255, 255, 220), 2, e=True); k.ell(x + 14 * z + math.cos(a) * 54 * z, y - 190 * z + math.sin(a) * 54 * z, 7 * z, 7 * z, (255, 255, 255, 230), line=False, e=True)
        for i in range(12):
            fx, fy = x + side * (60 + i * 70) + r.uniform(-20, 20), y - 230 * z - i * 34 + r.uniform(-30, 30)
            k.stroke([(fx, fy), (fx + 6, fy + 26)], (255, 255, 255, 200), 2, e=True); k.ell(fx, fy, 9, 6, (255, 255, 255, 220), line=False, e=True)
    elif prop == "broken":
        x, y = hx, max(150, hy - hr * 2.8)
        if who and who[0] and who[1]: x = (who[0]["x"] + who[1]["x"]) / 2
        for sx in (-1, 1):
            cx = x + sx * 26
            k.ell(cx + sx * 16, y - 12, 26, 26, (255, 120, 144), line=False, e=True); k.poly([(cx + sx * 42, y - 2), (cx - sx * 8, y - 6), (cx + sx * 2, y + 14), (cx - sx * 10, y + 30), (cx - sx * 2, y + 56)], (255, 120, 144), line=False, e=True)
    elif prop == "wine":
        x, y = (one["hands"][1] if one else (960, 600))
        z = 1.1 * sc
        k.stroke([(x, y), (x, y - 60 * z)], (236, 240, 250), 5 * z, e=True); k.ell(x, y + 2 * z, 22 * z, 6 * z, (236, 240, 250), e=True)
        k.d.pieslice([P(x - 34 * z), P(y - 140 * z), P(x + 34 * z), P(y - 50 * z)], 0, 180, fill=(190, 60, 90), outline=(236, 240, 250), width=P(4)); k.d.arc([P(x - 34 * z), P(y - 150 * z), P(x + 34 * z), P(y - 50 * z)], 180, 360, fill=(236, 240, 250), width=P(4))
    elif prop == "guitar" and one:
        x, y, z = one["x"], one["top"] + 110 * sc, sc
        k.limb([(x + 30 * z, y - 10 * z), (x + 190 * z, y - 110 * z)], (120, 86, 76), 16 * z)
        k.ell(x - 10 * z, y + 30 * z, 66 * z, 56 * z, (226, 170, 100)); k.ell(x + 44 * z, y - 4 * z, 46 * z, 42 * z, (226, 170, 100)); k.ell(x + 10 * z, y + 14 * z, 18 * z, 18 * z, (90, 60, 50))
        thing(k, "notes", "front", who, ground)
    elif prop == "camera":
        x, y = (one["hands"][1] if one else (960, 600))
        z = 1.2 * sc
        k.rect(x - 50 * z, y - 70 * z, x + 50 * z, y, (70, 74, 92), r=10 * z); k.rect(x - 20 * z, y - 86 * z, x + 14 * z, y - 68 * z, (70, 74, 92), r=4)
        k.ell(x, y - 34 * z, 26 * z, 26 * z, (200, 226, 250)); k.ell(x + 34 * z, y - 56 * z, 6 * z, 6 * z, (255, 236, 150), line=False, e=True)
        for i in range(8):
            a = i * math.pi / 4
            k.d.line([(P(x + math.cos(a) * 44 * z), P(y - 34 * z + math.sin(a) * 44 * z)), (P(x + math.cos(a) * 110 * z), P(y - 34 * z + math.sin(a) * 110 * z))], fill=(255, 255, 255, 150), width=P(4))
    elif prop == "diary":
        x, y = hx + side * (hr + 190), max(170, hy - hr - 40)
        k.poly([(x - 150, y - 80), (x, y - 60), (x, y + 90), (x - 150, y + 70)], (255, 252, 242), e=True); k.poly([(x + 150, y - 80), (x, y - 60), (x, y + 90), (x + 150, y + 70)], (255, 252, 242), e=True)
        for i in range(5):
            k.stroke([(x - 130, y - 44 + i * 24), (x - 20, y - 30 + i * 24)], (170, 176, 196), 3, e=True); k.stroke([(x + 20, y - 30 + i * 24), (x + 130 - (i == 4) * 60, y - 44 + i * 24)], (170, 176, 196), 3, e=True)
        k.limb([(x + 90, y + 100), (x + 170, y + 10)], (232, 110, 110), 12)
    elif prop == "footprints":
        for i in range(9):
            fx, fy, z = hx - side * (120 + i * 120), ground + 60 + (i % 2) * 30 + i * 4, 1.0 + i * 0.07
            k.ell(fx, fy, 22 * z, 11 * z, (60, 50, 70, 70), line=False, e=True); k.ell(fx + 26 * z, fy, 9 * z, 8 * z, (60, 50, 70, 70), line=False, e=True)
    elif prop == "raincloud":
        x, y = hx, max(120, hy - hr * 3.0)
        k.cloud(x, y, 1.2 * max(0.7, sc), col=(150, 160, 186))
        for i in range(9): k.stroke([(x - 110 + i * 28, y + 60), (x - 122 + i * 28, y + 60 + r.uniform(40, 110))], (170, 214, 250), 5, e=True)
    elif prop == "paperboat":
        for i in range(3):
            x, y, z = r.uniform(200, W - 200), min(H - 60, ground + r.uniform(20, 120)), r.uniform(0.8, 1.4)
            k.poly([(x - 70 * z, y - 20 * z), (x + 70 * z, y - 20 * z), (x + 44 * z, y + 14 * z), (x - 44 * z, y + 14 * z)], (255, 255, 255), e=True); k.poly([(x, y - 20 * z), (x, y - 86 * z), (x + 46 * z, y - 20 * z)], (255, 252, 240), e=True); k.poly([(x, y - 20 * z), (x, y - 70 * z), (x - 38 * z, y - 20 * z)], (236, 240, 250), e=True)
    elif prop == "butterfly":
        for i in range(7):
            x, y, z = hx + r.uniform(-420, 420), hy - r.uniform(-60, 380), r.uniform(0.7, 1.3)
            col = r.choice(((255, 190, 120), (190, 160, 250), (140, 210, 250), (255, 170, 200)))
            for sx in (-1, 1): k.ell(x + sx * 20 * z, y - 10 * z, 20 * z, 24 * z, col, e=True); k.ell(x + sx * 15 * z, y + 18 * z, 13 * z, 15 * z, col, e=True)
            k.limb([(x, y - 22 * z), (x, y + 26 * z)], (70, 60, 80), 5 * z)
    elif prop == "cat":
        x, y, z = bx, by, 1.1 * sc
        col = r.choice(((250, 250, 250), (240, 180, 110), (90, 90, 104), (226, 226, 230)))
        k.ell(x, y - 46 * z, 46 * z, 50 * z, col); k.ell(x, y - 120 * z, 38 * z, 34 * z, col)
        for sx in (-1, 1): k.poly([(x + sx * 34 * z, y - 136 * z), (x + sx * 30 * z, y - 176 * z), (x + sx * 8 * z, y - 150 * z)], col)
        k.d.arc([P(x + 20 * z), P(y - 90 * z), P(x + 110 * z), P(y + 6 * z)], 20, 180, fill=k.edge(k.c(col)), width=P(12 * z))
        for sx in (-14, 14): k.ell(x + sx * z, y - 124 * z, 4 * z, 6 * z, (46, 50, 74), line=False)
    elif prop in ("thought", "dream"):
        x, y = hx + side * (hr + 210), max(190, hy - hr - 150)
        for i, rr in enumerate((14, 22)): k.ell(x - side * (150 - i * 34), y + 150 - i * 38, rr, rr, (255, 255, 255), e=True)
        for dx, dy, rr in ((-90, 10, 86), (0, -36, 104), (96, 6, 88), (0, 46, 96)): k.ell(x + dx, y + dy, rr, rr * 0.82, (255, 255, 255), line=False, e=True)
        if prop == "thought":       # the other one, in a cloud
            who2 = "boy" if k.w["lead"] == "girl" else "girl"
            k.rect(x - 46, y + 30, x + 46, y + 76, tuple(k.w[who2]["top"]), r=20, e=True); k.ell(x, y - 10, 44, 44, SKIN, e=True)
            k.d.pieslice([P(x - 47), P(y - 58), P(x + 47), P(y + 28)], 180, 360, fill=tuple(k.w[who2]["hair"]))
            for e in (-15, 15): k.ell(x + e, y - 4, 5, 7, (46, 50, 74), line=False, e=True)
            k.d.arc([P(x - 9), P(y + 6), P(x + 9), P(y + 22)], 20, 160, fill=(120, 70, 80), width=P(3))
        else:
            k.d.ellipse([P(x - 60), P(y - 60), P(x + 20), P(y + 20)], fill=(255, 236, 150)); k.d.ellipse([P(x - 36), P(y - 70), P(x + 36), P(y + 2)], fill=(255, 255, 255))
            for dx, dy in ((50, -20), (20, 30), (-50, 34), (70, 30)): _star(k, x + dx, y + dy, 13, (255, 220, 110))
