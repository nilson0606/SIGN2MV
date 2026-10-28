"""Pitch-only key change of a set of WAV files (Rubber Band via ffmpeg).

Input: {"files": [{"src": "<abs wav>", "dst": "<abs wav>"}], "semitones": -12..12, "out_dir": "<abs>", "info": {...}}
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


def main() -> None:
    data = protocol.read_input()
    semis = int(data["semitones"])
    if not -12 <= semis <= 12 or semis == 0:
        protocol.fail("invalid_key")
    out_dir = Path(data["out_dir"])
    if (out_dir / "info.json").is_file():
        protocol.result({"out_dir": str(out_dir), "cached": True})
        return
    tmp = out_dir.with_name(out_dir.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    files = data["files"]
    ratio = 2 ** (semis / 12)
    try:
        for i, item in enumerate(files):
            src = Path(item["src"])
            info = sf.info(str(src))
            duration = info.frames / info.samplerate
            protocol.progress(i * 100 / len(files), "key", Path(item["dst"]).name)
            af = (f"rubberband=tempo=1:pitch={ratio:.12f}:channels=together:pitchq=quality,"
                  f"apad,atrim=duration={duration:.9f}")
            run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", src, "-af", af, "-ar", str(info.samplerate),
                 "-c:a", "pcm_f32le", tmp / Path(item["dst"]).name], timeout=1800)
        write_json(tmp / "info.json", {"schema_version": 1, "semitones": semis, **(data.get("info") or {}),
                                       "files": [Path(f["dst"]).name for f in files], "created_at": time.time()})
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
        os.replace(tmp, out_dir)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(tmp, ignore_errors=True)
        msg = str(exc)
        protocol.fail("rubberband_missing" if "rubberband" in msg.lower() and "no such filter" in msg.lower()
                      else "key_shift_failed", msg[-800:])
    protocol.progress(100, "done", "")
    protocol.result({"out_dir": str(out_dir)})


if __name__ == "__main__":
    main()
