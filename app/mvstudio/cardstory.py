"""Picture cards, premium grade, first part: a song told as one story (cardworld still draws the cards).

plan_premium() gives every part of the timeline a card, like cardworld.plan_standard(), but it reads the
whole song first:
- sections(): which lines are a verse, the lead-in to the chorus, the chorus (and which time round it is),
  or the bridge, from how the lines repeat and where the song's title is sung. No AI.
- the people follow a story: one person in the verses, the two of them in the choruses (closer each time
  round), apart in the bridge, closest in the last chorus. A line's own words (we, she, tears ...) still
  win, and a sad line in a chorus keeps both people but apart.
- the day goes on from the first card to the last. A line's words (night, stars ...) can move it on a
  step, never back.
- one thing of the song's own (an umbrella, a letter ...) comes back at the start of every section, at the
  first card and at the last; with nothing in the words, the lead wears a red scarf all through.
- every chorus goes back to the song's one chorus place, nearer and later each time round.
- the last card goes back to the place of the first, at night.
- a word right after 沒有 / 不再 / 別 ... is not put in the picture; how happy or sad a line is picks the
  stance (and a grey sky for a sad line in the daytime).
"""
from __future__ import annotations

import random
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import card_icons, cardgrammar, cardphrase, cardwords
from . import cardworld as cw

ORDER = ("dawn", "day", "golden", "sunset", "dusk", "night")
NEG = ("沒有", "不再", "不是", "不會", "不必", "不用", "不要", "未曾", "別", "沒", "無")
NEG_EN = {"not", "no", "never", "dont", "without", "nothing"}
FILLER = "喔哦啊呀耶噢嗚啦"
HAPPY = ("笑", "快樂", "幸福", "開心", "甜", "美好", "溫暖", "幸運", "勇氣", "希望", "好運", "真心", "美麗", "感謝", "守護",
         "smile", "happy", "lucky", "hope", "sweet", "warm")
SAD = ("淚", "哭", "傷", "痛", "苦", "失去", "離別", "寂寞", "孤單", "後悔", "遺憾", "錯過", "忘記", "亂", "心碎", "分手",
       "再見", "cry", "hurt", "lonely", "lost", "goodbye")
DUO_WORDS = ("我們", "一起", "相遇", "遇見", "擁抱", "牽", "together", "we", "us")
THIRD = ("她", "他", "別人")
# the song's own thing, from the words it sings most: (prop, what it is called in a still shot, words)
KEEPSAKES = (
    ("umbrella", "umbrellai", ("雨", "傘", "rain", "umbrella")),
    ("envelope", "envelope", ("信", "紙", "日記", "寫", "千言萬語", "letter", "write")),
    ("cat", "cat", ("貓", "cat")),
    ("rose", "rose", ("玫瑰", "花", "rose", "flower")),
    ("photo", "photo", ("照片", "回憶", "記憶", "一幕", "photo", "memory")),
    ("guitar", "guitar", ("吉他", "歌", "唱", "旋律", "guitar", "song", "sing")),
    ("kite", "kite", ("風箏", "風", "wind", "kite")),
    ("paperboat", "paperboat", ("紙船", "船", "漂", "boat")),
    ("ticket", "ticket", ("車票", "旅", "遠方", "travel")),
    ("teddy", "teddy", ("熊", "抱", "懷", "hug")),
)
ICONIC = ("ferris", "lighthouse", "chapel", "clocktower", "windmill", "bigtree", "cherry", "carousel", "observatory", "gazebo",
          "farbridge", "castle", "piano", "telescope", "maple", "fountain", "swings", "benchlamp", "signpost",
          "pagoda", "temple", "torii", "eiffel", "palace", "treehouse", "waterwheel", "archbridge", "watchtower", "willow", "wishtree",
          "moongate", "weddingarch", "heartsign", "teahouse", "lovelocks", "porchswing", "ginkgo", "appletree", "palmtree", "pinetree",
          "windturbine", "rowboat", "fishingboat", "hotspring", "statue", "museum", "cablecar", "skylanterns", "bigship", "greatwall")
# who is in the picture and how, by the section a line is in (a line's own words can say otherwise)
VERSE = ("solo_walk", "solo_sit", "solo_front", "solo_look", "solo_back", "solo_think", "solo_hips", "solo_shade", "solo_away",
         "solo_ground", "solo_give", "solo_heart")
PRE = ("solo_reach", "solo_open", "solo_run", "solo_front", "solo_point", "solo_shade", "solo_cheer", "solo_jump")
BRIDGE = ("solo_back", "duo_apart", "solo_sit", "other_back", "solo_ground", "duo_far", "solo_crouch", "other_away", "duo_backs", "solo_away")
CHORUS = (("duo_back", "duo_front", "duo_sit", "duo_hands", "duo_walk", "duo_point", "duo_wave", "duo_ground"),   # the first time round: together, seen from afar
          ("duo_hands", "duo_face", "duo_sit", "duo_run", "duo_lean", "duo_back", "duo_cheer", "duo_stars", "duo_dance"),
          ("duo_hug", "duo_face", "duo_hands", "duo_dance", "duo_lean", "duo_hug", "duo_stars", "duo_cheer"))        # the last time round: closest
CHORUS_FRAMES = (("wide", "mid", "far", "mid", "mirror", "mid", "wide", "close"),
                 ("mid", "close", "mid", "window", "mid", "hands", "moon", "mid"),
                 ("mid", "close", "hands", "sil", "moon", "close", "photo", "mid"))
CHORUS_VIEWS = ("", "near", "", "small", "", "near", "centre", "")
SAD_SOLO = ("solo_cover", "solo_back", "solo_crouch", "solo_sit", "solo_head", "solo_ground")
SAD_DUO = ("duo_apart", "solo_back", "duo_backs", "duo_comfort", "duo_far", "solo_cover")
GLAD_SOLO = ("solo_open", "solo_wave", "solo_cheer", "solo_jump", "solo_heart")
NO_CLOSE = ("none", "solo_sit", "duo_sit", "duo_apart", "solo_ground", "solo_crouch", "solo_jump", "solo_away", "other_away", "duo_far",
            "duo_follow", "duo_wave", "duo_ground", "duo_stars", "duo_lean", "solo_run", "duo_run", "duo_walk", "duo_backs")
NO_UMBRELLA = {"solo": "solo_front", "duo": "duo_hands"}      # under an umbrella they simply stand (or walk hand in hand)
UMBRELLA_OK = ("solo_front", "solo_back", "solo_walk", "solo_look", "solo_away", "duo_front", "duo_back", "duo_hands", "duo_walk")
# words for the premium grade's ways to stand (before cardworld's own rows)
POSE_WORDS = (
    (("祈禱", "禱告", "祈求", "pray"), "solo_pray"), (("跳躍", "雀躍", "蹦跳", "jump"), "solo_jump"), (("跳舞", "共舞", "起舞", "華爾滋", "dance"), "duo_dance"),
    (("眺望", "遙望", "遠望", "張望"), "solo_shade"), (("蹲", "蜷縮", "縮在"), "solo_crouch"), (("掩面", "捂著臉", "摀"), "solo_cover"),
    (("歡呼", "萬歲", "吶喊"), "solo_cheer"), (("指著", "指向"), "solo_point"), (("背對背", "背靠背"), "duo_backs"),
    (("追著你", "跟著你", "追隨"), "duo_follow"), (("揮手", "招手", "揮別"), "duo_wave"), (("安慰", "擦乾", "別哭"), "duo_comfort"),
    (("看星星", "數星星", "看流星"), "duo_stars"), (("並肩", "散步", "漫步", "同行"), "duo_walk"), (("依偎", "靠著", "肩膀", "依靠"), "duo_lean"),
    (("沉思", "思考", "想不通"), "solo_think"), (("轉身", "離去", "走遠", "遠去"), "solo_away"), (("坐在地", "席地"), "solo_ground"))
# words that ask for a kind of shot
SHOT_WORDS = {"memory": ("回憶", "記憶", "曾經", "從前", "那年", "當年", "往事", "過去", "一幕", "想起", "remember", "memory", "memories"),
              "photo": ("照片", "相片", "合照", "相簿", "photo"), "window": ("窗",), "tilt": ("亂", "跌跌撞撞", "瘋", "暈", "旋轉", "崩", "搖晃", "crazy"),
              "globe": ("雪", "冬", "聖誕", "snow", "winter"), "moon": ("月光", "月亮", "明月", "月色", "moon"), "split": ("兩地", "各自", "天涯", "相隔", "遠距")}
# what a card with nothing of its own can have in it, by the kind of place (only things that are there on
# their own: beside the people, in the sky or in the air)
DRESS = {
    "water": ("seagull", "sailboat", "boat", "crab", "starfish", "kitei", "paperboat", "birds", "dragonfly", "duck", "frog", "cloudi"),
    "town": ("pigeon", "sparrow", "cat", "puppy", "bicyclei", "cari", "taxi", "bus", "roadsign", "balloons", "kite", "birds", "trafficcone", "scooter"),
    "green": ("butterfly", "rabbit", "lamb", "puppy", "bee", "ladybug", "dragonfly", "sparrow", "kitei", "dandelion", "birds", "sunflower", "cloudi", "pony"),
    "woods": ("squirrel", "deer", "owl", "fox", "mushroom", "butterfly", "leaves", "birds", "hedgehog", "sparrow", "fern"),
    "snow": ("snowmani", "penguin", "fox", "deer", "snowflake", "moose", "xmas", "polarbear"),
    "dry": ("camel", "cactus", "lizard", "eagle", "sun", "birds", "cloudi"),
    "high": ("eagle", "cloudi", "kitei", "birds", "hotairballoon", "airplane"),
    "room": ("cat", "pottedplant", "bookstack", "vase", "lampi", "teddy", "radio", "goldfish", "chair", "bonsai"),
    "night": ("fireflies", "stars", "owl", "fullmoon", "halfmoon", "shooting", "constellation", "lanterni")}
# [2026-11-16] what may drift into a card whose line names nothing: air and sky, nothing that reads as a thing the
# song is about (a road sign, a puppy, a lamb said things the words did not)
AMBIENT = {
    "water": ("birds", "seagull", "cloudi", "dragonfly"), "town": ("birds", "pigeon", "sparrow"),
    "green": ("butterfly", "dandelion", "birds", "cloudi", "dragonfly"), "woods": ("leaves", "birds", "butterfly"),
    "snow": ("snowflake",), "dry": ("birds", "cloudi"), "high": ("cloudi", "birds"), "room": (),
    "night": ("fireflies", "stars", "constellation", "halfmoon")}
KEEP_NOT_ALONE = ("umbrella", "bike", "thread", "wings", "dots", "ask", "call", "tears", "frames", "kite")
KIND = {"water": ("coast", "island", "boardwalk", "harbor", "lake", "river", "reeds", "sea", "pier", "riverbank", "bridge", "waterfall"),
        "town": ("town", "skyline", "plaza", "oldtown", "rooftops", "tracks", "highway", "street", "alley", "market", "busstop", "station", "rooftop", "school", "fair", "stairs"),
        "woods": ("woods", "bamboo", "forest"), "snow": ("snow", "aurora", "snowtown"), "dry": ("dunes", "canyon", "savanna"),
        "high": ("cloudsea", "peaks", "cliff", "hill"), "room": cw.INDOOR + cw.INDOOR_STD}
NAMES = {"intro": "前奏", "outro": "尾奏", "interlude": "間奏", "verse": "主歌", "pre": "導歌", "chorus": "副歌", "bridge": "橋段"}


# ------------------------------------------------------------------------------------------- the sections
def _norm(text: str) -> str:
    t = re.sub(r"[(（\[【].*?[)）\]】]", "", str(text or ""))
    t = "".join(ch for ch in cw._simple(t) if ch.isalnum())
    fill = cw._simple(FILLER)
    while t and t[-1] in fill:
        t = t[:-1]
    return t


def sections(parts: Sequence[Tuple[str, str]], title: str = "") -> List[Dict[str, Any]]:
    """For every part: {"sec": intro|outro|interlude|verse|pre|chorus|bridge, "k": its place in the section,
    "turn": which time round the chorus is (chorus only), "turns": how many times, "again": how many times
    the same line was sung before}."""
    idx = [i for i, (k, _) in enumerate(parts) if k not in ("intro", "outro", "interlude")]
    norms = {i: _norm(parts[i][1]) for i in idx}
    count = Counter(v for v in norms.values() if v)
    rep = {i: bool(norms[i]) and count[norms[i]] > 1 for i in idx}
    tn = _norm(title)
    need = max(2, len(tn) // 2)

    def has_title(n: str) -> bool:
        return len(tn) >= 2 and any(tn[a:a + need] in n for a in range(len(tn) - need + 1))
    runs: List[List[int]] = []
    cur: List[int] = []
    for i in idx:
        if rep[i]:
            cur.append(i)
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    chorus: set = set()
    head = ""
    if runs:
        best = next(((run, i) for run in runs for i in run if has_title(norms[i])), None)
        if best is None:     # no title sung: the lines sung most, or the longest repeated stretch
            run = max(runs, key=lambda rn: (max(count[norms[i]] for i in rn), len(rn)))
            top = max(count[norms[i]] for i in run)
            best = (run, next(i for i in run if count[norms[i]] == top))
        run, hit = best
        before = {norms[i] for i in idx if i < hit}
        for i in run[run.index(hit):]:     # up to where the song starts over (a line sung before the chorus)
            if norms[i] in before:
                break
            chorus.add(norms[i])
        head = norms[hit]
    first = next((i for i in idx if norms[i] in chorus), None)
    pos = {i: n for n, i in enumerate(idx)}

    def leads_in(i: int) -> bool:    # a repeated line that runs straight into the chorus (within four lines)
        for j in idx[pos[i] + 1:pos[i] + 5]:
            if norms[j] in chorus:
                return True
            if not rep[j]:
                return False
        return False
    out: List[Dict[str, Any]] = []
    sec_prev, k = "", 0
    turn, pairs, prev_chorus = -1, set(), False
    nxt = {a: (norms[b] if b is not None else "") for a, b in zip(idx, idx[1:] + [None])}
    sung: Counter = Counter()
    for i, (kind, _) in enumerate(parts):
        if kind in ("intro", "outro", "interlude"):
            out.append({"sec": kind, "k": 0, "turn": 0, "again": 0})
            continue
        n = norms[i]
        if n in chorus:
            sec = "chorus"
            # a new time round: after other lines, at the chorus's first line, or where two lines in a row
            # repeat two lines already sung this time round
            if not prev_chorus or n == head or (n, nxt[i]) in pairs:
                turn, pairs = turn + 1, set()
            pairs.add((n, nxt[i]))
        elif rep[i] and leads_in(i):
            sec = "pre"
        elif first is not None and i > first and not rep[i]:
            sec = "bridge"
        else:
            sec = "verse"
        prev_chorus = sec == "chorus"
        k = k + 1 if sec == sec_prev else 0
        sec_prev = sec
        out.append({"sec": sec, "k": k, "turn": max(0, turn), "again": sung[n]})
        sung[n] += 1
    for o in out:
        o["turns"] = turn + 1
    return out


# ---------------------------------------------------------------------------------------- reading a line
def _found(line: str, w: str) -> List[int]:
    at, out = 0, []
    while True:
        j = line.find(w, at)
        if j < 0:
            return out
        out.append(j)
        at = j + 1


_NEG = None


def _negated(line: str, j: int) -> bool:
    global _NEG
    if _NEG is None:
        _NEG = tuple(cw._simple(w) for w in NEG)
    before = line[max(0, j - 3):j]
    if before.endswith(("有没有", "是不是", "会不会", "能不能", "要不要")):
        return False            # a question ("有沒有口罩"), not a no
    return " " not in before and any(w in before for w in _NEG)


def says(line: str, words: Sequence[str]) -> bool:
    """Whether a (simplified) line says one of the words, not right after a no / never."""
    toks = "".join(ch if ch.isalpha() and ch.isascii() else " " for ch in line).split()
    for w in words:
        if w.isascii():
            if any(t == w and (n == 0 or toks[n - 1] not in NEG_EN) for n, t in enumerate(toks)):
                return True
        elif any(not _negated(line, j) for j in _found(line, w)):
            return True
    return False


def said(line: str, words: Sequence[str]) -> int:
    """The length of the longest of the words the (simplified) line says, not right after a no / never; 0: none."""
    toks = "".join(ch if ch.isalpha() and ch.isascii() else " " for ch in line).split()
    best = 0
    for w in words:
        if len(w) <= best:
            continue
        if w.isascii():
            if any(t == w and (n == 0 or toks[n - 1] not in NEG_EN) for n, t in enumerate(toks)):
                best = len(w)
        elif any(not _negated(line, j) for j in _found(line, w)):
            best = len(w)
    return best


def hints(line: str, rows) -> Dict[str, str]:
    """As cardworld._hints(longest=True): of the rows whose words the line says, the longest word wins."""
    got: Dict[str, str] = {}
    size: Dict[str, int] = {}
    for ws, what in rows:
        n = said(line, ws) if line else 0
        if n:
            for k, v in what.items():
                if k == "prop" and k in got and str(v).startswith("e_") and got[k] not in ("dots", "ask", "call"):
                    continue        # an emoji only when nothing else has named a thing (they come last); "?" or "..." is no thing
                if k == "prop" and k in got and str(v).startswith("e_"):
                    if not str(got[k]).startswith("e_"):
                        got[k], size[k] = v, n
                    continue
                if k not in got or n > size[k]:
                    got[k], size[k] = v, n
    return got


def feeling(line: str) -> int:
    """How happy (more than 0) or sad (less than 0) a line is."""
    return sum(1 for w in HAPPY if says(line, (cw._simple(w),))) - sum(1 for w in SAD if says(line, (cw._simple(w),)))


# -------------------------------------------------------------------------------------------- the story
NOT_A_THING = ("none", "dots", "ask", "call", "tears", "notes")


ICON_TWIN = {"stars": "e_glowing_star", "hearts": "hearti", "letter": "envelope", "phone": "e_mobile_phone", "wine": "e_wine_glass",
             "clock": "e_alarm_clock", "hourglass": "e_hourglass_done", "diary": "e_notebook", "cranes": "cranebird", "plane": "e_airplane",
             "balloons": "e_balloon", "clover": "e_four_leaf_clover", "bike": "e_bicycle", "butterfly": "e_butterfly", "birds": "e_dove",
             "notes": "e_musical_notes", "paperboat": "e_sailboat", "bigmoon": "e_full_moon", "frames": "e_framed_picture"}


def icon_for(prop: str) -> str:
    """The small picture (card_icons) of a thing that is otherwise drawn by hand, or the thing itself."""
    for name in (ICON_TWIN.get(prop, ""), prop + "i", "e_" + prop):
        if name and name in card_icons.TABLE:
            return name
    return prop


def title_keep(title: str) -> Optional[Tuple[str, str, Tuple[str, ...]]]:
    """[2026-11-15] The thing a song's name is about (〈彩虹〉: a rainbow), as a KEEPSAKES entry: the name says
    what the song is, so its thing comes before what the lines say most often. None when the name names no thing."""
    t = cw._simple(title or "")
    if not t:
        return None
    for prop, still, words in KEEPSAKES:
        ws = tuple(cw._simple(w) for w in words)
        hit = tuple(w for w in ws if says(t, (w,)))
        if hit:
            return prop, still, hit
    rows = [(ws, what) for ws, what in _rows() if what.get("prop") and what["prop"] not in NOT_A_THING]
    prop = hints(t, rows).get("prop")
    if not prop:
        return None
    hit = tuple(w for ws, what in rows if what["prop"] == prop for w in ws if says(t, (w,)))
    return prop, prop, tuple(dict.fromkeys(hit))


def story(parts: Sequence[Tuple[str, str]], world: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """What stays the same through the song: its sections, its thing, its chorus place, where it starts."""
    secs = sections(parts, title)
    lines = [cw._simple(t) for k, t in parts if k not in ("intro", "outro", "interlude")]
    score = []
    for n, (prop, still, words) in enumerate(KEEPSAKES):
        ws = tuple(cw._simple(w) for w in words)
        score.append((sum(1 for ln in lines if says(ln, ws)), -n, prop, still, ws))
    named = title_keep(title)
    if "keep" in world:      # chosen when the song's cards were first drawn: it stays, whatever the words say now
        keep = next((sc[2:] for sc in score if sc[2] == world["keep"]), None)
        if keep is None and named and named[0] == world["keep"]:
            keep = named
    elif named:              # the song's name names a thing: that is the song's thing
        keep = named
    else:
        best = max(score)
        keep = best[2:] if best[0] >= 1 else None
    places = list(world["places"])
    rooms = cw.INDOOR + cw.INDOOR_STD
    outdoor = [p for p in places if p not in rooms]
    comps = [p for p in outdoor if cw.composite(p)]
    rows = _rows()
    ch_lines = [cw._simple(parts[i][1]) for i, s in enumerate(secs) if s["sec"] == "chorus" and s["again"] == 0]
    chorus = next((p for lm in ICONIC for p in comps if cw.composite(p)[1] == lm), comps[0] if comps else outdoor[0])
    said = Counter()
    for ln in ch_lines:
        h = hints(ln, rows)
        for key in ("terrain", "landmark"):
            if h.get(key):
                said[(key, h[key])] += 1
    lm = next((v for (key, v), c in said.most_common() if key == "landmark" and c >= 2), None)
    tr = next((v for (key, v), c in said.most_common() if key == "terrain" and c >= 2), None)
    if lm or tr:
        chorus = cw.compose(chorus, tr, lm, world)
    home = next((p for lm in ICONIC for p in comps if p != chorus and cw.composite(p)[1] == lm),
                next((p for p in comps if p != chorus), next((p for p in outdoor if p != chorus), outdoor[0])))
    walk = [p for p in outdoor if p not in (chorus, home)]
    room = [p for p in places if p in rooms]
    bridge = room[0] if room else (walk[-1] if walk else home)
    walk = [home] + walk + room[1:]
    start = next((x for x in world["lights"] if x in ("dawn", "day", "golden")), "day")
    return {"secs": secs, "keep": keep, "chorus": chorus, "home": home, "walk": walk, "bridge": bridge,
            "arc": list(ORDER[ORDER.index(start):])}


def _rows():
    # the standard grade's words, without its last three rows (the feeling of a line): that is feeling() here
    poses = tuple((ws, {"subject": subject}) for ws, subject in POSE_WORDS)
    return [(tuple(cw._simple(w) for w in ws), what) for ws, what in poses + cw.HINTS_STD[:-3] + cw.ICON_HINTS + cw.HINTS + cw.EMOJI_HINTS]


def _drawable(prop: str) -> bool:
    return prop in cw.PROPS + cw.PROPS_STD or prop in card_icons.TABLE


def kind_of(place: str) -> str:
    """What kind of place it is, for what can be in it (DRESS)."""
    t = str(place).split(".")[0]
    return next((kind for kind, names in KIND.items() if t in names), "green")


def prepare(world: Dict[str, Any], parts: Sequence[Tuple[str, str]], title: str = "") -> Dict[str, Any]:
    """A premium world made ready for its song: its thing ("keep"), the thing's colour, or the red scarf.
    A world that has it already (from the project's cards.json) is left as it is."""
    if "keep" in world:
        return world
    return premium_world(world, story(parts, world, title))


def premium_world(world: Dict[str, Any], st: Dict[str, Any]) -> Dict[str, Any]:
    """The world as the cards are drawn with it: with no thing of its own, the lead wears a red scarf."""
    wd = {**world, "girl": dict(world["girl"]), "boy": dict(world["boy"]), "keep": st["keep"][0] if st["keep"] else ""}
    if not st["keep"]:
        wd[wd["lead"]].update(extra="scarf", extra_col=[226, 64, 72])
    else:                    # the song's thing keeps one colour all through
        wd["keep_col"] = list(random.Random(f"keep:{st['keep'][0]}:{world.get('hue')}:{world['lead']}").choice(
            ((236, 84, 96), (255, 200, 80), (110, 170, 240), (130, 200, 150))))
    return wd


def plan_premium(parts: Sequence[Tuple[str, str]], seed: int, world: Dict[str, Any], title: str = "") -> Tuple[List[str], Dict[str, Any]]:
    """A card for every part of the timeline (as cardworld.plan()), and the story it was told with."""
    st = story(parts, world, title)
    secs, arc, keep = st["secs"], st["arc"], st["keep"]
    rows = _rows()
    phrase_rows = [(ws, what) for ws, what in rows if what.get("prop") and what["prop"] not in NOT_A_THING]
    place_rows = [(ws, what) for ws, what in rows if what.get("place") or what.get("terrain") or what.get("landmark")]
    r = random.Random(f"premium:{int(seed)}")
    rf = random.Random(f"premium-fill:{int(seed)}")      # what fills an empty card, drawn apart from the rest
    lyr = [i for i, (k, _) in enumerate(parts) if k not in ("intro", "outro", "interlude")]
    at = {i: n / max(1, len(lyr)) for n, i in enumerate(lyr)}
    rooms = cw.INDOOR + cw.INDOOR_STD
    frames = list(world["frames"])
    shot_words = {name: tuple(cw._simple(w) for w in ws) for name, ws in SHOT_WORDS.items()}
    duo_words, third_words = tuple(cw._simple(w) for w in DUO_WORDS), tuple(cw._simple(w) for w in THIRD)
    out: List[str] = []
    seen: set = set()
    walk, wi, stay, here = st["walk"], 0, 0, 0
    place, light_now, turn_light = st["home"], arc[0], {}
    since = 2
    last_feel: List[int] = []
    tb = cardwords.table(cw._simple, _drawable)      # [2026-11-16] more words, and more than one picture for a word
    turns: Counter = Counter()    # how many times a word's pictures were used: the next time takes the next one
    recent: List[str] = []        # the things in the last cards, so that what fills an empty card is not one of them
    used = {"memory": 0, "sad": 0, "glad": 0}
    # the chorus place seen several ways: its own foreground and two or three others
    ch = cw.composite(st["chorus"])
    ch_fronts = [ch[2]] + r.sample([f for f in cw.FRONTS if f not in (ch[2], "none") and cw.front_fits(f, ch[0])], 3) if ch else []

    def arc_light(t: float) -> str:
        return arc[min(len(arc) - 1, int(t * len(arc)))]

    def put(spec: str) -> None:
        out.append(spec); seen.add(spec)
        recent.append(spec.split("|")[5])
        del recent[:-7]

    for i, ((kind, text), sc) in enumerate(zip(parts, secs)):
        sec = sc["sec"]
        line = cw._simple(text)
        if sec == "intro":       # the song's thing on a table, or (an umbrella, say) the lead holding it at the first place
            if keep and keep[1] in card_icons.TABLE and card_icons.TABLE[keep[1]][0] in ("hold", "side"):
                put(cw.card(st["home"], arc[0], "clear", "none", keep[1], "still", "c", 0))
            else:
                put(cw.card(st["home"], arc[0], "clear", "solo_back" if keep else "none", keep[0] if keep else "none", "wide", "c", 0))
            continue
        if sec == "outro":       # back where it began, at night: small against the moon
            happy = sum(last_feel[-6:]) >= 0
            spec, n = "", 0
            while not spec or spec in seen:
                spec = cw.card(st["home"], "night", "clear", "duo_back" if happy else "solo_back",
                               keep[0] if keep and keep[0] not in ("umbrella", "rainbow") else "stars", "moon" if n == 0 else "wide", "c", n)
                n += 1
            put(spec)
            continue
        if sec == "interlude":
            pl = out[-1].split("|")[1] if out else st["home"]
            if cw.composite(pl):
                pl = cw.with_view(pl, None, "small")
            spec, n = "", 0
            while not spec or spec in seen:
                spec = cw.card(pl, light_now, "clear", "none", world["ambient"] if world["ambient"] != "none" and n == 0 else ("birds" if n % 2 else "none"),
                               "far" if n == 0 else "wide", "c", n)
                n += 1
            put(spec)
            continue
        t = at.get(i, 0.0)
        h = hints(line, rows)
        g = cardgrammar.read(line, rows)        # None without jieba: the cards as before
        more = cardwords.read(line, [cw._simple(w) for w, _f in g["words"]] if g else (), tb, says)
        feel = feeling(line)
        last_feel.append(feel)
        k = sc["k"]
        step = 0 if sc["turn"] == 0 else (2 if sc["turn"] == sc.get("turns", 1) - 1 else 1)
        # ---- where
        if sec == "chorus":
            pl = st["chorus"]
        elif sec == "bridge":
            if k == 0:
                place, stay, here = st["bridge"], 2, 0
            elif stay <= 0:
                place, stay, here = walk[wi % len(walk)], 2, 0
                wi += 1
            stay -= 1
            pl = place
        else:
            if stay <= 0:
                place, stay, here = walk[wi % len(walk)], r.choice((2, 3, 3)), 0
                wi += 1
            stay -= 1
            pl = place
        if sec != "chorus":
            if h.get("place"):
                pl = h["place"]
            elif h.get("terrain") or h.get("landmark"):
                pl = cw.compose(pl if cw.composite(pl) else st["chorus"], h.get("terrain"), h.get("landmark"), world)
        # ---- when: the day goes on; a chorus keeps the light it began with
        base = arc_light(t)
        if sec == "chorus":
            if sc["turn"] not in turn_light:
                turn_light[sc["turn"]] = arc[max(arc.index(base), arc.index(light_now) if light_now in arc else 0)]
                if sc["turn"] - 1 in turn_light:     # each time round a step later than the last, while there is a later
                    turn_light[sc["turn"]] = arc[max(arc.index(turn_light[sc["turn"]]), min(len(arc) - 1, arc.index(turn_light[sc["turn"] - 1]) + 1))]
                if sc["turns"] > 1 and sc["turn"] == sc["turns"] - 1:
                    turn_light[sc["turn"]] = arc[max(arc.index(turn_light[sc["turn"]]), len(arc) - 2)]
            base = turn_light[sc["turn"]]
        if light_now in arc and arc.index(base) < arc.index(light_now):
            base = light_now
        light_now = light = base
        want = h.get("light") or more.get("light")
        if want in arc and arc.index(want) > arc.index(base) and sec != "chorus":   # the words move it on a step, for this card
            light = arc[arc.index(base) + 1]
        weather = h.get("weather", "clear")
        if weather != "clear" and light in ("day", "golden"):
            light = "overcast"
        elif feel <= -2 and light in ("day", "golden") and sec != "chorus":
            light = "overcast"
        if pl in rooms:
            weather = "clear"
        dark = light in ("dusk", "night")
        # ---- who
        doers = set(str(g["who"]).split("、")) if g and g["who"] else set()
        both = bool(doers & {"我", "我們"}) and bool(doers & {"你", "他", "她", "你們", "他們", "她們"})   # 我走回從前你往未來飛
        duo_said, third = says(line, duo_words), says(line, third_words)
        hs, hs_more = h.get("subject"), more.get("subject")      # a pose the rows know; one the further words give
        if sec == "chorus":
            subject = CHORUS[step][k % len(CHORUS[step])]
            if feel <= -2 or hs == "duo_apart":      # sung sad: the two of them apart, or one of them alone
                subject = SAD_DUO[used["sad"] % len(SAD_DUO)]
                used["sad"] += 1
            elif third:
                subject = "other_back"
            elif (hs or hs_more or "").startswith("duo"):
                subject = hs if hs and hs.startswith("duo") else hs_more
        else:
            pool = {"verse": VERSE, "pre": PRE, "bridge": BRIDGE}[sec]
            subject = pool[(k + sc["again"] * 3 + (i // 7)) % len(pool)]
            if third:
                subject = "other_back" if k % 2 == 0 else "other_away"
            elif hs:
                subject = hs
            elif both and feel <= -1:
                subject = ("duo_apart", "duo_backs", "duo_far")[used["sad"] % 3]
                used["sad"] += 1
            elif duo_said or both:
                subject = ("duo_back", "duo_sit", "duo_walk", "duo_ground")[(k + i) % 4]
            elif hs_more:
                subject = hs_more
            elif feel <= -2:
                subject = SAD_SOLO[used["sad"] % len(SAD_SOLO)]
                used["sad"] += 1
            elif feel >= 2:
                subject = GLAD_SOLO[used["glad"] % len(GLAD_SOLO)]
                used["glad"] += 1
        if subject == "duo_stars" and not dark:
            subject = "duo_ground"
        # ---- what is in it
        prop = h.get("prop", "none")
        if sc["again"]:           # sung before: another of the things its words name
            alts = []
            for ws, what in rows:
                if "prop" in what and what["prop"] not in alts and says(line, ws):
                    alts.append(what["prop"])
            if any(not a.startswith("e_") for a in alts):
                alts = [a for a in alts if not a.startswith("e_")]         # an emoji is not "another thing" beside a drawn one
            if len(alts) > 1:
                prop = alts[sc["again"] % len(alts)]
            elif sc["again"] % 2 and prop not in tb["vary"]:
                prop = "none"
        # [2026-11-16] a word with several pictures: each time it comes, the next one (the song's own thing stays)
        group: Tuple[str, ...] = ()
        if prop == "none" and more.get("pics"):
            group = more["pics"]
        elif prop in tb["vary"] and not (keep and prop == keep[0]):
            group = tb["vary"][prop]
        if group:
            for _try in range(len(group)):
                prop = group[turns[group] % len(group)]
                turns[group] += 1
                if not (dark and (prop.startswith("e_sun") or prop in ("sun", "sunrise", "rays", "sunriseclock"))):
                    break           # no sun in a night card
        if keep and (k == 0 or says(line, keep[2])):
            prop = keep[0]
        duo = subject.startswith("duo")
        if sec == "chorus" and duo and prop in ("bike", "dots", "ask", "call"):
            prop = "none"           # a chorus keeps the two of them: what belongs to one person stays out
        if prop in ("bike", "dots", "ask", "call", "wings") and duo:
            subject = {"bike": "solo_walk", "wings": "solo_open"}.get(prop, "solo_front")
        if prop == "tears" and (duo and subject not in ("duo_apart", "duo_comfort") or subject in ("solo_cover", "solo_back", "solo_away", "solo_ground", "other_back", "other_away", "none")):
            subject = "duo_comfort" if sec == "chorus" and duo else "solo_front"
        if prop == "thread" and not duo:
            subject = "duo_face"
        if prop == "umbrella" and subject not in UMBRELLA_OK:
            subject = NO_UMBRELLA["duo" if duo and subject not in ("duo_apart", "duo_far", "duo_follow", "duo_wave") else "solo"]
        if prop in ("dots", "ask", "call") and subject in ("none", "solo_back", "other_back", "solo_away", "other_away", "solo_ground", "solo_cover"):
            subject = "solo_front"
        if prop == "bike":
            subject = "solo_walk"
        duo = subject.startswith("duo")
        outdoor = pl not in rooms
        # ---- how it is seen
        shot = ""
        if sec == "chorus":
            shot = CHORUS_FRAMES[step][k % len(CHORUS_FRAMES[step])]
        else:
            shot = frames[(i + k) % len(frames)]
            since += 1
            if since >= 2 and r.random() < 0.7:
                fam = card_icons.TABLE[prop][0] if prop in card_icons.TABLE else ""
                pick = ""
                if prop in ("letter", "clock", "frames", "hourglass", "calendar", "key", "candle", "diary") or (fam in ("hold", "side") and not duo and r.random() < 0.5):
                    pick = "still"
                elif subject.startswith("solo") and subject in ("solo_front", "solo_back", "solo_reach", "solo_open", "solo_look", "solo_point") and prop in (
                        "none", "stars", "shooting", "bigmoon", "birds", "rainbow", "lantern", "kite", "plane", "balloons"):
                    pick = "over"
                elif subject in ("solo_walk", "solo_away", "solo_run", "solo_back", "other_away", "duo_walk", "duo_far", "solo_shade"):
                    pick = "far"
                elif outdoor and (weather == "rain" or kind_of(pl) == "water"):
                    pick = "mirror"
                if pick and not (out and out[-1].split("|")[6] == pick):
                    shot, since = pick, 0
        # what the words ask for comes before the turn of the section
        if says(line, shot_words["photo"]):
            shot = "photo"
        elif says(line, shot_words["memory"]):
            shot = "memory" if used["memory"] % 2 == 0 else "photo"
            used["memory"] += 1
        elif says(line, shot_words["moon"]) or prop == "bigmoon":
            shot, prop = "moon", ("none" if prop == "bigmoon" else prop)
        elif says(line, shot_words["window"]) and pl not in rooms and sc["again"] % 2 == 0:
            shot = "window"
        elif says(line, shot_words["split"]) or (subject == "duo_apart" and sc["again"] % 2 == 1):
            shot, subject = "split", "duo_apart"
        elif says(line, shot_words["tilt"]) and feel <= 0 and sc["again"] % 3 == 0:
            shot = "tilt"
        elif says(line, shot_words["globe"]) and sc["again"] % 2 == 1:
            shot = "globe"
        if more.get("shot") and sec != "chorus" and shot not in ("photo", "memory", "moon", "window", "split", "tilt", "globe"):
            shot = more["shot"]         # 遙遠: seen from far; 臉, 眼前: close
        # ---- [2026-11-15] what the line does with its thing (a verb or a preposition and the thing: cardphrase)
        act = cardphrase.read(line, phrase_rows, _negated, cw._simple, place_rows)
        if act and keep and act["thing"] and act["thing"] != keep[0] and says(line, keep[2]):
            # the song's own thing, when the line names it, comes first: it is what is handed over or held (a
            # thing of the sky, a rainbow, stays in the sky)
            if card_icons.TABLE.get(keep[0], ("",))[0] == "sky" or keep[0] in ("rainbow", "stars", "kite", "balloons", "birds"):
                act = None
            else:
                act = {**act, "thing": keep[0]}
        if act:
            a, th = act["act"], str(act["thing"])
            duo = subject.startswith("duo")
            if act["with"] and not duo:
                subject, duo = ("duo_walk" if a == "toward" else "duo_front"), True
            fam = card_icons.TABLE.get(th, ("",))[0]
            skyish = fam == "sky" or th in ("stars", "shooting", "bigmoon", "birds", "rainbow", "kite", "plane", "balloons", "lantern")
            if a == "give" and th:
                prop, subject, shot = th, "duo_face", "give"
            elif a == "hold" and th:
                prop = th
                if not duo:
                    subject = "solo_front"
                shot = "close" if fam == "hold" else "still"
            elif a == "under" and th:
                if th == "bigmoon":
                    shot, prop = "moon", "none"
                elif th in ("umbrella", "umbrellai"):
                    prop = "umbrella"
                else:
                    prop, shot = th, "under"
                    if not duo:
                        subject = "solo_front"
            elif a == "look" and th:
                prop, subject = th, ("duo_back" if duo else "solo_back")
                shot = "wide" if skyish else "toward"
            elif a == "toward":
                subject = "duo_walk" if duo else "solo_away"
                if th and not skyish:
                    prop, shot = th, "toward"
                else:
                    prop, shot = (th or prop), "far"
            elif a == "write":
                prop, shot = (th or "letter"), "still"
            elif a == "listen":
                prop = th or "notes"
                if not duo:
                    subject = "solo_think"
            elif a == "wait":
                prop = th or prop
                if not duo:
                    subject = "solo_front" if th else "solo_sit"
            elif a == "ride" and th:
                prop = th
                if not duo:
                    subject = "solo_walk"
            if act["way"] and shot not in ("give", "under", "toward"):
                subject, shot = ("duo_walk" if duo else "solo_walk"), "far"
        if shot in cw.ACT_FRAMES and prop not in card_icons.TABLE:
            prop = icon_for(prop)   # a hand-drawn thing has a small picture to hand over or stand under
        duo = subject.startswith("duo")
        # a shot that does not suit the card gives way
        if shot == "give" and (not duo or prop not in card_icons.TABLE):
            shot = "mid"
        if shot in ("under", "toward") and prop not in card_icons.TABLE:
            shot = "wide" if shot == "under" else "far"
        if shot == "moon" and not (outdoor and weather == "clear" and light in ("golden", "sunset", "dusk", "night", "dawn")):
            shot = "wide"
        if shot == "mirror" and not outdoor:
            shot = "mid"
        if shot == "sil" and not (outdoor and weather == "clear" and light in ("sunset", "golden", "dawn", "dusk") and prop in ("none", "hearts", "thread", "leaves", "petals", "birds")):
            shot = "close"
        if shot == "hands" and (not duo or subject in ("duo_apart", "duo_far", "duo_follow", "duo_wave", "duo_backs") or prop not in (
                "none", "hearts", "thread", "petals", "leaves", "bubbles", "fireflies", "stars")):
            shot = "close"
        if shot == "over" and (duo or prop == "umbrella"):
            shot = "mid"
        if shot == "still" and prop not in card_icons.TABLE and prop not in ("letter", "clock", "frames", "none", "umbrella"):
            prop = icon_for(prop)       # [2026-11-16] on the table lies the thing itself (an hourglass was a cup and a book)
            if prop not in card_icons.TABLE:
                shot = "mid"
        if shot == "still" and prop == "umbrella":
            prop = "umbrellai"
        if shot == "still" and (prop == "none" or any(sp.split("|")[5:7] == [prop, "still"] for sp in out[-12:])):
            shot = "mid"            # (and not the same thing on the table again so soon)
        if shot == "close" and (subject in NO_CLOSE or prop in ("bike", "wings", "thread", "frames", "kite", "rainbow", "umbrella")):
            shot = "mid"
        if out and out[-1].split("|")[6] == shot and shot in cw.FRAMES_STD + cw.FRAMES_PREM:
            shot = "mid" if shot != "mid" else "wide"       # never the same special shot twice running
        # ---- [2026-11-16] a card whose line names nothing: the song's own thing again (not when it was in one of the
        # last cards), or air and sky of the place (AMBIENT), or nothing: the people and their faces carry it.
        # (Before: four in five of these took any thing of the place, a road sign or a lamb, which said things
        # the words did not.)
        if prop == "none" and shot not in ("hands", "still", "split", "moon"):
            roll = rf.random()
            if (keep and roll < 0.3 and keep[0] not in recent and keep[0] not in KEEP_NOT_ALONE
                    and (keep[0] in cw.PROPS + cw.PROPS_STD or keep[0] in card_icons.TABLE)
                    and not (shot == "close" and keep[0] in ("rainbow",))):
                prop = keep[0]
            elif roll < 0.7:
                pool2 = [x for x in (AMBIENT["night"] if dark and outdoor and rf.random() < 0.5 else AMBIENT[kind_of(pl)])
                         if (x in cw.PROPS + cw.PROPS_STD or x in card_icons.TABLE) and x not in recent]
                if shot == "close":
                    pool2 = [x for x in pool2 if x in cw.PROPS or card_icons.TABLE.get(x, ("",))[0] == "rain"]
                if pool2:
                    prop = rf.choice(pool2)
        # ---- the place, seen this way or that
        if cw.composite(pl):
            if sec == "chorus" and ch_fronts and pl.split(".")[:2] == st["chorus"].split(".")[:2]:
                view = CHORUS_VIEWS[(k + sc["turn"] * 3) % len(CHORUS_VIEWS)]
                if view == "centre" and duo and shot != "far":
                    view = "near"
                pl = cw.with_view(pl, ch_fronts[((k + 1) // 2 + sc["turn"]) % len(ch_fronts)], view)
            elif sec != "chorus":
                view = ("", "near", "small")[here % 3] if h.get("landmark") is None else ("", "near")[here % 2]
                pl = cw.with_view(pl, None, view)
        here += 1
        pos = "c" if duo else cw.POSES[(i + seed) % 3]
        if shot == "toward" and not duo and pos == "c":
            pos = "l"               # beside the middle, where the thing they go to is
        # ---- [2026-11-16] the line's grammar (cardgrammar; nothing without jieba): the face it asks for, how many
        # of its thing, and whether a card with one person shows the other one (你 / 她 does it, not 我)
        face, count, who = "", 1, "m"
        if g:
            face = cardgrammar.FACE_KEY.get(str(g["face"]), "")
            for th in g["things"]:
                if th["n"] > 1 and prop in card_icons.TABLE:
                    named = hints(cardgrammar.simple(th["word"]), phrase_rows).get("prop")
                    if named and prop in (named, icon_for(named)):
                        count = int(th["n"])
                        break
            if doers and doers <= {"你", "他", "她", "你們", "他們", "她們"} and not duo and "我" not in line:
                who = "o"
        spec, n = cw.card(pl, light, weather, subject, prop, shot, pos, 0, face, count, who), 0
        while spec in seen:
            n += 1
            spec = cw.card(pl, light, weather, subject, prop, shot, pos if duo else cw.POSES[(i + n) % 3], n, face, count, who)
        put(spec)
    return out, st
