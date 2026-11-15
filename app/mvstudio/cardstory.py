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

from . import card_icons
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
          "farbridge", "castle", "piano", "telescope", "maple", "fountain", "swings", "benchlamp", "signpost")
VERSE = ("solo_walk", "solo_sit", "solo_front", "solo_back")
PRE = ("solo_reach", "solo_open", "solo_run", "solo_front")
BRIDGE = ("solo_back", "duo_apart", "solo_sit", "other_back")
CHORUS = (("duo_back", "duo_front", "duo_sit", "duo_hands"),     # the first time round: together, seen from afar
          ("duo_hands", "duo_face", "duo_sit", "duo_back"),
          ("duo_hug", "duo_face", "duo_hands", "duo_hug"))        # the last time round: closest
CHORUS_FRAMES = (("wide", "mid", "wide", "mid"), ("mid", "mid", "close", "mid"), ("mid", "close", "hands", "close"))
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


def hints(line: str, rows) -> Dict[str, str]:
    got: Dict[str, str] = {}
    for ws, what in rows:
        if line and says(line, ws):
            for k, v in what.items():
                got.setdefault(k, v)
    return got


def feeling(line: str) -> int:
    """How happy (more than 0) or sad (less than 0) a line is."""
    return sum(1 for w in HAPPY if says(line, (cw._simple(w),))) - sum(1 for w in SAD if says(line, (cw._simple(w),)))


# -------------------------------------------------------------------------------------------- the story
def story(parts: Sequence[Tuple[str, str]], world: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """What stays the same through the song: its sections, its thing, its chorus place, where it starts."""
    secs = sections(parts, title)
    lines = [cw._simple(t) for k, t in parts if k not in ("intro", "outro", "interlude")]
    score = []
    for n, (prop, still, words) in enumerate(KEEPSAKES):
        ws = tuple(cw._simple(w) for w in words)
        score.append((sum(1 for ln in lines if says(ln, ws)), -n, prop, still, ws))
    if "keep" in world:      # chosen when the song's cards were first drawn: it stays, whatever the words say now
        keep = next((sc[2:] for sc in score if sc[2] == world["keep"]), None)
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
                next((p for p in outdoor if p != chorus and not cw.composite(p)), outdoor[0]))
    walk = [p for p in outdoor if p not in (chorus, home)]
    room = [p for p in places if p in rooms]
    bridge = room[0] if room else (walk[-1] if walk else home)
    walk = [home] + walk + room[1:]
    start = next((x for x in world["lights"] if x in ("dawn", "day", "golden")), "day")
    return {"secs": secs, "keep": keep, "chorus": chorus, "home": home, "walk": walk, "bridge": bridge,
            "arc": list(ORDER[ORDER.index(start):])}


def _rows():
    # the standard grade's words, without its last three rows (the feeling of a line): that is feeling() here
    return [(tuple(cw._simple(w) for w in ws), what) for ws, what in cw.HINTS_STD[:-3] + cw.ICON_HINTS + cw.HINTS]


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
    r = random.Random(f"premium:{int(seed)}")
    lyr = [i for i, (k, _) in enumerate(parts) if k not in ("intro", "outro", "interlude")]
    at = {i: n / max(1, len(lyr)) for n, i in enumerate(lyr)}
    rooms = cw.INDOOR + cw.INDOOR_STD
    frames = list(world["frames"])
    out: List[str] = []
    seen: set = set()
    walk, wi, stay = st["walk"], 0, 0
    place, light_now, turn_light = st["home"], arc[0], {}
    since = 2
    last_feel = []

    def arc_light(t: float) -> str:
        return arc[min(len(arc) - 1, int(t * len(arc)))]

    for i, ((kind, text), sc) in enumerate(zip(parts, secs)):
        sec = sc["sec"]
        line = cw._simple(text)
        if sec == "intro":       # the song's thing on a table, or (an umbrella, say) the lead holding it at the first place
            if keep and keep[1] in card_icons.TABLE and card_icons.TABLE[keep[1]][0] in ("hold", "side"):
                spec = cw.card(st["home"], arc[0], "clear", "none", keep[1], "still", "c", 0)
            else:
                spec = cw.card(st["home"], arc[0], "clear", "solo_back" if keep else "none", keep[0] if keep else "none", "wide", "c", 0)
            out.append(spec); seen.add(spec)
            continue
        if sec == "outro":
            happy = sum(last_feel[-6:]) >= 0
            spec = cw.card(st["home"], "night", "clear", "duo_back" if happy else "solo_back",
                           keep[0] if keep and keep[0] not in ("umbrella",) else "stars", "wide", "c", 0)
            while spec in seen:
                spec = spec[:-1] + str(int(spec[-1]) + 1)
            out.append(spec); seen.add(spec)
            continue
        t = at.get(i, at[lyr[-1]] if lyr else 0.0) if sec != "interlude" else (at.get(i - 1, 0.0) if i else 0.0)
        if sec == "interlude":
            pl = out[-1].split("|")[1] if out else st["home"]
            spec, n = cw.card(pl, light_now, "clear", "none", world["ambient"] if world["ambient"] != "none" else "birds", "wide", "c", 0), 0
            while spec in seen:
                n += 1; spec = cw.card(pl, light_now, "clear", "none", "birds" if n % 2 else "none", "wide", "c", n)
            out.append(spec); seen.add(spec)
            continue
        h = hints(line, rows)
        feel = feeling(line)
        last_feel.append(feel)
        k = sc["k"]
        # ---- where
        if sec == "chorus":
            pl = st["chorus"]
        elif sec == "bridge":
            pl = st["bridge"] if k < 2 else place
            if k >= 2 and stay <= 0:
                wi, stay = wi + 1, 2
            place = pl
        else:
            if stay <= 0:
                place, stay = walk[wi % len(walk)], r.choice((3, 3, 4))
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
        want = h.get("light")
        if want in arc and arc.index(want) > arc.index(base) and sec != "chorus":   # the words move it on a step, for this card
            light = arc[arc.index(base) + 1]
        weather = h.get("weather", "clear")
        if weather != "clear" and light in ("day", "golden"):
            light = "overcast"
        elif feel <= -2 and light in ("day", "golden") and sec != "chorus":
            light = "overcast"
        if pl in rooms:
            weather = "clear"
        # ---- who
        duo_said = says(line, tuple(cw._simple(w) for w in DUO_WORDS))
        third = says(line, tuple(cw._simple(w) for w in THIRD))
        hs = h.get("subject")
        if sec == "chorus":
            step = 0 if sc["turn"] == 0 else (2 if sc["turn"] == sc["turns"] - 1 else 1)
            subject = CHORUS[step][k % 4]
            if feel <= -2 or hs == "duo_apart":      # sung sad: the two of them apart, or one thinking of the other
                subject = "duo_apart" if sc["again"] % 2 == 0 else "solo_back"
            elif third:
                subject = "other_back"
            elif hs in ("duo_hug", "duo_face", "duo_hands", "duo_sit"):
                subject = hs
        else:
            subject = {"verse": VERSE, "pre": PRE, "bridge": BRIDGE}[sec][k % 4]
            if third:
                subject = "other_back"
            elif hs:
                subject = hs
            elif duo_said:
                subject = "duo_sit" if k % 2 else "duo_back"
            elif feel <= -2:
                subject = "solo_back" if k % 2 else "solo_sit"
            elif feel >= 2:
                subject = "solo_wave" if k % 2 else "solo_open"
        # ---- what is in it
        prop = h.get("prop", "none")
        if sc["again"]:           # sung before: another of the things its words name
            alts = []
            for ws, what in rows:
                if "prop" in what and what["prop"] not in alts and says(line, ws):
                    alts.append(what["prop"])
            if len(alts) > 1:
                prop = alts[sc["again"] % len(alts)]
            elif sc["again"] % 2:
                prop = "none"
        if keep and (k == 0 or says(line, keep[2])):
            prop = keep[0]
        if prop == "none" and world["ambient"] != "none" and r.random() < 0.25:
            prop = world["ambient"]
        duo = subject.startswith("duo")
        if sec == "chorus" and duo and prop in ("bike", "dots", "ask", "call"):
            prop = "none"           # a chorus keeps the two of them: what belongs to one person stays out
        if prop in ("bike", "dots", "ask", "call", "wings") and duo:
            subject = {"bike": "solo_walk", "wings": "solo_open"}.get(prop, "solo_front")
        if prop == "tears" and duo and subject != "duo_apart":
            subject = "duo_apart" if sec == "chorus" else "solo_front"
        if prop == "thread" and not duo:
            subject = "duo_face"
        if prop == "umbrella":
            if subject in ("duo_face", "duo_apart", "duo_hug"):
                subject = "duo_hands"
            elif subject in ("solo_reach", "solo_open", "solo_wave", "solo_sit", "solo_run"):
                subject = "solo_front"
            elif subject in ("none", "other_back"):
                subject = "solo_back"
        if prop in ("tears", "dots", "ask", "call") and subject in ("none", "solo_back", "other_back"):
            subject = "solo_front"
        duo = subject.startswith("duo")
        # ---- how close
        if sec == "chorus":
            step = 0 if sc["turn"] == 0 else (2 if sc["turn"] == sc["turns"] - 1 else 1)
            frame = CHORUS_FRAMES[step][k % 4]
            if frame == "close" and step == 2 and k % 4 == 1 and pl not in rooms and weather == "clear" \
                    and light in ("sunset", "golden", "dawn", "dusk") and prop in ("none", "hearts", "thread", "leaves", "petals", "birds"):
                frame = "sil"
        else:
            frame = frames[(i + k) % len(frames)]
            since += 1
            if since >= 3 and r.random() < 0.6:
                fam = card_icons.TABLE[prop][0] if prop in card_icons.TABLE else ""
                if out and out[-1].split("|")[6] == "still":
                    pass
                elif prop in ("letter", "clock", "frames", "hourglass", "calendar", "key", "candle", "diary") or (fam in ("hold", "side") and not duo):
                    frame, since = "still", 0
                elif subject.startswith("solo") and subject not in ("solo_sit", "solo_run") and prop in ("none", "stars", "shooting", "bigmoon", "birds", "rainbow", "lantern", "kite", "plane", "balloons"):
                    frame, since = "over", 0
        if frame == "hands" and (not duo or subject == "duo_apart" or prop not in ("none", "hearts", "thread", "petals", "leaves", "bubbles", "fireflies", "stars")):
            frame = "close" if subject not in ("duo_sit", "duo_apart") else "mid"
        if frame == "close" and (subject in ("solo_sit", "duo_sit", "duo_apart", "none") or prop in ("bike", "wings", "thread", "frames", "kite", "rainbow", "umbrella")):
            frame = "mid"
        if frame == "still" and prop == "umbrella":
            prop = "umbrellai"
        pos = "c" if duo else cw.POSES[(i + seed) % 3]
        spec, n = cw.card(pl, light, weather, subject, prop, frame, pos, 0), 0
        while spec in seen:
            n += 1
            spec = cw.card(pl, light, weather, subject, prop, frame, pos if duo else cw.POSES[(i + n) % 3], n)
        seen.add(spec)
        out.append(spec)
    return out, st
