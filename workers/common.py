"""Helpers shared by the engine workers (run inside the engine environment)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("SIGN2MV_ROOT") or Path(__file__).resolve().parent.parent)
MODELS = ROOT / "models"
IS_WINDOWS = os.name == "nt"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
GPU_ERROR_WORDS = ("cuda", "cudnn", "cublas", "out of memory", "nvidia", "no kernel image", "device-side")


def add_torch_dll_dir() -> None:
    """CTranslate2 (faster-whisper) needs cuBLAS/cuDNN DLLs; PyTorch ships them."""
    if not IS_WINDOWS:
        return
    try:
        import importlib.util
        spec = importlib.util.find_spec("torch")
        if spec and spec.origin:
            lib = Path(spec.origin).parent / "lib"
            if lib.is_dir():
                os.add_dll_directory(str(lib))
                os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


def ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def ffprobe() -> str:
    return shutil.which("ffprobe") or "ffprobe"


def run(args: list, timeout: float | None = None, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    if check and res.returncode != 0:
        err = re.sub(r"https?://\S+", "[url]", (res.stderr or res.stdout or "")[-2000:])
        raise RuntimeError(err.strip() or f"{Path(str(args[0])).name} exited with {res.returncode}")
    return res


def probe(path: Path) -> dict[str, Any]:
    """Duration and audio/video stream info of a media file."""
    res = run([ffprobe(), "-v", "error", "-show_entries",
               "format=duration,size:stream=index,codec_type,codec_name,sample_rate,channels,width,height,r_frame_rate",
               "-of", "json", path], timeout=120)
    data = json.loads(res.stdout or "{}")
    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    video = next((s for s in streams if s.get("codec_type") == "video" and s.get("codec_name") not in ("mjpeg", "png")), None)
    return {
        "duration": float(data.get("format", {}).get("duration") or 0),
        "size": int(data.get("format", {}).get("size") or 0),
        "audio": audio,
        "video": video,
    }


def sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_gpu_error(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in GPU_ERROR_WORDS)


def pick_device(mode: str = "auto") -> str:
    if mode == "cpu" or os.environ.get("SIGN2MV_FORCE_CPU"):
        return "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def replace_retry(src, dst, attempts: int = 20, delay: float = 0.5) -> None:
    """os.replace that waits for Windows file locks (a player, antivirus or indexer holding the target)."""
    import time
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == attempts - 1:
                raise RuntimeError("file_in_use:" + str(dst))
            time.sleep(delay)


def file_sig(path) -> str:
    st = os.stat(path)
    return f"{Path(path).name}|{st.st_size}|{int(st.st_mtime)}"
