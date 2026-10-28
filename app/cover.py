"""AI cover: parameters, voice models, versions and the work plan.

Pure Python (no numpy): imported by the server and by workers/cover_run.py.

A cover "version" is one conversion of a song with one set of settings. Its
mixed MP3 is a render of the song (songs/<id>/renders/<rid>/, kind "cover"),
so the MV workspace can use it. Layout inside the song folder:

  cover/settings.json             last settings used for this song (form state)
  cover/versions/<vid>/version.json
  cover/rvc/<hash>.wav            converted vocals (shared cache, keyed by input + model + settings)
  cover/midi/<hash>.mid           melody of a converted vocal (instrument track)
  cover/patches/                  uploaded clips (up_*), re-converted / re-separated sections
Every path stored in a version is relative to the song folder.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from . import stems as stems_mod

F0_METHODS = ("rmvpe", "fcpe", "crepe")
SEPARATORS = ("demucs", "bs_roformer", "mel_roformer")
VOCAL_MODES = ("full", "lead_keep_backing", "lead_keep_backing_x2")
LEAD_MODES = ("lead_keep_backing", "lead_keep_backing_x2")
INSTRUMENTS = ("none", "steel_guitar", "yangqin", "guzheng", "dizi", "duet")
OCTAVES = (99, 0, 1, -1)
MF_MODELS = ("aufr33", "sucial")
KARAOKE_MODELS = ("aufr33", "becruily")   # old 卡拉OK（拆主唱）模型
KEY_MIN, KEY_MAX = -8, 8
PATCH_PAD = 1.0          # seconds of context on each side when a section is re-converted
VERSION_ID = re.compile(r"^v[a-f0-9]{10}$")
MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,59}$")
EPOCH_FILE = re.compile(r"_(\d+)e_(\d+)s\.pth$")
PATCH_FILE = re.compile(r"^up_[a-f0-9]{12}\.wav$")

RVC_DEFAULTS = {"protect": 0.33, "index_rate": 0.75, "f0": "rmvpe", "envelope": 0.0, "autotune": False,
                "autotune_strength": 1.0, "clean": False, "clean_strength": 0.5}
MIX_DEFAULTS = {"vocal_vol": 0.95, "bgm_vol": 0.85, "inst_vol": 0.0, "instrument": "none",
                "octave_shift": 99, "reverb_wet": 0.10}
DEFAULTS: dict[str, Any] = {
    "model": "", "pitch": 0, "key": 0, "rvc": dict(RVC_DEFAULTS),
    "sep_model": "demucs", "bgm_refine": "none", "vocal_mode": "lead_keep_backing", "backing_on": True,
    "mf": None, "mix": dict(MIX_DEFAULTS), "masks": [], "vol_segments": [],
}


class CoverError(ValueError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


# ------------------------------------------------------------------ cleaning
def _num(v: Any, d: float, lo: float, hi: float, nd: int = 3) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return d
    if x != x:  # NaN
        return d
    return round(min(hi, max(lo, x)), nd)


def _int(v: Any, d: int, lo: int, hi: int) -> int:
    try:
        return int(min(hi, max(lo, int(round(float(v))))))
    except (TypeError, ValueError):
        return d


def clean_model_name(v: Any) -> str:
    name = str(v or "").strip()
    return name if MODEL_NAME.match(name.split("__e")[0]) and re.fullmatch(r"[A-Za-z0-9_.\-]+(__e\d+)?", name) else ""


def clean_rvc(p: Any, base: dict | None = None) -> dict:
    p = p if isinstance(p, dict) else {}
    b = dict(RVC_DEFAULTS)
    b.update(base or {})
    return {"protect": _num(p.get("protect", b["protect"]), b["protect"], 0, 0.5),
            "index_rate": _num(p.get("index_rate", b["index_rate"]), b["index_rate"], 0, 1),
            "f0": p.get("f0") if p.get("f0") in F0_METHODS else b["f0"],
            "envelope": _num(p.get("envelope", b["envelope"]), b["envelope"], 0, 1),
            "autotune": bool(p.get("autotune", b["autotune"])),
            "autotune_strength": _num(p.get("autotune_strength", b["autotune_strength"]), b["autotune_strength"], 0, 1),
            "clean": bool(p.get("clean", b["clean"])),
            "clean_strength": _num(p.get("clean_strength", b["clean_strength"]), b["clean_strength"], 0, 1)}


def clean_mix(p: Any) -> dict:
    p = p if isinstance(p, dict) else {}
    oc = _int(p.get("octave_shift", 99), 99, -1, 99)
    return {"vocal_vol": _num(p.get("vocal_vol", 0.95), 0.95, 0, 2, 2),
            "bgm_vol": _num(p.get("bgm_vol", 0.85), 0.85, 0, 2, 2),
            "inst_vol": _num(p.get("inst_vol", 0.0), 0.0, 0, 2, 2),
            "instrument": p.get("instrument") if p.get("instrument") in INSTRUMENTS else "none",
            "octave_shift": oc if oc in OCTAVES else 99,
            "reverb_wet": _num(p.get("reverb_wet", 0.10), 0.10, 0, 0.6, 2)}


def clean_side(p: Any, model: str, pitch: int, rvc: dict) -> dict:
    p = p if isinstance(p, dict) else {}
    out = {"model": clean_model_name(p.get("model")) or model, "pitch": _int(p.get("pitch", pitch), pitch, -24, 24),
           "keep": bool(p.get("keep")), "vol": _num(p.get("vol", 1.0), 1.0, 0, 2, 2)}
    out.update(clean_rvc(p.get("rvc") if isinstance(p.get("rvc"), dict) else p, rvc))
    return out


def clean_sep(p: Any) -> dict:
    p = p if isinstance(p, dict) else {}
    out = {"sep_model": p.get("sep_model") if p.get("sep_model") in SEPARATORS else "demucs",
           "vocal_mode": p.get("vocal_mode") if p.get("vocal_mode") in VOCAL_MODES else "full",
           "bgm_refine": "second_pass" if p.get("bgm_refine") == "second_pass" else "none"}
    if out["vocal_mode"] in LEAD_MODES and p.get("karaoke_model") == "becruily":
        out["karaoke_model"] = "becruily"
    return out


def clean_masks(masks: Any, model: str, pitch: int, rvc: dict) -> list[dict]:
    out = []
    for m in (masks if isinstance(masks, list) else [])[:100]:
        if not isinstance(m, dict):
            continue
        try:
            st, et = round(float(m.get("start")), 2), round(float(m.get("end")), 2)
        except (TypeError, ValueError):
            continue
        if not (0 <= st < et <= 36000):
            continue
        mode = m.get("mode") if m.get("mode") in ("mute", "original", "rvc", "file") else "mute"
        item: dict[str, Any] = {"start": st, "end": et, "mode": mode}
        if mode == "rvc":
            r = m.get("rvc") if isinstance(m.get("rvc"), dict) else {}
            item["rvc"] = {"model": clean_model_name(r.get("model")) or model,
                           "pitch": _int(r.get("pitch", pitch), pitch, -24, 24), **clean_rvc(r, rvc)}
            if m.get("sep"):
                item["sep"] = clean_sep(m.get("sep"))
        elif mode == "file":
            fn = os.path.basename(str(m.get("file") or ""))
            if not PATCH_FILE.match(fn):
                continue
            item.update(file=fn, name=str(m.get("name") or fn)[:80],
                        target="mix" if m.get("target") == "mix" else "vocal",
                        offset=_num(m.get("offset", 0), 0.0, -600, 600, 2))
            item["to_ai"] = bool(m.get("to_ai")) and item["target"] == "vocal"
            if item["to_ai"]:
                r = m.get("rvc") if isinstance(m.get("rvc"), dict) else {}
                item["rvc"] = {"model": clean_model_name(r.get("model")) or model,
                               "pitch": _int(r.get("pitch", pitch), pitch, -24, 24), **clean_rvc(r, rvc)}
        out.append(item)
    return sorted(out, key=lambda x: x["start"])


def clean_vol_segments(segs: Any) -> list[dict]:
    out = []
    for sg in (segs if isinstance(segs, list) else [])[:100]:
        if not isinstance(sg, dict):
            continue
        try:
            st, et = round(float(sg.get("start")), 2), round(float(sg.get("end")), 2)
            g = round(min(2.0, max(0.0, float(sg.get("gain")))), 2)
        except (TypeError, ValueError):
            continue
        tr = sg.get("track") if sg.get("track") in ("vocal", "bgm", "backing") else None
        if tr is None or st < 0 or et - st < 0.1 or abs(g - 1.0) < 1e-6:
            continue
        out.append({"track": tr, "start": st, "end": et, "gain": g})
    return sorted(out, key=lambda x: (x["start"], x["track"]))


def clean_params(p: Any) -> dict:
    p = p if isinstance(p, dict) else {}
    model = clean_model_name(p.get("model"))
    pitch = _int(p.get("pitch", 0), 0, -24, 24)
    rvc = clean_rvc(p.get("rvc"))
    out = {"model": model, "pitch": pitch, "key": _int(p.get("key", 0), 0, KEY_MIN, KEY_MAX), "rvc": rvc,
           "sep_model": p.get("sep_model") if p.get("sep_model") in SEPARATORS else "demucs",
           "bgm_refine": "second_pass" if p.get("bgm_refine") == "second_pass" else "none",
           "vocal_mode": p.get("vocal_mode") if p.get("vocal_mode") in VOCAL_MODES else "lead_keep_backing",
           "backing_on": p.get("backing_on") is not False, "mf": None, "mix": clean_mix(p.get("mix")),
           "masks": clean_masks(p.get("masks"), model, pitch, rvc),
           "vol_segments": clean_vol_segments(p.get("vol_segments"))}
    if p.get("karaoke_model") == "becruily":
        out["karaoke_model"] = "becruily"
    mf = p.get("mf")
    if isinstance(mf, dict) and mf.get("enabled", True):
        out["mf"] = {"sep_model": mf.get("sep_model") if mf.get("sep_model") in MF_MODELS else "aufr33",
                     "male": clean_side(mf.get("male"), model, pitch, rvc),
                     "female": clean_side(mf.get("female"), model, pitch, rvc)}
    return out


def models_used(p: dict) -> set[str]:
    names = set()
    if p.get("mf"):
        names |= {p["mf"][s]["model"] for s in ("male", "female") if not p["mf"][s]["keep"]}
    else:
        names.add(p["model"])
    for m in p.get("masks") or []:
        if m.get("rvc"):
            names.add(m["rvc"]["model"])
    return {n for n in names if n}


def validate(p: dict) -> None:
    if p.get("mf"):
        sides = [p["mf"][s] for s in ("male", "female")]
        if all(sp["keep"] for sp in sides):
            raise CoverError("mf_both_original")
        if any(not sp["keep"] and not sp["model"] for sp in sides):
            raise CoverError("model_required")
    elif not p.get("model"):
        raise CoverError("model_required")
    for m in p.get("masks") or []:
        if m.get("rvc") and not m["rvc"].get("model"):
            raise CoverError("model_required")


# ------------------------------------------------------------------ voice models
def model_files(d: Path) -> tuple[Path | None, Path | None]:
    pths = sorted((x for x in d.glob("*.pth") if x.is_file() and not re.match(r"^[GD]_\d+\.pth$", x.name)),
                  key=lambda x: x.stat().st_mtime, reverse=True)
    idx = sorted((x for x in d.glob("*.index") if x.is_file()),
                 key=lambda x: (not x.name.startswith("added_"), -x.stat().st_mtime))
    return (pths[0] if pths else None), (idx[0] if idx else None)


def epoch_files(d: Path) -> list[dict]:
    out = []
    for f in (d / "epochs").glob("*.pth") if (d / "epochs").is_dir() else []:
        m = EPOCH_FILE.search(f.name)
        if m:
            out.append({"epoch": int(m.group(1)), "file": f.name, "size": f.stat().st_size})
    return sorted(out, key=lambda x: x["epoch"])


def model_dir(voices: Path, name: str) -> Path | None:
    name = (name or "").strip()
    if not MODEL_NAME.match(name) or not voices.is_dir():
        return None
    for d in voices.iterdir():
        if d.is_dir() and d.name.lower() == name.lower() and not d.name.startswith("_"):
            return d
    return None


def list_models(voices: Path) -> list[dict]:
    out = []
    if not voices.is_dir():
        return out
    for d in sorted(voices.iterdir(), key=lambda x: x.name.lower()):
        if not d.is_dir() or d.name.startswith((".", "_")) or not MODEL_NAME.match(d.name):
            continue
        pth, idx = model_files(d)
        if not pth:
            continue
        desc = ""
        for txt in d.glob("*.txt"):
            try:
                desc = txt.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                pass
            break
        out.append({"name": d.name, "pth": pth.name, "index": idx.name if idx else None, "size": pth.stat().st_size,
                    "mtime": pth.stat().st_mtime, "epochs": epoch_files(d),
                    "has_loss": (d / "epochs" / "loss.json").is_file(), "description": desc})
    return out


def resolve_model(voices: Path, name: str) -> dict:
    """name or name__e<epoch> -> {"pth", "index", "sig"}; raises CoverError(model_not_found)."""
    base, _, ep = name.partition("__e")
    d = model_dir(voices, base)
    if not d:
        raise CoverError("model_not_found", 404)
    pth, idx = model_files(d)
    if ep:
        hit = [e for e in epoch_files(d) if str(e["epoch"]) == ep]
        if not hit:
            raise CoverError("model_not_found", 404)
        pth = d / "epochs" / hit[0]["file"]
    if not pth:
        raise CoverError("model_not_found", 404)

    def sig(p: Path | None) -> str:
        if not p:
            return ""
        st = p.stat()
        return f"{p.name}|{st.st_size}|{int(st.st_mtime)}"
    return {"name": name, "pth": str(pth), "index": str(idx) if idx else "", "sig": sig(pth) + "#" + sig(idx)}


# ------------------------------------------------------------------ planning
def _h(*parts: Any) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str).encode()).hexdigest()[:16]


def _rvc_sig(r: dict) -> dict:
    keys = ("protect", "index_rate", "f0", "envelope", "autotune", "clean")
    s = {k: r[k] for k in keys}
    if r["autotune"]:
        s["autotune_strength"] = r["autotune_strength"]
    if r["clean"]:
        s["clean_strength"] = r["clean_strength"]
    return s


def recipe_for(p: dict) -> dict:
    lead = p["vocal_mode"] in LEAD_MODES and not p.get("mf")
    r = {"model": p["sep_model"], "second_pass": p["bgm_refine"] == "second_pass", "lead": lead}
    if lead and p["vocal_mode"] == "lead_keep_backing_x2":
        r["lead_passes"] = 2
    if lead and p.get("karaoke_model") == "becruily":
        r["karaoke"] = "becruily"
    if p.get("mf"):
        r["male_female"] = p["mf"]["sep_model"]
    return r


def plan(song_dir: Path, song: dict, p: dict, resolve: Callable[[str], dict],
         reuse: dict | None = None) -> dict:
    """Everything the worker has to do (paths relative to the song folder).

    reuse: the "vocal" entry of the version being remixed. Its converted vocal
    (or male / female sides) is used as it is, so a remix never needs the voice
    model again (the model may have been deleted or retrained since).
    """
    skipped: list[str] = []
    layers, tracks = stems_mod.plan(song_dir, song, recipe_for(p))
    key = p["key"]
    lead = p["vocal_mode"] in LEAD_MODES and not p.get("mf")
    voice = tracks["vocals"] if p.get("mf") else tracks["voice"]
    src = song.get("source") or {}
    src_sig = src.get("source_hash") or src.get("audio")

    keyed: dict[str, str] = {}
    key_jobs: list[dict] = []

    def shifted(name: str, rel: str) -> str:
        if not key:
            return rel
        if name in keyed:
            return keyed[name]
        d, dst = stems_mod.key_track(rel, key)   # shared with the library page and sing & record
        key_jobs.append({"name": name, "src": rel, "dst": dst, "dir": f"keys/{d}"})
        keyed[name] = dst
        return dst

    rvc_tasks: list[dict] = []

    def rvc_task(input_rel: str, model: str, pitch: int, r: dict, label: str, input_sig: str | None = None) -> str:
        m = resolve(model)
        h = _h("rvc", input_sig or input_rel, m["sig"], pitch, _rvc_sig(r))
        out = f"cover/rvc/{h}.wav"
        if not any(t["output"] == out for t in rvc_tasks):
            rvc_tasks.append({"input": input_rel, "output": out, "pth": m["pth"], "index": m["index"], "pitch": pitch,
                              "label": label, "sig": m["sig"], **{k: r[k] for k in RVC_DEFAULTS}})
        return out

    files: list[str] = []
    vocal: dict[str, Any]
    if p.get("mf"):
        mf = p["mf"]
        sides = {}
        old_sides = (reuse or {}).get("combine") or {}
        for side in ("male", "female"):
            sp = mf[side]
            if old_sides.get(side) and (song_dir / old_sides[side]).is_file():
                sides[side] = old_sides[side]
            elif sp["keep"]:
                sides[side] = shifted(side, tracks[side])
            else:
                sides[side] = rvc_task(tracks[side], sp["model"], sp["pitch"] + key, sp, side)
        mixed = f"cover/rvc/mf_{_h('mf', sides, mf['male']['vol'], mf['female']['vol'])}.wav"
        vocal = {"path": mixed, "combine": {"male": sides["male"], "female": sides["female"],
                                            "male_vol": mf["male"]["vol"], "female_vol": mf["female"]["vol"]}}
        files += [mixed] + [v for v in sides.values() if v.startswith("cover/")]
    elif reuse and not reuse.get("combine") and reuse.get("path") and (song_dir / reuse["path"]).is_file():
        out = reuse["path"]
        vocal = {"path": out}
        files.append(out)
    else:
        out = rvc_task(voice, p["model"], p["pitch"] + key, p["rvc"], "main")
        vocal = {"path": out}
        files.append(out)

    backings = []
    if lead and p["backing_on"]:
        backings = [shifted("backing", tracks["backing"])]
        if tracks.get("backing2"):
            backings.append(shifted("backing2", tracks["backing2"]))
    bgm = shifted("instrumental", tracks["instrumental"])

    # vocal sections
    mix_masks: list[dict] = []
    seg_jobs: list[dict] = []
    cut_jobs: list[dict] = []
    for m in p.get("masks") or []:
        if m["mode"] in ("mute", "original"):
            mix_masks.append({"start": m["start"], "end": m["end"], "mode": m["mode"]})
        elif m["mode"] == "rvc":
            pr = m["rvc"]
            c0 = max(0.0, m["start"] - PATCH_PAD)
            dur = round(m["end"] + PATCH_PAD - c0, 3)
            seg_bgm = None
            if m.get("sep"):
                sp = m["sep"]
                hs = _h("sep", src_sig, c0, dur, sp)
                v_rel, b_rel = f"cover/patches/sepv_{hs}.wav", f"cover/patches/sepb_{hs}.wav"
                if not any(j["vocal"] == v_rel for j in seg_jobs):
                    seg_jobs.append({"src": tracks["mix"], "start": c0, "dur": dur, "sep": sp, "vocal": v_rel,
                                     "bgm": b_rel})
                rvc_in, in_sig = v_rel, None
                seg_bgm = b_rel
                if key:
                    kb = f"cover/patches/sepb_{hs}_k{key}.wav"
                    key_jobs.append({"name": "segment", "src": b_rel, "dst": kb, "dir": None})
                    seg_bgm = kb
                files += [v_rel, b_rel] + ([seg_bgm] if seg_bgm != b_rel else [])
            else:
                hc = _h("cut", voice, c0, dur)
                rvc_in = f"cover/patches/cut_{hc}.wav"
                if not any(j["dst"] == rvc_in for j in cut_jobs):
                    cut_jobs.append({"src": voice, "start": c0, "dur": dur, "dst": rvc_in})
                in_sig = rvc_in
                files.append(rvc_in)
            clip = rvc_task(rvc_in, pr["model"], pr["pitch"] + key, pr, f"{m['start']:.1f}-{m['end']:.1f}s", in_sig)
            files.append(clip)
            mix_masks.append({"start": m["start"], "end": m["end"], "mode": "replace", "target": "vocal",
                              "src": clip, "src_start": c0, "match": False})
            if seg_bgm:
                mix_masks.append({"start": m["start"], "end": m["end"], "mode": "replace", "target": "bgm",
                                  "src": seg_bgm, "src_start": c0, "match": False})
        elif m["mode"] == "file":
            src_rel = f"cover/patches/{m['file']}"
            if not (song_dir / src_rel).is_file():
                skipped.append(f"clip missing: {m.get('name') or m['file']} ({m['start']:.1f}-{m['end']:.1f}s)")
                continue
            files.append(src_rel)
            if m.get("to_ai"):
                pr = m["rvc"]
                src_rel = rvc_task(src_rel, pr["model"], pr["pitch"], pr, m.get("name", "file"))
                files.append(src_rel)
            mix_masks.append({"start": m["start"], "end": m["end"], "mode": "replace",
                              "target": m.get("target", "vocal"), "src": src_rel,
                              "src_start": round(m["start"] + float(m.get("offset") or 0), 3), "match": True})

    orig_vocal = shifted("voice", voice) if any(m["mode"] == "original" for m in p.get("masks") or []) else voice
    mix = dict(p["mix"])
    midi = None
    if mix["instrument"] != "none" and mix["inst_vol"] > 0:
        midi = {"from": vocal["path"], "out": f"cover/midi/{_h('midi', vocal['path'])}.mid"}
        files.append(midi["out"])
    need_gpu = bool(layers) or bool(seg_jobs and any(not (song_dir / j["vocal"]).is_file() for j in seg_jobs)) \
        or any(not (song_dir / t["output"]).is_file() for t in rvc_tasks)
    return {"recipe": recipe_for(p), "layers": layers, "tracks": tracks, "voice": voice, "key": key,
            "key_jobs": key_jobs, "seg_jobs": seg_jobs, "cut_jobs": cut_jobs, "rvc_tasks": rvc_tasks,
            "vocal": vocal, "bgm": bgm, "backings": backings, "orig_vocal": orig_vocal, "masks": mix_masks,
            "vol_segments": p.get("vol_segments") or [], "mix": mix, "midi": midi,
            "files": sorted(set(files)), "need_gpu": need_gpu, "skipped": skipped}


# ------------------------------------------------------------------ storage
def cover_dir(song_dir: Path) -> Path:
    return song_dir / "cover"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def list_versions(song_dir: Path) -> list[dict]:
    base = cover_dir(song_dir) / "versions"
    out = []
    if base.is_dir():
        for d in base.iterdir():
            if VERSION_ID.match(d.name):
                v = read_json(d / "version.json")
                if isinstance(v, dict):
                    out.append(v)
    out.sort(key=lambda v: v.get("created_at", 0), reverse=True)
    return out


def load_version(song_dir: Path, vid: str) -> dict:
    if not VERSION_ID.match(vid or ""):
        raise CoverError("version_not_found", 404)
    v = read_json(cover_dir(song_dir) / "versions" / vid / "version.json")
    if not isinstance(v, dict):
        raise CoverError("version_not_found", 404)
    return v


def new_version_id() -> str:
    return "v" + uuid.uuid4().hex[:10]


def next_number(song_dir: Path) -> int:
    return max([int(v.get("number") or 0) for v in list_versions(song_dir)] + [0]) + 1


def version_label(p: dict) -> str:
    def name(model: str, pitch: int) -> str:
        return model if not pitch else "%s %+d" % (model, pitch)
    if p.get("mf"):
        m, f = p["mf"]["male"], p["mf"]["female"]
        label = "%s + %s" % ("Original" if m["keep"] else name(m["model"], m["pitch"]),
                             "Original" if f["keep"] else name(f["model"], f["pitch"]))
    else:
        label = name(p["model"], p["pitch"])
    if p["key"]:
        label += " · Key %+d" % p["key"]
    return label


def referenced_files(song_dir: Path) -> set[str]:
    refs: set[str] = set()
    for v in list_versions(song_dir):
        refs |= set((v.get("plan") or {}).get("files") or [])
    settings = read_json(cover_dir(song_dir) / "settings.json", {}) or {}
    for m in (settings.get("masks") or []):
        if isinstance(m, dict) and m.get("file"):
            refs.add(f"cover/patches/{os.path.basename(str(m['file']))}")
    return refs


GARBAGE_KINDS = ("rvc", "midi", "patches", "tmp", "preview")


def garbage(song_dir: Path, min_age_s: float = 600, keep_recent_s: float = 600, dry_run: bool = False) -> dict:
    """Cached cover files no version (or the saved form) uses any more, per kind: {kind: {"files", "bytes"}}.
    dry_run lists them (old 🧹 清理中間檔 showed the list first); otherwise they are deleted."""
    refs = referenced_files(song_dir)
    now = time.time()
    out: dict[str, dict] = {}
    for sub in GARBAGE_KINDS:
        d = cover_dir(song_dir) / sub
        if not d.is_dir():
            continue
        for f in d.iterdir():
            rel = f"cover/{sub}/{f.name}"
            try:
                age = min_age_s if sub in ("rvc", "midi", "tmp") else max(min_age_s, keep_recent_s)
                if rel in refs or now - f.stat().st_mtime < age:
                    continue
                if f.is_dir():
                    size = sum(x.stat().st_size for x in f.rglob("*") if x.is_file())
                    if not dry_run:
                        shutil.rmtree(f)
                else:
                    size = f.stat().st_size
                    if not dry_run:
                        f.unlink()
            except OSError:
                continue
            k = out.setdefault(sub, {"files": 0, "bytes": 0})
            k["files"] += 1
            k["bytes"] += size
    return out


def collect_garbage(song_dir: Path, min_age_s: float = 600, keep_recent_s: float = 600) -> int:
    """Delete cached cover files no version (or the saved form) uses any more. Returns bytes freed."""
    return sum(k["bytes"] for k in garbage(song_dir, min_age_s, keep_recent_s).values())
