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
from pathlib import Path
from typing import Any

SEPARATORS = ("demucs", "bs_roformer", "mel_roformer")
MF_MODELS = ("aufr33", "sucial")
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
        k3 = _h("lead", voice_rel, "karaoke", ROFORMER_PARAMS)
        need(k3, {"kind": "lead", "model": "karaoke", "input": str(song_dir / voice_rel), "input_ref": voice_rel,
                  "params": ROFORMER_PARAMS})
        tracks["lead"] = f"stems/{k3}/lead.wav"
        tracks["backing"] = f"stems/{k3}/backing.wav"
        if r.get("lead_passes") == 2:
            k3b = _h("lead", tracks["lead"], "karaoke", ROFORMER_PARAMS)
            need(k3b, {"kind": "lead", "model": "karaoke", "input": str(song_dir / tracks["lead"]),
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


def key_dir_name(tracks: dict[str, str], names: list[str], semitones: int) -> str:
    base = _h("key", sorted((n, tracks[n]) for n in names))
    return f"{base}_{'m' if semitones < 0 else 'p'}{abs(semitones)}"


def recipe_id(recipe: dict[str, Any]) -> str:
    return _h("recipe", normalize(recipe))
