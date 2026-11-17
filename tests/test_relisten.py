"""Anchors in the library's lyric timing, and Whisper listening again to the stretches it missed
(app/relisten.py, app/quick_lyrics.anchored_report). Without anchors everything is timed exactly as before."""
import json

from app import quick_lyrics, relisten
from app.mvstudio import align
from test_lyric_align import CHORUS, VERSE, _song_with_audio, sing


def _missed(t0=8.0):
    """Eight lines sung; Whisper heard nothing of lines 3 to 5 (as with 彩虹 at 0:09–0:55)."""
    lines, starts, words = sing([VERSE, CHORUS], t0=t0, between=4.0)
    per_line, k = [], 0
    for ln in lines:
        n = len(ln)
        per_line.append(words[k:k + n])
        k += n
    heard = [w for i, ws in enumerate(per_line) if i not in (2, 3, 4) for w in ws]
    segs = [{"start": heard[0]["start"], "end": heard[-1]["end"], "text": "".join(w["word"] for w in heard), "words": heard}]
    return lines, starts, per_line, segs


def test_anchored_report_and_listening_again(tmp_path):
    lines, starts, per_line, segs = _missed()
    total = 120.0
    wf = tmp_path / "whisper.json"
    wf.write_text(json.dumps({"segments": segs}), encoding="utf-8")

    plain = quick_lyrics.align_report(lines, segs)          # no anchors: as before (lines 3-5 spread in the gap)
    assert plain["placed"] == 5

    a1 = {"start": starts[1], "end": round(per_line[1][-1]["end"] + 0.5, 2), "text": lines[1], "locked": True}
    a2 = {"start": starts[5], "end": round(per_line[5][-1]["end"] + 0.5, 2), "text": lines[5], "locked": True}
    rep = quick_lyrics.anchored_report(lines, segs, [a2, a1], total)
    got = rep["lines"]
    assert [x["text"] for x in got] == lines
    assert got[1] == a1 and got[5] == a2                    # anchors keep their time exactly
    assert [x["start"] for i, x in enumerate(got) if i in (0, 6, 7)] == [starts[0], starts[6], starts[7]]
    assert all(a1["end"] <= got[i]["start"] < a2["start"] for i in (2, 3, 4))   # the missed lines stay between anchors
    assert len(rep["gaps"]) == 1 and rep["gaps"][0]["lines"] == lines[2:5]
    g = rep["gaps"][0]
    assert a1["end"] - 0.01 <= g["start"] and g["end"] <= a2["start"] + 0.01

    wins = relisten.windows(rep["gaps"], wf)
    assert len(wins) == 1 and lines[2] in wins[0]["prompt"] and wins[0]["start"] < g["start"] < g["end"] < wins[0]["end"]
    assert relisten.merged({"segments": segs}, wf) == segs   # nothing heard again yet

    # what the worker writes (workers/mv_whisper.py, input "windows"): the missed lines, heard this time,
    # and a stray word outside the stretch that must not be taken
    heard = [w for i in (2, 3, 4) for w in per_line[i]]
    stray = {"word": "啦", "start": 100.0, "end": 100.3}
    relisten.new_file(wf).write_text(json.dumps({"windows": [{**wins[0], "segments": [
        {"start": heard[0]["start"], "end": stray["end"], "text": "x", "words": heard + [stray]}]}]}), encoding="utf-8")
    assert relisten.collect(wf) == 1 and not relisten.new_file(wf).exists() and len(relisten.done(wf)) == 1
    assert json.loads(wf.read_text(encoding="utf-8")) == {"segments": segs}     # the Whisper result is not touched
    merged = relisten.merged({"segments": segs}, wf)
    assert not any(w["start"] == 100.0 for s in merged for w in s["words"])
    rep2 = quick_lyrics.anchored_report(lines, merged, [a1, a2], total)
    assert [x["start"] for x in rep2["lines"][2:5]] == starts[2:5] and rep2["gaps"] == [] and rep2["placed"] == 8
    assert relisten.windows(rep["gaps"], wf) == []          # the same stretch is not asked for twice
    relisten.forget(wf)
    assert relisten.done(wf) == [] and wf.is_file()


def test_locked_lines_are_kept_and_nothing_else_changes():
    got = quick_lyrics.clean_lines([{"start": 3, "end": 5, "text": "b", "locked": True}, {"start": 1, "end": 2, "text": "a"},
                                    {"start": 6, "end": 7, "text": "c", "locked": "yes"}])
    assert got == [{"start": 1.0, "end": 2.0, "text": "a"}, {"start": 3.0, "end": 5.0, "text": "b", "locked": True},
                   {"start": 6.0, "end": 7.0, "text": "c"}]
    # an anchor whose words are no longer in the lyrics anchors nothing; no anchor at all: align_report
    lines, starts, per_line, segs = _missed()
    stray = {"start": 50.0, "end": 52.0, "text": "不在歌詞裡", "locked": True}
    rep = quick_lyrics.anchored_report(lines, segs, [stray], 120.0)
    assert not any(x.get("locked") for x in rep["lines"])


def test_library_api_lines_not_heard_are_listened_to_again_with_or_without_anchors(client, root, monkeypatch):
    from app import stems as stems_mod
    lines, starts, per_line, segs = _missed()
    secs = int(per_line[-1][-1]["end"] + 6)
    sid, song_dir = _song_with_audio(client, root, secs)
    wf = song_dir / "quickmv" / "lyrics" / "whisper.json"
    wf.parent.mkdir(parents=True)
    wf.write_text(json.dumps({"segments": segs}), encoding="utf-8")
    url = f"/api/songs/{sid}/quickmv/lyrics/align"
    text = "\n".join(lines)
    before = client.post(url, json={"text": text}).json()
    want = quick_lyrics.align_report(lines, segs)
    assert before["mode"] == "whisper" and before["matched"] == want["placed"] == 5 and before["relistened"] == 0
    assert [x["start"] for i, x in enumerate(before["lines"]) if i not in (2, 3, 4)] == [x["start"] for i, x in enumerate(want["lines"]) if i not in (2, 3, 4)]

    # something heard again earlier counts without anchors too (it took anchors before 2026-11-18)
    relisten.store_file(wf).write_text(json.dumps({"windows": [{"start": 10.0, "end": 40.0, "segments": [
        {"start": 11, "end": 12, "text": "x", "words": [{"word": "清", "start": 11.0, "end": 11.4}]}]}]}), encoding="utf-8")
    plain_lines = [{k: v for k, v in x.items() if k != "locked"} for x in before["lines"]]
    again = client.post(url, json={"text": text, "lines": plain_lines}).json()
    assert again["mode"] == "whisper" and again["relistened"] == 1
    relisten.forget(wf)

    # anchors: the stretch between them where lines were not heard is listened to again (once)
    vocals = song_dir / "stems" / "v.wav"
    monkeypatch.setattr(stems_mod, "plan", lambda *a, **k: ([], {"vocals": "stems/v.wav", "voice": "stems/v.wav"}))
    # no anchors: the stretch whose lines were not heard is listened to again, with those lines as the hint
    auto = client.post(url, json={"text": text, "lines": plain_lines}).json()
    assert auto["relisten"] == 1 and auto["job"]["kind"] == "quickmv_relisten"
    asked = client.app.state.jobs._jobs[auto["job"]["id"]].spec.input["windows"][0]
    assert all(lines[i] in asked["prompt"] for i in (2, 3, 4))
    # listened to (and nothing heard): not asked again for the same lines, asked again when the lines change
    relisten.store_file(wf).write_text(json.dumps({"windows": [{**asked, "segments": []}]}), encoding="utf-8")
    assert "job" not in client.post(url, json={"text": text, "lines": plain_lines}).json()
    changed = "\n".join(lines[:3] + [lines[3][:-2] + "呀呀"] + lines[4:])
    other = client.post(url, json={"text": changed}).json()
    assert other["relisten"] == 1          # (the job is the one already waiting: one listen-again job at a time)
    gaps = quick_lyrics.anchored_report(quick_lyrics.plain_lines(changed), segs, [], secs)["gaps"]
    assert "呀呀" in relisten.windows(gaps, wf)[0]["prompt"]
    relisten.forget(wf)
    anchored = [dict(x) for x in before["lines"]]
    anchored[1]["locked"] = anchored[5]["locked"] = True
    first = client.post(url, json={"text": text, "lines": anchored}).json()
    assert first["relisten"] == 1 and first["job"]
    assert json.loads(wf.read_text(encoding="utf-8")) == {"segments": segs}
    spec = client.app.state.jobs._jobs[first["job"]["id"]].spec
    assert first["job"]["kind"] == "quickmv_relisten" and spec.args[-1].endswith("mv_whisper.py")
    job = {"input": spec.input}
    assert job["input"]["voice"] == str(vocals) and job["input"]["out"] == str(relisten.new_file(wf))
    assert job["input"]["windows"][0]["start"] < starts[2] and lines[2] in job["input"]["windows"][0]["prompt"]
    # the worker's answer (as workers/mv_whisper.py writes it), then the page asks again
    heard = [w for i in (2, 3, 4) for w in per_line[i]]
    win = job["input"]["windows"][0]
    relisten.new_file(wf).write_text(json.dumps({"windows": [{**win, "segments": [
        {"start": heard[0]["start"], "end": heard[-1]["end"], "text": "x", "words": heard}]}]}), encoding="utf-8")
    done = client.post(url, json={"text": text, "lines": anchored}).json()
    assert done["mode"] == "anchored" and done["matched"] == 8 and done["anchors"] == 2 and done["relistened"] == 1
    assert [x["start"] for x in done["lines"]] [2:5] == starts[2:5] and done["missing"] == []
    assert done["lines"][1]["locked"] and done["lines"][5]["start"] == anchored[5]["start"]
    # unlocked again: what was heard again still counts
    free = client.post(url, json={"text": text, "lines": plain_lines}).json()
    assert free["mode"] == "whisper" and free["matched"] == 8 and free["relistened"] == 1


def test_mv_page_uses_what_was_heard_again_only_with_anchors(client, root):
    lines, starts, per_line, segs = _missed()
    secs = int(per_line[-1][-1]["end"] + 6)
    sid, song_dir = _song_with_audio(client, root, secs)
    proj = client.post("/api/mv/project/create", json={"song_id": sid, "slug": "rl", "title": "t", "scene_count": 3}).json()["project"]
    w_json = song_dir / "mv" / "rl" / "whisper.json"
    w_json.write_text(json.dumps({"pipeline": align.WHISPER_PIPELINE, "segments": segs, "duration": float(secs),
                                  "lead_requested": False, "audio_file": str(song_dir / "source" / "audio.wav")}), encoding="utf-8")
    body = {"slug": proj["slug"], "lyrics_text": "\n".join(lines), "mode": "whisper_align"}
    first = client.post("/api/mv/paste_lyrics", json=body).json()["project"]
    # heard again earlier: without anchors the MV page does not use it
    heard = [w for i in (2, 3, 4) for w in per_line[i]]
    relisten.store_file(w_json).write_text(json.dumps({"windows": [{"start": per_line[1][-1]["end"], "end": starts[5], "segments": [
        {"start": heard[0]["start"], "end": heard[-1]["end"], "text": "x", "words": heard}]}]}), encoding="utf-8")
    second = client.post("/api/mv/paste_lyrics", json=body).json()["project"]
    assert [(s["start"], s["end"]) for s in second["timeline"]] == [(s["start"], s["end"]) for s in first["timeline"]]
    # with two anchors it does
    tl = second["timeline"]
    lyric = [s for s in tl if s["type"] == "lyric"]
    lyric[1]["locked"] = lyric[5]["locked"] = True
    second["timeline"] = tl
    assert client.post("/api/mv/project/save", json=second).status_code == 200
    third = client.post("/api/mv/paste_lyrics", json=body).json()
    lyric3 = [s for s in third["project"]["timeline"] if s["type"] == "lyric"]
    lead = third["project"]["early_lead_applied"]
    assert lyric3[1]["locked"] and (lyric3[1]["start"], lyric3[1]["end"]) == (lyric[1]["start"], lyric[1]["end"])
    # lines 4 and 5 where they are sung; line 3 starts where the anchor before it ends (the MV page leaves no gaps)
    assert max(abs(s["start"] - (t + lead)) for s, t in zip(lyric3[3:5], starts[3:5])) < 0.011
    assert lyric3[2]["start"] == lyric[1]["end"] and "聽得到歌聲" not in third["warning"]


def test_worker_listens_to_just_the_stretches(tmp_path, monkeypatch):
    """workers/mv_whisper.py with "windows": each stretch cut out of the voice, given to Whisper with its
    lines as the prompt and no silence filter; word times put back on the song's clock."""
    import subprocess
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
    import mv_whisper
    voice = tmp_path / "v.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=30:sample_rate=44100",
                    "-ac", "2", str(voice)], check=True)
    calls = []

    class Model:
        def transcribe(self, clip, **opts):
            calls.append((len(clip), opts))
            w = [SimpleNamespace(word="雨", start=1.0, end=1.4, probability=0.9), SimpleNamespace(word="天", start=1.4, end=1.8, probability=0.8)]
            return iter([SimpleNamespace(start=1.0, end=1.8, text="雨天", words=w)]), SimpleNamespace(duration=len(clip) / 16000)
    monkeypatch.setattr(mv_whisper, "load_model", lambda device: (Model(), "cpu"))
    sent = {}
    monkeypatch.setattr(mv_whisper.protocol, "result", lambda r: sent.update(r))
    monkeypatch.setattr(mv_whisper.protocol, "progress", lambda *a, **k: None)
    out = tmp_path / "w.json.relisten.new.json"
    mv_whisper.relisten({"voice": str(voice), "out": str(out),
                         "windows": [{"start": 5.0, "end": 15.0, "prompt": "第一句，第二句"}, {"start": 20.0, "end": 24.0, "prompt": "第三句"}]}, "cpu")
    got = json.loads(out.read_text(encoding="utf-8"))["windows"]
    assert [c for c, _ in calls] == [160000, 64000]
    assert calls[0][1]["initial_prompt"] == "第一句，第二句" and calls[0][1]["vad_filter"] is False and calls[0][1]["word_timestamps"]
    assert [w["start"] for w in got[0]["segments"][0]["words"]] == [6.0, 6.4] and got[1]["segments"][0]["start"] == 21.0
    assert sent["windows"] == 2 and sent["words"] == 4
