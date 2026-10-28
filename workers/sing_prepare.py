"""Prepare a song for sing & record: stems -> melody/beat reference -> key version.

Input JSON (built by app/api_sing.py):
  song_dir, layers (separation layers still missing),
  base: {dir, stems: {vocals, accompaniment, lead?, backing?} (abs), pitch_input, beat_input, meta{...}}
  key:  null | {semitones, dir, out_dir, stems: [names], meta{...}}
  force_reference: bool
Stage names follow the original sign_record helper (separating, accompaniment_separating,
lead_separating, reference, transposing) so the sing page shows familiar progress.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import protocol
import separate
import sing_reference
from common import pick_device, read_json, write_json

STAGE = {"mix": "separating", "second_pass": "accompaniment_separating", "lead": "lead_separating",
         "male_female": "lead_separating"}


class StageProgress:
    """Per-stage 0-100 progress (the sing page shows progress per stage)."""

    def __init__(self, stage: str, device: str):
        self.stage, self.device, self.last = stage, device, -1.0

    def __call__(self, pct: float) -> None:
        pct = max(0.0, min(100.0, float(pct)))
        if pct - self.last >= 1 or pct >= 100:
            self.last = pct
            protocol.progress(round(pct, 1), self.stage, self.device.upper())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    data = protocol.read_input()
    song_dir = Path(data["song_dir"])
    device = pick_device(data.get("device", "auto"))
    try:
        clip = data.get("clip")
        if clip and not Path(clip["dst"]).is_file():
            # "try the first N seconds": the separation and the reference use only this clip
            from common import ffmpeg, run
            dst = Path(clip["dst"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.stem + f".part{os.getpid()}.wav")
            run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", clip["src"], "-t", str(int(clip["seconds"])),
                 "-vn", "-c:a", "pcm_f32le", tmp], timeout=600)
            os.replace(tmp, dst)
        made: list[Path] = []
        for layer in data.get("layers") or []:
            made.append(song_dir / "stems" / layer["key"])
            stage = STAGE.get(layer["kind"], "separating")
            report = StageProgress(stage, device)
            used = separate.run_layer(layer, song_dir, device, _Adapter(report))
            if used != device:
                protocol.log("GPU failed; used CPU")

        base = data["base"]
        base_dir = Path(base["dir"])
        ref_file = base_dir / "reference.json"
        if data.get("force_reference") or not ref_file.is_file():
            report = StageProgress("reference", device)
            protocol.progress(0, "reference", device.upper())
            ref = sing_reference.build(Path(base["pitch_input"]), Path(base["beat_input"]),
                                       base["meta"]["pitchMethod"], device, report)
            value = {"version": 1, **base["meta"], **ref, "cacheVersion": 1, "hasPreview": True,
                     "stems": base["stems_rel"], "savedAt": now_iso(),
                     "quality": "experimental-lead-vocals" if base["meta"].get("vocalMode") == "lead"
                     else "experimental-separated-vocals"}
            tmp = base_dir.with_name(base_dir.name + ".tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            write_json(tmp / "reference.json", value)
            if base_dir.exists():
                shutil.rmtree(base_dir, ignore_errors=True)
            os.replace(tmp, base_dir)

        key = data.get("key")
        if key:
            from key_shift import shift_items
            source = read_json(ref_file)
            semis = int(key["semitones"])
            made += [Path(it["out_dir"]) for it in key["items"] if not (Path(it["out_dir"]) / "info.json").is_file()]
            shift_items(key["items"], semis, StageProgress("transposing", device))
            factor = 2 ** (semis / 12)
            label = f"{'升' if semis > 0 else '降'} {abs(semis)} Key"
            value = {**source, "pitchShift": semis, "baseTitle": source.get("baseTitle") or source["title"],
                     "sourceCacheId": source["cacheId"], "cacheId": key["meta"]["cacheId"],
                     "title": f"{source['title'][:280]} · {label}",
                     "frames": [None if hz is None else hz * factor for hz in source["frames"]],
                     "stems": key["stems_rel"], "savedAt": now_iso()}
            kdir = Path(key["dir"])
            tmp = kdir.with_name(kdir.name + ".tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            write_json(tmp / "reference.json", value)
            if kdir.exists():
                shutil.rmtree(kdir, ignore_errors=True)
            os.replace(tmp, kdir)
        if data.get("drop_new"):
            # "keep separated tracks" was off (sign_record: only the reference is kept, temporary audio
            # is removed): drop what this job had to make; stems that existed before are left alone.
            for d in made:
                shutil.rmtree(d, ignore_errors=True)
            if clip:
                Path(clip["dst"]).unlink(missing_ok=True)
            if made:
                protocol.log(f"separated tracks not kept: removed {len(made)} folder(s)")
    except FileNotFoundError as exc:
        protocol.fail("model_missing", str(exc))
    except ValueError as exc:
        code = str(exc) if str(exc) in ("melody_too_short",) else "reference_failed"
        protocol.fail(code, str(exc)[-800:])
    except Exception as exc:  # noqa: BLE001
        protocol.fail("prepare_failed", str(exc)[-1500:])
    protocol.progress(100, "ready", device.upper())
    protocol.result({"ok": True})


class _Adapter:
    """separate.run_layer expects a Progress-like object with .device."""

    def __init__(self, report: StageProgress):
        self.report = report
        self.device = report.device

    def __call__(self, pct: float) -> None:
        self.report.device = self.device
        self.report(pct)


if __name__ == "__main__":
    main()
