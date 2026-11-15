"""A lyric line taken apart for the picture cards (draft, 2026-11-15): who, does what, to what (how many, what
like), where, how, when, in what tone, with what face.

The words are cut and tagged by jieba (MIT; offline), which knows every word the cards know as one word (so
路燈 is not 燈). The line is turned into simplified characters one by one for jieba, so the parts can be shown
in the line's own characters. cardstory takes the face, the number of a thing and who a card shows from it.
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
    ("心動", ("心动", "喜欢", "爱上", "动心", "暗恋", "怦然")), ("驚訝", ("惊讶", "竟然", "突然", "忽然", "居然", "惊喜", "意外", "没想到")),
    ("擔心", ("担心", "害怕", "怕", "不安", "紧张", "恐惧", "慌")), ("委屈", ("委屈", "心酸", "难过", "受伤", "伤心", "心碎", "痛")),
    ("思念", ("想你", "想念", "思念", "怀念", "回忆", "记得", "从前")), ("寂寞", ("寂寞", "孤单", "孤独", "一个人", "独自", "空荡")),
    ("想睡", ("睡", "困", "梦", "晚安", "眼皮")), ("堅定", ("勇敢", "坚强", "相信", "决定", "一定", "不怕", "坚持", "勇气")),
    ("微笑", ("笑", "微笑", "快乐", "幸福", "开心", "甜", "温暖", "美好", "幸运")), ("平靜", ("安静", "平静", "轻轻", "静静", "慢慢", "默默", "悄悄", "缓缓", "释怀")),
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


# what is a noun here -----------------------------------------------------------------------------------------
# jieba gives a word one tag wherever it stands (愿望 v, 解药 v, 幸运 a, 钟声 nr); where it stands says more.
COUNTERS = "个种颗张朵片首封杯壶条只座场段份句滴道束盏件本双对群阵丝缕抹粒枚页幕位名棵株辆艘架扇面块根支枝瓶碗盘盒包袋串圈层声口把"
TAKES_A_VERB = MODAL + ("开始", "继续", "停止", "学会", "学着", "喜欢", "害怕", "决定", "忘了", "忘记", "记得", "试着", "试过", "懂得",
                        "舍不得", "来不及", "忍不住", "习惯", "假装", "打算", "准备", "希望", "不敢", "不愿", "不肯", "不想", "不要",
                        "不会", "不能", "不用", "不必", "是", "有", "没有", "像", "去", "来", "让", "叫", "使")
ONE_CHAR_VERBS = {"飞": "v", "问": "v", "淋": "v", "流": "v", "记": "v", "藏": "v", "等": "v"}      # jieba: n, n, n, n, n, j, u
_NOT_A_NOUN = ("告诉", "没有", "不要", "不能", "不会", "不用", "不想", "不必", "不见", "不到", "不了")
_CAN_BE = ("v", "vn", "a", "an", "i", "l", "vg", "ag", "d", "m", "z", "b")


def _counter(tok: Tuple[str, str, str]) -> bool:
    w, f, _o = tok
    return f in ("m", "q", "mq") and w[-1] in COUNTERS and w not in ("一把", "一口", "一面", "一道", "一声") or (f == "q" and w in COUNTERS)


def _nouns(toks: Sequence[Tuple[str, str, str]], known) -> Tuple[List[int], List[int]]:
    """Where the nouns are: the words tagged so (a name too, when it is a word jieba knows), and a word of
    another tag standing where a noun stands: after 的 (我的願望, 妳的笑), after a number and its counter (一種解藥),
    before 是 or after a verb when it is one of the cards' things (回憶都是我; 遇見愛), and 生命 / 微笑 (vn)
    unless something is being done (忙著微笑). Second: the words jieba takes for a name that are done here (張開了)."""
    n = len(toks)
    at: List[int] = []
    done: List[int] = []
    for i, (w, f, _o) in enumerate(toks):
        if f == "x" or w in PRONOUNS or w in ASK or w in _NOT_A_NOUN:
            continue
        prv = toks[i - 1] if i > 0 else ("", "x", "")
        nxt = toks[i + 1] if i + 1 < n else ("", "x", "")
        if any(ch in w for ch in "你我他她") and len(w) > 1:
            continue            # 我会, 想你: not a thing
        if f in ("nr", "nrt", "nrfg"):      # a "name": jieba's guess for 張開, 呼喚, 消失 as much as for 鐘聲, 蒲公英
            if len(w) < 2 or not known(w):
                continue
            if w in _THINGS or prv[0] == "的" or _counter(prv) or nxt[1] == "f":
                at.append(i)
            elif (nxt[0] in ("了", "着", "过") or nxt[0] in PRONOUNS or prv[1] in ("d", "ad") or prv[0] in MODAL or prv[0] in NEG
                  or (nxt[1].startswith("n") and (prv[1] == "x" or prv[0] in PRONOUNS))):
                done.append(i)      # 張開了, 張開雙翼, 呼喚我
            elif prv[0] in ("着", "了") or prv[1] == "v":
                at.append(i)        # 拍著沙灘; 這麼安靜 and 青青草地 are neither
            continue
        if f.startswith("n") or f == "s":
            at.append(i)
            continue
        if f not in _CAN_BE or w in FUNC_ADV or w in NEG or w in IF or w in MODAL or w in COPULA or prv[0] in NEG:
            continue
        modifies = nxt[1].startswith("n") or nxt[0] == "的"        # 美麗的…, 幸運 兒: it says what the next one is like
        how = i > 1 and (toks[i - 2][1] in ("d", "ad", "z") or (toks[i - 2][1] in ("i", "l") and f.startswith("v")))
        if prv[0] == "的" and not modifies and f != "m" and not how:
            at.append(i)        # 我的願望; not 慢慢的走, 理所當然的忘記
        elif _counter(prv) and not modifies and f not in ("m", "d"):
            at.append(i)        # 一種解藥
        elif prv[0] in ("把", "将") and f in ("v", "vn", "a") and nxt[1].startswith("v") and w not in MODAL:
            at.append(i)        # 把回憶鎖進抽屜
        elif f == "vn" and nxt[0] != "的" and prv[0] not in ("着", "了", "在", "正", "正在") and prv[0] not in MODAL \
                and prv[1] not in ("d", "ad") and nxt[0] not in ("着", "了", "过"):
            at.append(i)        # 生命, 生活細節; not 忙著微笑
        elif w in _THINGS and f in ("v", "a", "i", "l"):
            j = i + 1
            while j < n and (toks[j][1] in ("d", "c", "zg") or toks[j][0] in FUNC_ADV):
                j += 1
            ends = nxt[1] in ("x", "f", "t", "c", "p", "y", "ul")
            if j < n and j > i and toks[j][0] == "是" and prv[1] in ("x", "d", "c", "v", "zg"):
                at.append(i)    # 回憶都是我, 發現愛是…
            elif prv[1] == "v" and prv[0] not in TAKES_A_VERB and ends:
                at.append(i)    # 遇見愛 以後, 許下願望; not 想要等待
    return at, done


# who does it ------------------------------------------------------------------------------------------------
NOT_DOER_AFTER = ("与", "和", "跟", "同", "把", "将", "被", "为", "对", "给", "替", "向", "往", "朝", "比", "像", "在", "从")
JOIN = ("与", "和", "跟", "同")
HANDLED = ("把", "将", "被")
STARTS_DOING = ("往", "向", "朝", "给", "把", "被", "在", "从", "跟", "陪", "对", "为", "替", "和", "与")   # 你往未來飛, 你給我勇氣
CARRY_ON = ("就", "才", "也", "又", "还", "却", "便", "再", "更", "仍", "依然", "仍然", "还是", "也是", "就是", "于是", "然后")
NOT_WHO = ("来不及", "习惯", "等待", "笑着", "从前", "以后", "时候")
RESULT = ("不见", "不到", "不了", "不着", "不起", "不住", "不完", "不动", "不下", "不上", "不出", "不开", "不清", "得见", "得到",
          "得了", "得起", "得着")      # 看妳不見: how the seeing ends, not what 妳 does
_LIGHT = ("d", "c", "zg", "t")          # words a doer can stand behind: 你[也許][明天]來


def _who(toks: Sequence[Tuple[str, str, str]], verbs_at: Sequence[int], act_at: Sequence[int],
         noun_at: Sequence[int] = ()) -> Tuple[str, str]:
    """Who does it, and to whom. Per clause (a space ends one): the pronoun or noun before the first action verb;
    a clause with a verb and no one named is "我" (lyrics leave it out). Not a doer: whose (我的), where (雨裏),
    with or for whom (與你, 為你), what is handled (把距離). More doers: 你和我, a second one inside the clause
    (我走回從前 你往未來飛; 聽 我說), the one before 是 (你是我最想留住的幸運). A clause that names no one goes
    on with the last one when it opens with 就/才/也/又, and a clause that is only a thing and an adverb (雨漸漸)
    hands its thing to the next one."""
    n = len(toks)

    def light(j: int) -> bool:
        w, f, _o = toks[j]
        return f in _LIGHT or w in FUNC_ADV or w in IF or w in NEG

    def named(j: int) -> str:
        w, f, o = toks[j]
        nxt = toks[j + 1] if j + 1 < n else ("", "x", "")
        prv = toks[j - 1] if j > 0 else ("", "x", "")
        if nxt[0] in ("的", "之") or prv[0] in NOT_DOER_AFTER:
            return ""
        if prv[0] == "有" and j > 1 and toks[j - 2][0] in ("哪里", "哪儿", "何处"):
            return ""           # 哪裡有彩虹: what is asked for
        if w in PRONOUNS:
            return PRONOUNS[w]
        if nxt[1] == "f":
            return ""           # 風裏, 路燈下: a place
        if ((f in ("n", "nz", "ns") or (j in noun_at and f not in ("s", "m"))) and w not in ASK and w not in FUNC_ADV
                and (len(w) <= 2 or (len(w) == 3 and w in _THINGS)) and w not in NOT_WHO
                and not any(ch in w for ch in "你我他她")):        # 想你 is a card's word, not someone
            return "人" if w == "个人" else o
        return ""

    def joined(j: int) -> List[str]:    # 你和我: both
        if j + 2 < n and toks[j][0] in PRONOUNS and toks[j + 1][0] in JOIN and toks[j + 2][0] in PRONOUNS:
            return [PRONOUNS[toks[j + 2][0]]]
        return []

    who: List[str] = []
    to = ""
    last = ""       # the last clause's doer
    carry = ""      # 雨漸漸: a thing waiting for what it does
    clause: List[int] = []
    for i in range(n + 1):
        if i < n and toks[i][1] != "x":
            clause.append(i)
            continue
        if not clause:
            continue
        vs = [j for j in clause if j in act_at]
        opens = next((j for j in clause if toks[j][1] != "c"), clause[0])
        goes_on = toks[opens][0] in CARRY_ON
        found: List[str] = []
        seconds: List[int] = []
        done = False
        # the one before 是, when 是 comes before anything is done
        be = next((j for j in clause if toks[j][0] == "是" and (not vs or j < vs[0])), -1)
        if be >= 0:
            j = be - 1
            while j >= clause[0] and light(j):
                j -= 1
            topic = named(j) if j >= clause[0] else ""
            told = any(toks[k][0] == "的" and toks[k - 1][1].startswith("v") for k in clause if k > be + 1)    # 是 我…留住的 幸運
            if topic:
                found = [topic] + joined(j)
                done = told or not vs
            elif told and goes_on and last:
                found, done = [last], True
            elif not vs and be + 1 <= clause[-1] and toks[be + 1][0] in PRONOUNS and named(be + 1):
                found, done = [named(be + 1)], True         # 一幕幕都是你: the one the line shows
        if not done and not vs:
            if any(j in verbs_at for j in clause):          # 沒有地球: nothing is done there
                clause = []
                continue
            if any(toks[j][0] in ("让", "叫", "使") and toks[j][1] == "v" for j in clause):
                found = found or ["我"]                      # 讓…的刺痛隨風而去: 我 lets it
            for j in clause:        # no verb found: the one it opens with (你張開了雙翼, 她會有多幸運), or 雨 in 雨漸漸
                if light(j):
                    continue
                name = named(j)
                if not name:
                    break
                rest = [k for k in clause if k > j]
                if toks[j][0] in PRONOUNS:
                    found = found or [name] + joined(j)
                elif rest and all(toks[k][1] in ("d", "zg", "a", "ad", "z") or toks[k][0] in FUNC_ADV for k in rest):
                    found = found or [name]
                    if all(toks[k][1] in ("d", "zg", "ad") for k in rest):      # only an adverb after it: it waits
                        who.extend(found)
                        last, carry, clause = found[0], name, []
                break
            if not clause:
                continue
        elif not done:
            handled = max([j for j in clause if j < vs[0] and toks[j][0] in HANDLED], default=-1)
            stop = handled if handled >= 0 else vs[0]
            for j in reversed([j for j in clause if j < stop]):
                name = named(j)
                if name:
                    found = found or [name] + joined(j)
                    if toks[j][0] not in PRONOUNS and j > clause[0] and toks[j - 1][0] in JOIN:
                        continue        # 我們和愛情: the one before 和 is who
                    if toks[j][0] not in PRONOUNS and any(named(k) and toks[k][0] in PRONOUNS for k in clause if k < j):
                        found = []      # a pronoun further back is who (我們 和 愛情 靠得…)
                        continue
                    break
            if not found:
                found = [carry or (last if goes_on and last else "") or "我"]
            if be == opens and be + 1 < vs[0] and toks[be + 1][0] in PRONOUNS and named(be + 1):
                found = [named(be + 1)] + [x for x in found if x != named(be + 1)]     # 是你讓我看見彩虹: 你, then 我
            # a second doer inside the clause: a pronoun after the first verb, with something it does after it
            for j in clause:
                if j <= vs[0] or toks[j][0] not in PRONOUNS or not named(j):
                    continue
                k = j + 1
                while k <= clause[-1] and (light(k) or toks[k][0] in ASK):
                    k += 1
                if k > clause[-1]:
                    continue
                w, f, _o = toks[k]
                before = toks[j - 1][0]
                after = [toks[m][0] for m in clause if m > k][:2]
                if "的" in after and (after[0] == "的" or after[0] in PRONOUNS or len(after[0]) <= 2):
                    continue        # 你眺望我的夜裡: it says which night
                does = f.startswith("v") and f != "vn" and w != before and w != "是" and w not in RESULT   # 想你想到…: not 你
                if does or (w in STARTS_DOING and k < clause[-1]):
                    found.append(named(j))
                    seconds.append(j)
        if found:
            who.extend(found)
            last = found[0]
        carry = ""
        if vs:
            for j in clause:
                if j > vs[0] and toks[j][0] in PRONOUNS and j not in seconds and not to:
                    to = PRONOUNS[toks[j][0]]
        for j in clause:        # 與你相遇, 跟你說: with whom
            if not to and toks[j][0] in PRONOUNS and j > 0 and toks[j - 1][0] in JOIN and PRONOUNS[toks[j][0]] not in found:
                to = PRONOUNS[toks[j][0]]
        clause = []
    return "、".join(dict.fromkeys(who)), to


_JIEBA = None
_THINGS: set = set()        # the words the cards have a thing for (simplified)
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
            if w and not w.isascii() and what.get("prop") and what["prop"] not in ("none", "dots", "ask", "call", "tears", "notes"):
                _THINGS.add(simple(w))
            if w and not w.isascii() and len(w) >= 2 and w not in PRONOUNS:
                s_w = simple(w)
                if known.get(s_w, 0) > 0:
                    jieba.add_word(s_w, freq=max(50000, known[s_w]))     # a word jieba knows keeps its own tag (喜欢 is a verb)
                else:       # a word of the cards' own: a thing, unless it is made like something done (不要了, 等了, 爬上, 敬你)
                    done = (s_w[0] in "不没别无" or s_w[-1] in "了着过上好到住" or any(ch in s_w for ch in "你我他她")) and tag == "n"
                    jieba.add_word(s_w, freq=50000, tag="v" if done else tag)
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
        toks.append((w, ONE_CHAR_VERBS.get(w, f), line[at:at + len(w)]))
        at += len(w)
    out: Dict[str, object] = {"words": [(o, f) for _w, f, o in toks if f != "x"], "who": "", "to": "", "do": [], "things": [],
                              "where": [], "how": [], "when": [], "tone": [], "face": ""}
    known = lambda w: jb.dt.FREQ.get(w, 0) > 0  # noqa: E731
    noun_at, done_at = _nouns(toks, known)
    verbs_at = [i for i, (w, f, _o) in enumerate(toks)
                if (f.startswith("v") or i in done_at) and w not in MODAL and w not in COPULA and i not in noun_at]
    act_at = [i for i in verbs_at if toks[i][0] not in ("没有", "没", "无")]     # 沒有地球: nothing is done there
    first_v = verbs_at[0] if verbs_at else len(toks)
    out["who"], out["to"] = _who(toks, verbs_at, act_at, noun_at)
    # what is done (with a no in front of it)
    for i in verbs_at:
        w, f, o = toks[i]
        neg = i > 0 and toks[i - 1][0] in NEG
        out["do"].append(("不" if neg else "") + o)
    # things: nouns, with the number and the words that say what they are like in front of them
    for i in noun_at:
        w, f, o = toks[i]
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
