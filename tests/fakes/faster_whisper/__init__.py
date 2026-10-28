"""Test double for faster-whisper (the real model cannot be downloaded in the test sandbox).

Produces one word per second of audio ("一", "二", ... cycling), timed inside the
voiced part of the synthetic test song (tests/synth_song.py), so the MV
pipeline (separation -> transcription -> vocal-activity refinement -> alignment)
can be exercised end to end. Records the call in FAKE_WHISPER_LOG if set.
"""
import json
import os
from types import SimpleNamespace

import soundfile as sf

__version__ = "fake"
CHARS = "一二三四五六七八九十"


class WhisperModel:
    def __init__(self, path, device="cpu", compute_type="int8"):
        if not os.path.isfile(os.path.join(path, "model.bin")):
            raise RuntimeError(f"no model at {path}")
        self.path, self.device = path, device

    def transcribe(self, audio, **kw):
        info = sf.info(audio)
        dur = info.frames / info.samplerate
        log = os.environ.get("FAKE_WHISPER_LOG")
        if log:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"audio": audio, "device": self.device, "model": self.path, "kw": sorted(kw)}) + "\n")

        def gen():
            n = int(dur)
            for start in range(0, n, 4):
                words = []
                for i in range(start, min(n, start + 4)):
                    words.append(SimpleNamespace(word=CHARS[i % 10], start=i + 0.06, end=i + 0.8, probability=0.9))
                if words:
                    yield SimpleNamespace(start=words[0].start, end=words[-1].end,
                                          text="".join(w.word for w in words), words=words)
        return gen(), SimpleNamespace(duration=dur)
