"""Long-lived RMVPE pitch service for sing & record scoring.

The song reference is RMVPE (workers/sing_reference.py); the take is scored with the same
model so both sides cut notes the same way. The server keeps one of these processes per
session and sends it short pieces of the take while the user sings.

Protocol (stdin/stdout, one JSON object per line):
  request  {"id": n, "rate": 48000, "pcm": "<base64 int16 little-endian mono>"}
  response {"id": n, "f0": [hz or 0 ...], "hop": 0.01, "ms": compute time}
           f0[j] is the pitch at j * 10 ms from the start of the piece (0 = unvoiced)
  error    {"id": n, "error": "..."}
The first line written is {"ready": true, "device": "cuda"|"cpu"} once the model is loaded.
"""
from __future__ import annotations

import base64
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import is_gpu_error, pick_device  # noqa: E402
from sing_reference import RMVPE_FILE  # noqa: E402


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def to_16k(audio: np.ndarray, rate: int) -> np.ndarray:
    if rate == 16000:
        return audio
    import librosa
    return librosa.resample(audio, orig_sr=rate, target_sr=16000, res_type="soxr_hq").astype(np.float32)


def main() -> int:
    import torch
    from vendor.rmvpe.inference import RMVPE
    if not RMVPE_FILE.is_file():
        send({"ready": False, "error": f"model_missing:{RMVPE_FILE}"})
        return 1
    torch.set_num_threads(4)
    device = pick_device()
    model = None

    def load(target: str):
        return RMVPE(str(RMVPE_FILE), is_half=False, device=target)

    try:
        model = load(device)
        with torch.inference_mode():
            model.infer_from_audio(np.zeros(16000, dtype=np.float32))   # warm up the kernels
    except RuntimeError as exc:
        if device != "cuda" or not is_gpu_error(str(exc)):
            raise
        model, device = None, "cpu"
        gc.collect()
        torch.cuda.empty_cache()
        model = load(device)
    send({"ready": True, "device": device})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req: dict = {}
        try:
            req = json.loads(line)
            started = time.perf_counter()
            raw = np.frombuffer(base64.b64decode(req["pcm"]), dtype="<i2").astype(np.float32) / 32768.0
            audio = to_16k(raw, int(req.get("rate", 16000)))
            if len(audio) < 6400:
                audio = np.pad(audio, (0, 6400 - len(audio)))
            try:
                with torch.inference_mode():
                    f0 = np.asarray(model.infer_from_audio(audio), dtype=float)
            except RuntimeError as exc:
                if device != "cuda" or not is_gpu_error(str(exc)):
                    raise
                # the graphics card ran out (a cover or separation is using it): carry on on the CPU
                model, device = None, "cpu"
                gc.collect()
                torch.cuda.empty_cache()
                model = load(device)
                with torch.inference_mode():
                    f0 = np.asarray(model.infer_from_audio(audio), dtype=float)
            f0 = np.where(np.isfinite(f0), f0, 0.0)
            send({"id": req.get("id"), "f0": [round(float(v), 2) for v in f0], "hop": 0.01,
                  "ms": round((time.perf_counter() - started) * 1000), "device": device})
        except Exception as exc:  # one bad piece must not end the session
            send({"id": req.get("id"), "error": f"{type(exc).__name__}: {exc}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
