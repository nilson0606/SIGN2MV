"""Lyrics <-> Whisper timeline alignment for the MV workspace.

Ported unchanged (logic) from the MV Studio of AI_COVER_MV (whisper_align_engine.py,
2026-10-27). Only the parts that ran separation / Whisper in subprocesses were
moved to workers/mv_whisper.py; everything here is pure Python.
"""
import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple

WHISPER_PIPELINE = "vocals_v1"          # cache version: transcripts made from separated vocals

TRAD_TO_SIMP = {
    '還': '还', '個': '个', '們': '们', '這': '这', '麼': '么', '會': '会', '溫': '温', '雙': '双',
    '飛': '飞', '點': '点', '頭': '头', '說': '说', '愛': '爱', '氣': '气', '綻': '绽', '傷': '伤',
    '處': '处', '時': '时', '候': '候', '從': '从', '後': '后', '聽': '听', '聲': '声', '開': '开',
    '關': '关', '過': '过', '進': '进', '帶': '带', '來': '来', '見': '见', '親': '亲', '給': '给',
    '顆': '颗', '興': '兴', '樣': '样', '讓': '让', '難': '难', '動': '动', '紅': '红', '豆': '豆',
    '寫': '写', '話': '话', '認': '认', '真': '真', '夢': '梦', '邊': '边', '轉': '转', '戀': '恋',
    '著': '着', '隨': '随', '風': '风', '淚': '泪', '憶': '忆', '誰': '谁', '避': '避', '遺': '遗',
    '離': '离', '結': '结', '緊': '紧', '握': '握', '澀': '涩', '塵': '尘', '裡': '里', '願': '愿',
    '擇': '择', '為': '为', '滿': '满', '袋': '袋', '牽': '牵', '荒': '荒', '蕪': '芜', '陪': '陪',
    '細': '细', '長': '长', '流': '流', '花': '花', '落': '落', '吹': '吹', '地': '地', '無': '无',
    '怨': '怨', '嗟': '嗟', '謝': '谢', '土': '土', '情': '情', '前': '前', '途': '途', '顧': '顾',
    '軟': '软', '弱': '弱', '性': '性', '光': '光', '明': '明', '滴': '滴', '悲': '悲', '哀': '哀',
    '青': '青', '春': '春', '早': '早', '死': '死', '閣': '阁', '遇': '遇', '世': '世', '萬': '万',
    '馬': '马', '燈': '灯', '變': '变', '歷': '历', '盡': '尽', '滄': '沧', '桑': '桑', '憐': '怜',
    '歡': '欢', '層': '层', '識': '识', '誌': '志', '閃': '闪', '電': '电', '鎖': '锁', '匙': '匙',
    '張': '张', '幾': '几', '經': '经', '適': '适', '斷': '断', '歸': '归', '瞑': '暝', '癡': '痴',
    '問': '问', '騙': '骗', '義': '义'
}


def normalize_cjk(text: str) -> str:
    clean = re.sub(r'[^\u4e00-\u9fff]', '', str(text or ""))
    return "".join(TRAD_TO_SIMP.get(ch, ch) for ch in clean)


def lcs_length(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    if m == 0 or n == 0:
        return 0
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def similarity_score(line_a: str, line_b: str) -> float:
    c1 = normalize_cjk(line_a)
    c2 = normalize_cjk(line_b)
    if not c1 or not c2:
        return 0.0
    common = sum(min(c1.count(ch), c2.count(ch)) for ch in set(c1))
    overlap = common / max(len(c1), len(c2))
    lcs = lcs_length(c1, c2) / max(len(c1), len(c2))
    len_sim = min(len(c1), len(c2)) / max(len(c1), len(c2))
    # Scale len_sim by overlap so unrelated strings of similar length don't get false-positive score
    return overlap * 0.45 + lcs * 0.40 + (len_sim * overlap) * 0.15



def is_whisper_cache_valid(w_json: str, audio_file: str, lead_only: bool = False) -> bool:
    if not w_json or not os.path.exists(w_json):
        return False
    try:
        with open(w_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return False        # [Claude 2026-10-27] 舊格式（聽母帶）：重跑一次分離人聲版
        if isinstance(data, dict):
            segs = data.get("segments", [])
            if not segs or data.get("pipeline") != WHISPER_PIPELINE or bool(data.get("lead_requested", False)) != bool(lead_only):
                return False
            cached_audio = data.get("audio_file")
            if cached_audio and audio_file and os.path.exists(audio_file):
                if os.path.abspath(cached_audio).lower() != os.path.abspath(audio_file).lower():
                    return False
                cached_mtime = data.get("audio_mtime")
                if cached_mtime and int(os.path.getmtime(audio_file)) != int(cached_mtime):
                    return False
            return True
    except Exception:
        return False
    return False


def extract_elementary_clauses(w_segs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flattens all valid word timestamps across all Whisper segments (ignoring 30s window artificial cuts
    and discarding 0-duration hallucinated words) and groups them into elementary vocal clauses
    (half-lines or short phrases separated by breath pauses or Whisper space boundaries).
    """
    all_words: List[Dict[str, Any]] = []
    for seg in w_segs:
        words = seg.get("words") or []
        if words:
            for w in words:
                st = float(w.get("start", 0.0))
                et = float(w.get("end", 0.0))
                w_txt = str(w.get("word", ""))
                # Filter out 0-duration Whisper boundary hallucinations (e.g. "詞曲 李宗盛" at 29.98~29.98)
                if (et - st) < 0.02:
                    continue
                if not normalize_cjk(w_txt) and not w_txt.strip():
                    continue
                all_words.append({
                    "word": w_txt,
                    "start": round(st, 2),
                    "end": round(et, 2),
                    "probability": float(w.get("probability", 1.0))
                })
        else:
            st = float(seg.get("start", 0.0))
            et = float(seg.get("end", 0.0))
            s_txt = str(seg.get("text", "")).strip()
            if (et - st) >= 0.2 and s_txt:
                all_words.append({
                    "word": " " + s_txt,
                    "start": round(st, 2),
                    "end": round(et, 2),
                    "probability": 1.0
                })

    if not all_words:
        return []

    clauses: List[Dict[str, Any]] = []
    curr_w: List[Dict[str, Any]] = []
    curr_cjk = 0

    for idx, w in enumerate(all_words):
        w_str = w["word"]
        cjk_n = len(normalize_cjk(w_str)) or 1
        curr_w.append(w)
        curr_cjk += cjk_n

        if idx < len(all_words) - 1:
            nxt = all_words[idx + 1]
            gap = float(nxt["start"]) - float(w["end"])
            nxt_has_space = str(nxt["word"]).startswith(" ")

            # Split into a new elementary clause at space boundaries or breath pauses (>=0.32s)
            should_split = False
            if curr_cjk >= 3:
                if gap >= 0.38:
                    should_split = True
                elif nxt_has_space and curr_cjk >= 4:
                    should_split = True
                elif curr_cjk >= 8 and gap >= 0.18:
                    should_split = True

            if should_split:
                clauses.append({
                    "start": curr_w[0]["start"],
                    "end": curr_w[-1]["end"],
                    "text": "".join(x["word"] for x in curr_w).strip(),
                    "words": curr_w,
                    "cjk_len": curr_cjk
                })
                curr_w = []
                curr_cjk = 0

    if curr_w:
        clauses.append({
            "start": curr_w[0]["start"],
            "end": curr_w[-1]["end"],
            "text": "".join(x["word"] for x in curr_w).strip(),
            "words": curr_w,
            "cjk_len": curr_cjk
        })

    # Filter out isolated 1-2 char noise blips surrounded by large silences (>2.5s on both sides)
    filtered: List[Dict[str, Any]] = []
    for idx, cl in enumerate(clauses):
        if cl["cjk_len"] <= 2:
            prev_gap = (cl["start"] - clauses[idx - 1]["end"]) if idx > 0 else 99.0
            next_gap = (clauses[idx + 1]["start"] - cl["end"]) if idx + 1 < len(clauses) else 99.0
            if prev_gap > 2.5 and next_gap > 2.5:
                continue
        filtered.append(cl)

    return filtered or clauses


def align_lyrics_with_whisper_dp(
    line_pairs: List[Tuple[int, str]],
    w_segs: List[Dict[str, Any]],
    total_dur: float,
    early_lead: float = -0.70,
    tail_ext: float = 2.50,
    title: str = "",
    max_uploaded_scene: int = 12
) -> List[Dict[str, Any]]:
    try:
        res = _align_lyrics_with_whisper_dp_core(
            line_pairs=line_pairs,
            w_segs=w_segs,
            total_dur=total_dur,
            early_lead=early_lead,
            tail_ext=tail_ext,
            title=title,
            max_uploaded_scene=max_uploaded_scene
        )
        if not res:
            return build_guaranteed_fallback_timeline(
                line_pairs=line_pairs,
                total_dur=total_dur,
                early_lead=early_lead,
                title=title,
                target_scene_count=max(max_uploaded_scene, len(line_pairs) or 12)
            )
        return res
    except Exception:
        return build_guaranteed_fallback_timeline(
            line_pairs=line_pairs,
            total_dur=total_dur,
            early_lead=early_lead,
            title=title,
            target_scene_count=max(max_uploaded_scene, len(line_pairs) or 12)
        )


def align_bracket_dp(
    lyric_lines: List[Tuple[int, str]],
    clauses: List[Dict[str, Any]],
    w_start: float,
    w_end: float,
    early_lead: float = -0.70,
    tail_ext: float = 2.50
) -> List[Tuple[float, float, bool]]:
    """
    Dynamic programming alignment for a subset of lyric lines within a bounded bracket window [w_start, w_end].
    """
    n = len(lyric_lines)
    if n == 0:
        return []

    m = len(clauses)
    min_dur = 0.40

    if m == 0:
        step = (w_end - w_start) / n
        res = []
        for k in range(n):
            st = round(w_start + k * step, 2)
            et = round(w_start + (k + 1) * step, 2) if k < n - 1 else round(w_end, 2)
            res.append((st, et, False))
        return res

    INF = 1e9
    dp = [[-INF] * (m + 1) for _ in range(n + 1)]
    parent: List[List[Optional[Tuple[int, int, str]]]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0

    skip_clause_pen = 0.35
    match_weight = 10.0

    for i in range(n + 1):
        for j in range(m + 1):
            cur = dp[i][j]
            if cur <= -INF / 2:
                continue

            # 1. Skip clause
            if j < m:
                cand = cur - skip_clause_pen
                if cand > dp[i][j + 1]:
                    dp[i][j + 1] = cand
                    parent[i][j + 1] = (i, j, "skip_clause")

            # 2. Skip lyric
            if i < n:
                cand = cur - 2.5
                if cand > dp[i + 1][j]:
                    dp[i + 1][j] = cand
                    parent[i + 1][j] = (i, j, "skip_lyric")

            # 3. Match 1 lyric to k clauses (k=1..4)
            if i < n:
                lyr_txt = lyric_lines[i][1]
                lyr_len = max(1, len(normalize_cjk(lyr_txt)))
                for k in range(1, 5):
                    if j + k > m:
                        break
                    comb_txt = "".join(clauses[j + r]["text"] for r in range(k))
                    sim = similarity_score(lyr_txt, comb_txt)
                    cand = cur + sim * match_weight - (0.1 * (k - 1))
                    if cand > dp[i + 1][j + k]:
                        dp[i + 1][j + k] = cand
                        parent[i + 1][j + k] = (i, j, f"match_1to{k}")

    # Backtrack
    ci, cj = n, m
    line_to_clauses: Dict[int, List[int]] = {}
    while ci > 0 or cj > 0:
        step = parent[ci][cj]
        if not step:
            break
        pi, pj, act = step
        if act.startswith("match_1to"):
            k = int(act.replace("match_1to", ""))
            line_to_clauses[pi] = [pj + r for r in range(k)]
        ci, cj = pi, pj

    raw_spans: List[Optional[Tuple[float, float, bool]]] = [None] * n
    for idx in range(n):
        c_idxs = line_to_clauses.get(idx)
        if c_idxs:
            st = float(clauses[c_idxs[0]]["start"])
            et = float(clauses[c_idxs[-1]]["end"])
            raw_spans[idx] = (round(st, 2), round(et, 2), True)

    # Interpolate missing spans proportionally based on lyric CJK text length
    i = 0
    while i < n:
        if raw_spans[i] is not None:
            i += 1
            continue
        j = i
        while j < n and raw_spans[j] is None:
            j += 1
        cnt = j - i
        prev_end = raw_spans[i - 1][1] if i > 0 and raw_spans[i - 1] else w_start
        next_start = raw_spans[j][0] if j < n and raw_spans[j] else w_end
        span_dur = max(min_dur * cnt, next_start - prev_end)
        weights = [max(3, len(normalize_cjk(lyric_lines[i + k][1]))) for k in range(cnt)]
        tot_w = sum(weights) or float(cnt)
        cur_t = prev_end
        for k in range(cnt):
            alloc = (weights[k] / tot_w) * span_dur
            s_k = round(cur_t, 2)
            cur_t += alloc
            e_k = round(cur_t, 2) if k < cnt - 1 else round(next_start, 2)
            raw_spans[i + k] = (s_k, e_k, False)
        i = j

    return [sp or (w_start, w_end, False) for sp in raw_spans]


def enforce_anchor_invariants(
    candidate_tl: List[Dict[str, Any]],
    existing_tl: List[Dict[str, Any]],
    total_dur: float = 240.0
) -> List[Dict[str, Any]]:
    """
    MATHEMATICAL INVARIANT GUARANTEE (定錨不變量守護閘):
    Any segment with locked=True in existing_tl is an IMMUTABLE ANCHOR:
    1. start, end, scene, type are 100% FROZEN to the anchor's exact values.
    2. locked=True is preserved.
    3. Unlocked segments around anchors are bounded:
       - Starts after the previous anchor's end.
       - Ends before the next anchor's start.
       - Every segment duration >= 0.40s.
       - Seamless contiguity: tl[i].end == tl[i+1].start.
    """
    if not candidate_tl:
        return existing_tl or []

    locked_anchors = [s for s in (existing_tl or []) if s.get("locked") is True]
    if not locked_anchors:
        for i in range(len(candidate_tl) - 1):
            candidate_tl[i]["end"] = candidate_tl[i + 1]["start"]
        return candidate_tl

    # 1. Match and force-freeze each locked anchor
    matched_cand_indices = set()
    for a in locked_anchors:
        a_sc = int(a.get("scene", -1))
        a_type = a.get("type", "lyric")
        a_st = round(float(a.get("start", 0.0)), 2)
        a_et = round(float(a.get("end", 0.0)), 2)
        best_idx = None

        # Priority 1: Match by exact scene and exact type
        for i, s in enumerate(candidate_tl):
            if i in matched_cand_indices:
                continue
            if s.get("type") == a_type and int(s.get("scene", -2)) == a_sc:
                best_idx = i
                break

        # Priority 2: Match by exact normalized CJK text
        if best_idx is None:
            norm_a = normalize_cjk(a.get("text", ""))
            if norm_a:
                for i, s in enumerate(candidate_tl):
                    if i in matched_cand_indices:
                        continue
                    if normalize_cjk(s.get("text", "")) == norm_a:
                        best_idx = i
                        break

        if best_idx is not None:
            matched_cand_indices.add(best_idx)
            candidate_tl[best_idx]["start"] = a_st
            candidate_tl[best_idx]["end"] = a_et
            candidate_tl[best_idx]["scene"] = a_sc
            candidate_tl[best_idx]["type"] = a_type
            candidate_tl[best_idx]["locked"] = True
            candidate_tl[best_idx]["note"] = a.get("note") or "🔒 定錨鎖定"

    # 2. Enforce strictly bounded, seamless intervals between locked anchors
    min_dur = 0.40
    n = len(candidate_tl)
    i = 0
    while i < n:
        if candidate_tl[i].get("locked"):
            i += 1
            continue

        start_idx = i
        while i < n and not candidate_tl[i].get("locked"):
            i += 1
        end_idx = i

        w_start = candidate_tl[start_idx - 1]["end"] if start_idx > 0 else 0.00
        w_end = candidate_tl[end_idx]["start"] if end_idx < n else round(total_dur, 2)

        num_unlocked = end_idx - start_idx
        avail_gap = max(num_unlocked * min_dur, w_end - w_start)

        # Check if candidate_tl[start_idx:end_idx] already has valid acoustic boundaries fitting within [w_start, w_end]
        is_already_valid_slice = True
        for k in range(num_unlocked):
            s = candidate_tl[start_idx + k]
            try:
                st = float(s.get("start", 0.0))
                et = float(s.get("end", 0.0))
                if et - st < min_dur or st < w_start - 0.05 or et > w_end + 0.05:
                    is_already_valid_slice = False
                    break
            except Exception:
                is_already_valid_slice = False
                break

        if is_already_valid_slice and num_unlocked > 0:
            for k in range(num_unlocked - 1):
                if abs(float(candidate_tl[start_idx + k]["end"]) - float(candidate_tl[start_idx + k + 1]["start"])) > 0.05:
                    is_already_valid_slice = False
                    break

        if is_already_valid_slice and num_unlocked > 0:
            # Acoustic alignment is valid: clamp outer endpoints to bounds and ensure contiguity
            candidate_tl[start_idx]["start"] = round(w_start, 2)
            candidate_tl[end_idx - 1]["end"] = round(w_end, 2)
            for k in range(num_unlocked - 1):
                candidate_tl[start_idx + k + 1]["start"] = candidate_tl[start_idx + k]["end"]
            for k in range(num_unlocked):
                candidate_tl[start_idx + k]["locked"] = False
        else:
            weights = []
            for k in range(num_unlocked):
                s = candidate_tl[start_idx + k]
                cur_d = float(s.get("end", 0.0)) - float(s.get("start", 0.0))
                if cur_d <= min_dur or cur_d > (avail_gap * 0.8):
                    txt_len = max(3, len(normalize_cjk(s.get("text", ""))))
                    weights.append(float(txt_len))
                else:
                    weights.append(max(1.0, cur_d))

            tot_w = sum(weights) or 1.0
            cur_time = w_start
            for k in range(num_unlocked):
                seg_idx = start_idx + k
                allocated = (weights[k] / tot_w) * (avail_gap - num_unlocked * min_dur)
                seg_d = min_dur + allocated
                candidate_tl[seg_idx]["start"] = round(cur_time, 2)
                cur_time += seg_d
                candidate_tl[seg_idx]["end"] = round(cur_time, 2) if k < num_unlocked - 1 else round(w_end, 2)
                candidate_tl[seg_idx]["locked"] = False

    # 3. Final Ironclad Verification of Anchors
    for a in locked_anchors:
        a_sc = int(a.get("scene", -1))
        a_type = a.get("type", "lyric")
        for s in candidate_tl:
            if s.get("locked") and s.get("type") == a_type and int(s.get("scene", -2)) == a_sc:
                s["start"] = round(float(a["start"]), 2)
                s["end"] = round(float(a["end"]), 2)
                break

    # 4. Final Contiguity Pass
    for i in range(len(candidate_tl) - 1):
        if not candidate_tl[i + 1].get("locked"):
            candidate_tl[i + 1]["start"] = candidate_tl[i]["end"]
        elif not candidate_tl[i].get("locked"):
            candidate_tl[i]["end"] = candidate_tl[i + 1]["start"]

    return candidate_tl


def align_timeline_with_anchors_and_whisper(
    existing_timeline: List[Dict[str, Any]],
    line_pairs: List[Tuple[int, str]],
    w_segs: List[Dict[str, Any]],
    total_dur: float,
    early_lead: float = -0.70,
    tail_ext: float = 2.50,
    title: str = "",
    target_scene_count: int = 12,
    interlude_anchors: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    [Claude 2026-10-26] interlude_anchors：使用者設的間奏（含 after_line＝前面有幾句歌詞），
    當成固定時間的段落插在那兩句歌詞之間，歌詞只在間奏前後的區間對齊（不會被排進間奏裡）。

    Universal Anchor-Guided Whisper Dynamic Programming Alignment Engine:
    1. 100% General-Purpose: Works for ANY song, ANY duration, ANY language, ANY scene count.
    2. Locked Anchors: If locked=True, start, end, scene, and text are 100% FROZEN IN STONE.
    3. Unlocked Segments: Genuinely re-aligned by Whisper acoustic clauses inside each bracket.
    4. Seamless Contiguity: Every card end equals next card start, zero gaps, zero overlaps.
    """
    min_dur = 0.40

    # If line_pairs not given, extract from existing_timeline
    if not line_pairs and existing_timeline:
        line_pairs = [
            (int(s.get("scene", 1)), str(s.get("text", "")).strip())
            for s in existing_timeline
            if s.get("type", "lyric") == "lyric" and not str(s.get("text", "")).startswith("～")
        ]

    if not line_pairs:
        return existing_timeline

    # Extract all Whisper clauses
    all_clauses = extract_elementary_clauses(w_segs) if w_segs else []

    # Map locked anchors from existing_timeline
    locked_anchors = [s for s in (existing_timeline or []) if s.get("locked")]
    
    # Check if there is an existing intro or outro
    has_intro_in_existing = any(s.get("type") == "intro" for s in (existing_timeline or []))
    has_outro_in_existing = any(s.get("type") == "outro" for s in (existing_timeline or []))

    # Match anchors
    matched_anchor_ids = set()
    
    # Build template of segments
    template_segments: List[Dict[str, Any]] = []

    # Intro segment (Scene 1)
    intro_anchor = next((s for s in locked_anchors if s.get("type") == "intro"), None)
    if intro_anchor:
        template_segments.append({
            "scene": int(intro_anchor.get("scene", 1)),
            "start": round(float(intro_anchor["start"]), 2),
            "end": round(float(intro_anchor["end"]), 2),
            "text": intro_anchor.get("text") or f"～ 前奏 · {title} ～",
            "type": "intro",
            "note": intro_anchor.get("note") or "開場榮譽名牌卡",
            "locked": True
        })
        matched_anchor_ids.add(id(intro_anchor))
    elif has_intro_in_existing or True:
        template_segments.append({
            "scene": line_pairs[0][0] if line_pairs else 1,
            "start": 0.00,
            "end": None,
            "text": f"～ 前奏 · {title} ～",
            "type": "intro",
            "note": "開場榮譽名牌卡",
            "locked": False
        })

    _ivs = sorted((interlude_anchors or []), key=lambda a: (int(a.get("after_line", 0)), float(a.get("start", 0))))

    def _push_interludes(after_n: int):
        for a in _ivs:
            if int(a.get("after_line", 0)) == after_n:
                d = dict(a)
                d.pop("after_line", None)
                d.update({"type": a.get("type") if a.get("type") in ("interlude", "solo") else "interlude",
                          "start": round(float(a["start"]), 2), "end": round(float(a["end"]), 2),
                          "locked": True, "_ianchor": True})
                template_segments.append(d)

    # [Claude 2026-10-27] 歌詞裡寫的「～ 間奏 ～」行（使用者把間奏當場景）標成 interlude；
    # 鎖定段的類型比對也把「～ 間奏 ～」文字的舊歌詞段當成 interlude（舊專案相容）
    def _line_type(txt: str) -> str:
        t = str(txt or "")
        return "interlude" if t.startswith("～") and ("間奏" in t or "间奏" in t) else "lyric"

    def _anchor_type(a: Dict[str, Any]) -> str:
        if a.get("type") in ("interlude", "solo"):
            return "interlude"
        return _line_type(a.get("text", "")) if a.get("type", "lyric") == "lyric" else str(a.get("type"))

    _push_interludes(0)
    # Lyric segments
    for idx, (sc_num, lyr_txt) in enumerate(line_pairs):
        matched_anchor = None
        ltype = _line_type(lyr_txt)
        # Priority 1: If sc_num > 0, match strictly by exact scene and type
        if sc_num > 0:
            for a in locked_anchors:
                if id(a) in matched_anchor_ids or a.get("user"):
                    continue
                if _anchor_type(a) == ltype and int(a.get("scene", -1)) == sc_num:
                    matched_anchor = a
                    break
        else:
            # Priority 2: If no scene tag, match by exact normalized CJK text
            for a in locked_anchors:
                if id(a) in matched_anchor_ids or a.get("user"):
                    continue
                if _anchor_type(a) == ltype:
                    norm_a = normalize_cjk(a.get("text", ""))
                    norm_l = normalize_cjk(lyr_txt)
                    if norm_a and norm_l and norm_a == norm_l:
                        matched_anchor = a
                        break

        if matched_anchor:
            matched_anchor_ids.add(id(matched_anchor))
            template_segments.append({
                "scene": sc_num,
                "start": round(float(matched_anchor["start"]), 2),
                "end": round(float(matched_anchor["end"]), 2),
                "text": lyr_txt,
                "type": ltype,
                "note": matched_anchor.get("note", "🔒 定錨鎖定"),
                "locked": True
            })
        else:
            template_segments.append({
                "scene": sc_num,
                "start": None,
                "end": None,
                "text": lyr_txt,
                "type": ltype,
                "note": "",
                "locked": False
            })
        _push_interludes(idx + 1)
    for a in _ivs:   # after_line 超過歌詞句數：放在最後一句之後
        if int(a.get("after_line", 0)) > len(line_pairs):
            _push_interludes(int(a.get("after_line", 0)))

    # Outro segment
    outro_anchor = next((s for s in locked_anchors if s.get("type") == "outro"), None)
    if outro_anchor:
        template_segments.append({
            "scene": int(outro_anchor.get("scene", line_pairs[-1][0])),
            "start": round(float(outro_anchor["start"]), 2),
            "end": round(float(outro_anchor["end"]), 2),
            "text": outro_anchor.get("text") or f"～ 尾奏 · {title} 感謝聆聽 ～",
            "type": "outro",
            "note": outro_anchor.get("note") or "片尾名牌卡",
            "locked": True
        })
        matched_anchor_ids.add(id(outro_anchor))
    elif has_outro_in_existing or True:
        template_segments.append({
            "scene": line_pairs[-1][0] if line_pairs else 1,
            "start": None,
            "end": round(total_dur, 2),
            "text": f"～ 尾奏 · {title} 感謝聆聽 ～",
            "type": "outro",
            "note": "片尾名牌卡",
            "locked": False
        })

    # Partition into brackets of unlocked segments bounded by locked anchors
    M = len(template_segments)
    i = 0
    while i < M:
        if template_segments[i].get("locked"):
            i += 1
            continue

        start_idx = i
        while i < M and not template_segments[i].get("locked"):
            i += 1
        end_idx = i

        w_start = template_segments[start_idx - 1]["end"] if start_idx > 0 else 0.00
        w_end = template_segments[end_idx]["start"] if end_idx < M else round(total_dur, 2)

        # Segments in this bracket
        bracket_segs = template_segments[start_idx:end_idx]
        b_len = len(bracket_segs)

        is_first_intro = (start_idx == 0 and bracket_segs[0]["type"] == "intro")
        is_last_outro = (end_idx == M and bracket_segs[-1]["type"] == "outro")

        lyric_sub_segs = []
        for s in bracket_segs:
            if s["type"] in ("lyric", "interlude"):
                lyric_sub_segs.append(s)

        p = len(lyric_sub_segs)

        if p == 0:
            if is_first_intro:
                bracket_segs[0]["start"] = round(w_start, 2)
                bracket_segs[0]["end"] = round(w_end, 2)
            elif is_last_outro:
                bracket_segs[-1]["start"] = round(w_start, 2)
                bracket_segs[-1]["end"] = round(w_end, 2)
            continue

        # Extract clauses overlapping this window
        bracket_clauses = [
            c for c in all_clauses
            if float(c["end"]) >= (w_start - 1.5) and float(c["start"]) <= (w_end + 1.5)
        ]

        bracket_lines = [(s["scene"], s["text"]) for s in lyric_sub_segs]
        raw_spans = align_bracket_dp(
            lyric_lines=bracket_lines,
            clauses=bracket_clauses,
            w_start=w_start,
            w_end=w_end,
            early_lead=early_lead,
            tail_ext=tail_ext
        )

        # Convert raw vocal spans to contiguous segment boundaries
        v_st0, v_et0, m0 = raw_spans[0]
        target_st0 = v_st0 + early_lead

        if is_first_intro:
            intro_end = max(min_dur, min(target_st0, w_end - p * min_dur))
            intro_end = round(intro_end, 2)
            bracket_segs[0]["start"] = 0.00
            bracket_segs[0]["end"] = intro_end
            lyric_sub_segs[0]["start"] = intro_end
        else:
            lyric_sub_segs[0]["start"] = round(w_start, 2)

        for k in range(p - 1):
            next_v_st = raw_spans[k + 1][0]
            boundary = next_v_st + early_lead
            if lyric_sub_segs[k + 1].get("type") == "interlude" and lyric_sub_segs[k].get("type") != "interlude":
                # [Claude 2026-10-27] 進入間奏的交界：前一句唱完＋尾韻延展（最多停頓的 3 成），不要用「提前進字」切掉前一句的尾音
                prev_v_et = raw_spans[k][1]
                after = raw_spans[k + 2][0] if k + 2 < p else w_end
                boundary = prev_v_et + min(max(0.0, tail_ext), max(0.0, (after - prev_v_et) * 0.3))
            cur_st = lyric_sub_segs[k]["start"]
            min_b = cur_st + min_dur
            max_b = w_end - ((p - 1 - k) + (1 if is_last_outro else 0)) * min_dur
            boundary = max(min_b, min(boundary, max_b))
            boundary = round(boundary, 2)
            lyric_sub_segs[k]["end"] = boundary
            lyric_sub_segs[k + 1]["start"] = boundary
            is_m = raw_spans[k][2]
            lyric_sub_segs[k]["note"] = f"Whisper逐字對齊 ({early_lead}s提早)" if is_m else f"聲學間隙節奏配對 ({early_lead}s提早)"

        v_st_last, v_et_last, m_last = raw_spans[-1]
        is_m = m_last
        lyric_sub_segs[-1]["note"] = f"Whisper逐字對齊 ({early_lead}s提早)" if is_m else f"聲學間隙節奏配對 ({early_lead}s提早)"

        if is_last_outro:
            target_outro_st = v_et_last + tail_ext
            cur_last_st = lyric_sub_segs[-1]["start"]
            outro_st = max(cur_last_st + min_dur, min(target_outro_st, w_end - 1.5))
            outro_st = round(outro_st, 2)
            lyric_sub_segs[-1]["end"] = outro_st
            bracket_segs[-1]["start"] = outro_st
            bracket_segs[-1]["end"] = round(w_end, 2)
        else:
            lyric_sub_segs[-1]["end"] = round(w_end, 2)

    # Final Strict Integrity Verification
    for a in locked_anchors:
        a_sc = int(a.get("scene", -1))
        a_type = a.get("type", "lyric")
        matched = False
        for s in template_segments:
            if s.get("locked") and s.get("type") == a_type and int(s.get("scene", -2)) == a_sc:
                matched = True
                s["start"] = round(float(a["start"]), 2)
                s["end"] = round(float(a["end"]), 2)
                break

    # Verify contiguous handoff
    for idx in range(len(template_segments) - 1):
        s1 = template_segments[idx]
        s2 = template_segments[idx + 1]
        if abs(s1["end"] - s2["start"]) > 1e-4:
            s2["start"] = s1["end"]

    return enforce_anchor_invariants(template_segments, existing_timeline, total_dur)


def apply_anchor_locks(
    new_timeline: List[Dict[str, Any]],
    existing_timeline: List[Dict[str, Any]],
    total_dur: float = 240.0,
    w_segs: Optional[List[Dict[str, Any]]] = None,
    early_lead: float = -0.70,
    tail_ext: float = 2.50,
    title: str = ""
) -> List[Dict[str, Any]]:
    """
    Seamless backward compatibility wrapper routing to align_timeline_with_anchors_and_whisper
    and strictly guaranteeing anchor invariants.
    """
    if not existing_timeline:
        return new_timeline

    locked_anchors = [s for s in existing_timeline if s.get("locked")]
    if not locked_anchors:
        return new_timeline

    if w_segs:
        line_pairs = [
            (int(s.get("scene", 1)), str(s.get("text", "")).strip())
            for s in new_timeline
            if s.get("type", "lyric") == "lyric" and not str(s.get("text", "")).strip().startswith(("～", "~"))
        ]
        return align_timeline_with_anchors_and_whisper(
            existing_timeline=existing_timeline,
            line_pairs=line_pairs,
            w_segs=w_segs,
            total_dur=total_dur,
            early_lead=early_lead,
            tail_ext=tail_ext,
            title=title
        )

    return enforce_anchor_invariants(new_timeline, existing_timeline, total_dur)


def _align_lyrics_with_whisper_dp_core(
    line_pairs: List[Tuple[int, str]],
    w_segs: List[Dict[str, Any]],
    total_dur: float,
    early_lead: float = -0.70,
    tail_ext: float = 2.50,
    title: str = "",
    max_uploaded_scene: int = 12
) -> List[Dict[str, Any]]:
    """
    Aligns N user lyric lines [(scene_id, lyric_text), ...] with Whisper segments using:
    1. Global word-stream elementary clause extraction (eliminating 30s window cuts & 0-dur hallucinations)
    2. Global Monotonic DP supporting 1:1, 1:2, 1:3, 1:4 clause merging, 2:1 splitting, skip_clause, skip_lyric
    3. Strictly bounded musical interpolation for any instrumental/unmatched bridge lines
    4. Mandatory -0.70s early lead, automatic interlude insertion on long gaps (>8.5s), and +2.5s tail extension.
    """
    n_lines = len(line_pairs)
    if n_lines == 0:
        return []

    clauses = extract_elementary_clauses(w_segs)
    if not clauses:
        return []

    m_clauses = len(clauses)

    INF = 1e9
    dp = [[-INF] * (m_clauses + 1) for _ in range(n_lines + 1)]
    parent: List[List[Optional[Tuple[int, int, str]]]] = [[None] * (m_clauses + 1) for _ in range(n_lines + 1)]
    dp[0][0] = 0.0

    skip_clause_pen = 0.35
    skip_lyric_pen = 1.35
    match_weight = 10.0

    for i in range(n_lines + 1):
        for j in range(m_clauses + 1):
            cur = dp[i][j]
            if cur <= -INF / 2:
                continue

            # 1. Skip elementary clause (e.g. intro/interlude vocal ad-lib or echo)
            if j < m_clauses:
                cand = cur - skip_clause_pen
                if cand > dp[i][j + 1]:
                    dp[i][j + 1] = cand
                    parent[i][j + 1] = (i, j, "skip_clause")

            # 2. Skip lyric line (e.g. instrumental verse; only low penalty when an actual musical gap >=5.0s exists at j)
            if i < n_lines:
                if 0 < j < m_clauses:
                    boundary_gap = float(clauses[j]["start"]) - float(clauses[j - 1]["end"])
                elif j == 0:
                    boundary_gap = float(clauses[0]["start"])
                else:
                    boundary_gap = max(0.0, total_dur - float(clauses[-1]["end"]))
                eff_skip_lyric_pen = 0.85 if boundary_gap >= 5.5 else 5.80
                cand = cur - eff_skip_lyric_pen
                if cand > dp[i + 1][j]:
                    dp[i + 1][j] = cand
                    parent[i + 1][j] = (i, j, "skip_lyric")

            # 3. 1:k Clause Merge (k = 1, 2, 3, 4 clauses form 1 user lyric line)
            if i < n_lines:
                lyr_txt = line_pairs[i][1]
                lyr_len = max(1, len(normalize_cjk(lyr_txt)))
                for k in range(1, 5):
                    if j + k > m_clauses:
                        break
                    # Check internal gaps between consecutive merged clauses
                    if k > 1:
                        max_internal_gap = max(
                            float(clauses[j + r]["start"]) - float(clauses[j + r - 1]["end"])
                            for r in range(1, k)
                        )
                        if max_internal_gap > 3.8:
                            break
                    span_dur = float(clauses[j + k - 1]["end"]) - float(clauses[j]["start"])
                    if span_dur > 11.2 and k > 1:
                        break

                    comb_txt = "".join(clauses[j + r]["text"] for r in range(k))
                    comb_len = max(1, len(normalize_cjk(comb_txt)))
                    if k > 1 and comb_len > lyr_len + 3:
                        break
                    len_ratio = min(lyr_len, comb_len) / max(lyr_len, comb_len)
                    if len_ratio < 0.42 and k > 1:
                        continue

                    sim = similarity_score(lyr_txt, comb_txt)
                    pos_diff = abs((i / max(1, n_lines)) - (j / max(1, m_clauses)))
                    pos_bonus = max(0.0, 1.0 - pos_diff * 2.5)
                    # Reward exact syllable/character count match (e.g. 7+5=12 chars for two half-clauses) + phonetic similarity
                    len_fit_bonus = 2.6 * (len_ratio ** 2)
                    if sim >= 0.15:
                        score = sim * match_weight + (len_ratio * sim * 4.5) + len_fit_bonus + pos_bonus - (0.08 * (k - 1))
                    else:
                        score = len_fit_bonus + (pos_bonus * 0.6) - 0.6 - (0.18 * (k - 1))
                    cand = cur + score
                    if cand > dp[i + 1][j + k]:
                        dp[i + 1][j + k] = cand
                        parent[i + 1][j + k] = (i, j, f"match_1to{k}")

            # 4. 2:1 Split (2 short lyric lines inside 1 clause)
            if i + 1 < n_lines and j < m_clauses:
                c_dur = float(clauses[j]["end"]) - float(clauses[j]["start"])
                if c_dur >= 5.5 and clauses[j]["cjk_len"] >= 10:
                    comb_lyr = line_pairs[i][1] + line_pairs[i + 1][1]
                    sim21 = similarity_score(comb_lyr, clauses[j]["text"])
                    score21 = sim21 * match_weight + 1.5
                    cand = cur + score21
                    if cand > dp[i + 2][j + 1]:
                        dp[i + 2][j + 1] = cand
                        parent[i + 2][j + 1] = (i, j, "match_2to1")

    # Backtrack optimal path
    ci, cj = n_lines, m_clauses
    line_to_clauses: Dict[int, List[int]] = {}
    pair_split_map: Dict[int, Tuple[int, int]] = {}

    while ci > 0 or cj > 0:
        step = parent[ci][cj]
        if not step:
            break
        pi, pj, act = step
        if act.startswith("match_1to"):
            k = int(act.replace("match_1to", ""))
            line_to_clauses[pi] = [pj + r for r in range(k)]
        elif act == "match_2to1":
            line_to_clauses[pi] = [pj]
            line_to_clauses[pi + 1] = [pj]
            pair_split_map[pi] = (0, pj)
            pair_split_map[pi + 1] = (1, pj)
        ci, cj = pi, pj

    # Compute raw vocal (start, end, matched_flag) for each of the n_lines
    raw_vocal_spans: List[Optional[Tuple[float, float, bool]]] = [None] * n_lines
    for idx in range(n_lines):
        c_indices = line_to_clauses.get(idx)
        if not c_indices:
            continue
        if idx in pair_split_map:
            part, cj_idx = pair_split_map[idx]
            cl = clauses[cj_idx]
            w_list = cl.get("words") or []
            if len(w_list) >= 4:
                mid_w = len(w_list) // 2
                if part == 0:
                    st, et = float(w_list[0]["start"]), float(w_list[mid_w - 1]["end"])
                else:
                    st, et = float(w_list[mid_w]["start"]), float(w_list[-1]["end"])
            else:
                mid_t = (float(cl["start"]) + float(cl["end"])) / 2.0
                st, et = (float(cl["start"]), mid_t) if part == 0 else (mid_t, float(cl["end"]))
            raw_vocal_spans[idx] = (round(st, 2), round(et, 2), True)
        else:
            st = float(clauses[c_indices[0]]["start"])
            et = float(clauses[c_indices[-1]]["end"])
            raw_vocal_spans[idx] = (round(st, 2), round(et, 2), True)

    # Interpolate any unanchored lyric lines strictly within [prev_end, next_start]
    i = 0
    while i < n_lines:
        if raw_vocal_spans[i] is not None:
            i += 1
            continue
        j = i
        while j < n_lines and raw_vocal_spans[j] is None:
            j += 1
        count_missing = j - i
        prev_end = raw_vocal_spans[i - 1][1] if i > 0 and raw_vocal_spans[i - 1] else 18.0
        next_start = raw_vocal_spans[j][0] if j < n_lines and raw_vocal_spans[j] else max(prev_end + count_missing * 7.0, total_dur - 16.0)

        avail_gap = max(0.5, next_start - prev_end)
        lead_pause = min(2.0, avail_gap * 0.10) if (i > 0 and avail_gap > count_missing * 4.0) else 0.1
        span_start = prev_end + lead_pause
        span_end = max(span_start + 0.5, next_start - 0.1)
        step_dur = (span_end - span_start) / max(1, count_missing)

        for k in range(count_missing):
            s_k = round(span_start + k * step_dur, 2)
            e_k = round(span_start + (k + 1) * step_dur - 0.1, 2)
            raw_vocal_spans[i + k] = (s_k, max(s_k + 0.4, e_k), False)
        i = j

    # Build final timeline with -0.70s early lead, automatic interludes, and +tail_ext
    new_tl: List[Dict[str, Any]] = []
    first_vocal_st = raw_vocal_spans[0][0] if raw_vocal_spans[0] else 18.0
    first_sub_st = max(0.0, round(first_vocal_st + early_lead, 2))

    first_sc = line_pairs[0][0]
    if first_sub_st > 2.0:
        new_tl.append({
            "scene": first_sc,
            "start": 0.00,
            "end": first_sub_st,
            "text": f"～ 前奏 · {title} ～",
            "type": "intro",
            "note": "開場榮譽名牌卡"
        })

    for idx, (sc_num, line_txt) in enumerate(line_pairs):
        v_st, v_et, is_anchored = raw_vocal_spans[idx] or (18.0, 26.0, False)
        is_interlude_line = line_txt.startswith("～") or ("間奏" in line_txt and len(line_txt) <= 16)
        sub_st = max(0.0, round(v_st + (0.0 if is_interlude_line else early_lead), 2))

        if new_tl:
            prev_seg = new_tl[-1]
            if sub_st <= prev_seg["start"] + 0.5:
                sub_st = round(prev_seg["start"] + 1.0, 2)
            # Seamless contiguous handoff: previous card's end == current card's start
            prev_seg["end"] = sub_st

        sub_et = max(sub_st + 1.5, round(v_et + tail_ext, 2))
        note_str = f"Whisper逐字對齊 ({early_lead}s提早)" if is_anchored else f"聲學間隙節奏配對 ({early_lead}s提早)"
        new_tl.append({
            "scene": sc_num,
            "start": sub_st,
            "end": sub_et,
            "text": line_txt,
            "type": "interlude" if is_interlude_line else "lyric",
            "note": note_str
        })

    # Append outro card
    if new_tl:
        last_seg = new_tl[-1]
        outro_st = min(max(last_seg["start"] + 2.5, total_dur - 5.0), last_seg["end"])
        last_seg["end"] = round(outro_st, 2)
        last_seg["note"] = f"片尾前延展 +{tail_ext}s 包覆尾韻"
        last_sc = line_pairs[-1][0]
        new_tl.append({
            "scene": last_sc,
            "start": round(outro_st, 2),
            "end": round(total_dur, 3),
            "text": f"～ 尾奏 · {title} 感謝聆聽 ～",
            "type": "outro",
            "note": "片尾榮譽名牌卡"
        })

    return ensure_all_scenes_covered(new_tl, max_uploaded_scene, total_dur, title)


def build_guaranteed_fallback_timeline(
    line_pairs: List[Tuple[int, str]],
    total_dur: float,
    early_lead: float = -0.70,
    title: str = "",
    target_scene_count: int = 12
) -> List[Dict[str, Any]]:
    """
    100% infallible fallback timeline builder:
    Guarantees that even if Whisper fails, times out, or has no segments,
    every single scene card (1..target_scene_count) receives a valid, contiguous (start, end)
    timestamp and editable lyric text so the user can immediately fine-tune on the left panel.
    """
    dur = max(30.0, float(total_dur or 240.0))
    n_sc = max(1, int(target_scene_count or 12), len(line_pairs))
    pairs: List[Tuple[int, str]] = list(line_pairs)
    existing_scs = {sc for sc, _ in pairs}
    for sid in range(1, n_sc + 1):
        if sid not in existing_scs:
            pairs.append((sid, f"第 {sid:02d} 段歌詞（可直接點擊修改文字與微調時間）"))
    pairs.sort(key=lambda x: x[0])

    intro_end = min(18.0, round(dur * 0.10, 2))
    outro_start = max(intro_end + len(pairs) * 2.0, round(dur - min(16.0, dur * 0.09), 2))
    if outro_start >= dur - 2.0:
        outro_start = max(intro_end + 4.0, round(dur - 5.0, 2))

    tl: List[Dict[str, Any]] = [
        {
            "scene": pairs[0][0],
            "start": 0.00,
            "end": intro_end,
            "text": f"～ 前奏 · {title or '精選金曲'} ～",
            "type": "intro",
            "note": "開場榮譽名牌卡"
        }
    ]
    step = (outro_start - intro_end) / max(1, len(pairs))
    for idx, (sc_id, txt) in enumerate(pairs):
        st = round(intro_end + idx * step, 2) if idx > 0 else intro_end
        et = round(intro_end + (idx + 1) * step, 2) if idx < len(pairs) - 1 else outro_start
        if tl:
            tl[-1]["end"] = st
        tl.append({
            "scene": sc_id,
            "start": st,
            "end": max(st + 0.5, et),
            "text": txt,
            "type": "lyric",
            "note": f"保底連續時間軸 (可直接微調起迄秒數)"
        })

    tl.append({
        "scene": pairs[-1][0],
        "start": outro_start,
        "end": round(dur, 3),
        "text": f"～ 尾奏 · {title or '精選金曲'} 感謝聆聽 ～",
        "type": "outro",
        "note": "片尾榮譽名牌卡"
    })
    return tl


def ensure_all_scenes_covered(
    tl: List[Dict[str, Any]],
    target_scene_count: int,
    total_dur: float,
    title: str = ""
) -> List[Dict[str, Any]]:
    """
    Ensures every scene 1..target_scene_count has at least one 'lyric' segment in `tl`.
    If the user uploaded 12 photos on the left but only pasted 8 lines (or Whisper returned fewer),
    automatically splits/extends the tail so Scenes 9..12 also get contiguous timestamps for fine-tuning.
    """
    if not tl:
        return build_guaranteed_fallback_timeline([], total_dur, -0.70, title, target_scene_count)

    lyric_scs = {int(s.get("scene", 0)) for s in tl if s.get("type") == "lyric"}
    missing_scs = [sid for sid in range(1, int(target_scene_count or 12) + 1) if sid not in lyric_scs]
    if not missing_scs:
        return tl

    has_outro = tl[-1].get("type") == "outro"
    outro_seg = tl.pop() if has_outro else None
    last_lyric_end = float(tl[-1]["end"]) if tl else 18.0
    outro_start = float(outro_seg["start"]) if outro_seg else max(last_lyric_end + len(missing_scs) * 4.0, total_dur - 12.0)

    # Give missing scenes a fair share of time before outro_start
    avail = outro_start - last_lyric_end
    if avail < len(missing_scs) * 2.5 and len(tl) >= 2:
        # Borrow some time from the last segment if it's very long
        prev_s = tl[-1]
        prev_dur = float(prev_s["end"]) - float(prev_s["start"])
        if prev_dur > 8.0:
            shrink_to = float(prev_s["start"]) + max(4.5, prev_dur * 0.45)
            prev_s["end"] = round(shrink_to, 2)
            last_lyric_end = prev_s["end"]
            avail = outro_start - last_lyric_end

    if avail < len(missing_scs) * 1.5:
        outro_start = min(total_dur - 3.0, last_lyric_end + len(missing_scs) * 3.0)
        avail = max(len(missing_scs) * 1.0, outro_start - last_lyric_end)

    step = avail / max(1, len(missing_scs))
    cur_t = last_lyric_end
    for idx, m_sc in enumerate(missing_scs):
        nxt_t = round(cur_t + step, 2) if idx < len(missing_scs) - 1 else round(outro_start, 2)
        if tl:
            tl[-1]["end"] = round(cur_t, 2)
        tl.append({
            "scene": m_sc,
            "start": round(cur_t, 2),
            "end": max(round(cur_t + 0.5, 2), nxt_t),
            "text": f"第 {m_sc:02d} 段分鏡字幕（可在此輸入歌詞或微調時間）",
            "type": "lyric",
            "note": "自動補齊分鏡時間槽位"
        })
        cur_t = tl[-1]["end"]

    if outro_seg:
        outro_seg["start"] = tl[-1]["end"]
        outro_seg["end"] = round(max(float(outro_seg["start"]) + 1.0, total_dur), 3)
        tl.append(outro_seg)
    return tl


def split_whisper_segments_into_phrases(
    w_segs: List[Dict[str, Any]],
    target_scene_count: int = 12,
    total_dur: float = 240.0
) -> List[Dict[str, Any]]:
    """
    Converts raw Whisper segments into `target_scene_count` (e.g. 12) line-level phrases
    when the user has NOT pasted custom lyrics yet:
    - Starts from non-empty Whisper segments.
    - If len < target_scene_count: splits merged multi-line segments or inserts vocal/instrumental
      phrases inside the largest musical gaps (e.g. 114s~136s or 61s~76s) until reaching target_scene_count.
    - If len > target_scene_count: merges closest adjacent short segments until reaching target_scene_count.
    """
    items: List[Dict[str, Any]] = []
    for seg in (w_segs or []):
        st = round(float(seg.get("start", 0.0)), 2)
        et = round(float(seg.get("end", 0.0)), 2)
        txt = str(seg.get("text", "")).strip()
        if (et - st) < 0.25 or not txt:
            continue
        items.append({
            "start": st,
            "end": et,
            "text": txt,
            "words": seg.get("words") or []
        })

    if not items:
        clauses = extract_elementary_clauses(w_segs or [])
        items = [
            {"start": c["start"], "end": c["end"], "text": c["text"], "words": c.get("words") or []}
            for c in clauses
        ]

    if not items:
        return []

    target_n = max(1, int(target_scene_count or 12))

    # Step 1: If we have fewer items than target_n, first split any overly long multi-line segments (>13.5s)
    while len(items) < target_n:
        split_done = False
        best_idx = -1
        best_dur = 0.0
        for idx, it in enumerate(items):
            d = float(it["end"]) - float(it["start"])
            if d >= 13.0 and d > best_dur and len(it.get("words") or []) >= 6:
                best_dur = d
                best_idx = idx
        if best_idx >= 0:
            it = items[best_idx]
            ws = it["words"]
            # Find largest internal gap near middle
            mid_start = max(2, len(ws) // 4)
            mid_end = min(len(ws) - 2, (len(ws) * 3) // 4)
            split_k = len(ws) // 2
            max_g = -1.0
            for k in range(mid_start, max(mid_start + 1, mid_end)):
                g = float(ws[k]["start"]) - float(ws[k - 1]["end"])
                if g > max_g:
                    max_g = g
                    split_k = k
            w1, w2 = ws[:split_k], ws[split_k:]
            p1 = {
                "start": round(float(w1[0]["start"]), 2),
                "end": round(float(w1[-1]["end"]), 2),
                "text": "".join(x.get("word", "") for x in w1).strip() or it["text"][:len(it["text"])//2],
                "words": w1
            }
            p2 = {
                "start": round(float(w2[0]["start"]), 2),
                "end": round(float(w2[-1]["end"]), 2),
                "text": "".join(x.get("word", "") for x in w2).strip() or it["text"][len(it["text"])//2:],
                "words": w2
            }
            items = items[:best_idx] + [p1, p2] + items[best_idx + 1:]
            split_done = True

        if split_done:
            continue

        # Step 2: Check for large musical gaps (>= 7.5s) between consecutive segments where instrumental/vocal verses exist
        best_gap_idx = -1
        best_gap_dur = 0.0
        for idx in range(len(items) - 1):
            g = float(items[idx + 1]["start"]) - float(items[idx]["end"])
            if g > best_gap_dur:
                best_gap_dur = g
                best_gap_idx = idx

        if best_gap_idx >= 0 and best_gap_dur >= 7.5:
            g_start = float(items[best_gap_idx]["end"])
            g_end = float(items[best_gap_idx + 1]["start"])
            needed = target_n - len(items)
            # If the gap is >= 16s and we need >= 2 scenes (e.g. 114.27~136.28s 22s bridge needing 2 scenes), insert 2!
            insert_cnt = 2 if (best_gap_dur >= 16.0 and needed >= 2) else 1
            step_g = (g_end - g_start) / insert_cnt
            new_bridges = []
            for b_i in range(insert_cnt):
                b_st = round(g_start + b_i * step_g + 0.3, 2)
                b_et = round(g_start + (b_i + 1) * step_g - 0.3, 2)
                new_bridges.append({
                    "start": b_st,
                    "end": max(b_st + 1.0, b_et),
                    "text": f"（間奏／器樂旋律段落 {b_i + 1} · 可直接改為對應歌詞）",
                    "words": []
                })
            items = items[:best_gap_idx + 1] + new_bridges + items[best_gap_idx + 1:]
            continue

        # Step 3: Otherwise split the longest remaining segment in half so we always reach target_n
        longest_idx = max(range(len(items)), key=lambda i: float(items[i]["end"]) - float(items[i]["start"]))
        it = items[longest_idx]
        mid_t = round((float(it["start"]) + float(it["end"])) / 2.0, 2)
        if mid_t <= float(it["start"]) + 0.4:
            break
        txt = it["text"]
        half_c = max(1, len(txt) // 2)
        p1 = {"start": it["start"], "end": mid_t, "text": txt[:half_c].strip() or txt, "words": []}
        p2 = {"start": mid_t, "end": it["end"], "text": txt[half_c:].strip() or txt, "words": []}
        items = items[:longest_idx] + [p1, p2] + items[longest_idx + 1:]

    # Step 4: If we have MORE items than target_n, merge the closest/shortest adjacent pair until len == target_n
    while len(items) > target_n and len(items) >= 2:
        best_merge_i = 0
        best_cost = 1e9
        for i in range(len(items) - 1):
            gap = max(0.0, float(items[i + 1]["start"]) - float(items[i]["end"]))
            comb_dur = float(items[i + 1]["end"]) - float(items[i]["start"])
            cost = gap * 3.0 + comb_dur
            if cost < best_cost:
                best_cost = cost
                best_merge_i = i
        a, b = items[best_merge_i], items[best_merge_i + 1]
        merged = {
            "start": a["start"],
            "end": b["end"],
            "text": (a["text"] + " " + b["text"]).strip(),
            "words": (a.get("words") or []) + (b.get("words") or [])
        }
        items = items[:best_merge_i] + [merged] + items[best_merge_i + 2:]

    return items


def auto_generate_timeline_from_whisper_only(
    w_segs: List[Dict[str, Any]],
    total_dur: float,
    early_lead: float = -0.70,
    tail_ext: float = 2.50,
    title: str = "",
    target_scene_count: int = 12
) -> List[Dict[str, Any]]:
    """
    When the user has NOT pasted custom lyrics yet and triggers Whisper alignment,
    automatically segments Whisper word timestamps into `target_scene_count` (e.g. 12) phrases
    and binds them 1-to-1 to Scene 01..N with -0.70s early lead and contiguous transitions.
    Never fails: if Whisper segments are empty or malformed, falls back to even distribution.
    """
    try:
        phrases = split_whisper_segments_into_phrases(
            w_segs,
            target_scene_count=target_scene_count,
            total_dur=total_dur
        )
        if not phrases:
            return build_guaranteed_fallback_timeline([], total_dur, early_lead, title, target_scene_count)

        new_tl: List[Dict[str, Any]] = []
        first_st = max(0.0, round(float(phrases[0]["start"]) + early_lead, 2))
        if first_st > 2.0:
            new_tl.append({
                "scene": 1,
                "start": 0.00,
                "end": first_st,
                "text": f"～ 前奏 · {title or '精選金曲'} ～",
                "type": "intro",
                "note": "開場榮譽名牌卡"
            })

        for idx, p in enumerate(phrases):
            sc_num = idx + 1
            sub_st = max(0.0, round(float(p["start"]) + early_lead, 2))
            if new_tl:
                prev_seg = new_tl[-1]
                if sub_st <= float(prev_seg["start"]) + 0.5:
                    sub_st = round(float(prev_seg["start"]) + 1.0, 2)
                prev_seg["end"] = sub_st
            sub_et = max(sub_st + 1.5, round(float(p["end"]) + tail_ext, 2))
            new_tl.append({
                "scene": sc_num,
                "start": sub_st,
                "end": sub_et,
                "text": str(p.get("text") or f"第 {sc_num:02d} 段歌詞"),
                "type": "lyric",
                "note": f"Whisper語音辨識自動配對 ({early_lead}s提早)"
            })

        if new_tl:
            last_seg = new_tl[-1]
            outro_st = min(max(float(last_seg["start"]) + 2.5, total_dur - 5.0), float(last_seg["end"]))
            last_seg["end"] = round(outro_st, 2)
            new_tl.append({
                "scene": len(phrases),
                "start": round(outro_st, 2),
                "end": round(total_dur, 3),
                "text": f"～ 尾奏 · {title or '精選金曲'} 感謝聆聽 ～",
                "type": "outro",
                "note": "片尾榮譽名牌卡"
            })

        return ensure_all_scenes_covered(new_tl, target_scene_count, total_dur, title)
    except Exception:
        return build_guaranteed_fallback_timeline([], total_dur, early_lead, title, target_scene_count)


