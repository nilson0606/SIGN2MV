"""Stem separation with layered caching.

Input JSON:
  {"song_dir": "...", "layers": [ {layer spec}, ... ], "device": "auto"|"cpu"}
Each layer spec (computed by the server, see app/stems.py):
  {"key": "...", "kind": "mix", "model": "demucs"|"bs_roformer"|"mel_roformer", "input": "<abs wav>"}
      -> vocals.wav, instrumental.wav
  {"key": "...", "kind": "second_pass", "model": ..., "input": "<abs instrumental.wav>", "mix": "<abs source wav>"}
      -> instrumental2.wav, residual_vocals.wav (= mix - instrumental2)
  {"key": "...", "kind": "lead", "model": "karaoke", "input": "<abs vocals wav>"}
      -> lead.wav, backing.wav
  {"key": "...", "kind": "male_female", "model": "aufr33"|"sucial", "input": "<abs vocals wav>"}
      -> male.wav, female.wav
Every layer is written to <song_dir>/stems/<key>.tmp and renamed to
<song_dir>/stems/<key> only when complete and validated. All stems are float32 WAV
with the original gain (no per-stem normalisation).
"""
from __future__ import annotations

import gc
import os
import shutil
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import protocol
from common import MODELS, is_gpu_error, pick_device, write_json, ffmpeg, run

DEMUCS_SHIFTS = 1
DEMUCS_OVERLAP = 0.25
ROFORMER_FILES = {
    "bs_roformer": ("model_bs_roformer_ep_317_sdr_12.9755.ckpt", ("vocals", "instrumental")),
    "mel_roformer": ("vocals_mel_band_roformer.ckpt", ("vocals", "instrumental")),
    "karaoke": ("mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", ("lead", "backing")),
    # optional, downloaded by hand like in AI_COVER_MV (about 1.7 GB); its config comes with audio-separator
    "karaoke_becruily": ("mel_band_roformer_karaoke_becruily.ckpt", ("lead", "backing")),
    "aufr33": ("bs_roformer_male_female_by_aufr33_sdr_7.2889.ckpt", ("male", "female")),
    "sucial": ("model_chorus_bs_roformer_ep_267_sdr_24.1275.ckpt", ("male", "female")),
}
FIRST_LABELS = ["Vocals", "vocals", "Karaoke", "karaoke", "Lead", "lead", "Lead Vocals", "Main Vocals", "Male", "male"]
SECOND_LABELS = ["Instrumental", "instrumental", "Other", "other", "Backing", "backing", "Backing Vocals",
                 "No Vocals", "Female", "female"]
FIRST_MARKERS = ("(vocals)", "(lead)", "(karaoke)", "(main vocals)", "(lead vocals)", "(male)")
SECOND_MARKERS = ("(instrumental)", "(other)", "(backing)", "(no_vocal", "(no vocals)", "(backing vocals)", "(female)")


class Progress:
    """Maps one layer's 0-100 onto the overall job range."""

    def __init__(self, lo: float, hi: float, stage: str, device: str):
        self.lo, self.hi, self.stage, self.device = lo, hi, stage, device
        self.last = -1.0

    def __call__(self, pct: float) -> None:
        val = self.lo + (self.hi - self.lo) * max(0.0, min(100.0, pct)) / 100
        if val - self.last >= 0.5 or pct >= 100:
            self.last = val
            protocol.progress(round(val, 1), self.stage, self.device.upper())

    def phase(self, sub: str) -> None:
        """A step without a percentage ("read" the audio, "load" the model): the page names it and shows a
        moving bar instead of a still 0 %."""
        protocol.progress(None, f"{self.stage}:{sub}", self.device.upper())
        self.last = -1.0          # the next percentage is shown at once (and names the step again)


def phase(report, sub: str) -> None:
    fn = getattr(report, "phase", None)
    if fn:
        fn(sub)


def _base_tqdm():
    """tqdm's own class, kept from before any patch (see patch_tqdm)."""
    import tqdm as _tqdm
    if not hasattr(_base_tqdm, "cls"):
        _base_tqdm.cls = _tqdm.tqdm
    return _base_tqdm.cls


def patch_tqdm(module, report: Progress) -> None:
    """Route one library's tqdm progress bars into our progress messages, for this layer only.

    Never change the shared tqdm module, and always build on tqdm's own class: demucs.apply does
    `import tqdm`, and patching tqdm.tqdm there left the first layer's reporter in every later bar, so
    the lead/backing split (second layer) reported each step twice, as "separate" and as "lead"."""
    import types
    base = _base_tqdm()

    class Reporting(base):
        def __init__(self, *a, **k):
            k["disable"] = False
            k["file"] = open(os.devnull, "w")
            super().__init__(*a, **k)

        def update(self, n=1):
            r = super().update(n)
            if self.total:
                report(100.0 * self.n / self.total)
                if self.n >= self.total:
                    phase(report, "save")      # the library writes its output files after the last chunk
            return r

    if hasattr(module, "tqdm"):
        if isinstance(module.tqdm, type):
            module.tqdm = Reporting                                  # `from tqdm import tqdm`
        else:
            module.tqdm = types.SimpleNamespace(tqdm=Reporting)      # `import tqdm` (demucs.apply)


def demucs_separate(src: Path, out: Path, device: str, report: Progress) -> None:
    import torch
    from demucs.apply import apply_model
    import demucs.apply as dapply
    from demucs.pretrained import get_model

    patch_tqdm(dapply, report)
    phase(report, "load")
    model = get_model("htdemucs")
    model.eval()
    report(0)
    wav_np, sr = sf.read(str(src), dtype="float32", always_2d=True)
    if sr != model.samplerate:
        raise RuntimeError(f"unexpected sample rate {sr}")
    wav = torch.from_numpy(wav_np.T.copy())
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    # Same normalisation as demucs.separate.
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()
    std = std if float(std) > 1e-8 else torch.tensor(1.0)
    norm = (wav - mean) / std
    with torch.inference_mode():
        sources = apply_model(model, norm[None], device=device, shifts=DEMUCS_SHIFTS, split=True,
                              overlap=DEMUCS_OVERLAP, progress=True, num_workers=0)[0]
    sources = sources * std + mean
    names = list(model.sources)
    vocals = sources[names.index("vocals")]
    others = sum(sources[i] for i, n in enumerate(names) if n != "vocals")
    out.mkdir(parents=True, exist_ok=True)
    sf.write(str(out / "vocals.wav"), vocals.cpu().numpy().T, sr, subtype="FLOAT")
    sf.write(str(out / "instrumental.wav"), others.cpu().numpy().T, sr, subtype="FLOAT")
    del model, sources
    gc.collect()


def roformer_separate(model_key: str, src: Path, out: Path, device: str, report: Progress) -> None:
    import logging
    from audio_separator.separator import Separator

    filename, (first, second) = ROFORMER_FILES[model_key]
    model_dir = MODELS / "separation"
    if not (model_dir / filename).is_file():
        raise FileNotFoundError(f"model_missing:{filename}")
    if device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    out.mkdir(parents=True, exist_ok=True)
    phase(report, "load")
    t0 = time.time()
    sep = Separator(model_file_dir=str(model_dir), output_dir=str(out), output_format="WAV",
                    use_soundfile=True, log_level=logging.WARNING,
                    mdxc_params={"batch_size": 1, "segment_size": 256, "override_model_segment_size": True,
                                 "overlap": 4, "pitch_shift": 0})
    sep.load_model(model_filename=filename)
    protocol.log(f"{filename}: model loaded in {time.time() - t0:.1f} s")
    report(0)
    # Keep original gain: no independent peak normalisation per stem.
    sep.model_instance.normalization_threshold = float("inf")
    sep.model_instance.amplification_threshold = 0.0
    try:
        import audio_separator.separator.architectures.mdxc_separator as mdxc
        patch_tqdm(mdxc, report)
    except Exception:  # noqa: BLE001
        pass
    names = {label: first for label in FIRST_LABELS}
    names.update({label: second for label in SECOND_LABELS})
    produced = sep.separate(str(src), names) or []
    a, b = out / f"{first}.wav", out / f"{second}.wav"
    if not (a.is_file() and b.is_file()):
        for f in produced:
            p = Path(f) if Path(f).is_absolute() else out / f
            low = p.name.lower()
            if not a.is_file() and any(m in low for m in FIRST_MARKERS):
                shutil.move(str(p), a)
            elif not b.is_file() and any(m in low for m in SECOND_MARKERS):
                shutil.move(str(p), b)
    if not (a.is_file() and b.is_file()):
        raise RuntimeError(f"separation did not produce {first}/{second}: {produced}")
    # Karaoke models sometimes swap labels: the lead must be clearly louder than backing.
    if model_key in ("karaoke", "karaoke_becruily"):
        ra, rb = rms(a), rms(b)
        if ra is not None and rb is not None and ra < 0.25 * rb:
            tmp = out / "_swap.wav"
            shutil.move(str(a), tmp)
            shutil.move(str(b), a)
            shutil.move(str(tmp), b)
            protocol.log("lead/backing labels were swapped by the model; corrected")
    del sep
    gc.collect()


def rms(path: Path) -> float | None:
    try:
        total, count = 0.0, 0
        with sf.SoundFile(str(path)) as f:
            for block in f.blocks(blocksize=262144, dtype="float32", always_2d=True):
                total += float(np.square(block, dtype=np.float64).sum())
                count += block.size
        return (total / count) ** 0.5 if count else 0.0
    except Exception:  # noqa: BLE001
        return None


def subtract(mix: Path, inst: Path, out: Path) -> None:
    """residual vocals = mix - instrumental (sample-aligned, float, block-wise)."""
    with sf.SoundFile(str(mix)) as m, sf.SoundFile(str(inst)) as i:
        if (m.samplerate, m.channels) != (i.samplerate, i.channels) or abs(m.frames - i.frames) > 2:
            raise RuntimeError("residual: stems are not aligned with the mix")
        with sf.SoundFile(str(out), "w", samplerate=m.samplerate, channels=m.channels, subtype="FLOAT") as o:
            while True:
                a = m.read(262144, dtype="float32", always_2d=True)
                if not len(a):
                    break
                b = i.read(len(a), dtype="float32", always_2d=True)
                if len(b) < len(a):
                    b = np.pad(b, ((0, len(a) - len(b)), (0, 0)))
                o.write(a - b)


def ensure_float_wav(src: Path, work: Path) -> Path:
    """audio-separator needs PCM/float WAV input (it reuses the input subtype for output)."""
    try:
        info = sf.info(str(src))
        if info.format in ("WAV", "WAVEX") and info.subtype in ("PCM_16", "PCM_24", "PCM_32", "FLOAT", "DOUBLE"):
            return src
    except Exception:  # noqa: BLE001
        pass
    dst = work / "_input.wav"
    run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", src, "-map", "0:a:0", "-vn",
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_f32le", dst], timeout=1800)
    return dst


def frames_of(path: Path) -> tuple[int, int]:
    info = sf.info(str(path))
    return info.frames, info.samplerate


def validate(out: Path, names: tuple[str, ...], ref: Path) -> None:
    ref_frames, ref_sr = frames_of(ref)
    for n in names:
        f = out / f"{n}.wav"
        if not f.is_file() or f.stat().st_size < 1000:
            raise RuntimeError(f"missing stem {n}")
        frames, sr = frames_of(f)
        if abs(frames / sr - ref_frames / ref_sr) > 0.15:
            raise RuntimeError(f"stem {n} length does not match the source")


def run_layer(layer: dict, song_dir: Path, device: str, report: Progress) -> str:
    stems = song_dir / "stems"
    final = stems / layer["key"]
    if (final / "info.json").is_file():
        return device
    tmp = stems / (layer["key"] + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    src = Path(layer["input"])
    kind, model = layer["kind"], layer["model"]

    def attempt(dev: str) -> None:
        report(0)
        phase(report, "read")
        if kind in ("mix", "second_pass"):
            if model == "demucs":
                demucs_separate(src, tmp, dev, report)
            else:
                roformer_separate(model, ensure_float_wav(src, tmp), tmp, dev, report)
        elif kind == "lead":
            roformer_separate(model if model in ("karaoke", "karaoke_becruily") else "karaoke",
                              ensure_float_wav(src, tmp), tmp, dev, report)
        elif kind == "male_female":
            roformer_separate(model, ensure_float_wav(src, tmp), tmp, dev, report)
        else:
            raise RuntimeError(f"unknown layer kind {kind}")

    used = device
    try:
        attempt(device)
    except Exception as exc:  # noqa: BLE001
        if device != "cuda" or not is_gpu_error(str(exc)):
            raise
        protocol.log(f"GPU failed ({str(exc)[:200]}); retrying on CPU")
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass
        for f in tmp.glob("*"):
            if f.is_file():
                f.unlink()
        used = "cpu"
        report.device = "cpu"
        attempt("cpu")

    phase(report, "save")          # writing, checking and moving the stems (the bar would sit at 100 %)
    (tmp / "_input.wav").unlink(missing_ok=True)
    if kind == "second_pass":
        os.replace(tmp / "instrumental.wav", tmp / "instrumental2.wav")
        (tmp / "vocals.wav").unlink(missing_ok=True)
        subtract(Path(layer["mix"]), tmp / "instrumental2.wav", tmp / "residual_vocals.wav")
        names = ("instrumental2", "residual_vocals")
    elif kind == "mix":
        names = ("vocals", "instrumental")
    elif kind == "lead":
        names = ("lead", "backing")
    else:
        names = ("male", "female")
    for extra in tmp.glob("*.wav"):
        if extra.stem not in names:
            extra.unlink()
    validate(tmp, names, src)
    write_json(tmp / "info.json", {
        "schema_version": 1, "key": layer["key"], "kind": kind, "model": model,
        "params": layer.get("params", {}), "input": layer.get("input_ref"),
        "files": [f"{n}.wav" for n in names], "device": used, "created_at": time.time(),
    })
    if final.exists():
        shutil.rmtree(final, ignore_errors=True)
    os.replace(tmp, final)
    return used


def main() -> None:
    data = protocol.read_input()
    song_dir = Path(data["song_dir"])
    layers = data.get("layers") or []
    device = pick_device(data.get("device", "auto"))
    n = max(1, len(layers))
    used = []
    for idx, layer in enumerate(layers):
        stage = {"mix": "separate", "second_pass": "second_pass", "lead": "lead", "male_female": "male_female"}.get(layer["kind"], "separate")
        report = Progress(idx * 100 / n, (idx + 1) * 100 / n, stage, device)
        try:
            used.append(run_layer(layer, song_dir, device, report))
        except FileNotFoundError as exc:
            shutil.rmtree(song_dir / "stems" / (layer["key"] + ".tmp"), ignore_errors=True)
            protocol.fail("model_missing", str(exc))
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(song_dir / "stems" / (layer["key"] + ".tmp"), ignore_errors=True)
            protocol.fail("separation_failed", str(exc)[-1500:])
    protocol.progress(100, "done", "")
    protocol.result({"layers": [l["key"] for l in layers], "devices": used})


if __name__ == "__main__":
    main()
