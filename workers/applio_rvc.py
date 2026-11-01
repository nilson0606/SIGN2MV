"""RVC voice conversion with Applio (runs in the applio environment, cwd = Applio folder).

Input JSON: {"tasks": [{"input": wav, "output": wav, "pth": ..., "index": ...|"",
                        "pitch": int, "f0": "rmvpe"|"fcpe"|"crepe", "index_rate": 0-1,
                        "envelope": 0-1, "protect": 0-0.5, "autotune": bool,
                        "autotune_strength": 0-1, "clean": bool, "clean_strength": 0-1,
                        "label": "..."}]}
All tasks run in one process so the pitch and content models load once.
Each output is resampled to 44.1 kHz stereo float WAV (sample-accurate with the
stems). Applio's own prints go to stderr; stdout carries the job protocol.

"Clean" maps the old Applio option (clean_audio, strength 0-1, default 0.5) to
Applio 3.7's output clean-up (cleanup_mode="light", reduction limit in dB):
strength x 24 dB, so the old default 0.5 becomes Applio's default 12 dB.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path

import protocol

T0 = time.time()   # process start (imports above are light)

if os.environ.get("SIGN2MV_FORCE_CPU"):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""


def ffmpeg() -> str:
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"


def cleanup_db(strength: float) -> float:
    return float(min(30.0, max(1.0, round(float(strength) * 24.0, 1))))


def to_44k_stereo(src: Path, dst: Path) -> None:
    tmp = dst.with_name(dst.stem + ".part.wav")
    res = subprocess.run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", str(src), "-ar", "44100", "-ac", "2",
                          "-c:a", "pcm_f32le", str(tmp)], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if res.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise RuntimeError("resample failed: " + (res.stderr or "")[-300:])
    os.replace(tmp, dst)


def main() -> None:
    data = protocol.read_input()
    tasks = data.get("tasks") or []
    sys.path.insert(0, os.getcwd())
    with protocol.Heartbeat(0, "rvc_load"), contextlib.redirect_stdout(sys.stderr):
        from rvc.infer.infer import VoiceConverter
        vc = VoiceConverter()
    load_s = round(time.time() - T0, 1)
    protocol.log(f"Applio loaded in {load_s} s")
    dev = str(getattr(vc.config, "device", "") or "")
    gpu = getattr(vc.config, "gpu_name", None)
    where = f"GPU {gpu}" if dev.startswith("cuda") and gpu else ("GPU" if dev.startswith("cuda") else "CPU")
    protocol.log(f"Applio device: {dev} ({where})")
    done = []
    for i, t in enumerate(tasks):
        out = Path(t["output"])
        out.parent.mkdir(parents=True, exist_ok=True)
        raw = out.with_name(out.stem + f".{os.getpid()}.native.wav")
        pct = round(i * 100 / max(1, len(tasks)), 1)
        kwargs = {}
        if t.get("autotune"):
            kwargs.update(f0_autotune=True, f0_autotune_strength=float(t.get("autotune_strength", 1.0)))
        if t.get("clean"):
            kwargs.update(cleanup_mode="light", cleanup_stage="output",
                          cleanup_strength=cleanup_db(t.get("clean_strength", 0.5)))
        started = time.time()
        index = str(t.get("index") or "")
        tmp_index = None
        if index and "trained" in index.lower():
            # Applio rewrites "trained" to "added" in index paths: give it a copy under a neutral name
            import shutil
            import tempfile
            tmp_index = Path(tempfile.gettempdir()) / f"sign2mv_{os.getpid()}_{i}.index"
            shutil.copyfile(index, tmp_index)
            index = str(tmp_index)
        try:
            with protocol.Heartbeat(pct, "rvc", f"{t.get('title') or t.get('label', '')} · {where}"), \
                    contextlib.redirect_stdout(sys.stderr):
                vc.convert_audio(audio_input_path=str(t["input"]), audio_output_path=str(raw),
                                 model_path=str(t["pth"]), index_path=index,
                                 pitch=int(t.get("pitch", 0)), f0_method=t.get("f0", "rmvpe"),
                                 index_rate=float(t.get("index_rate", 0.75)),
                                 volume_envelope=float(t.get("envelope", 1.0)),
                                 protect=float(t.get("protect", 0.33)), export_format="WAV", resample_sr=0,
                                 **kwargs)
            if not raw.is_file() or raw.stat().st_size < 1000:
                raise RuntimeError("Applio produced no audio")
            to_44k_stereo(raw, out)
        except Exception as exc:  # noqa: BLE001
            raw.unlink(missing_ok=True)
            protocol.fail("rvc_failed", f"{t.get('label', '')}: {str(exc)[-600:]}")
        raw.unlink(missing_ok=True)
        if tmp_index:
            tmp_index.unlink(missing_ok=True)
        try:
            import soundfile
            audio_s = soundfile.info(str(out)).duration
        except Exception:  # noqa: BLE001
            audio_s = 0
        done.append({"output": str(out), "seconds": round(time.time() - started, 1), "audio_s": round(audio_s, 1)})
        protocol.log(f"✔ 已轉換{t.get('title') or t.get('label', '')}（{done[-1]['seconds']} 秒）")
    protocol.progress(100, "rvc", "")
    protocol.result({"done": done, "device": dev, "gpu": gpu if dev.startswith("cuda") else "", "load_s": load_s,
                     "convert_s": round(sum(d.get("seconds", 0) for d in done), 1),
                     "audio_seconds": round(sum(d.get("audio_s", 0) for d in done), 1)})


if __name__ == "__main__":
    main()
