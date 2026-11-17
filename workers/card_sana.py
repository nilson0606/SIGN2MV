"""AI picture cards: an image model (Sana) draws the cards of a song from their prompts.

Input (stdin, one JSON document):
  items     [{"slot": ..., "prompt": ..., "seed": int, "out": path of the PNG to write}, ...]
  negative  what the pictures must not show
  width, height, steps, guidance   how the model draws (1280x720)
  pag       above 0: perturbed-attention guidance of this strength beside the usual one (SanaPAGPipeline)
  size      [w, h] of the card that is written (1920x1080)
  pkgs      folder of the libraries (runtime/sana/pkgs); installed there on first use
  lock      the libraries' lock file (installer/requirements/sana.lock.txt)
  repo, revision   the model on Hugging Face; downloaded on first use into HF_HOME (models/sana)
  fake      true: no model, flat pictures (the tests, and a computer without a graphics card)

Every finished card is written as <out>.part and then renamed, so the server can pick the cards up one
by one while the job runs. Result: {"drawn": n, "seconds": [...]}.

The model is not quantized: its three parts go to the graphics card one after the other
(enable_model_cpu_offload), which keeps the peak near 5 GB and was the fastest way that fits 8 GB
(4-bit: 6.4 GB, 8-bit: over 8 GB and half the speed; measured 2026-11-16 on an RTX 4060 Laptop).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

from protocol import Heartbeat, fail, log, progress, read_input, result

sys.stdout = sys.stderr          # libraries print progress bars and notes; the server reads only protocol lines

LIBS = ("diffusers", "transformers", "accelerate")


def lock_mark(pkgs: Path, lock: Path) -> Path:
    """The file that says the libraries of this lock file are in place."""
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()[:16]
    return pkgs / f".installed-{digest}"


def ensure_libs(pkgs: Path, lock: Path) -> None:
    mark = lock_mark(pkgs, lock)
    if mark.exists():
        return
    pkgs.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "pip", "install", "--python", sys.executable, "--target", str(pkgs), "--no-deps",
           "-r", str(lock)]
    with Heartbeat(2, "install", "安裝 AI 繪圖需要的程式庫（約 0.3 GB，只有第一次）"):
        done = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace")
    if done.returncode != 0:
        print(done.stdout, file=sys.stderr)
        fail("sana_install_failed", (done.stdout or "")[-600:])
    for old in pkgs.glob(".installed-*"):
        old.unlink()
    mark.write_text("ok", encoding="utf-8")


def model_dir(repo: str, revision: str):
    """The folder of the model: what is on the disk (no network asked), else downloaded."""
    from diffusers import SanaPipeline
    try:
        return SanaPipeline.download(repo, variant="bf16", revision=revision or None, local_files_only=True)
    except Exception as exc:  # noqa: BLE001 - not there yet (or not all of it)
        log(f"model not on the disk yet: {type(exc).__name__}: {str(exc)[:200]}")
    with Heartbeat(5, "download", "下載 AI 繪圖模型（約 10 GB，只有第一次；中斷了再按一次會接著下載）"):
        return SanaPipeline.download(repo, variant="bf16", revision=revision or None)


def fake_card(item: dict, size: tuple) -> None:
    """A flat picture that says which card it is: for the tests."""
    from PIL import Image, ImageDraw
    h = int(hashlib.sha256(f"{item['prompt']}|{item['seed']}".encode("utf-8")).hexdigest()[:6], 16)
    img = Image.new("RGB", size, (60 + h % 120, 60 + (h >> 8) % 120, 60 + (h >> 16) % 120))
    pen = ImageDraw.Draw(img)
    pen.rectangle((80, 80, size[0] - 80, size[1] - 80), outline=(255, 255, 255), width=6)
    pen.text((120, 120), f"{item['slot']}  seed {item['seed']}", fill=(255, 255, 255))
    save(img, item["out"])


def save(img, out: str) -> None:
    part = out + ".part"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(part, format="PNG", compress_level=1)
    os.replace(part, out)


def main() -> None:
    job = read_input()
    items = [i for i in job.get("items") or [] if i.get("prompt") and i.get("out")]
    if not items:
        fail("sana_nothing_to_draw", "no cards")
    size = tuple(int(v) for v in (job.get("size") or (1920, 1080)))[:2]
    n = len(items)
    seconds = []
    if job.get("fake"):
        for i, item in enumerate(items, 1):
            time.sleep(float(job.get("fake_wait") or 0))
            fake_card(item, size)
            seconds.append(0.0)
            progress(100 * i / n, "draw", f"{i}/{n}")
        result({"drawn": n, "seconds": seconds})
        return

    pkgs, lock = Path(job["pkgs"]), Path(job["lock"])
    ensure_libs(pkgs, lock)
    sys.path.insert(0, str(pkgs))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    progress(4, "load", "載入 AI 繪圖模型…")
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        fail("sana_no_torch", f"{type(exc).__name__}: {exc}")
    if not torch.cuda.is_available():
        fail("sana_no_gpu", "AI 繪圖需要 NVIDIA 顯示卡")
    try:
        pag = float(job.get("pag") or 0)
        path = model_dir(str(job["repo"]), str(job.get("revision") or ""))
        with Heartbeat(6, "load", "載入 AI 繪圖模型…"):
            if pag > 0:
                from diffusers import SanaPAGPipeline
                pipe = SanaPAGPipeline.from_pretrained(path, variant="bf16", torch_dtype=torch.bfloat16,
                                                       pag_applied_layers="transformer_blocks.8")
            else:
                from diffusers import SanaPipeline
                pipe = SanaPipeline.from_pretrained(path, variant="bf16", torch_dtype=torch.bfloat16)
            pipe.enable_model_cpu_offload()
    except Exception as exc:  # noqa: BLE001
        fail("sana_load_failed", f"{type(exc).__name__}: {str(exc)[:500]}")

    from PIL import Image
    width, height = int(job.get("width") or 1280), int(job.get("height") or 720)
    steps, guidance = int(job.get("steps") or 20), float(job.get("guidance") or 4.5)
    negative = str(job.get("negative") or "")
    for i, item in enumerate(items, 1):
        t0 = time.time()
        progress(8 + 92 * (i - 1) / n, "draw", f"{i}/{n}")
        try:
            gen = torch.Generator(device="cpu").manual_seed(int(item.get("seed") or 0))
            more = {"pag_scale": pag} if pag > 0 else {}
            img = pipe(prompt=str(item["prompt"]), negative_prompt=negative, width=width, height=height,
                       num_inference_steps=steps, guidance_scale=guidance, generator=gen, **more).images[0]
        except Exception as exc:  # noqa: BLE001
            fail("sana_draw_failed", f"{item.get('slot')}: {type(exc).__name__}: {str(exc)[:400]}")
        if img.size != size:
            img = img.convert("RGB").resize(size, Image.LANCZOS)
        save(img, item["out"])
        seconds.append(round(time.time() - t0, 1))
        log(f"card {item.get('slot')}: {seconds[-1]} s")
        progress(8 + 92 * i / n, "draw", f"{i}/{n}")
    result({"drawn": n, "seconds": seconds,
            "peak_mb": round(torch.cuda.max_memory_allocated() / 2 ** 20)})


if __name__ == "__main__":
    main()
