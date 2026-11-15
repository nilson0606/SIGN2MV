"""A lyric line taken apart for the picture cards (draft, 2026-11-15): who, does what, to what (how many, what
like), where, how, when, in what tone, with what face.

The words are cut and tagged by jieba (MIT; offline), which knows every word the cards know as one word (so
路燈 is not 燈). The line is turned into simplified characters one by one for jieba, so the parts can be shown
in the line's own characters. Nothing here draws yet: read() gives the reading, for people to look over.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

PRONOUNS = {"我": "我", "你": "你", "妳": "你", "您": "你", "他": "他", "她": "她", "它": "它", "我们": "我們", "你们": "你們",
            "他们": "他們", "她们": "她們", "咱们": "我們", "大家": "大家", "谁": "誰", "自己": "我"}
MODAL = ("想", "要", "会", "能", "能够", "可以", "愿意", "应该", "该", "得", "敢", "肯", "想要", "需要", "必须", "只能", "不能")
COPULA = ("是", "有", "在", "像", "成", "为", "让", "使", "叫", "做", "当", "变成", "成为")
NEG = ("不", "没", "没有", "别", "不再", "未", "无", "莫", "不要", "不必", "不用", "不会", "不想", "不能", "不曾", "从未")
IF = ("如果", "假如", "要是", "若", "也许", "或许", "可能", "倘若", "假设", "大概", "彷佛", "仿佛", "好像")
ASK_END = ("吗", "呢", "吧")
ASK = ("为什么", "怎么", "怎样", "哪里", "哪儿", "何时", "多久", "是否", "有没有", "能不能", "会不会", "是不是", "要不要", "可不可以")
FUNC_ADV = ("也", "还", "就", "都", "才", "又", "正", "再", "却", "只", "很", "太", "更", "最", "已", "已经", "曾", "曾经", "总",
            "总是", "一直", "依然", "仍", "仍然", "终于", "竟", "竟然", "真", "真的", "那么", "这么", "多么", "好", "越", "只是",
            "还是", "就是", "也是", "其实", "原来", "然后", "于是", "所以", "因为", "但", "但是", "可是", "而", "并")
# a line's feeling, the face it asks for (16 faces; the first word found wins, longer words first)
FACES = (
    ("大笑", ("大笑", "哈哈", "笑开", "开怀", "笑得")), ("苦笑", ("苦笑", "强颜欢笑", "笑着哭", "假装快乐")),
    ("流淚", ("流泪", "泪", "眼泪", "泪水", "哭泣", "掉眼泪", "泪流")), ("哭", ("哭", "痛哭", "哽咽", "啜泣")),
    ("生氣", ("生气", "愤怒", "气", "恨", "怒")), ("害羞", ("害羞", "脸红", "心跳", "偷偷", "腼腆", "羞")),
    ("心動", ("心动", "喜欢", "爱上", "动心", "暗恋", "怦然")), ("驚訝", ("惊讶", "竟然", "突然", "居然", "惊喜", "意外", "没想到")),
    ("擔心", ("担心", "害怕", "怕", "不安", "紧张", "恐惧", "慌")), ("委屈", ("委屈", "心酸", "难过", "受伤", "伤心", "心碎", "痛")),
    ("思念", ("想你", "想念", "思念", "怀念", "回忆", "记得", "从前")), ("寂寞", ("寂寞", "孤单", "孤独", "一个人", "空荡")),
    ("想睡", ("睡", "困", "梦", "晚安", "眼皮")), ("堅定", ("勇敢", "坚强", "相信", "决定", "一定", "不怕", "坚持", "勇气")),
    ("微笑", ("笑", "微笑", "快乐", "幸福", "开心", "甜", "温暖", "美好", "幸运")), ("平靜", ("安静", "平静", "轻轻", "静静", "慢慢", "释怀")),
)

FACE_KEY = {"大笑": "laugh", "苦笑": "wry", "流淚": "tear", "哭": "cry", "生氣": "angry", "害羞": "shy", "心動": "love", "驚訝": "wow",
            "擔心": "worry", "委屈": "sad", "思念": "miss", "寂寞": "lonely", "想睡": "sleepy", "堅定": "firm", "微笑": "smile", "平靜": "closed"}


def how_many(count: str) -> int:
    """兩顆 -> 2, 幾個 -> 3, 滿天 / 無數 -> 5; 1 when it does not say."""
    for ch, n in (("两", 2), ("二", 2), ("双", 2), ("三", 3), ("四", 4), ("五", 5), ("几", 3), ("数", 3), ("许多", 5), ("好多", 5),
                  ("无数", 5), ("满", 5), ("千", 5), ("万", 5), ("百", 5)):
        if ch in count:
            return n
    return 1


_JIEBA = None
_T2S: Dict[str, str] = {}
_S2T_WORD: Dict[str, str] = {}


def _load(rows=()) -> Optional[object]:
    """jieba, knowing the cards' words (rows: (words, what) as cardstory reads them); None without jieba."""
    global _JIEBA, _T2S
    if _JIEBA is not None:
        return _JIEBA
    try:
        import jieba
        import jieba.posseg
        jieba.setLogLevel(60)
    except Exception:  # noqa: BLE001
        return None
    try:
        from ..lyric_align import _t2s
        _T2S = dict(_t2s())
    except Exception:  # noqa: BLE001
        _T2S = {}
    jieba.initialize()
    known = jieba.dt.FREQ
    for ws, what in rows:
        tag = "n" if what.get("prop") else ("ns" if (what.get("place") or what.get("terrain") or what.get("landmark")) else "")
        if not tag:
            continue
        for w in ws:
            if w and not w.isascii() and len(w) >= 2 and w not in PRONOUNS:
                s_w = simple(w)
                if known.get(s_w, 0) > 0:
                    jieba.add_word(s_w, freq=max(50000, known[s_w]))     # a word jieba knows keeps its own tag (喜欢 is a verb)
                else:
                    jieba.add_word(s_w, freq=50000, tag=tag)
    _JIEBA = jieba
    return jieba


def simple(text: str) -> str:
    """Simplified characters, one for one (positions stay the same)."""
    return "".join(_T2S.get(ch, ch) for ch in text)


def read(line: str, rows=(), things: Optional[Dict[str, str]] = None) -> Optional[Dict[str, object]]:
    """The reading of one line, in its own characters: {"words": [(word, tag)], "who", "to", "do", "things":
    [{"word", "count", "like", "picture"}], "where", "how", "when", "tone", "face"}. things: simplified word ->
    picture name (what the cards would draw for it). None without jieba."""
    jb = _load(rows)
    if jb is None:
        return None
    import jieba.posseg as pseg
    s = simple(line)
    toks: List[Tuple[str, str, str]] = []           # (simplified, tag, own characters)
    at = 0
    for p in pseg.cut(s):
        w, f = p.word, p.flag
        toks.append((w, f, line[at:at + len(w)]))
        at += len(w)
    out: Dict[str, object] = {"words": [(o, f) for _w, f, o in toks if f != "x"], "who": "", "to": "", "do": [], "things": [],
                              "where": [], "how": [], "when": [], "tone": [], "face": ""}
    verbs_at = [i for i, (w, f, _o) in enumerate(toks) if f.startswith("v") and w not in MODAL and w not in COPULA]
    act_at = [i for i in verbs_at if toks[i][0] not in ("没有", "没", "无")]     # 沒有地球: nothing is done there
    first_v = verbs_at[0] if verbs_at else len(toks)
    # who: per clause, the pronoun or noun just before its first verb; a clause with a verb and no one named
    # is "我" (lyrics leave it out). to: the first pronoun after a verb.
    who: List[str] = []
    clause: List[int] = []
    for i in range(len(toks) + 1):
        if i < len(toks) and toks[i][1] != "x":
            clause.append(i)
            continue
        vs = [j for j in clause if j in act_at]
        if not vs and any(j in verbs_at for j in clause):
            clause = []
            continue
        if not vs:              # no verb found: whoever the clause names first (你張開了雙翼, 她會有多幸運)
            first = PRONOUNS.get(toks[clause[0]][0], "") if clause else ""
            if first:
                who.append(first)
        if vs:
            subj = ""
            for j in reversed([j for j in clause if j < vs[0]]):
                w, f, o = toks[j]
                if w in ("把", "将", "被", "让", "为"):
                    break       # what follows 把 is what is handled, not who does it
                if w in PRONOUNS:
                    subj = PRONOUNS[w]; break
                if (f in ("n", "nz", "ns") and w not in ASK and w not in FUNC_ADV and len(w) <= 2
                        and w not in ("来不及", "习惯", "等待", "笑着", "从前", "以后", "时候")):
                    subj = o; break
            if subj and any(toks[j][0] in ("把", "将") for j in clause if j < vs[0]) and subj not in PRONOUNS.values():
                subj = ""
            who.append(subj or "我")
            for j in clause:
                if j > vs[0] and toks[j][0] in PRONOUNS and not out["to"]:
                    out["to"] = PRONOUNS[toks[j][0]]
        clause = []
    out["who"] = "、".join(dict.fromkeys(who))
    # what is done (with a no in front of it)
    for i in verbs_at:
        w, f, o = toks[i]
        neg = i > 0 and toks[i - 1][0] in NEG
        out["do"].append(("不" if neg else "") + o)
    # things: nouns, with the number and the words that say what they are like in front of them
    for i, (w, f, o) in enumerate(toks):
        if not (f.startswith("n") and f not in ("nr", "nrt", "nrfg")) or w in PRONOUNS or w in ASK or w in ("告诉",):
            continue
        count, like = "", []
        j = i - 1
        while j >= 0 and (toks[j][1] in ("uj", "a", "ad", "an", "b", "z", "m", "q", "mq") or toks[j][0] == "的"):
            if toks[j][1] in ("m", "q", "mq"):
                count = toks[j][2] + count
            elif toks[j][1] in ("a", "ad", "an", "b", "z"):
                like.insert(0, toks[j][2])
            j -= 1
        out["things"].append({"word": o, "count": count, "n": how_many(simple(count)), "like": "".join(like),
                              "picture": (things or {}).get(w, "")})
    # where: a preposition, what follows it, and 上/下/里/旁 after
    for i, (w, f, o) in enumerate(toks):
        if f == "p" and w in ("在", "往", "向", "朝", "从", "到", "对", "于", "沿着", "顺着", "跟", "和", "与", "陪"):
            phrase, j = o, i + 1
            while j < len(toks) and toks[j][1] not in ("v", "p", "x", "d") and len(phrase) < 10:
                phrase += toks[j][2]
                if toks[j][1] == "f":
                    break
                j += 1
            if phrase != o:
                out["where"].append(phrase)
        elif f == "f" and i > 0 and toks[i - 1][1].startswith("n") and not any(toks[i - 1][2] in p for p in out["where"]):
            out["where"].append(toks[i - 1][2] + o)
    # how and when
    for i, (w, f, o) in enumerate(toks):
        if f in ("d", "z", "ad") and w not in FUNC_ADV and w not in NEG and w not in IF and len(w) >= 2:
            out["how"].append(o)
        if f == "t" or w in ("昨天", "今天", "明天", "从前", "以后", "未来", "现在", "夜里", "夜晚", "清晨", "黄昏", "那年", "那天", "永远"):
            out["when"].append(o)
    # the tone of it
    tone = []
    if any(w in NEG for w, f, _o in toks):
        tone.append("否定")
    if any(w in IF for w, f, _o in toks):
        tone.append("假設／也許")
    if any(w in ASK for w, f, _o in toks) or (toks and toks[-1][0] in ASK_END) or any(x in s for x in ASK):
        tone.append("疑問")
    out["tone"] = tone
    words = {w for w, _f, _o in toks}
    def felt(w: str) -> bool:   # said, as a word of its own when it is one character (气 is not in 勇气), and not after a no
        if len(w) < 2 and w not in words:
            return False
        j = s.find(w)
        before = s[max(0, j - 5):j].split(" ")[-1]
        for ok in ("忍不住", "不禁", "不由得", "不停", "不断", "止不住"):
            before = before.replace(ok, "")
        return j >= 0 and not any(x in before for x in ("不", "没", "别", "无"))
    for face, ws in FACES:
        if any(felt(w) for w in ws):
            out["face"] = face
            break
    out["where"] = list(dict.fromkeys(out["where"]))
    return out
