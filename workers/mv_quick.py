"""Quick MV: an audio-reactive title card (the "製作 MV" video of sign_record).

Input: {"audio": "<abs audio file>", "out_dir": "<abs final folder>", "font": "<abs font file>",
        "bold_font": "<abs font file>", "style": "card"|"studio", "resolution": "1080p"|"720p",
        "title": str, "artist_line": str, "heading": str, "footer": str,
        "subtitle": str, "badge": str, "credits": str, "info": {...}}
Output folder: video.mp4 + info.json, written to out_dir + ".tmp<pid>" and renamed at the end.

Two pictures:
- "card" is sign_record's mv-server.mjs filter unchanged: dark card 1920x1080 at 30 fps,
  teal accent bar and letter-spaced heading, white title, grey artist line, a 1600x300
  frequency bar graph (showfreqs, log frequency, sqrt amplitude) and a footer line.
  User text goes through text files (textfile=, expansion=none), never into filter syntax.
  720p scales the finished picture down.
- "studio" is AI_COVER_MV's 12_generate_dynamic_mv.py: a gradient card with title, subtitle,
  credits line, a badge at the top right and a vinyl record in the middle (drawn with Pillow),
  and a 160 px bar spectrum along the bottom at 60 fps; 720p draws everything at 2/3 size.
Encoding uses NVENC when the graphics card offers it, else libx264 like the originals.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import protocol
from common import NO_WINDOW, ffmpeg, write_json

MAX_SECONDS = 1200   # 20 minutes; library imports are limited to 15


def text_size(text: str, max_size: int, width: int) -> int:
    """Same as sign_record: CJK characters count 1, others 0.6 of the font size."""
    units = sum(1 if ord(c) > 255 else 0.6 for c in text) or 1
    return int(min(max_size, width // units))


def build_filter(title: str, artist_line: str) -> str:
    def text(file: str, size: int, y: int, color: str) -> str:
        return (f"drawtext=fontfile=font.ttc:textfile={file}:expansion=none:fontsize={size}:"
                f"fontcolor={color}:x=(w-text_w)/2:y={y}")
    return ("[0:a]showfreqs=s=1600x300:mode=bar:ascale=sqrt:fscale=log:colors=0x7fe0d6:rate=30:win_size=2048:"
            "averaging=3,format=rgba[bars];"
            "color=c=0x101d2c:s=1920x1080:r=30[base];[base]drawbox=x=160:y=150:w=90:h=6:color=0x7fe0d6:t=fill,"
            f"{text('heading.txt', 28, 180, '0x7fe0d6')},{text('title.txt', text_size(title, 84, 1580), 305, 'white')},"
            f"{text('artist.txt', text_size(artist_line, 42, 1500), 435, '0xb6c6d8')},"
            f"drawbox=x=160:y=945:w=1600:h=2:color=0x30475d:t=fill,{text('footer.txt', 22, 995, '0x8196ac')}[card];"
            "[card][bars]overlay=160:610:shortest=1,format=yuv420p[v]")


def build_card_filter(title: str, artist_line: str, resolution: str) -> str:
    graph = build_filter(title, artist_line)
    if resolution == "720p":
        graph = graph.replace("format=yuv420p[v]", "scale=1280:720:flags=bicubic,format=yuv420p[v]")
    return graph


def fit_font(draw, text: str, path: str, size: int, max_w: int, min_size: int):
    from PIL import ImageFont
    while True:
        font = ImageFont.truetype(path, size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_w or size <= min_size:
            return font
        size = max(min_size, int(size * 0.92))


def studio_background(path: Path, font: str, bold: str, title: str, subtitle: str, badge: str, credits: str,
                      resolution: str) -> None:
    """AI_COVER_MV's create_background_artwork (same colours, positions and sizes)."""
    import re
    from PIL import Image, ImageDraw, ImageFont
    w, h, scale = (1280, 720, 720.0 / 1080.0) if resolution == "720p" else (1920, 1080, 1.0)
    img = Image.new("RGB", (w, h), (14, 20, 35))
    draw = ImageDraw.Draw(img)
    top_c, mid_c, bot_c = (15, 23, 42), (20, 45, 60), (45, 25, 45)
    for y in range(h):
        ratio = y / h
        if ratio < 0.6:
            a, b, f = top_c, mid_c, ratio / 0.6
        else:
            a, b, f = mid_c, bot_c, (ratio - 0.6) / 0.4
        draw.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3)))
    clean_badge = re.sub(r"[\U00010000-\U0010ffff]|[\u2000-\u2bff]|[\ufe00-\ufe0f]", "", badge).strip()
    font_badge = ImageFont.truetype(bold, max(14, int(32 * scale)))
    bw = bh = 0
    if clean_badge:
        bbox = draw.textbbox((0, 0), clean_badge, font=font_badge)
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # the title may not run into the badge (the old card did not check; long titles overlapped)
    room = w - int(120 * scale) - (bw + int(80 * scale) if clean_badge else 0) - int(120 * scale) - int(20 * scale)
    font_title = fit_font(draw, title, bold, max(28, int(76 * scale)), room, max(20, int(40 * scale)))
    font_sub = fit_font(draw, subtitle, font, max(14, int(30 * scale)), room, max(12, int(20 * scale)))
    font_credits = fit_font(draw, credits, font, max(11, int(24 * scale)), w - int(250 * scale), max(10, int(16 * scale)))
    draw.text((int(120 * scale), int(100 * scale)), title, font=font_title, fill=(255, 255, 255))
    if subtitle:
        draw.text((int(125 * scale), int(200 * scale)), subtitle, font=font_sub, fill=(52, 211, 153))
    if credits:
        draw.text((int(125 * scale), int(250 * scale)), credits, font=font_credits, fill=(148, 163, 184))
    if clean_badge:
        bx, by = w - int(120 * scale) - bw - int(40 * scale), int(110 * scale)
        draw.rounded_rectangle([bx, by, bx + bw + int(40 * scale), by + bh + int(24 * scale)], radius=max(8, int(16 * scale)),
                               fill=(16, 185, 129, 60), outline=(52, 211, 153), width=max(1, int(2 * scale)))
        draw.text((bx + int(20 * scale), by + int(10 * scale)), clean_badge, font=font_badge, fill=(255, 255, 255))
    cx, cy = w // 2, int((1080 // 2 + 30) * scale)
    cr = int(220 * scale)
    step, halo_w = max(1, int(2 * scale)), int(40 * scale)
    for halo in range(cr + halo_w, cr, -step):
        draw.ellipse([cx - halo, cy - halo, cx + halo, cy + halo], outline=(16, 185, 129), width=max(1, int(2 * scale)))
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(15, 23, 42), outline=(52, 211, 153), width=max(2, int(4 * scale)))
    draw.ellipse([cx - int(80 * scale), cy - int(80 * scale), cx + int(80 * scale), cy + int(80 * scale)], fill=(22, 163, 74))
    draw.ellipse([cx - int(20 * scale), cy - int(20 * scale), cx + int(20 * scale), cy + int(20 * scale)], fill=(255, 255, 255))
    img.save(path)


def font_family(path: str) -> str:
    try:
        from PIL import ImageFont
        return ImageFont.truetype(path, 20).getname()[0] or "Microsoft YaHei"
    except Exception:  # noqa: BLE001
        return "Microsoft YaHei"


def lyrics_ass(lines: list, family: str, resolution: str) -> str:
    """Old parse_lyrics_to_ass look: white, dark outline, bottom centre, 310 px from the bottom."""
    scale = 720.0 / 1080.0 if resolution == "720p" else 1.0
    rx, ry = (1280, 720) if resolution == "720p" else (1920, 1080)

    def ts(sec: float) -> str:
        return f"{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:05.2f}"

    head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {rx}", f"PlayResY: {ry}", "WrapStyle: 2", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            f"Style: MV_Lyric,{family.replace(',', ' ')},{int(46 * scale)},&H00FFFFFF,&H000000FF,&H000F172A,"
            f"&H80000000,-1,0,0,0,100,100,1,0,1,{round(3.5 * scale, 1)},{round(1.5 * scale, 1)},2,80,80,"
            f"{int(310 * scale)},1",
            "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    body = [f"Dialogue: 0,{ts(float(x['start']))},{ts(float(x['end']))},MV_Lyric,,0,0,0,,"
            + str(x["text"]).replace("{", "").replace("}", "").replace("\\", "").replace("\n", " ")
            for x in lines]
    return "\n".join(head + body) + "\n"


def build_studio_filter(resolution: str, subtitles: bool = False) -> str:
    """Input 0: the background picture (looped), input 1: the audio. Subtitles: lyrics.ass + font.ttc
    in the working folder (relative names, nothing user-typed in the filter)."""
    scale = 720.0 / 1080.0 if resolution == "720p" else 1.0
    wave_w, wave_h, wave_x, wave_y = int(1680 * scale), int(160 * scale), int(120 * scale), int(880 * scale)
    return ("[1:a]aformat=channel_layouts=mono,"
            "showfreqs=s=210x80:rate=60:mode=bar:ascale=cbrt:fscale=log:win_size=2048:colors=0x34d399,"
            f"format=rgba,colorkey=black:0.05:0.0,scale={wave_w}:{wave_h}:flags=neighbor[waves];"
            f"[0:v][waves]overlay=x={wave_x}:y={wave_y}:shortest=1,"
            + ("subtitles=filename=lyrics.ass:fontsdir=.," if subtitles else "") + "format=yuv420p[v]")


ENCODERS = {
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "22", "-b:v", "0"],
    "libx264": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-threads", "4"],
}


def run_ffmpeg(args: list, cwd: Path, seconds: float, lo: float, hi: float) -> tuple[int, str]:
    proc = subprocess.Popen([ffmpeg(), *args], cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    err: list[str] = []

    def read_err() -> None:
        for raw in proc.stderr:
            err.append(raw.decode("utf-8", "replace"))
            del err[:-40]
    import threading
    t = threading.Thread(target=read_err, daemon=True)
    t.start()
    last = -1.0
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("out_time_us="):
            try:
                done = int(line.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            pct = lo + (hi - lo) * max(0.0, min(1.0, done / max(seconds, 0.1)))
            if pct - last >= 0.5:
                last = pct
                protocol.progress(round(pct, 1), "quickmv_render", "")
    rc = proc.wait()
    t.join(timeout=5)
    return rc, "".join(err)[-1500:]


def main() -> None:
    data = protocol.read_input()
    out_dir = Path(data["out_dir"])
    tmp = out_dir.with_name(f"{out_dir.name}.tmp{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    started = time.time()
    try:
        protocol.progress(0, "quickmv_prepare", "")
        res = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", data["audio"],
                              "-map", "0:a:0", "-vn", "-t", str(MAX_SECONDS + 1), "-ar", "48000", "-c:a", "pcm_s16le",
                              str(tmp / "source.wav")], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", creationflags=NO_WINDOW)
        if res.returncode != 0:
            protocol.fail("quickmv_audio_failed", res.stderr[-800:])
        import soundfile as sf
        seconds = sf.info(str(tmp / "source.wav")).duration
        if not 1 <= seconds <= MAX_SECONDS:
            protocol.fail("quickmv_length", f"{seconds:.1f} s")
        font = Path(data.get("font") or "")
        if not font.is_file():
            protocol.fail("quickmv_font_missing", str(font))
        shutil.copyfile(font, tmp / "font.ttc")
        for name, value in (("title.txt", data["title"]), ("artist.txt", data["artist_line"]),
                            ("heading.txt", data["heading"]), ("footer.txt", data["footer"])):
            (tmp / name).write_text(value, encoding="utf-8")
        style = "studio" if data.get("style") == "studio" else "card"
        resolution = "720p" if data.get("resolution") == "720p" else "1080p"
        if style == "studio":
            bold = Path(data.get("bold_font") or font)
            studio_background(tmp / "background.png", str(tmp / "font.ttc"), str(bold if bold.is_file() else tmp / "font.ttc"),
                              data["title"], data.get("subtitle") or "", data.get("badge") or "",
                              data.get("credits") or "", resolution)
            lines = [x for x in (data.get("lyrics") or []) if isinstance(x, dict) and x.get("text")]
            if lines:
                (tmp / "lyrics.ass").write_text(lyrics_ass(lines, font_family(str(tmp / "font.ttc")), resolution),
                                                encoding="utf-8")
            graph = build_studio_filter(resolution, bool(lines))
            inputs = ["-loop", "1", "-framerate", "60", "-i", "background.png", "-i", "source.wav"]
            audio_map, fps = "1:a:0", "60"
        else:
            graph = build_card_filter(data["title"], data["artist_line"], resolution)
            inputs = ["-i", "source.wav"]
            audio_map, fps = "0:a:0", "30"
        order = ["h264_nvenc", "libx264"] if not os.environ.get("SIGN2MV_FORCE_CPU") else ["libx264"]
        used, rc, err = "", 1, ""
        for enc in order:
            args = ["-hide_banner", "-loglevel", "error", "-nostdin", "-y", *inputs,
                    "-filter_complex", graph, "-map", "[v]", "-map", audio_map, "-t", f"{seconds:.3f}",
                    *ENCODERS[enc], "-r", fps, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                    "-progress", "pipe:1", "result.mp4"]
            rc, err = run_ffmpeg(args, tmp, seconds, 2, 97)
            if rc == 0 and (tmp / "result.mp4").is_file():
                used = enc
                break
            protocol.log(f"{enc} failed, trying the next encoder: {err[-300:]}")
            (tmp / "result.mp4").unlink(missing_ok=True)
        if not used:
            protocol.fail("quickmv_failed", err)
        protocol.progress(98, "save", "")
        final = tmp / "video.mp4"
        os.replace(tmp / "result.mp4", final)
        for name in ("source.wav", "font.ttc", "title.txt", "artist.txt", "heading.txt", "footer.txt", "background.png", "lyrics.ass"):
            (tmp / name).unlink(missing_ok=True)
        info = {"schema_version": 1, **(data.get("info") or {}), "title": data["title"], "artist_line": data["artist_line"],
                "style": style, "resolution": resolution, "fps": int(fps),
                **({"subtitle": data.get("subtitle") or "", "badge": data.get("badge") or "",
                    "credits": data.get("credits") or "", "lyric_lines": len(data.get("lyrics") or [])}
                   if style == "studio" else {}),
                "duration": round(seconds, 2), "bytes": final.stat().st_size, "encoder": used,
                "render_s": round(time.time() - started, 1), "created_at": time.time()}
        write_json(tmp / "info.json", info)
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
        os.replace(tmp, out_dir)
        protocol.progress(100, "done", "")
        protocol.result({"id": out_dir.name, **info})
    except SystemExit:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(tmp, ignore_errors=True)
        protocol.fail("quickmv_failed", str(exc)[-800:])


if __name__ == "__main__":
    main()
