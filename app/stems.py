"""Separation recipes -> cached layers -> track files.

A recipe describes what a workspace needs:
  {"model": "demucs"|"bs_roformer"|"mel_roformer",
   "second_pass": bool,               # separate the instrumental again (cleaner backing)
   "lead": bool,                      # split vocals into lead / backing (karaoke model)
   "lead_from": "vocals"|"residual",  # which vocals the lead split uses
   "lead_passes": 1|2,                # 2 = split the lead again (harmonies the first pass missed)
   "male_female": null|"aufr33"|"sucial"}  # split (lead) vocals into male / female
Each step is a cached layer in <song>/stems/<key>/ whose key is derived from its
input and settings, so changing only a later step reuses the earlier ones.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SEPARATORS = ("demucs", "bs_roformer", "mel_roformer")
MF_MODELS = ("aufr33", "sucial")
KARAOKE_MODELS = {"aufr33": "karaoke", "becruily": "karaoke_becruily"}   # lead/backing split
DEMUCS_PARAMS = {"name": "htdemucs", "shifts": 1, "overlap": 0.25, "v": 1}
ROFORMER_PARAMS = {"batch_size": 1, "segment_size": 256, "overlap": 4, "v": 1}


class RecipeError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _h(*parts: Any) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, ensure_ascii=True).encode()).hexdigest()[:12]


def normalize(recipe: dict[str, Any] | None) -> dict[str, Any]:
    r = dict(recipe or {})
    model = r.get("model", "demucs")
    if model not in SEPARATORS:
        raise RecipeError("invalid_separator")
    mf = r.get("male_female") or None
    if mf is not None and mf not in MF_MODELS:
        raise RecipeError("invalid_male_female_model")
    lead_from = r.get("lead_from", "vocals")
    if lead_from not in ("vocals", "residual"):
        raise RecipeError("invalid_lead_from")
    second = bool(r.get("second_pass"))
    if lead_from == "residual" and not second:
        lead_from = "vocals"
    out = {"model": model, "second_pass": second, "lead": bool(r.get("lead")),
           "lead_from": lead_from, "male_female": mf}
    if out["lead"] and int(r.get("lead_passes") or 1) == 2:
        out["lead_passes"] = 2
    karaoke = r.get("karaoke", "aufr33")
    if karaoke not in KARAOKE_MODELS:
        raise RecipeError("invalid_karaoke_model")
    if out["lead"] and karaoke != "aufr33":
        out["karaoke"] = karaoke
    return out


def plan(song_dir: Path, song: dict[str, Any], recipe: dict[str, Any]) -> tuple[list[dict], dict[str, str]]:
    """Return (layers that still have to be computed, track -> relative file path)."""
    r = normalize(recipe)
    src = song.get("source") or {}
    if not src.get("audio"):
        raise RecipeError("song_has_no_audio")
    source_hash = src.get("source_hash") or src.get("audio")
    mix_rel = src["audio"]
    params = DEMUCS_PARAMS if r["model"] == "demucs" else ROFORMER_PARAMS
    layers: list[dict] = []
    tracks: dict[str, str] = {"mix": mix_rel}

    def need(key: str, spec: dict) -> None:
        if not (song_dir / "stems" / key / "info.json").is_file():
            layers.append({"key": key, **spec})

    k1 = _h("mix", source_hash, r["model"], params)
    need(k1, {"kind": "mix", "model": r["model"], "input": str(song_dir / mix_rel), "input_ref": mix_rel,
              "params": params})
    tracks["vocals"] = f"stems/{k1}/vocals.wav"
    tracks["instrumental"] = f"stems/{k1}/instrumental.wav"

    if r["second_pass"]:
        k2 = _h("second_pass", k1, r["model"], params)
        need(k2, {"kind": "second_pass", "model": r["model"], "input": str(song_dir / tracks["instrumental"]),
                  "input_ref": tracks["instrumental"], "mix": str(song_dir / mix_rel), "params": params})
        tracks["instrumental_first"] = tracks["instrumental"]
        tracks["instrumental"] = f"stems/{k2}/instrumental2.wav"
        tracks["residual_vocals"] = f"stems/{k2}/residual_vocals.wav"

    voice_rel = tracks["residual_vocals"] if (r["lead"] and r["lead_from"] == "residual") else tracks["vocals"]
    if r["lead"]:
        km = KARAOKE_MODELS[r.get("karaoke", "aufr33")]
        k3 = _h("lead", voice_rel, km, ROFORMER_PARAMS)
        need(k3, {"kind": "lead", "model": km, "input": str(song_dir / voice_rel), "input_ref": voice_rel,
                  "params": ROFORMER_PARAMS})
        tracks["lead"] = f"stems/{k3}/lead.wav"
        tracks["backing"] = f"stems/{k3}/backing.wav"
        if r.get("lead_passes") == 2:
            k3b = _h("lead", tracks["lead"], km, ROFORMER_PARAMS)
            need(k3b, {"kind": "lead", "model": km, "input": str(song_dir / tracks["lead"]),
                       "input_ref": tracks["lead"], "params": ROFORMER_PARAMS})
            tracks["lead_first"] = tracks["lead"]
            tracks["lead"] = f"stems/{k3b}/lead.wav"
            tracks["backing2"] = f"stems/{k3b}/backing.wav"
        voice_rel = tracks["lead"]

    if r["male_female"]:
        k4 = _h("male_female", voice_rel, r["male_female"], ROFORMER_PARAMS)
        need(k4, {"kind": "male_female", "model": r["male_female"], "input": str(song_dir / voice_rel),
                  "input_ref": voice_rel, "params": ROFORMER_PARAMS})
        tracks["male"] = f"stems/{k4}/male.wav"
        tracks["female"] = f"stems/{k4}/female.wav"

    tracks["voice"] = voice_rel  # the vocal line a workspace should analyse/convert
    return layers, tracks


def key_track(rel: str, semitones: int) -> tuple[str, str]:
    """Key copy of one track: (dir name under keys/, relative file path).

    One folder per source track and key, shared by the library page, sing & record
    and AI cover: whichever needs it first makes it, the others reuse it."""
    d = f"{_h('keytrack', rel)}_{'m' if semitones < 0 else 'p'}{abs(semitones)}"
    return d, f"keys/{d}/{Path(rel).name}"


def key_item(song_dir: Path, rel: str, semitones: int) -> dict[str, Any]:
    """Work item for workers/key_shift.py (absolute paths) for one track."""
    d, dst = key_track(rel, semitones)
    name = Path(rel).stem
    return {"src": str(song_dir / rel), "dst": str(song_dir / dst), "out_dir": str(song_dir / "keys" / d),
            "info": {"tracks": [name], "sources": {name: rel}}}


def recipe_id(recipe: dict[str, Any]) -> str:
    return _h("recipe", normalize(recipe))


# ------------------------------------------------------------------ stored copies
# Every separation layer (stems/<key>/) and key-shifted copy (keys/<dir>/) of a song is
# a cache: deleting one only means the next workspace that needs it computes it again.
DIR_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
REF_RE = re.compile(r"^(stems|keys)/([^/]+)/")


def dir_bytes(path: Path) -> int:
    total = 0
    for f in path.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def _read(path: Path) -> dict | None:
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else None
    except (OSError, ValueError):
        return None


def refs_in(value: Any, out: set[str]) -> set[str]:
    """Collect 'stems/<key>' / 'keys/<dir>' folders mentioned anywhere in a JSON value."""
    if isinstance(value, str):
        m = REF_RE.match(value)
        if m:
            out.add(f"{m.group(1)}/{m.group(2)}")
    elif isinstance(value, dict):
        for v in value.values():
            refs_in(v, out)
    elif isinstance(value, list):
        for v in value:
            refs_in(v, out)
    return out


def _parent(ref: str | None) -> str | None:
    m = REF_RE.match(ref or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def inventory(song_dir: Path) -> list[dict]:
    """All stored copies: [{"dir", "type": layer|key|incomplete, "bytes", "parents": [...], ...info}]."""
    out: list[dict] = []
    for top in ("stems", "keys"):
        base = song_dir / top
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            info = _read(d / "info.json")
            item: dict[str, Any] = {"dir": f"{top}/{d.name}", "bytes": dir_bytes(d)}
            if info is None:
                item.update({"type": "incomplete", "parents": []})
                try:
                    item["created_at"] = d.stat().st_mtime
                except OSError:
                    pass
            elif top == "stems":
                p = _parent(info.get("input"))
                item.update({"type": "layer", "kind": info.get("kind"), "model": info.get("model"), "input": info.get("input"),
                             "files": info.get("files") or [], "created_at": info.get("created_at"),
                             "device": info.get("device"), "parents": [p] if p else []})
            else:
                src = info.get("sources") or {}
                item.update({"type": "key", "semitones": info.get("semitones"), "tracks": info.get("tracks") or [],
                             "files": info.get("files") or [], "created_at": info.get("created_at"),
                             "parents": sorted({p for p in (_parent(v) for v in src.values()) if p})})
            out.append(item)
    return out


def dependents(items: list[dict], target: str) -> list[str]:
    """target plus every stored copy computed from it (directly or further down)."""
    gone = [target]
    changed = True
    while changed:
        changed = False
        for it in items:
            if it["dir"] not in gone and any(p in gone for p in it.get("parents") or []):
                gone.append(it["dir"])
                changed = True
    return gone
