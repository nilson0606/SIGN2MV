"""Lyric picture for a library song: the song's own audio with the pasted lyrics as subtitles.

For songs whose picture has no lyrics (or that have no picture at all), so that sing & record shows
the words. Only the picture is new: source/audio.wav is not touched, so stems, key versions, covers
and takes stay valid.

Input: {"song_dir": "<abs>", "style": "plain"|"overlay", "lines": [{"start", "end", "text"}],
        "lead": seconds a line shows before it is sung, "font": "<abs font file>", "title": str,
        "source_hash": str}
Two pictures:
- "plain": a dark 1920x1080 card with the title, the line in the middle, 10 fps; the audio is
  encoded from source/audio.wav (AAC 192k, as the import does for a song with a picture).
- "overlay": the song's original picture with the line along the bottom, same size and frame rate;
  the audio stream of the original picture file is copied (bit-identical to what was played before).
Output: <song_dir>/lyricvideo/v_<id>.mp4 + info.json, then source/source.json points "video" at it
and remembers the original picture in "video_original" (nothing of the original is changed or removed).
"""
from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path

import protocol
from common import probe, read_json, write_json
from mv_quick import ENCODERS, GPU_LABELS, font_family, run_ffmpeg

MIN_SHOW_S = 0.3
PLAIN_SIZE = (1920, 1080)
PLAIN_FPS = 10       # one still line at a time: more frames only cost encoding time
KEYFRAME_S = 2       # a keyframe every 2 s, so that jumping around in sing & record is quick


def shown_lines(lines: list, lead: float) -> list[tuple[float, float, str]]:
    """When each line is on screen: `lead` seconds before it is sung until its end, never into the
    next line's time (the next line also comes early)."""
    rows = []
    for x in sorted(lines, key=lambda v: float(v["start"])):
        text = str(x.get("text") or "").strip()
        if text:
            rows.append([max(0.0, float(x["start"]) - lead), float(x["end"]), text])
    for a, b in zip(rows, rows[1:]):
        a[1] = min(a[1], b[0])
    return [(st, max(en, st + MIN_SHOW_S), tx) for st, en, tx in rows]


def _units(text: str) -> list[str]:
    """Pieces a row may be broken between: one CJK character, or a word with the spaces after it."""
    out: list[str] = []
    word = ""
    for ch in text:
        wide = ord(ch) >= 0x2E80
        if wide:
            if word:
                out.append(word)
                word = ""
            out.append(ch)
        elif ch == " ":
            word += ch
            out.append(word)
            word = ""
        else:
            word += ch
    if word:
        out.append(word)
    return out


def line_ratio(font_path: str) -> float:
    """libass sizes a font by its line height (ascent + descent), Pillow by its em: ASS size = em * this."""
    from PIL import ImageFont
    asc, desc = ImageFont.truetype(font_path, 200).getmetrics()
    return max(1.0, (asc + desc) / 200.0)


def wrap(text: str, font_path: str, em: int, max_w: int, max_rows: int = 3) -> tuple[list[str], int]:
    """Rows that fit max_w, of about the same width, and the em size used (smaller only when max_rows
    would not hold the line). Done here because libass does not break CJK text that has no spaces."""
    from PIL import ImageFont
    units = _units(text)
    floor = max(10, int(em * 0.55))

    def rows_for(font, limit: float) -> list[str]:
        rows, cur = [], ""
        for u in units:
            if cur and font.getlength((cur + u).rstrip()) * 1.06 > limit:   # 1.06: the subtitle is drawn bold
                rows.append(cur.rstrip())
                cur = u.lstrip()
            else:
                cur += u
        if cur.strip():
            rows.append(cur.rstrip())
        return rows

    while True:
        font = ImageFont.truetype(font_path, em)
        rows = rows_for(font, max_w)
        fits = len(rows) <= max_rows and all(font.getlength(r) * 1.06 <= max_w for r in rows)
        if fits or em <= floor:
            break
        em = max(floor, int(em * 0.9))
    if len(rows) > 1:   # the narrowest limit that needs no more rows: no last row of one character
        limit = font.getlength(text) * 1.06 / len(rows)
        while limit < max_w:
            even = rows_for(font, limit)
            if len(even) <= len(rows):
                rows = even
                break
            limit *= 1.04
    return rows or [text], em


def ass_text(lines: list[tuple[float, float, str]], family: str, font_path: str, w: int, h: int, style: str) -> str:
    def ts(sec: float) -> str:
        return f"{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:05.2f}"

    if style == "plain":
        em, align, margin_v, max_w = round(h * 0.085), 5, 0, int(w * 0.84)
    else:
        em, align, margin_v, max_w = round(min(h * 0.05, w * 0.048)), 2, round(h * 0.06), int(w * 0.9)
    ratio = line_ratio(font_path)
    outline, shadow = round(em * 0.09, 1), round(em * 0.04, 1)
    side = int((w - max_w) / 2)
    head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 2",
            "ScaledBorderAndShadow: yes", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            f"Style: Lyric,{family.replace(',', ' ')},{round(em * ratio)},&H00FFFFFF,&H000000FF,&H000F172A,&H80000000,"
            f"-1,0,0,0,100,100,1,0,1,{outline},{shadow},{align},{side},{side},{margin_v},1",
            "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    body = []
    for st, en, text in lines:
        clean = text.replace("{", "").replace("}", "").replace("\\", "").replace("\n", " ")
        rows, used = wrap(clean, font_path, em, max_w)
        body.append(f"Dialogue: 0,{ts(st)},{ts(en)},Lyric,,0,0,0,,"
                    + (f"{{\\fs{round(used * ratio)}}}" if used != em else "") + "\\N".join(rows))
    return "\n".join(head + body) + "\n"


def plain_background(path: Path, font_path: str, title: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    w, h = PLAIN_SIZE
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    top_c, mid_c, bot_c = (15, 23, 42), (20, 45, 60), (45, 25, 45)
    for y in range(h):
        ratio = y / h
        a, b, f = (top_c, mid_c, ratio / 0.6) if ratio < 0.6 else (mid_c, bot_c, (ratio - 0.6) / 0.4)
        draw.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3)))
    if title:
        size = 44
        font = ImageFont.truetype(font_path, size)
        while font.getlength(title) > w - 240 and size > 24:
            size -= 4
            font = ImageFont.truetype(font_path, size)
        draw.text((120, 84), title, font=font, fill=(148, 163, 184))
    img.save(path)


def _fps(rate: object) -> float:
    """ffprobe's r_frame_rate ("30000/1001") as a number; 30 when it says nothing usable."""
    try:
        num, _, den = str(rate or "").partition("/")
        value = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return 30.0
    return value if 1 <= value <= 120 else 30.0


def encode(inputs: list, graph: str, tail: list, work: Path, seconds: float) -> tuple[str, list[str]]:
    """Graphics card encoders first, then the CPU (same order and settings as the quick MV)."""
    order = list(ENCODERS) if not os.environ.get("SIGN2MV_FORCE_CPU") else ["libx264"]
    gpu_errors: list[str] = []
    err = ""
    for enc in order:
        args = ["-hide_banner", "-loglevel", "error", "-nostdin", "-y", *inputs, "-filter_complex", graph,
                "-map", "[v]", *tail, *ENCODERS[enc], "-movflags", "+faststart", "-progress", "pipe:1", "result.mp4"]
        rc, err = run_ffmpeg(args, work, seconds, 3, 96)
        if rc == 0 and (work / "result.mp4").is_file():
            return enc, gpu_errors
        (work / "result.mp4").unlink(missing_ok=True)
        protocol.log(f"{enc} failed, trying the next encoder: {err[-300:]}")
        if enc in GPU_LABELS:
            gpu_errors.append(f"{GPU_LABELS[enc]}: {err.strip()[-200:]}")
            nxt = order[order.index(enc) + 1] if order.index(enc) + 1 < len(order) else ""
            protocol.progress(3, "encode", f"{GPU_LABELS[enc]} 顯示卡編碼失敗，改用 "
                              + (f"{GPU_LABELS[nxt]} 顯示卡" if nxt in GPU_LABELS else "CPU 編碼，會比較慢"))
    protocol.fail("lyricvideo_failed", err)
    raise SystemExit(1)


def main() -> None:
    data = protocol.read_input()
    song_dir = Path(data["song_dir"])
    out_dir = song_dir / "lyricvideo"
    work = out_dir / f"work{os.getpid()}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    started = time.time()
    try:
        protocol.progress(0, "quickmv_prepare", "")
        src_json = song_dir / "source" / "source.json"
        rec = read_json(src_json)
        if not isinstance(rec, dict) or not rec.get("audio"):
            protocol.fail("song_has_no_audio", "")
        audio = song_dir / rec["audio"]
        active = isinstance(rec.get("lyric_video"), dict)
        orig = (rec.get("video_original") or {}) if active else {"video": rec.get("video"), "video_size": rec.get("video_size")}
        picture = song_dir / orig["video"] if orig.get("video") else None
        style = "overlay" if data.get("style") == "overlay" else "plain"
        if style == "overlay" and not (picture and picture.is_file()):
            protocol.fail("lyricvideo_no_picture", "")
        lead = max(0.0, min(3.0, float(data.get("lead") or 0)))
        lines = shown_lines([x for x in (data.get("lines") or []) if isinstance(x, dict)], lead)
        if not lines:
            protocol.fail("lyricvideo_lines", "")
        font = Path(data.get("font") or "")
        if not font.is_file():
            protocol.fail("quickmv_font_missing", str(font))
        shutil.copyfile(font, work / "font.ttc")
        family = font_family(str(work / "font.ttc"))

        if style == "overlay":
            info = probe(picture)
            v = info.get("video") or {}
            w, h, seconds = int(v.get("width") or 0), int(v.get("height") or 0), float(info.get("duration") or 0)
            if w < 16 or h < 16 or seconds <= 0:
                protocol.fail("lyricvideo_no_picture", f"{w}x{h} {seconds}s")
            inputs = ["-i", str(picture)]
            graph = "[0:v]subtitles=filename=lyrics.ass:fontsdir=.,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p[v]"
            fps = _fps(v.get("r_frame_rate"))
            if info.get("audio"):
                tail = ["-map", "0:a:0", "-c:a", "copy"]
            else:   # a picture file without sound (not made by the import): use the song audio
                inputs += ["-i", str(audio)]
                tail = ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            w, h = PLAIN_SIZE
            seconds = float(probe(audio).get("duration") or 0)
            if seconds <= 0:
                protocol.fail("song_has_no_audio", "")
            plain_background(work / "background.png", str(work / "font.ttc"), str(data.get("title") or ""))
            inputs = ["-framerate", str(PLAIN_FPS), "-i", "background.png", "-i", str(audio)]
            graph = "[0:v]loop=loop=-1:size=1,subtitles=filename=lyrics.ass:fontsdir=.,format=yuv420p[v]"
            tail = ["-map", "1:a:0", "-t", f"{seconds:.3f}", "-r", str(PLAIN_FPS), "-c:a", "aac", "-b:a", "192k"]
            fps = float(PLAIN_FPS)
        tail += ["-g", str(max(2, round(fps * KEYFRAME_S)))]
        (work / "lyrics.ass").write_text(ass_text(lines, family, str(work / "font.ttc"), w, h, style), encoding="utf-8")

        protocol.progress(3, "quickmv_render", "")
        used, gpu_errors = encode(inputs, graph, tail, work, seconds)
        made = probe(work / "result.mp4")
        mv, ma = made.get("video") or {}, made.get("audio")
        if not mv or not ma or abs(float(made.get("duration") or 0) - seconds) > 1.5:
            protocol.fail("lyricvideo_failed", f"result: video={bool(mv)} audio={bool(ma)} "
                          f"{made.get('duration')}s, expected {seconds:.2f}s")

        protocol.progress(98, "save", "")
        # the song may not have changed underneath (the job keeps the song busy; this is the last check)
        now = read_json(src_json)
        if not isinstance(now, dict) or now.get("source_hash") != rec.get("source_hash") or now.get("audio") != rec.get("audio"):
            protocol.fail("lyricvideo_source_changed", "")
        name = f"v_{uuid.uuid4().hex[:10]}.mp4"
        os.replace(work / "result.mp4", out_dir / name)
        rel = f"lyricvideo/{name}"
        size = [int(mv.get("width") or w), int(mv.get("height") or h)]
        info_out = {"schema_version": 1, "file": rel, "style": style, "lead": round(lead, 2), "lines": len(lines),
                    "video_size": size, "duration": round(float(made.get("duration") or seconds), 2),
                    "bytes": (out_dir / name).stat().st_size, "encoder": used,
                    **({"gpu_error": " | ".join(gpu_errors)} if gpu_errors and used == "libx264" else {}),
                    "source_hash": rec.get("source_hash"), "render_s": round(time.time() - started, 1),
                    "made_at": time.time()}
        write_json(out_dir / "info.json", info_out)
        if not active:
            now["video_original"] = {"video": now.get("video"), "video_size": now.get("video_size")}
        now["video"], now["video_size"] = rel, size
        now["lyric_video"] = {k: info_out[k] for k in ("file", "style", "lead", "lines", "made_at")}
        write_json(src_json, now)
        for old in out_dir.glob("v_*.mp4"):   # earlier lyric pictures of this song (a player may still hold one)
            if old.name != name:
                try:
                    old.unlink()
                except OSError:
                    pass
        shutil.rmtree(work, ignore_errors=True)
        protocol.progress(100, "done", "")
        protocol.result(info_out)
    except SystemExit:
        shutil.rmtree(work, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(work, ignore_errors=True)
        protocol.fail("lyricvideo_failed", f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
