"""Lyric lines placed where they are sung (app/lyric_align.py), in the MV workspace and the quick MV.

The lines and "recognized" words are made up here; the cases are the ones that went wrong with the old
clause matching on real songs: clause borders that are not line borders, repeats the pasted lyrics lack,
misheard characters, both Chinese scripts in one transcript.
"""
import random

from app import lyric_align as la
from app import quick_lyrics
from app.mvstudio import align

VERSE = ["清晨的窗外有鳥在唱", "陽光慢慢爬上舊書桌", "我把昨天摺成紙飛機", "讓它飛過對面的屋頂"]
CHORUS = ["就這樣一直走不回頭", "風會記得我們的名字", "走到天黑也不害怕", "因為有你"]
ENGLISH = ["Walking down the empty road tonight", "I can hear the river calling out my name",
           "Don't you know I'm waiting here for you", "Hold on, hold on, we're almost home"]


def sing(sections, t0=20.0, gap=0.7, between=9.0, simplified=(), per_char=0.38):
    """Words with times for the given sections (lists of lines). Returns (lines, starts, words).
    Lines of a section in `simplified` are "heard" in Simplified Chinese."""
    t2s = la._t2s()
    lines, starts, words, t = [], [], [], t0
    for si, sec in enumerate(sections):
        for ln in sec:
            lines.append(ln)
            starts.append(round(t, 2))
            for part in ([c for c in ln] if la._is_cjk(ln[0]) else ln.split()):
                if part.strip() == "":
                    continue
                heard = "".join(t2s.get(c, c) for c in part) if si in simplified else part
                dur = per_char if la._is_cjk(part[0]) else 0.2 + 0.04 * len(part)
                words.append({"word": heard if la._is_cjk(part[0]) else " " + heard, "start": round(t, 2), "end": round(t + dur, 2)})
                t += dur
            t += gap
        t += between
    return lines, starts, words


def placed(lines, words, hi=400.0):
    found = la.align_lines(lines, words)
    return found, la.fill_unplaced(found["spans"], lines, 0.0, hi, words)


def test_tokens():
    assert la.tokens("Don't stop — Привет, ёлка! café 123") == ["dont", "stop", "привет", "елка", "cafe", "123"]
    assert la.tokens("想著妳的臉") == la.tokens("想着你的脸")          # both scripts, everyday variants
    assert la.tokens("～ 間奏 ～") and la.tokens("…！？") == []


def test_every_line_at_its_own_first_word():
    lines, starts, words = sing([VERSE, CHORUS, VERSE, CHORUS, CHORUS], simplified={1, 3})
    found, spans = placed(lines, words)
    assert [s[0] for s in spans] == starts and all(s[2] for s in spans)
    assert found["matched"] == found["total"] and found["unsung"] == []
    # no pauses at all between the lines (one long clause): still each line at its own first character
    lines, starts, words = sing([VERSE, CHORUS], gap=0.0)
    assert [s[0] for s in placed(lines, words)[1]] == starts


def test_repeat_missing_from_the_paste():
    sung, starts, words = sing([VERSE, CHORUS, VERSE, CHORUS, CHORUS])
    pasted = VERSE + CHORUS + CHORUS + CHORUS                     # second verse not pasted
    found, spans = placed(pasted, words)
    assert [s[0] for s in spans] == starts[:8] + starts[12:]
    assert [(u["start"], u["text"][:4]) for u in found["unsung"]] == [(starts[8], VERSE[0][:4])]
    pasted = VERSE + CHORUS + VERSE + CHORUS                      # last chorus not pasted: the first is taken
    found, spans = placed(pasted, words)
    assert [s[0] for s in spans] == starts[:16]
    assert len(found["unsung"]) == 1 and found["unsung"][0]["start"] == starts[16]
    found, spans = placed(VERSE + CHORUS, words)                  # only the first verse and chorus pasted
    assert [s[0] for s in spans] == starts[:8] and found["unsung"][0]["start"] == starts[8]


def test_misheard_and_unheard():
    lines, starts, words = sing([VERSE, CHORUS, VERSE, CHORUS])
    rng = random.Random(3)
    wrong = [dict(w, word=rng.choice("東西南北山水")) if rng.random() < 0.3 else w for w in words]
    spans = placed(lines, wrong)[1]
    assert max(abs(s[0] - t) for s, t in zip(spans, starts)) <= 0.5
    # one line not recognized at all: it lands between its neighbours, the others stay exact
    lost = [w for w in words if not (starts[5] - 0.01 <= w["start"] < starts[6] - 0.01)]
    found, spans = placed(lines, lost)
    assert found["spans"][5] is None and not spans[5][2]
    assert spans[4][1] <= spans[5][0] <= starts[6] and spans[5][1] <= starts[6] + 0.01
    assert [s[0] for i, s in enumerate(spans) if i != 5] == [t for i, t in enumerate(starts) if i != 5]
    # words that are not in the lyrics (a credit read out in the intro, a spoken aside) do not move anything
    extra = [{"word": c, "start": 2 + i * 0.3, "end": 2.3 + i * 0.3} for i, c in enumerate("詞曲某某某製作")] + words
    assert [s[0] for s in placed(lines, extra)[1]] == starts
    # a pasted line that is never sung stays unplaced between its neighbours
    found, spans = placed(lines[:4] + ["這一句根本沒有人唱"] + lines[4:], words)
    assert found["spans"][4] is None and [s[0] for i, s in enumerate(spans) if i != 4] == starts


def test_lines_cut_differently_and_no_word_times():
    lines, starts, words = sing([CHORUS])
    halves = [CHORUS[0][:5], CHORUS[0][5:]] + CHORUS[1:]
    spans = placed(halves, words)[1]
    assert spans[0][0] == starts[0] and abs(spans[1][0] - (starts[0] + 5 * 0.38)) < 0.01 and spans[2][0] == starts[1]
    # Whisper segments without word times: two lines in one segment are divided by their length
    seg = [{"word": " " + CHORUS[0] + CHORUS[1], "start": 20.0, "end": 26.84}]
    spans = placed(CHORUS[:2], seg)[1]
    assert spans[0][0] == 20.0 and abs(spans[1][0] - 23.42) < 0.05


def test_latin_words():
    lines, starts, words = sing([ENGLISH, ENGLISH])
    assert [s[0] for s in placed(lines, words)[1]] == starts
    heard = [dict(w) for w in words]
    heard[3]["word"], heard[9]["word"] = " emptier", " rivers"      # endings heard differently
    del heard[20]
    upper = ["".join(c for c in ln.upper() if c.isalnum() or c == " ") for ln in lines]
    assert max(abs(s[0] - t) for s, t in zip(placed(upper, heard)[1], starts)) < 0.01


def test_quick_mv_lines():
    sung, starts, words = sing([VERSE, CHORUS, CHORUS], gap=0.7, between=9.0)
    segs = [{"start": words[0]["start"], "end": words[-1]["end"], "text": "x", "words": words}]
    rep = quick_lyrics.align_report(VERSE + CHORUS, segs)
    out = rep["lines"]
    assert [x["start"] for x in out] == starts[:8] and [x["text"] for x in out] == VERSE + CHORUS
    assert rep["placed"] == 8 and len(rep["unsung"]) == 1
    assert out[0]["end"] == out[1]["start"]                       # next line within a second: no flicker
    assert abs(out[3]["end"] - (starts[3] + len(VERSE[3]) * 0.38 + 0.5)) < 0.02      # before a pause: off soon after
    assert out[3]["end"] < out[4]["start"] - 5
    assert quick_lyrics.align_report(VERSE, []) == {"lines": [], "placed": 0, "unsung": []}
    assert quick_lyrics.align(["a"], [(1.0, 2.0, "a")])[0]["start"] == 1.0           # old tuple segments


def test_mv_timeline_uses_it():
    lines, starts, words = sing([VERSE, CHORUS, VERSE, CHORUS], simplified={1})
    w_segs = []
    for k in range(0, len(words), 13):                           # segment borders unrelated to the lines
        chunk = [dict(w) for w in words[k:k + 13]]
        for w, nxt in zip(chunk, chunk[1:]):                     # as Whisper writes them: a word lasts until the
            w["end"] = min(nxt["start"], w["end"] + 1.0)         # next one, the pause between two lines is swallowed
        w_segs.append({"start": chunk[0]["start"], "end": chunk[-1]["end"],
                       "text": "".join(w["word"] for w in chunk), "words": chunk})
    # (with these word times the clause matching this replaced put all 16 lines more than 0.6 s off)
    total = words[-1]["end"] + 12
    pairs = [(i + 1, t) for i, t in enumerate(lines[:8] + ["～ 間奏 ～"] + lines[8:])]
    tl = align.align_timeline_with_anchors_and_whisper(existing_timeline=[], line_pairs=pairs, w_segs=w_segs,
                                                       total_dur=total, early_lead=-0.7, tail_ext=2.5, title="t",
                                                       target_scene_count=len(pairs))
    tl = align.enforce_anchor_invariants(tl, [], total)
    lyric = [s for s in tl if s["type"] == "lyric"]
    assert [s["text"] for s in lyric] == lines
    assert max(abs(s["start"] - (t - 0.7)) for s, t in zip(lyric, starts)) < 0.011      # 0.7 s before the voice
    assert all(abs(a["end"] - b["start"]) < 1e-6 for a, b in zip(tl, tl[1:]))
    gap = next(s for s in tl if s["type"] == "interlude")
    assert starts[7] < gap["start"] < gap["end"] <= starts[8]
    assert gap["end"] - gap["start"] > 5                          # the marker line takes the pause, not a lyric's time
    assert tl[0]["type"] == "intro" and tl[-1]["type"] == "outro"
    assert align.unsung_sections(pairs, w_segs) == []
    assert align.unsung_sections(pairs[:8], w_segs)[0]["start"] == starts[8]


def _song_with_audio(client, root, secs):
    import json
    import subprocess
    sid = client.post("/api/songs", json={"title": "align"}).json()["song_id"]
    song_dir = next(p for p in root.rglob(sid) if (p / "song.json").is_file())
    src = song_dir / "source"
    src.mkdir()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=330:duration={secs}:sample_rate=44100",
                    "-ac", "2", "-c:a", "pcm_f32le", str(src / "audio.wav")], check=True)
    (src / "source.json").write_text(json.dumps({"type": "file", "audio": "source/audio.wav", "duration": float(secs),
                                                 "source_hash": "file:align", "imported_at": 1.0}), encoding="utf-8")
    return sid, song_dir


def test_mv_and_quick_mv_api_with_a_cached_transcript(client, root):
    """The two pages' requests end to end (the transcript is already there, so no engine is needed):
    lines at their sung times, and the notice about singing that the pasted lyrics lack."""
    import json
    lines, starts, words = sing([VERSE, CHORUS, CHORUS], t0=8.0, between=6.0)
    secs = int(words[-1]["end"] + 6)
    sid, song_dir = _song_with_audio(client, root, secs)
    segs = [{"start": words[0]["start"], "end": words[-1]["end"], "text": "".join(w["word"] for w in words), "words": words}]

    created = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "demo", "title": "t", "scene_count": 3}).json()
    proj = created["project"]
    pdir = song_dir / "mv" / "demo"
    (pdir / "whisper.json").write_text(json.dumps({
        "pipeline": align.WHISPER_PIPELINE, "segments": segs, "duration": float(secs), "lead_requested": False,
        "audio_file": str(song_dir / "source" / "audio.wav")}), encoding="utf-8")
    body = {"slug": proj["slug"], "lyrics_text": "\n".join(VERSE + CHORUS), "mode": "whisper_align"}
    res = client.post("/api/mv/paste_lyrics", json=body)
    data = res.json()
    assert res.status_code == 200 and data["whisper_source"] == "cache" and data["fallback_used"] is False, data
    lyric = [s for s in data["project"]["timeline"] if s["type"] == "lyric"]
    lead = data["project"]["early_lead_applied"]
    assert [s["text"] for s in lyric] == VERSE + CHORUS
    assert max(abs(s["start"] - (t + lead)) for s, t in zip(lyric, starts)) < 0.011
    m, s = divmod(int(starts[8]), 60)
    assert "有 1 段聽得到歌聲" in data["warning"] and f"{m}:{s:02d}–" in data["warning"]      # the chorus sung twice
    body["lyrics_text"] = "\n".join(lines)
    again = client.post("/api/mv/paste_lyrics", json=body).json()
    assert "聽得到歌聲" not in again["warning"] and sum(1 for x in again["project"]["timeline"] if x["type"] == "lyric") == 12

    wf = song_dir / "quickmv" / "lyrics" / "whisper.json"
    wf.parent.mkdir(parents=True)
    wf.write_text(json.dumps({"segments": segs}), encoding="utf-8")
    q = client.post(f"/api/songs/{sid}/quickmv/lyrics/align", json={"text": "\n".join(VERSE + CHORUS)}).json()
    assert q["mode"] == "whisper" and q["matched"] == 8 and q["total"] == 8
    assert [x["start"] for x in q["lines"]] == starts[:8] and len(q["unsung"]) == 1 and q["unsung"][0]["start"] == starts[8]
