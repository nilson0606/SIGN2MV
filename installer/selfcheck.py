"""Engine environment self-check. Prints one JSON line (last line of stdout)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workers.common import add_torch_dll_dir  # noqa: E402


def main() -> None:
    out: dict = {"checks": {}}
    c = out["checks"]
    try:
        import torch
        out["torch"] = torch.__version__
        out["cuda"] = bool(torch.cuda.is_available())
        if out["cuda"]:
            out["gpu_name"] = torch.cuda.get_device_name(0)
            x = torch.randn(512, 512, device="cuda")
            float((x @ x).sum())
            out["gpu_mem_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1)
        c["torch"] = True
    except Exception as exc:  # noqa: BLE001
        c["torch"] = False
        out["torch_error"] = str(exc)[:300]
    for mod in ("demucs", "audio_separator", "faster_whisper", "soundfile", "librosa", "yt_dlp", "PIL"):
        try:
            __import__(mod)
            c[mod] = True
        except Exception:  # noqa: BLE001
            c[mod] = False
    try:
        add_torch_dll_dir()
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
        out["whisper_gpu"] = n > 0
        c["whisper"] = True
    except Exception as exc:  # noqa: BLE001
        c["whisper"] = False
        out["whisper_error"] = str(exc)[:300]
    ffmpeg = shutil.which("ffmpeg")
    try:
        res = subprocess.run([ffmpeg or "ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
        c["ffmpeg_rubberband"] = "rubberband" in res.stdout
        enc = subprocess.run([ffmpeg or "ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
        out["nvenc_listed"] = "h264_nvenc" in enc.stdout
    except Exception:  # noqa: BLE001
        c["ffmpeg_rubberband"] = False
    models = ROOT / "models"
    c["models"] = all((models / p).exists() for p in (
        "torch/hub/checkpoints/955717e8-8726e21a.th",
        "separation/model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        "separation/vocals_mel_band_roformer.ckpt",
        "separation/mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt",
        "rmvpe/rmvpe.pt",
        "whisper/medium/model.bin",
    ))
    print(json.dumps(out))


if __name__ == "__main__":
    main()
