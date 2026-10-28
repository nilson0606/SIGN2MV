"""Import a song: YouTube (audio + video up to 1080p) or a local audio/video file.

Input JSON:
  {"song_dir": "...", "mode": "youtube", "url": "https://..."}
  {"song_dir": "...", "mode": "file", "path": "<uploaded file>", "original_name": "x.mp4"}
Output: writes <song_dir>/source/ and returns the "source" record for song.json.
  source/original.<ext>   the file as received (local import only)
  source/audio.wav        44.1 kHz stereo float32, used by every engine
  source/video.mp4|webm   video without audio, browser-playable (if any)
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import protocol
from common import ffmpeg, probe, run, sha256_file, write_json, NO_WINDOW

MAX_SECONDS = 15 * 60
MAX_LOCAL_BYTES = 2 * 1024 ** 3


def normalize_youtube(url: str) -> tuple[str, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("invalid_url")
    host = (parsed.hostname or "").lower()
    vid = ""
    if host == "youtu.be":
        vid = parsed.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            vid = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            vid = parsed.path.split("/")[2]
    else:
        raise ValueError("not_youtube")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid or ""):
        raise ValueError("invalid_youtube_id")
    return vid, f"https://www.youtube.com/watch?v={vid}"


def ipv6_ok(timeout: float = 2.0) -> bool:
    """Bounded IPv6 check (some networks hang on IPv6; then use IPv4 at once)."""
    result: "queue.Queue[bool]" = queue.Queue()
    deadline = time.monotonic() + timeout

    def probe6() -> None:
        try:
            for fam, kind, proto, _, addr in socket.getaddrinfo("www.youtube.com", 443, socket.AF_INET6, socket.SOCK_STREAM):
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                try:
                    with socket.socket(fam, kind, proto) as s:
                        s.settimeout(left)
                        s.connect(addr)
                    result.put(True)
                    return
                except OSError:
                    continue
        except OSError:
            pass
        result.put(False)

    threading.Thread(target=probe6, daemon=True).start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        return False


def is_network_failure(text: str) -> bool:
    low = text.lower()
    if re.search(r"\b(403|429)\b|sign in|private video|not available", low):
        return False
    return bool(re.search(r"timed? out|timeout|unreachable|no route to host|connection (refused|reset|aborted)|"
                          r"failed to establish|unable to resolve|getaddrinfo failed|name or service not known", low))


def ytdlp(args: list[str], family: str, stage: str, lo: float, hi: float) -> None:
    cmd = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist", "--no-cache-dir",
           "--js-runtimes", "deno", "--socket-timeout", "20", "--retries", "3", "--newline",
           "--progress-template", "download:PCT %(progress._percent_str)s", f"--force-{family}"] + args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    tail: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        tail.append(line.rstrip())
        del tail[:-30]
        m = re.search(r"PCT\s+([\d.]+)%", line)
        if m:
            protocol.progress(lo + (hi - lo) * float(m.group(1)) / 100, stage, family.upper())
    rc = proc.wait(timeout=60)
    if rc:
        text = re.sub(r"https?://\S+", "[url]", "\n".join(tail[-12:]))
        raise RuntimeError(text)


def to_wav(src: Path, dst: Path) -> None:
    run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", src, "-map", "0:a:0", "-vn",
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_f32le", dst], timeout=1800)


def make_playable_video(src: Path, dest_dir: Path, info: dict, audio_wav: Path) -> Path | None:
    """video.mp4 = the video (max 1080p, browser-playable) + the song audio (AAC).

    The audio is muxed in so that the player's clock is the music itself; there is
    nothing to keep in sync. The lossless song audio stays in audio.wav.
    """
    v = info.get("video")
    if not v:
        return None
    out = dest_dir / "video.mp4"
    audio_args = ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]
    codec = v.get("codec_name", "")
    height = int(v.get("height") or 0)
    if codec in ("h264", "vp9") and height <= 1080:
        try:
            run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", src, "-i", audio_wav, "-map", "0:v:0",
                 "-c:v", "copy", *audio_args, out], timeout=1800)
            return out
        except RuntimeError:
            out.unlink(missing_ok=True)
    # Re-encode to H.264 (GPU encoder if present, else CPU), max 1080p.
    scale = "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    for codec_args in (["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"],
                       ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"]):
        try:
            run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", src, "-i", audio_wav, "-map", "0:v:0",
                 "-vf", scale, *codec_args, "-pix_fmt", "yuv420p", *audio_args, out], timeout=3600)
            return out
        except RuntimeError:
            out.unlink(missing_ok=True)
    return None


def import_youtube(song_dir: Path, url: str) -> dict:
    vid, clean = normalize_youtube(url)
    src = song_dir / "source"
    work = song_dir / "source.importing"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    protocol.progress(1, "network", "")
    family = "ipv6" if ipv6_ok() else "ipv4"
    common = ["--match-filter", f"duration <= {MAX_SECONDS} & !is_live & !is_upcoming", "--write-info-json"]

    def attempt(fam: str) -> None:
        ytdlp(common + ["-f", "bestaudio/best", "-o", str(work / "audio_dl.%(ext)s"), clean], fam, "download_audio", 2, 45)
        try:
            ytdlp(["--match-filter", f"duration <= {MAX_SECONDS} & !is_live",
                   "-f", "bv*[height<=1080][vcodec^=avc1]/bv*[height<=1080][vcodec^=vp09]/bv*[height<=1080]",
                   "-o", str(work / "video_dl.%(ext)s"), clean], fam, "download_video", 45, 85)
        except RuntimeError as exc:  # video is optional: audio-only songs still work
            protocol.log(f"video download failed: {exc}")

    try:
        attempt(family)
    except RuntimeError as exc:
        if family == "ipv6" and is_network_failure(str(exc)):
            for f in work.glob("*"):
                f.unlink()
            attempt("ipv4")
        else:
            raise
    audio_dl = next((p for p in work.glob("audio_dl.*") if p.suffix not in (".json", ".part")), None)
    if audio_dl is None:
        raise RuntimeError("no audio file was downloaded")
    info_json = next(work.glob("audio_dl*.info.json"), None)
    meta = json.loads(info_json.read_text(encoding="utf-8")) if info_json else {}
    protocol.progress(86, "convert", "")
    to_wav(audio_dl, work / "audio.wav")
    video_dl = next((p for p in work.glob("video_dl.*") if p.suffix not in (".json", ".part")), None)
    video = None
    if video_dl:
        protocol.progress(92, "video", "")
        video = make_playable_video(video_dl, work, probe(video_dl), work / "audio.wav")
        video_dl.unlink(missing_ok=True)
    audio_dl.unlink(missing_ok=True)
    for j in work.glob("*.info.json"):
        j.unlink()
    record = finish(song_dir, work, {
        "source_hash": "yt:" + vid,
        "type": "youtube", "url": clean, "video_id": vid,
        "youtube_title": str(meta.get("title") or "")[:300],
        "uploader": str(meta.get("uploader") or "")[:200],
        "original": None,
    }, video)
    return record


def import_file(song_dir: Path, path: Path, original_name: str) -> dict:
    if not path.is_file():
        raise ValueError("upload_missing")
    if path.stat().st_size > MAX_LOCAL_BYTES:
        raise ValueError("file_too_large")
    info = probe(path)
    if not info["audio"]:
        raise ValueError("no_audio_stream")
    if info["duration"] <= 0 or info["duration"] > MAX_SECONDS + 1:
        raise ValueError("too_long")
    work = song_dir / "source.importing"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    ext = (Path(original_name).suffix or path.suffix or ".bin").lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,5}", ext):
        ext = ".bin"
    original = work / f"original{ext}"
    shutil.move(str(path), original)
    protocol.progress(10, "hash", "")
    digest = sha256_file(original)
    protocol.progress(30, "convert", "")
    to_wav(original, work / "audio.wav")
    video = None
    if info["video"]:
        protocol.progress(60, "video", "")
        video = make_playable_video(original, work, info, work / "audio.wav")
    record = finish(song_dir, work, {
        "source_hash": "sha256:" + digest,
        "type": "video" if video else "audio",
        "original": f"source/{original.name}",
        "original_name": original_name[:260],
    }, video)
    return record


def finish(song_dir: Path, work: Path, record: dict, video: Path | None) -> dict:
    audio = work / "audio.wav"
    info = probe(audio)
    if info["duration"] <= 0:
        raise RuntimeError("converted audio is empty")
    record.update({
        "audio": "source/audio.wav",
        "video": f"source/{video.name}" if video else None,
        "duration": round(info["duration"], 3),
        "imported_at": time.time(),
    })
    if video:
        vinfo = probe(video).get("video") or {}
        record["video_size"] = [vinfo.get("width"), vinfo.get("height")]
    record["schema_version"] = 1
    write_json(work / "source.json", record)
    target = song_dir / "source"
    if target.exists():
        old = song_dir / "source.old"
        shutil.rmtree(old, ignore_errors=True)
        os.replace(target, old)
        shutil.rmtree(old, ignore_errors=True)
    os.replace(work, target)
    return record


def main() -> None:
    data = protocol.read_input()
    song_dir = Path(data["song_dir"])
    try:
        if data.get("mode") == "youtube":
            record = import_youtube(song_dir, data.get("url", ""))
        else:
            record = import_file(song_dir, Path(data["path"]), data.get("original_name", "file"))
    except ValueError as exc:
        shutil.rmtree(song_dir / "source.importing", ignore_errors=True)
        protocol.fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(song_dir / "source.importing", ignore_errors=True)
        protocol.fail("import_failed", str(exc)[-1500:])
    protocol.progress(100, "done", "")
    protocol.result(record)


if __name__ == "__main__":
    main()
