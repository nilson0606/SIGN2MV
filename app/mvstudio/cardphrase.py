"""What a lyric line does with a thing: a verb or a preposition and the thing it goes with (2026-11-15).

cardstory picks the words of a line (a place, a thing, a way to stand); this reads how they go together, with
a few plain patterns and no grammar:

  verb + thing      送你一束花 (give)  抱著你的照片 (hold)  看著星星 (look)  等公車 (wait)  騎單車 (ride)
                    寫一封信 (write)  聽一首歌 (listen)  走向燈塔 / 追著風箏 (toward)
  把 + thing + verb 把傘給你 (give)
  thing + 下         月光下, 樹下, 路燈下 (under)
  和你 / 跟你 / 陪你   (with: the two of them)
  從 … 到 …          (a way to go)

The thing is the nearest one the line names after the verb (within a few characters), or before 下. A verb
right after a no ("不想看見") does nothing. read() takes the line as cardworld._simple() gives it.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

ACTS = (   # (act, verbs): the first act whose verb the line says with a thing after it wins
    ("give", ("送給", "交給", "遞給", "獻給", "送你", "送妳", "給你", "給妳", "遞", "送", "給")),
    ("hold", ("拿著", "握著", "捧著", "抱著", "提著", "帶著", "揣著", "拿起", "摘下", "撿起", "抱緊", "握緊", "緊握", "抓著", "抓住")),
    ("write", ("寫下", "寫著", "寫給", "寫")),
    ("listen", ("聽見", "聽到", "聽著", "傾聽", "聽")),
    ("ride", ("騎著", "騎", "搭上", "搭著", "坐上", "乘著", "搭")),
    ("look", ("看著", "望著", "凝視", "仰望", "望向", "看向", "看見", "看到", "望見", "盯著", "注視", "抬頭看", "數著")),
    ("toward", ("走向", "奔向", "飛向", "跑向", "走到", "回到", "追著", "追逐", "追", "前往", "向著", "朝著", "往", "朝")),
    ("wait", ("等待", "等著", "守著", "等")),
)
NEAR = {"give": 6, "hold": 5, "write": 5, "listen": 5, "ride": 3, "look": 5, "toward": 5, "wait": 4}
WITH = ("和你", "跟你", "與你", "陪著你", "陪你", "和妳", "跟妳", "與妳", "陪著妳", "陪妳", "我們一起", "跟我走", "牽著你", "牽著妳")
UNDER = ("底下", "之下", "下")
NOT_HERE = ("往事", "以往", "過往", "嚮往", "往往", "往來", "方向", "一向", "向來", "朝陽", "朝夕", "王朝", "送別", "給予", "等等", "等於",
            "帶著走", "看著辦", "聽說", "聽話", "回到過去", "回到從前")
# words that name a feeling or a time, not something to hand over, hold or look at (their cards still use them)
ABSTRACT = ("幸福", "永遠", "一生", "一輩子", "今生", "勇氣", "思念", "想念", "回憶", "記憶", "未來", "時間", "時光", "希望", "夢想",
            "愛情", "溫柔", "快樂", "自由", "答案", "承諾", "秘密", "青春", "世界", "生命", "感覺", "心情", "寂寞", "孤單", "眼淚", "來不及", "一瞬間", "瞬間")
UNDER_NOT = ("下來", "下去", "下雨", "下雪", "下次", "下午", "下一", "放下", "留下", "剩下", "天下", "下輩子", "上下")


def _prep(simple) -> None:
    global ACTS, WITH, UNDER, NOT_HERE, UNDER_NOT, ABSTRACT, _READY
    ACTS = tuple((a, tuple(simple(v) for v in vs)) for a, vs in ACTS)
    WITH = tuple(simple(w) for w in WITH)
    UNDER = tuple(simple(w) for w in UNDER)
    NOT_HERE = tuple(simple(w) for w in NOT_HERE)
    UNDER_NOT = tuple(simple(w) for w in UNDER_NOT)
    ABSTRACT = tuple(simple(w) for w in ABSTRACT)
    _READY = True


_READY = False


def _spans(line: str, words: Sequence[str]) -> List[Tuple[int, int]]:
    out = []
    for w in words:
        at = 0
        while True:
            j = line.find(w, at)
            if j < 0:
                break
            out.append((j, j + len(w)))
            at = j + 1
    return out


def _inside(line: str, j: int, e: int, words: Sequence[str]) -> bool:
    """Whether line[j:e] is part of one of the words (往 in 往事, 下 in 下雨)."""
    for w in words:
        for k in range(max(0, j - len(w) + 1), j + 1):
            if line.startswith(w, k) and k + len(w) >= e:
                return True
    return False


def _clause(line: str, j: int) -> Tuple[int, int]:
    """The stretch of the line between spaces or punctuation that position j is in."""
    seps = " ,，、。.!！?？…;；:："
    c0 = max(line.rfind(ch, 0, j) for ch in seps) + 1
    ends = [i for i in (line.find(ch, j) for ch in seps) if i >= 0]
    return c0, min(ends) if ends else len(line)


def things(line: str, rows, places=()) -> List[Tuple[int, int, str]]:
    """Where the line names a thing: (start, end, prop), the longer word first where two start together; not
    inside a word for a place (places: rows of places, terrains and landmarks: 燈 is no lamp in 燈塔)."""
    blocked = [(j, e) for ws, _what in places for w in ws if w and not w.isascii() and len(w) >= 2 for j, e in _spans(line, (w,))]
    got = []
    for ws, what in rows:
        prop = what.get("prop")
        if not prop:
            continue
        for w in ws:
            if w and not w.isascii() and w not in ABSTRACT:
                for j, e in _spans(line, (w,)):
                    if not any(bj <= j and e <= be and e - j < be - bj for bj, be in blocked):
                        got.append((j, e, prop))
    got.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    out, last_end = [], -1
    for j, e, p in got:
        if j >= last_end:       # a shorter word inside a longer one is not another thing
            out.append((j, e, p))
            last_end = e
    return out


def read(line: str, rows, negated=None, simple=None, places=()) -> Optional[Dict[str, object]]:
    """{"act": ..., "thing": prop or "", "with": bool, "way": bool} for a (simplified) line, or None.
    rows: (words, {"prop": ...}) as cardstory reads them; negated(line, j): whether position j follows a no."""
    if not _READY and simple:
        _prep(simple)
    if not line:
        return None
    named = things(line, rows, places)
    out: Dict[str, object] = {"act": "", "thing": "", "with": any(w in line for w in WITH),
                              "way": bool(re.search(r"从.{1,8}到|從.{1,8}到", line))}
    # thing + 下: under it
    for j, e, prop in named:
        for u in UNDER:
            if line.startswith(u, e) and not _inside(line, e, e + len(u), UNDER_NOT) and not (negated and negated(line, j)):
                out.update(act="under", thing=prop)
                return out
    for act, verbs in ACTS:
        for j, e in sorted(_spans(line, verbs), key=lambda s: (s[0], s[0] - s[1])):
            if _inside(line, j, e, NOT_HERE) or (negated and negated(line, j)) or line[e:e + 1] == "不":
                continue                          # (看不見, 抱不到: not done either)
            c0, c1 = _clause(line, j)
            after = [t for t in named if e <= t[0] <= e + NEAR[act] and t[1] <= c1]
            if after:
                out.update(act=act, thing=after[0][2])
                return out
            if act in ("give", "hold"):          # the thing before: 把傘給你, 摘兩顆星給妳, 一壺酒給妳
                before = [t for t in named if c0 <= t[0] and t[1] <= j and j - t[1] <= 6]
                if before:
                    out.update(act=act, thing=before[-1][2])
                    return out
            if act in ("write", "listen", "wait", "toward") and not out["act"]:
                out["act"] = act                  # with nothing named: a letter, music, waiting, walking away
    return out if (out["act"] or out["with"] or out["way"]) else None
