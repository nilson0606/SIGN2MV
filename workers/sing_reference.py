"""Melody (pitch) and beat reference for sing & record scoring.

Ported from sign_record tools/reference_audio.py and rmvpe_pitch.py (same
algorithms and thresholds): 100 ms grid, 65-1000 Hz, stable runs only, beat grid
estimated from the accompaniment.
"""
from __future__ import annotations

import gc
import math
import subprocess
from pathlib import Path

import numpy as np

from common import MODELS, NO_WINDOW, ffmpeg, is_gpu_error

RMVPE_FILE = MODELS / "rmvpe" / "rmvpe.pt"


def pcm(path: Path, rate: int = 16000) -> np.ndarray:
    res = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"],
                         capture_output=True, timeout=600, creationflags=NO_WINDOW)
    if res.returncode:
        raise ValueError("could not decode stem for reference analysis")
    return np.frombuffer(res.stdout, dtype="<f4").copy()


def yin_pitch(frame: np.ndarray, rate: int = 16000):
    frame = frame.astype(np.float64)
    frame -= frame.mean()
    if np.sqrt(np.mean(frame * frame)) < .004:
        return None
    max_lag = math.ceil(rate / 65)
    window = len(frame) - max_lag
    reference = frame[:window]
    shifted = np.lib.stride_tricks.sliding_window_view(frame, window)[:max_lag + 1]
    diff = np.sum((shifted - reference) ** 2, axis=1)
    cumulative = np.cumsum(diff[1:])
    normalized = np.ones(max_lag + 1)
    normalized[1:] = diff[1:] * np.arange(1, max_lag + 1) / np.maximum(cumulative, 1e-15)
    lag = rate // 1000
    while lag < max_lag - 1:
        if normalized[lag] < .12:
            while lag + 1 < max_lag and normalized[lag + 1] < normalized[lag]:
                lag += 1
            if lag >= max_lag:
                return None
            a, b, c = normalized[lag - 1:lag + 2]
            denominator = 2 * (2 * b - a - c)
            refined = lag + ((c - a) / denominator if denominator else 0)
            hz = rate / refined
            return round(float(hz), 2) if 65 <= hz <= 1000 else None
        lag += 1
    return None


def beat_grid(audio: np.ndarray, rate: int = 16000):
    hop, window = 320, 1024
    if len(audio) < rate * 5:
        return None, []
    previous = None
    flux = []
    for start in range(0, len(audio) - window, hop):
        spectrum = np.abs(np.fft.rfft(audio[start:start + window] * np.hanning(window)))
        flux.append(0 if previous is None else float(np.maximum(spectrum - previous, 0).sum()))
        previous = spectrum
    envelope = np.array(flux)
    envelope = np.maximum(envelope - np.median(envelope), 0)
    if not envelope.size or envelope.max() < 1e-5:
        return None, []
    best_lag, best = None, 0
    for lag in range(round(60 / 180 / .02), round(60 / 60 / .02) + 1):
        if lag >= len(envelope):
            continue
        a, b = envelope[:-lag], envelope[lag:]
        similarity = float(np.dot(a, b) / max(1e-10, np.linalg.norm(a) * np.linalg.norm(b)))
        if similarity > best:
            best, best_lag = similarity, lag
    if best_lag is None or best < .15:
        return None, []
    phase = max(range(best_lag), key=lambda n: float(envelope[n::best_lag].mean()))
    beats = [round((n * hop + window / 2) / rate, 3) for n in range(phase, len(envelope), best_lag)]
    return round(60 / (best_lag * .02), 1), beats


def rmvpe_grid(audio: np.ndarray, infer, progress=lambda v: None) -> list:
    """Centered 10 ms predictions onto the 100 ms grid; 8 s cores with 1 s context."""
    audio = np.asarray(audio, dtype=np.float32)
    frames = []
    for core in range(0, len(audio), 128000):
        end = min(len(audio), core + 128000)
        left, right = max(0, core - 16000), min(len(audio), end + 16000)
        segment = audio[left:right]
        if len(segment) < 6400:
            segment = np.pad(segment, (0, 6400 - len(segment)))
        f0 = np.asarray(infer(segment), dtype=float)
        if f0.ndim != 1 or len(f0) < math.ceil((end - left) / 160):
            raise ValueError("RMVPE returned an incomplete pitch track")
        for sample in range(core, end, 1600):
            center = (sample - left) // 160
            candidates = f0[max(0, center - 4):center + 5]
            valid = candidates[np.isfinite(candidates) & (candidates >= 65) & (candidates <= 1000)]
            frames.append(round(float(np.median(valid)), 2) if len(valid) > len(candidates) / 2 else None)
        progress(round(end / len(audio) * 100))
    return frames


def rmvpe_frames(audio: np.ndarray, device: str, progress=lambda v: None) -> list:
    import torch
    from vendor.rmvpe.inference import RMVPE
    if not RMVPE_FILE.is_file():
        raise FileNotFoundError(f"model_missing:{RMVPE_FILE}")
    torch.set_num_threads(4)
    selected = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"

    def run(target):
        model = RMVPE(str(RMVPE_FILE), is_half=False, device=target)
        try:
            with torch.inference_mode():
                return rmvpe_grid(audio, model.infer_from_audio, progress)
        finally:
            del model
            gc.collect()

    try:
        return run(selected)
    except RuntimeError as exc:
        if selected != "cuda" or not is_gpu_error(str(exc)):
            raise
        torch.cuda.empty_cache()
        progress(0)
        return run("cpu")


def build(vocals: Path, accompaniment: Path, pitch_method: str, device: str, progress=lambda v: None,
          on_phase=lambda sub: None) -> dict:
    audio = pcm(vocals)
    step, window = .1, 2048
    if pitch_method == "rmvpe":
        frames = rmvpe_frames(audio, device, progress)
    elif pitch_method == "yin":
        pad = np.pad(audio, (window // 2, window // 2))
        frames = [yin_pitch(pad[s:s + window]) for s in range(0, len(audio), 1600)]
        progress(100)
    else:
        raise ValueError("invalid pitch method")
    # Reject isolated detections; keep only stable runs (at least 200 ms).
    for i, value in enumerate(frames.copy()):
        if value is None:
            continue
        neighbors = [f for f in frames[max(0, i - 1):i + 2] if f is not None]
        if len(neighbors) < 2:
            frames[i] = None
        elif len(neighbors) == 3:
            frames[i] = round(float(np.median(neighbors)), 2)
    voiced = sum(f is not None for f in frames) * step
    if voiced < 3:
        raise ValueError("melody_too_short")
    on_phase("beats")
    bpm, beats = beat_grid(pcm(accompaniment))
    return {"step": step, "frames": frames, "duration": round(len(audio) / 16000, 3), "bpm": bpm, "beats": beats,
            "pitchMethod": pitch_method, "voicedSeconds": round(voiced, 1)}
