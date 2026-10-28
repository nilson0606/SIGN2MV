"""AI cover: train an RVC voice model with Applio (applio environment, cwd = Applio folder).

Port of AI_COVER_MV scripts/train_voice_pipeline.py (6 steps):
  1. import the recordings (any audio/video -> mono WAV at the training rate)
  2. slice (Applio preprocess, automatic cut, 3 s chunks)
  3. extract features (RMVPE pitch + ContentVec)
  4. train (HiFi-GAN, pretrained G/D; batch lowered when there are few slices)
  5. build the FAISS index
  6. install into models/voices/<name>/ (final weights + index, the last 4 epoch
     versions in epochs/, the loss curve in epochs/loss.json) and delete the
     training scratch folder.
Training scratch lives in runtime/applio-logs (APPLIO_LOGS_DIR), never in the
user profile. Only the latest G/D checkpoint is kept while training.

Input JSON: {"name", "inputs": [abs paths], "epochs", "batch_size", "save_every",
             "sample_rate", "logs_dir", "voices_dir", "upload_dir"?, "overwrite"}
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import protocol
from common import replace_retry

ROOT = Path(os.environ.get("SIGN2MV_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT))
AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus", ".webm", ".mp4", ".mkv", ".mov")
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
KEEP_EPOCHS = 4


def ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def say(pct: float, stage: str, msg: str = "") -> None:
    protocol.progress(round(pct, 1), stage, msg)


def run_step(args: list, stage: str, lo: float, hi: float, parse=None) -> list[str]:
    """Run an Applio script; its output goes to the job log (stderr), progress is parsed from it."""
    proc = subprocess.Popen([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=NO_WINDOW, cwd=os.getcwd())
    tail: list[str] = []
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").rstrip()
        if not line:
            continue
        sys.stderr.write(line + "\n")
        tail.append(line)
        del tail[:-40]
        if parse:
            parse(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"{stage} failed (exit {rc}): " + " | ".join(tail[-6:]))
    return tail


def import_audio(inputs: list[str], dataset: Path, sr: int) -> int:
    dataset.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_EXTS)
        elif p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            files.append(p)
    count = 0
    for i, f in enumerate(files):
        say(1 + 4 * i / max(1, len(files)), "train_import", f.name)
        dst = dataset / f"audio_{count:04d}.wav"
        r = subprocess.run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", str(f), "-vn", "-ar", str(sr), "-ac", "1",
                            "-c:a", "pcm_s16le", str(dst)], capture_output=True, creationflags=NO_WINDOW)
        if r.returncode == 0 and dst.is_file() and dst.stat().st_size > 1000:
            count += 1
        else:
            protocol.log(f"skipped (cannot read): {f.name}")
    return count


def epoch_weights(folder: Path, name: str) -> list[tuple[int, Path]]:
    found = []
    for wp in folder.glob(f"{glob.escape(name)}_*e_*s.pth"):
        m = re.search(r"_(\d+)e_(\d+)s\.pth$", wp.name)
        if m:
            found.append((int(m.group(1)), wp))
    return sorted(found)


def main() -> None:
    data = protocol.read_input()
    name = data["name"]
    sr = int(data.get("sample_rate") or 40000)
    epochs = int(data.get("epochs") or 100)
    save_every = max(1, int(data.get("save_every") or 10))
    batch = int(data.get("batch_size") or 8)
    logs_dir = Path(data["logs_dir"])
    voices = Path(data["voices_dir"])
    exp_dir = logs_dir / name
    dataset = logs_dir / f"{name}__dataset"
    os.environ["APPLIO_LOGS_DIR"] = str(logs_dir)
    py = sys.executable
    started = time.time()
    try:
        import torch
        gpu = "0" if torch.cuda.is_available() and not os.environ.get("SIGN2MV_FORCE_CPU") else "-"
    except Exception:  # noqa: BLE001
        gpu = "-"
    cores = max(1, min(8, (os.cpu_count() or 4) - 1))
    try:
        pg = Path("rvc/models/pretraineds/hifi-gan") / f"f0G{sr // 1000}k.pth"
        pd = Path("rvc/models/pretraineds/hifi-gan") / f"f0D{sr // 1000}k.pth"
        if not (pg.is_file() and pd.is_file()):
            protocol.fail("model_missing", f"pretrained {pg.name}/{pd.name}")
        shutil.rmtree(exp_dir, ignore_errors=True)
        shutil.rmtree(dataset, ignore_errors=True)
        exp_dir.mkdir(parents=True)

        # 1
        say(1, "train_import")
        count = import_audio(data.get("inputs") or [], dataset, sr)
        if count == 0:
            protocol.fail("train_no_audio", "")
        protocol.log(f"imported {count} recordings")
        # 2
        say(5, "train_slice")
        run_step([py, "rvc/train/preprocess/preprocess.py", exp_dir, dataset, sr, cores, "Automatic", False, 3.0, 0.3,
                  "none"], "slice", 5, 15)
        slices = len(list((exp_dir / "sliced_audios").glob("*.wav")))
        if slices == 0:
            protocol.fail("train_no_slices", "")
        protocol.log(f"{slices} slices")
        # 3
        say(15, "train_features", str(slices))
        run_step([py, "rvc/train/extract/extract.py", exp_dir, "rmvpe", cores, gpu, sr, "contentvec", "None", 2],
                 "features", 15, 30)
        # 4
        real_batch = batch if slices >= batch * 3 else max(1, slices // 3)
        if real_batch != batch:
            protocol.log(f"batch size lowered to {real_batch} ({slices} slices)")
        state = {"epoch": 0, "loss": None}

        def parse(line: str) -> None:
            m = re.search(r"epoch=(\d+)", line)
            if not m or "batch=" in line:
                return
            state["epoch"] = int(m.group(1))
            lv = re.search(r"lowest_value=([\d.]+)", line)
            if lv:
                state["loss"] = float(lv.group(1))
            msg = f"{state['epoch']}/{epochs}" + (f" · loss {state['loss']:.3f}" if state["loss"] is not None else "")
            say(30 + 60 * min(1.0, state["epoch"] / epochs), "train_epochs", msg)

        say(30, "train_epochs", f"0/{epochs}")
        run_step([py, "rvc/train/train.py", name, save_every, epochs, pg, pd, gpu, real_batch, sr,
                  True, True, False, False, "HiFi-GAN", False], "training", 30, 90, parse)
        weights = epoch_weights(exp_dir, name)
        if not weights:
            raise RuntimeError("training produced no model weights")
        # 5
        say(90, "train_index")
        try:
            run_step([py, "rvc/train/process/extract_index.py", exp_dir, "Auto"], "index", 90, 94)
        except RuntimeError as exc:
            protocol.log(f"index skipped: {exc}")
        # 6
        say(95, "train_install")
        final_epoch, final_pth = weights[-1]
        target = voices / name
        tmp = voices / f"_{name}.installing"
        shutil.rmtree(tmp, ignore_errors=True)
        (tmp / "epochs").mkdir(parents=True)
        shutil.copy2(final_pth, tmp / f"{name}_{final_epoch}e.pth")
        indices = sorted(exp_dir.glob("*.index"), key=lambda p: (not p.name.startswith("added_"), p.name))
        if indices:
            shutil.copy2(indices[0], tmp / f"{name}.index")
        keep = [w for w in weights if w[1] != final_pth][-KEEP_EPOCHS:]
        for _ep, wp in keep:
            shutil.copy2(wp, tmp / "epochs" / wp.name)
        try:
            from app import tb_scalars
            ev = tb_scalars.latest_event_file(str(exp_dir))
            if ev:
                loss = tb_scalars.loss_by_epoch(ev)
                loss.update(model=name, total_epochs=epochs, final_epoch=final_epoch,
                            kept_epochs=[e for e, _ in keep] + [final_epoch])
                (tmp / "epochs" / "loss.json").write_text(json.dumps(loss), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            protocol.log(f"loss curve not saved: {exc}")
        (tmp / "model_info.txt").write_text(
            f"Voice model: {name}\nTrained: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Recordings: {count} ({slices} slices)\nRVC v2 / HiFi-GAN {sr // 1000}k, RMVPE, ContentVec\n"
            f"Epochs: {final_epoch}, batch {real_batch}\n", encoding="utf-8")
        if target.exists():
            old = voices / f"_{name}.old"
            shutil.rmtree(old, ignore_errors=True)
            replace_retry(target, old, attempts=60)
            shutil.rmtree(old, ignore_errors=True)
        replace_retry(tmp, target, attempts=60)
        # clean the scratch (SIGN2MV_KEEP_TRAIN_SCRATCH=1 keeps it for diagnosis)
        if not os.environ.get("SIGN2MV_KEEP_TRAIN_SCRATCH"):
            shutil.rmtree(exp_dir, ignore_errors=True)
            shutil.rmtree(dataset, ignore_errors=True)
        if data.get("upload_dir"):
            shutil.rmtree(data["upload_dir"], ignore_errors=True)
        say(100, "done")
        protocol.result({"name": name, "epochs": final_epoch, "slices": slices, "recordings": count,
                         "seconds": round(time.time() - started, 1)})
    except RuntimeError as exc:
        protocol.fail("train_failed", str(exc)[-800:])
    except Exception as exc:  # noqa: BLE001
        protocol.fail("train_failed", f"{type(exc).__name__}: {str(exc)[-800:]}")


if __name__ == "__main__":
    main()
