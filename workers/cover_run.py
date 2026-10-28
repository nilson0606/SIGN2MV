"""AI cover: make (or remix) one cover version of a song. Queue worker, engine environment.

The server builds the plan (app/cover.py: plan) and passes it here:
  {"song_dir", "plan", "params", "version": {...}, "render": {"id", "replace", "title"},
   "applio": {"python", "dir"}, "soundfonts", "device"}
Steps (each one is skipped when its result is already cached):
  1. stem layers (shared stem cache of the song)
  2. key change of the accompaniment / backing vocals / original vocal (Rubber Band)
  3. sections with their own separation settings: cut from the original and separate again
  4. RVC conversions in one Applio process (main vocal, male / female, re-converted sections)
  5. male + female vocals combined by their volumes
  6. melody MIDI for the instrument track (only when the instrument is audible)
  7. master mix -> songs/<id>/renders/<rid>/audio.mp3 (kind "cover") + the version record
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import protocol
from common import NO_WINDOW, ROOT, ffmpeg, file_sig, pick_device, replace_retry, run, write_json

sys.path.insert(0, str(ROOT))


class Step:
    def __init__(self, lo: float, hi: float, stage: str):
        self.lo, self.hi, self.stage, self.last, self.last_text = lo, hi, stage, -1.0, None

    def __call__(self, pct: float, detail: str = "", stage: str | None = None) -> None:
        val = self.lo + (self.hi - self.lo) * max(0.0, min(100.0, float(pct))) / 100
        text = (stage or self.stage, detail)
        if val - self.last >= 0.5 or pct >= 100 or text != self.last_text:
            self.last, self.last_text = val, text
            protocol.progress(round(val, 1), stage or self.stage, detail)


def cut(src: Path, dst: Path, start: float, dur: float) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.wav")
    run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", src, "-vn",
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_f32le", tmp], timeout=600)
    os.replace(tmp, dst)


def key_shift_file(src: Path, dst: Path, semis: int) -> None:
    info = sf.info(str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.wav")
    af = (f"rubberband=tempo=1:pitch={2 ** (semis / 12):.12f}:channels=together:pitchq=quality,"
          f"apad,atrim=duration={info.frames / info.samplerate:.9f}")
    try:
        run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", src, "-af", af, "-ar", str(info.samplerate),
             "-c:a", "pcm_f32le", tmp], timeout=1800)
    except RuntimeError as exc:
        if "rubberband" in str(exc).lower() and "filter" in str(exc).lower():
            raise RuntimeError("rubberband_missing") from exc
        raise
    os.replace(tmp, dst)


def sum_tracks(paths: list[Path], out: Path) -> None:
    data = None
    sr = 44100
    for p in paths:
        d, sr = sf.read(str(p), dtype="float32", always_2d=True)
        if data is None:
            data = d
        else:
            n = max(len(data), len(d))
            data = np.pad(data, ((0, n - len(data)), (0, 0))) + np.pad(d, ((0, n - len(d)), (0, 0)))
    sf.write(str(out), data, sr, subtype="FLOAT")


def separate_segment(job: dict, song_dir: Path, device: str, report: Step) -> None:
    """Cut a section of the original and separate it with the section's own settings."""
    import separate as sep
    v_out, b_out = song_dir / job["vocal"], song_dir / job["bgm"]
    if v_out.is_file() and b_out.is_file():
        return
    work = v_out.parent / ("sepwork_" + v_out.stem[5:])
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        clip = work / "clip.wav"
        cut(song_dir / job["src"], clip, job["start"], job["dur"])
        s = job["sep"]
        prog = sep.Progress(report.lo, report.hi, report.stage, device)

        def split(src: Path, out: Path) -> tuple[Path, Path]:
            if s["sep_model"] == "demucs":
                sep.demucs_separate(src, out, device, prog)
            else:
                sep.roformer_separate(s["sep_model"], src, out, device, prog)
            return out / "vocals.wav", out / "instrumental.wav"

        vocal, bgm = split(clip, work / "p1")
        if s["bgm_refine"] == "second_pass":
            _, bgm = split(bgm, work / "p2")
        backings = []
        passes = {"lead_keep_backing": 1, "lead_keep_backing_x2": 2}.get(s["vocal_mode"], 0)
        for i in range(passes):
            kd = work / f"k{i + 1}"
            sep.roformer_separate("karaoke", vocal, kd, device, prog)
            vocal = kd / "lead.wav"
            backings.append(kd / "backing.wav")
        if backings:
            mixed = work / "bgm_plus_backing.wav"
            sum_tracks([bgm] + backings, mixed)
            bgm = mixed
        os.replace(vocal, v_out)
        os.replace(bgm, b_out)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_applio(tasks: list[dict], applio: dict, report: Step) -> dict:
    worker = Path(__file__).resolve().parent / "applio_rvc.py"
    py, cwd = applio.get("python") or "", applio.get("dir") or ""
    if not (py and Path(py).exists() and Path(cwd, "core.py").is_file()):
        raise FileNotFoundError("model_missing:applio")
    proc = subprocess.Popen([py, "-u", str(worker)], cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, creationflags=NO_WINDOW)
    err_tail: list[str] = []

    def read_err() -> None:
        for raw in proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                err_tail.append(line)
                del err_tail[:-30]
    err_thread = threading.Thread(target=read_err, daemon=True)
    err_thread.start()
    proc.stdin.write(json.dumps({"tasks": tasks}, ensure_ascii=False).encode("utf-8"))
    proc.stdin.close()
    error = None
    result: dict = {}
    n = max(1, len(tasks))
    for raw in proc.stdout:
        try:
            msg = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        if msg.get("type") == "progress":
            done = float(msg.get("percent") or 0)
            label = msg.get("message") or ""
            if msg.get("stage") == "rvc" and done < 100:
                label = f"{int(round(done * n / 100)) + 1}/{n} {label}".strip()
            report(done, label, "rvc_load" if msg.get("stage") == "rvc_load" else None)
        elif msg.get("type") == "log":
            protocol.log(msg.get("message", ""))
        elif msg.get("type") == "error":
            error = (msg.get("code"), msg.get("message"))
        elif msg.get("type") == "result":
            result = msg.get("data") or {}
    rc = proc.wait()
    err_thread.join(timeout=5)
    if error or rc != 0:
        detail = (error[1] if error else "") or "\n".join(err_tail[-8:])
        raise RuntimeError("rvc_failed:" + str(detail)[-800:])
    return result


def free_gpu() -> None:
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


def combine(male: Path, female: Path, mv: float, fv: float, out: Path) -> None:
    tmp = out.with_name(out.stem + ".part.wav")
    run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", male, "-i", female, "-filter_complex",
         f"[0:a]volume={mv:.2f}[m];[1:a]volume={fv:.2f}[f];[m][f]amix=inputs=2:duration=longest:normalize=0",
         "-ar", "44100", "-ac", "2", "-c:a", "pcm_f32le", tmp], timeout=600)
    os.replace(tmp, out)


def write_render(song_dir: Path, render: dict, mp3: Path, extra: dict) -> dict:
    base = song_dir / "renders"
    base.mkdir(parents=True, exist_ok=True)
    rid = render["id"]
    target = base / rid
    now = time.time()
    if render.get("replace") and (target / "render.json").is_file():
        info = json.loads((target / "render.json").read_text(encoding="utf-8"))
        old_audio = target / info.get("audio", "audio.mp3")
        replace_retry(mp3, target / "audio.mp3")
        if old_audio.name != "audio.mp3":
            old_audio.unlink(missing_ok=True)
        info.update({"audio": "audio.mp3", "bytes": (target / "audio.mp3").stat().st_size, "updated_at": now,
                     "title": info.get("title", "")})
        info.update(extra)
        write_json(target / "render.json", info)
        return info
    tmp = base / (rid + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    os.replace(mp3, tmp / "audio.mp3")
    info = {"schema_version": 1, "id": rid, "kind": "cover", "title": (render.get("title") or "")[:200],
            "audio": "audio.mp3", "bytes": (tmp / "audio.mp3").stat().st_size, "created_at": now, **extra}
    write_json(tmp / "render.json", info)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    os.replace(tmp, target)
    return info


MIX_STEPS = {"mix_read": 90, "mix_sections": 91, "mix_balance": 92, "mix_instrument": 93, "mix_master": 95}


def main() -> None:
    data = protocol.read_input()
    protocol.progress(0, "prepare", "")   # loading torch below takes a while on Windows
    song_dir = Path(data["song_dir"])
    plan = data["plan"]
    device = pick_device(data.get("device", "auto"))
    A = lambda rel: song_dir / rel  # noqa: E731
    try:
        stats: dict = {"started_at": time.time()}
        mark = {"t": time.time()}

        def lap(name: str) -> None:
            now = time.time()
            stats[name] = round(now - mark["t"], 1)
            mark["t"] = now

        # 1. stems
        import separate as sep
        layers = plan.get("layers") or []
        for i, layer in enumerate(layers):
            lo = 35 * i / max(1, len(layers))
            hi = 35 * (i + 1) / max(1, len(layers))
            stage = "separate" if layer["kind"] == "mix" else layer["kind"]
            try:
                sep.run_layer(layer, song_dir, device, sep.Progress(lo, hi, stage, device))
            except FileNotFoundError:
                raise
            except Exception as exc:  # noqa: BLE001
                shutil.rmtree(song_dir / "stems" / (layer["key"] + ".tmp"), ignore_errors=True)
                protocol.fail("separation_failed", str(exc)[-1500:])
        lap("separate_s")
        # 2. sections with their own separation, and plain cuts for re-converted sections
        for msg in plan.get("skipped") or []:
            protocol.log("section skipped: " + msg)
        failed: set[str] = set()
        seg = [j for j in plan.get("seg_jobs") or [] if not (A(j["vocal"]).is_file() and A(j["bgm"]).is_file())]
        for i, j in enumerate(seg):
            try:
                separate_segment(j, song_dir, device, Step(40 + 5 * i / len(seg), 40 + 5 * (i + 1) / len(seg),
                                                           "section_separate"))
            except Exception as exc:  # noqa: BLE001  (the old program kept the converted vocal there)
                protocol.log(f"section {j['start']:.1f}s could not be separated again, kept as it was: {str(exc)[-300:]}")
                failed |= {j["vocal"], j["bgm"]}
        # 3. key
        kjobs = [j for j in plan.get("key_jobs") or [] if not A(j["dst"]).is_file()]
        for i, j in enumerate(kjobs):
            protocol.progress(round(35 + 5 * i / max(1, len(kjobs)), 1), "key", j["name"])
            if j.get("dir"):
                import key_shift
                if not (A(j["dir"]) / "info.json").is_file():
                    stem = Path(j["src"]).stem
                    key_shift.shift_files([{"src": str(A(j["src"])), "dst": str(A(j["dst"]))}], int(plan["key"]),
                                          A(j["dir"]), {"tracks": [stem], "sources": {stem: j["src"]}})
            elif j["src"] in failed or not A(j["src"]).is_file():
                failed.add(j["dst"])
            else:
                key_shift_file(A(j["src"]), A(j["dst"]), int(plan["key"]))
        for j in plan.get("cut_jobs") or []:
            if not A(j["dst"]).is_file():
                cut(A(j["src"]), A(j["dst"]), j["start"], j["dur"])
        lap("prepare_s")
        # 4. RVC
        for t in plan.get("rvc_tasks") or []:
            if t["input"] in failed:
                failed.add(t["output"])
        tasks = [dict(t, input=str(A(t["input"])), output=str(A(t["output"])))
                 for t in plan.get("rvc_tasks") or [] if not A(t["output"]).is_file() and t["output"] not in failed]
        for t in tasks:   # the model must still be the one the plan was made with
            if not Path(t["pth"]).is_file():
                protocol.fail("model_not_found", Path(t["pth"]).name)
            if t.get("sig") and file_sig(t["pth"]) != t["sig"].split("#")[0]:
                protocol.fail("model_changed", Path(t["pth"]).name)
        if tasks:
            free_gpu()   # Applio runs in its own process: give it the graphics memory separation used
            info_rvc = run_applio(tasks, data.get("applio") or {}, Step(45, 85, "rvc"))
            stats["rvc_device"] = info_rvc.get("device", "")
            stats["rvc_gpu"] = info_rvc.get("gpu", "")
            stats["rvc_audio_s"] = info_rvc.get("audio_seconds")
        lap("rvc_s")
        # 5. male + female
        vocal = plan["vocal"]
        if vocal.get("combine") and not A(vocal["path"]).is_file():
            c = vocal["combine"]
            protocol.progress(85, "mf_combine", "")
            combine(A(c["male"]), A(c["female"]), c["male_vol"], c["female_vol"], A(vocal["path"]))
        # 6. melody
        midi = plan.get("midi")
        if midi and not A(midi["out"]).is_file():
            protocol.progress(86, "melody", "")
            try:
                import cover_melody
                n = cover_melody.transcribe_vocal_to_midi(str(A(midi["from"])), str(A(midi["out"])))
                protocol.log(f"melody notes: {n}")
            except Exception as exc:  # noqa: BLE001  (mix without the instrument, as the old program did)
                protocol.log(f"melody transcription failed, mixed without the instrument: {str(exc)[-300:]}")
        # 7. mix
        protocol.progress(90, "mix", "")
        import cover_mix
        mix = plan["mix"]
        sfonts = Path(data.get("soundfonts") or "")
        instrument = mix["instrument"]
        if instrument != "none" and mix["inst_vol"] > 0 and not cover_mix.instrument_available(instrument, sfonts):
            protocol.log(f"instrument {instrument} is not installed; mixed without it")
            instrument = "none"
        masks = [dict(m, src=str(A(m["src"]))) if m.get("src") else dict(m) for m in plan.get("masks") or []
                 if not (m.get("src") in failed)]
        tmp_dir = song_dir / "cover" / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        out_mp3 = tmp_dir / f"{data['render']['id']}_{os.getpid()}.mp3"
        info = cover_mix.mix_master_audio(
            str(A(vocal["path"])), str(A(plan["bgm"])), str(out_mp3), soundfonts=sfonts,
            vocal_vol=mix["vocal_vol"], bgm_vol=mix["bgm_vol"], inst_vol=mix["inst_vol"], instrument=instrument,
            midi_path=str(A(midi["out"])) if midi else None, octave_shift=mix["octave_shift"],
            reverb_wet=mix["reverb_wet"], vocal_masks=masks or None, orig_vocal_path=str(A(plan["orig_vocal"])),
            vol_segments=plan.get("vol_segments") or None, backing_paths=[str(A(b)) for b in plan.get("backings") or []],
            log=protocol.log, progress=lambda stage: protocol.progress(MIX_STEPS.get(stage, 90), stage, ""))
        lap("mix_s")
        stats["total_s"] = round(time.time() - stats.pop("started_at"), 1)
        protocol.log("timing: " + json.dumps(stats))
        # 8. records
        protocol.progress(97, "save", "")
        v = dict(data["version"])
        vfile = song_dir / "cover" / "versions" / v["id"] / "version.json"
        if vfile.is_file():   # keep a title the user changed while this job ran
            try:
                v["title"] = json.loads(vfile.read_text(encoding="utf-8")).get("title") or v.get("title")
            except (OSError, ValueError):
                pass
        render = write_render(song_dir, data["render"], out_mp3,
                              {"cover_version": v["id"], "duration": round(info["duration"], 3)})
        now = time.time()
        v.update({"schema_version": 1, "render_id": render["id"], "params": data["params"], "plan": {
            k: plan[k] for k in ("recipe", "tracks", "voice", "vocal", "bgm", "backings", "orig_vocal", "midi", "files", "key")},
            "duration": round(info["duration"], 3), "instrument_used": info["instrument_used"], "updated_at": now,
            "stats": stats})
        v.setdefault("created_at", now)
        write_json(song_dir / "cover" / "versions" / v["id"] / "version.json", v)
        protocol.progress(100, "done", "")
        protocol.result({"version_id": v["id"], "render_id": render["id"], "title": render.get("title", ""),
                         "stats": stats})
    except FileNotFoundError as exc:
        msg = str(exc)
        protocol.fail("model_missing" if msg.startswith("model_missing") else "file_not_found", msg[-500:])
    except RuntimeError as exc:
        msg = str(exc)
        if msg.startswith("file_in_use:"):
            protocol.fail("file_in_use", msg.split(":", 1)[1])
        if msg.startswith("rvc_failed:"):
            protocol.fail("rvc_failed", msg[len("rvc_failed:"):])
        if msg == "rubberband_missing":
            protocol.fail("rubberband_missing", "")
        protocol.fail("cover_failed", msg[-800:])
    except Exception as exc:  # noqa: BLE001
        protocol.fail("cover_failed", f"{type(exc).__name__}: {str(exc)[-800:]}")


if __name__ == "__main__":
    main()
