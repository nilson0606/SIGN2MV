"""Quick MV: an audio-reactive title card (the "製作 MV" video of sign_record).

Input: {"audio": "<abs audio file>", "out_dir": "<abs final folder>", "font": "<abs font file>",
        "title": str, "artist_line": str, "heading": str, "footer": str, "info": {...}}
Output folder: video.mp4 + info.json, written to out_dir + ".tmp<pid>" and renamed at the end.

The picture is sign_record's mv-server.mjs filter unchanged: dark card 1920x1080 at 30 fps,
teal accent bar and letter-spaced heading, white title, grey artist line, a 1600x300
frequency bar graph (showfreqs, log frequency, sqrt amplitude) and a footer line.
User text goes through text files (textfile=, expansion=none), never into filter syntax.
Encoding uses NVENC when the graphics card offers it, else libx264 like the original.
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
        graph = build_filter(data["title"], data["artist_line"])
        order = ["h264_nvenc", "libx264"] if not os.environ.get("SIGN2MV_FORCE_CPU") else ["libx264"]
        used, rc, err = "", 1, ""
        for enc in order:
            args = ["-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", "source.wav",
                    "-filter_complex", graph, "-map", "[v]", "-map", "0:a:0", "-t", f"{seconds:.3f}",
                    *ENCODERS[enc], "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
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
        for name in ("source.wav", "font.ttc", "title.txt", "artist.txt", "heading.txt", "footer.txt"):
            (tmp / name).unlink(missing_ok=True)
        info = {"schema_version": 1, **(data.get("info") or {}), "title": data["title"], "artist_line": data["artist_line"],
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
