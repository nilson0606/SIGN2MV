"""Download and verify all AI models (runs inside the engine environment).

Everything goes under <app>/models. Files with a known SHA-256 are verified;
a file only gets its final name once completely downloaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "installer"))

from install import download, sha256_of, InstallError  # noqa: E402  (pure-stdlib helpers)

MANIFEST = json.loads((ROOT / "installer" / "manifest.json").read_text(encoding="utf-8"))
MODELS = ROOT / "models"
M = MANIFEST["models"]


def say(msg: str) -> None:
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def verify(key: str) -> None:
    info = M[key]
    path = MODELS / info["file"]
    if not path.is_file():
        raise InstallError(f"{key}: file missing after download: {path}")
    if "size" in info and path.stat().st_size != info["size"]:
        raise InstallError(f"{key}: size {path.stat().st_size} != expected {info['size']}")
    if "sha256" in info:
        digest = sha256_of(path)
        if digest != info["sha256"]:
            path.unlink()
            raise InstallError(f"{key}: checksum mismatch; deleted the bad file, run install.bat again")
    say(f"  OK {key}: {path.name}")


def fetch_htdemucs() -> None:
    from demucs.pretrained import get_model
    say("htdemucs (Demucs)...")
    get_model("htdemucs")
    verify("htdemucs")


class _Downloader:
    """audio-separator model download, using our resumable verified downloader."""

    def __init__(self):
        from audio_separator.separator import Separator

        class LocalSeparator(Separator):
            def download_file_if_not_exists(self, url, output_path):
                if Path(output_path).name == Path(M["mel_roformer_kim"]["file"]).name:
                    # audio-separator's catalogue name for Kim's vocal model:
                    # fetch the author's checkpoint at a fixed revision.
                    url = M["mel_roformer_kim"]["url"]
                if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                    return
                download(url, Path(output_path))

        self.sep = LocalSeparator(model_file_dir=str(MODELS / "separation"), info_only=True,
                                  log_level=logging.WARNING)

    def get(self, key: str) -> None:
        name = Path(M[key]["file"]).name
        say(f"{key} ({name})...")
        self.sep.download_model_files(name)
        verify(key)


def fetch_rmvpe() -> None:
    info = M["rmvpe"]
    say("RMVPE pitch model...")
    download(info["url"], MODELS / info["file"], sha256=info["sha256"], size=info["size"])
    verify("rmvpe")


def fetch_whisper() -> None:
    from faster_whisper.utils import download_model
    for key, size in (("whisper_medium", "medium"), ("whisper_small", "small")):
        out = MODELS / M[key]["dir"]
        say(f"Whisper {size} (faster-whisper)...")
        download_model(size, output_dir=str(out))
        needed = ["model.bin", "config.json", "tokenizer.json"]
        missing = [n for n in needed if not (out / n).is_file()]
        if missing:
            raise InstallError(f"whisper {size}: missing files {missing}")
        say(f"  OK whisper {size}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-sucial", action="store_true")
    args = parser.parse_args()
    (MODELS / "separation").mkdir(parents=True, exist_ok=True)
    try:
        fetch_htdemucs()
        dl = _Downloader()
        for key in ("bs_roformer", "mel_roformer_kim", "karaoke_aufr33", "male_female_aufr33"):
            dl.get(key)
        if args.with_sucial:
            dl.get("male_female_sucial")
        fetch_rmvpe()
        fetch_whisper()
    except InstallError as exc:
        say(f"ERROR: {exc}")
        return 1
    say("All models ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
