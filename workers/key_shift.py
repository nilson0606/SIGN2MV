"""Pitch-only key change of a set of WAV files (Rubber Band via ffmpeg).

Input: {"semitones": -12..12, "items": [{"src", "dst", "out_dir", "info"}]}
  one item per track; each track has its own folder keys/<hash of source>_<p|m><n>/
  (app/stems.key_track) so every workspace shares the same key copies.
tempo=1 keeps every song-time boundary; the output is padded/trimmed to the
exact source length. Output is written to out_dir + ".tmp" and renamed at the end.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import soundfile as sf

import protocol
from common import ffmpeg, run, write_json


def shift_files(files: list[dict], semis: int, out_dir: Path, info: dict, report=lambda pct: None) -> None:
    if not -12 <= semis <= 12 or semis == 0:
        raise ValueError("invalid_key")
    # unique scratch name: the library page and a cover job may shift the same track at the same time
    tmp = out_dir.with_name(f"{out_dir.name}.tmp{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    ratio = 2 ** (semis / 12)
    try:
        for i, item in enumerate(files):
            src = Path(item["src"])
            sinfo = sf.info(str(src))
            duration = sinfo.frames / sinfo.samplerate
            report(i * 100 / len(files))
            af = (f"rubberband=tempo=1:pitch={ratio:.12f}:channels=together:pitchq=quality,"
                  f"apad,atrim=duration={duration:.9f}")
            run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", src, "-af", af, "-ar", str(sinfo.samplerate),
                 "-c:a", "pcm_f32le", tmp / Path(item["dst"]).name], timeout=1800)
        write_json(tmp / "info.json", {"schema_version": 1, "semitones": semis, **(info or {}),
                                       "files": [Path(f["dst"]).name for f in files], "created_at": time.time()})
        if (out_dir / "info.json").is_file():   # finished by the other job meanwhile
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
            os.replace(tmp, out_dir)
        report(100)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def shift_items(items: list[dict], semis: int, report=lambda pct: None) -> int:
    """Make the key copy of every item that does not exist yet. Returns how many were made."""
    todo = [it for it in items if not (Path(it["out_dir"]) / "info.json").is_file()]
    for i, it in enumerate(todo):
        shift_files([{"src": it["src"], "dst": it["dst"]}], semis, Path(it["out_dir"]), it.get("info") or {},
                    lambda pct, i=i: report((i + pct / 100) * 100 / len(todo)))
    return len(todo)


def main() -> None:
    data = protocol.read_input()
    semis = int(data["semitones"])
    items = data.get("items") or []
    try:
        shift_items(items, semis, lambda pct: protocol.progress(round(pct, 1), "key", ""))
    except ValueError as exc:
        protocol.fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        protocol.fail("rubberband_missing" if "rubberband" in msg.lower() and "no such filter" in msg.lower()
                      else "key_shift_failed", msg[-800:])
    protocol.progress(100, "done", "")
    protocol.result({"files": [it["dst"] for it in items]})


if __name__ == "__main__":
    main()
