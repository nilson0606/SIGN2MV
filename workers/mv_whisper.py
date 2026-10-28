"""MV workspace: word-level Whisper timestamps for the MV audio.

Port of the MV Studio pipeline (whisper_align_engine.run_whisper_via_venv_bp +
whisper_worker.py): separate the vocals first (and optionally the lead vocal),
transcribe the separated voice with faster-whisper (medium on the GPU, small on
the CPU), then use the vocal loudness to trim words that leak into instrumental
parts and drop instrumental hallucinations.

Separation reuses the layered stem cache of the song (app/stems.py), so a song
that was already separated for sing & record or a cover is not separated again.

Input JSON:
  song_dir, layers (missing stem layers), convert: null | {src, dst}  (non-WAV audio -> 44.1 kHz WAV),
  voice: abs path of the separated voice to transcribe (vocals or lead),
  vocals: abs path of the vocals (fallback when the lead split fails),
  used: "vocals" | "lead", audio_file: the MV audio (cache identity), w_json: output path,
  prompt, lead_requested, models_dir
Progress messages are the ones the MV page shows (stage = title, message = detail).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import protocol
from common import MODELS, add_torch_dll_dir, ffmpeg, pick_device, run

WHISPER_PIPELINE = "vocals_v1"


def say(pct: float, stage: str, detail: str = "") -> None:
    protocol.progress(pct, stage, detail)


class _LayerProgress:
    def __init__(self, lo: float, hi: float, stage: str, device: str):
        self.lo, self.hi, self.stage, self.device, self.last = lo, hi, stage, device, -1.0

    def __call__(self, pct: float) -> None:
        val = self.lo + (self.hi - self.lo) * max(0.0, min(100.0, float(pct))) / 100
        if val - self.last >= 0.5:
            self.last = val
            say(round(val, 1), self.stage, f"{self.device.upper()} {int(pct)}%")


def separate(data: dict, device: str) -> tuple[str | None, str]:
    """Run the missing stem layers. Returns (file to transcribe, 'lead'|'vocals'|'master')."""
    import separate as sep
    song_dir = Path(data["song_dir"])
    conv = data.get("convert")
    if conv and not Path(conv["dst"]).is_file():
        say(4, "🎤 [階段 0/3] 正在準備音檔…", Path(conv["src"]).name)
        dst = Path(conv["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.stem + ".part.wav")
        run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", conv["src"], "-vn", "-ac", "2", "-ar", "44100",
             "-c:a", "pcm_f32le", tmp], timeout=600)
        os.replace(tmp, dst)
    vocals_ok = True
    for layer in data.get("layers") or []:
        if layer["kind"] == "lead":
            stage = "🎤 [階段 0/3] 正在把主唱和和聲拆開（卡拉 OK 模型）..."
            lo, hi = 14, 18
        else:
            stage = "🎤 [階段 0/3] 正在把人聲從母帶分離出來（Demucs）..."
            lo, hi = 5, 14
        try:
            sep.run_layer(layer, song_dir, device, _LayerProgress(lo, hi, stage, device))
        except Exception as exc:  # noqa: BLE001
            protocol.log(f"separation failed: {str(exc)[:300]}")
            if layer["kind"] == "lead":
                say(16, "⚠️ 主唱／和聲拆不開，這次用整條人聲辨識", "")
                break
            say(12, "⚠️ 人聲分離沒有成功，這次改聽母帶辨識（沒人聲的地方會比較不準）", "")
            vocals_ok = False
            break
    voice, vocals = data.get("voice"), data.get("vocals")
    if vocals_ok and voice and Path(voice).is_file():
        return voice, data.get("used") or "vocals"
    if vocals_ok and vocals and Path(vocals).is_file():
        return vocals, "vocals"
    return None, "master"


def load_model(device: str):
    from faster_whisper import WhisperModel
    models_dir = Path(os.environ.get("SIGN2MV_WHISPER_DIR") or (MODELS / "whisper"))
    medium, small = models_dir / "medium", models_dir / "small"
    if device == "cuda":
        try:
            return WhisperModel(str(medium), device="cuda", compute_type="float16"), "cuda"
        except Exception as exc:  # noqa: BLE001
            say(14, "🎙️ [階段 1/3] GPU 顯存忙碌，自動切換至 CPU int8 模式載入模型...", str(exc)[:60])
    path = small if (small / "model.bin").is_file() else medium
    if not (path / "model.bin").is_file():
        raise FileNotFoundError("model_missing:whisper")
    return WhisperModel(str(path), device="cpu", compute_type="int8"), "cpu"


TRANSCRIBE = {"beam_size": 5, "word_timestamps": True, "vad_filter": True,
              "vad_parameters": {"min_silence_duration_ms": 350}, "condition_on_previous_text": False}


def transcribe(model, path: str, device: str, lo: int):
    segments_gen, info = model.transcribe(path, **TRANSCRIBE)
    dur = max(1.0, float(getattr(info, "duration", 0.0) or 240.0))
    out = []
    for s in segments_gen:
        txt = (s.text or "").strip()
        tag = "" if device == "cuda" else " (CPU)"
        say(lo + int(min(1.0, float(s.end) / dur) * 60), f"🎙️ [階段 2/3] Whisper{tag} 逐字聲學定位中 ({int(s.end)}s / {int(dur)}s)",
            f"辨識片段：「{txt[:26]}」")
        out.append({"start": round(float(s.start), 2), "end": round(float(s.end), 2), "text": txt,
                    "words": [{"word": w.word, "start": round(float(w.start), 2), "end": round(float(w.end), 2),
                               "probability": round(float(getattr(w, "probability", 1.0)), 3)} for w in (s.words or [])]})
    return out, dur


def vocal_activity(vocals_path: str, hop: float = 0.02):
    """Voice present per 20 ms (95th-percentile loudness - 35 dB; gaps < 0.25 s filled, blips < 0.12 s removed)."""
    try:
        import numpy as np
        raw = subprocess.run([ffmpeg(), "-v", "error", "-i", vocals_path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL, timeout=120,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0).stdout
        x = np.frombuffer(raw, dtype=np.float32)
        n = int(16000 * hop)
        if x.size < n * 10:
            return None
        frames = x[: (x.size // n) * n].reshape(-1, n)
        db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
        thr = max(float(np.percentile(db, 95)) - 35.0, -55.0)
        act = (db > thr).tolist()
    except Exception:  # noqa: BLE001
        return None

    def _runs(arr, val):
        i = 0
        while i < len(arr):
            if arr[i] == val:
                j = i
                while j < len(arr) and arr[j] == val:
                    j += 1
                yield i, j
                i = j
            else:
                i += 1
    for a, b in list(_runs(act, False)):
        if a > 0 and b < len(act) and (b - a) * hop < 0.25:
            act[a:b] = [True] * (b - a)
    for a, b in list(_runs(act, True)):
        if (b - a) * hop < 0.12:
            act[a:b] = [False] * (b - a)
    return act


def refine_words_with_activity(segs, act, hop: float = 0.02):
    trimmed = dropped = 0
    out = []
    n = len(act)
    for sg in segs:
        words = sg.get("words") or []
        if not words:
            out.append(sg)
            continue
        keep = []
        for w in words:
            try:
                ws, we = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            a, b = max(0, int(ws / hop)), min(n, int(we / hop) + 1)
            idx = [k for k in range(a, b) if act[k]]
            if not idx:
                dropped += 1
                continue
            ns, ne = round(max(ws, idx[0] * hop), 2), round(min(we, (idx[-1] + 1) * hop), 2)
            if ne - ns < 0.05:
                ne = round(ns + 0.05, 2)
            if abs(ns - ws) > 0.04 or abs(ne - we) > 0.04:
                trimmed += 1
            w2 = dict(w)
            w2["start"], w2["end"] = ns, ne
            keep.append(w2)
        if keep:
            sg2 = dict(sg)
            sg2["words"] = keep
            sg2["start"], sg2["end"] = keep[0]["start"], keep[-1]["end"]
            sg2["text"] = "".join(str(k.get("word", "")) for k in keep).strip()
            out.append(sg2)
    return out, trimmed, dropped


def main() -> None:
    data = protocol.read_input()
    add_torch_dll_dir()
    device = pick_device(data.get("device", "auto"))
    audio_file = data["audio_file"]
    w_json = Path(data["w_json"])
    try:
        listen, used = separate(data, device)
        say(10, "🎙️ [階段 1/3] 正在啟動獨立聲學環境載入 faster-whisper 模型...", Path(listen or audio_file).name)
        model, dev = load_model(device)
        say(20, f"🎙️ [階段 2/3] 正在逐字剖析母帶人聲時間戳 ({dev.upper()})...", Path(listen or audio_file).name)
        try:
            segs, dur = transcribe(model, listen or audio_file, dev, 22)
        except Exception as exc:  # noqa: BLE001
            if dev != "cuda":
                raise
            say(22, "🎙️ [階段 2/3] CUDA 推理中斷，自動切換 CPU int8 重新剖析...", str(exc)[:60])
            model, dev = load_model("cpu")
            segs, dur = transcribe(model, listen or audio_file, dev, 25)
        info = {"vad_refined": False, "trimmed": 0, "dropped": 0}
        if listen:
            act = vocal_activity(listen)
            if act:
                segs, info["trimmed"], info["dropped"] = refine_words_with_activity(segs, act)
                info["vad_refined"] = True
        payload = {"audio_file": os.path.abspath(audio_file), "audio_mtime": int(os.path.getmtime(audio_file)),
                   "duration": round(dur, 3), "device": dev, "segments": segs, "pipeline": WHISPER_PIPELINE,
                   "transcribed_from": used, "lead_requested": bool(data.get("lead_requested")), "refine": info}
        w_json.parent.mkdir(parents=True, exist_ok=True)
        tmp = w_json.with_name(w_json.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, w_json)
        label = {"lead": "主唱", "vocals": "分離人聲"}.get(used, "")
        if listen:
            say(86, f"🎤 已用{label}校正字的時間",
                f"切掉拖進器樂段的字 {info['trimmed']} 個、刪掉器樂段幻聽 {info['dropped']} 個")
        protocol.result({"segments": len(segs), "source": f"faster-whisper（{label}）" if label else "faster-whisper",
                         "device": dev})
    except FileNotFoundError as exc:
        protocol.fail("model_missing", str(exc))
    except Exception as exc:  # noqa: BLE001
        protocol.fail("whisper_failed", str(exc)[-800:])


if __name__ == "__main__":
    main()
