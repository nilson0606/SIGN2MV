"""AI cover: master mix (port of AI_COVER_MV scripts/render_instrument_track.py).

The mixing math is kept as it was in the old system so a cover sounds the same:
  * converted vocal: 80 Hz high-pass, peak-normalised, x vocal_vol x 0.86
  * accompaniment (instrumental [+ original backing vocals]): peak-normalised, x bgm_vol x 0.88
  * optional melody instrument (from the converted vocal's MIDI): x inst_vol x 0.85
  * per-section volume envelopes (vocal / bgm / backing, 80 ms crossfades)
  * vocal sections: mute / original singer / replaced clip (30-50 ms crossfades)
  * 1.5 s tail fade, look-ahead limiter at 0.96, MP3 320 kbps
Differences: sound font / sample folders are parameters (models/soundfonts), the
temporary WAV is written next to the output, and messages go to a log callback.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
import scipy.signal
import soundfile as sf

from common import NO_WINDOW, ffmpeg

TARGET_SR = 44100
PITCH_TO_NAME = {0: 'C', 1: 'C#', 2: 'D', 3: 'D#', 4: 'E', 5: 'F', 6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'Bb', 11: 'B'}
INSTRUMENTS = ("none", "steel_guitar", "yangqin", "guzheng", "dizi", "duet")
GM_PROGRAMS = {"steel_guitar": 25, "yangqin": 15}


def _noop(_msg: str) -> None:
    pass


def _sample_name(pitch: int) -> str:
    return f'{PITCH_TO_NAME[pitch % 12]}{pitch // 12 - 1}.ogg'


def load_instrument_samples(sample_dir, notes, target_sr=TARGET_SR):
    cache = {}
    for n in notes:
        fn = _sample_name(n.pitch)
        if fn not in cache:
            fp = os.path.join(sample_dir, fn)
            if not os.path.exists(fp):
                continue
            data, sr = sf.read(fp)
            if data.ndim == 1:
                data = np.stack([data, data], axis=1)
            if sr != target_sr:
                data = scipy.signal.resample(data, int(len(data) * target_sr / sr))
            cache[fn] = data.astype(np.float32)
    return cache


def _render_samples(notes, sample_cache, total_samples, target_sr, min_dur, attack_s, release_s, vel_exp):
    out = np.zeros((total_samples, 2), dtype=np.float32)
    for n in notes:
        fn = _sample_name(n.pitch)
        if fn not in sample_cache:
            continue
        samp = sample_cache[fn]
        start_sample = int(round(n.start * target_sr))
        if start_sample >= total_samples:
            continue
        dur_samples = int(max(n.end - n.start, min_dur) * target_sr)
        attack_samples = int(attack_s * target_sr)
        note_len = min(len(samp), dur_samples + int(release_s * target_sr))
        wave = samp[:note_len].copy()
        if attack_samples and note_len > attack_samples:
            wave[:attack_samples] *= np.linspace(0.0, 1.0, attack_samples, dtype=np.float32)[:, None]
        if note_len > dur_samples:
            wave[dur_samples:] *= np.linspace(1.0, 0.0, note_len - dur_samples, dtype=np.float32)[:, None]
        wave *= (n.velocity / 127.0) ** vel_exp
        end_sample = min(total_samples, start_sample + note_len)
        out[start_sample:end_sample] += wave[:end_sample - start_sample]
    peak = np.max(np.abs(out))
    if peak > 0:
        out = out / peak * 0.90
    return out


def render_guzheng(notes, sample_cache, total_samples, target_sr=TARGET_SR):
    return _render_samples(notes, sample_cache, total_samples, target_sr, 0.32, 0.0, 1.35, 0.85)


def render_dizi(notes, sample_cache, total_samples, target_sr=TARGET_SR):
    return _render_samples(notes, sample_cache, total_samples, target_sr, 0.28, 0.022, 0.12, 0.90)


def render_sf2_program(notes, sf_path, program, total_samples, target_sr=TARGET_SR):
    # Offline rendering only (no synth.start(): that would also play to the speakers).
    import tinysoundfont
    synth = tinysoundfont.Synth(samplerate=target_sr)
    sfid = synth.sfload(str(sf_path))
    synth.program_select(0, sfid, 0, program)
    events = []
    for n in notes:
        events.append((n.start, 'on', n.pitch, n.velocity))
        events.append((n.end, 'off', n.pitch, 0))
    events.sort(key=lambda x: x[0])
    out = np.zeros((total_samples, 2), dtype=np.float32)
    ev_idx, curr_sample, block_size = 0, 0, 512
    while curr_sample < total_samples:
        curr_time = curr_sample / target_sr
        while ev_idx < len(events) and events[ev_idx][0] <= curr_time:
            _t, ev_type, pitch, vel = events[ev_idx]
            if ev_type == 'on':
                synth.noteon(0, pitch, vel)
            else:
                synth.noteoff(0, pitch)
            ev_idx += 1
        n_samples = min(block_size, total_samples - curr_sample)
        block = np.frombuffer(synth.generate_simple(n_samples), dtype=np.float32).reshape(-1, 2)
        out[curr_sample:curr_sample + n_samples] = block
        curr_sample += n_samples
    peak = np.max(np.abs(out))
    if peak > 0:
        out = out / peak * 0.90
    return out


def apply_acoustic_ambience(audio, target_sr=TARGET_SR, wet=0.10):
    if wet <= 0:
        return audio
    rev_l = np.zeros_like(audio[:, 0])
    rev_r = np.zeros_like(audio[:, 1])
    for d_ms, g in zip([24, 38, 52, 68], [0.28, 0.22, 0.16, 0.11]):
        d_samp = int(d_ms * target_sr / 1000)
        if d_samp < len(audio):
            rev_l[d_samp:] += audio[:-d_samp, 0] * g
            rev_r[d_samp:] += audio[:-d_samp, 1] * g
    sos = scipy.signal.butter(2, 3500, btype='lowpass', fs=target_sr, output='sos')
    rev = np.stack([scipy.signal.sosfilt(sos, rev_l), scipy.signal.sosfilt(sos, rev_r)], axis=1)
    mixed = audio * (1.0 - wet) + rev * wet
    peak = np.max(np.abs(mixed))
    if peak > 0.95:
        mixed = mixed / peak * 0.95
    return mixed


def instrument_available(instrument: str, soundfonts: Path) -> bool:
    sf2 = soundfonts / "GeneralUser-GS.sf2"
    if instrument == "none":
        return True
    if instrument in GM_PROGRAMS:
        return sf2.is_file()
    dirs = {"guzheng": ["guzheng"], "dizi": ["dizi"], "duet": ["guzheng", "dizi"]}.get(instrument, [])
    return bool(dirs) and all(any((soundfonts / d).glob("*.ogg")) for d in dirs)


def render_instrument(instrument_type, midi_path, total_samples, soundfonts: Path, sr=TARGET_SR, octave_shift=99,
                      reverb_wet=0.10):
    import pretty_midi
    if instrument_type == "none" or not os.path.exists(midi_path):
        return None
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    if not pm.instruments or not pm.instruments[0].notes:
        return None
    notes = pm.instruments[0].notes
    # Octave: 99 = auto (shift up an octave when the melody sits low), else -1/0/+1 octaves.
    if octave_shift == 99:
        shift = 12 if sum(n.pitch for n in notes) / len(notes) < 58 else 0
    else:
        shift = int(octave_shift * 12)
    if shift:
        for n in notes:
            n.pitch = int(np.clip(n.pitch + shift, 24, 108))
    sf2 = soundfonts / "GeneralUser-GS.sf2"
    if instrument_type in GM_PROGRAMS:
        raw = render_sf2_program(notes, sf2, GM_PROGRAMS[instrument_type], total_samples, target_sr=sr)
    elif instrument_type == "guzheng":
        raw = render_guzheng(notes, load_instrument_samples(soundfonts / "guzheng", notes, sr), total_samples, sr)
    elif instrument_type == "dizi":
        raw = render_dizi(notes, load_instrument_samples(soundfonts / "dizi", notes, sr), total_samples, sr)
    elif instrument_type == "duet":
        gz = render_guzheng(notes, load_instrument_samples(soundfonts / "guzheng", notes, sr), total_samples, sr)
        dz = render_dizi(notes, load_instrument_samples(soundfonts / "dizi", notes, sr), total_samples, sr)
        raw = gz * 0.5 + dz * 0.5
    else:
        return None
    wet = apply_acoustic_ambience(raw, target_sr=sr, wet=reverb_wet)
    peak = np.max(np.abs(wet))
    if peak > 0:
        wet = wet / peak * 0.90
    return wet


def mask_envelope(total_samples, ranges, sr=TARGET_SR, fade_s=0.03):
    """1 inside the ranges, 0 outside; raised-cosine ramps at the edges (no clicks)."""
    env = np.zeros(total_samples, dtype=np.float32)
    fl = max(1, int(fade_s * sr))
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fl))).astype(np.float32)
    for st, et in ranges:
        a, b = max(0, int(st * sr)), min(total_samples, int(et * sr))
        if b <= a:
            continue
        env[a:b] = 1.0
        f_in = min(fl, b - a)
        lo = max(0, a - f_in)
        env[lo:a] = np.maximum(env[lo:a], ramp[fl - (a - lo):])
        hi = min(total_samples, b + f_in)
        env[b:hi] = np.maximum(env[b:hi], ramp[::-1][:hi - b])
    return env


def _rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0


def _read_stereo(path, sr=TARGET_SR):
    with open(path, 'rb') as f:
        d, d_sr = sf.read(f, dtype='float32')
    if d.ndim == 1:
        d = np.stack([d, d], axis=1)
    d = d[:, :2]
    if d_sr != sr:
        d = scipy.signal.resample(d, int(round(len(d) * sr / d_sr))).astype(np.float32)
    return d


def _fit(d, total_samples):
    if len(d) < total_samples:
        return np.pad(d, ((0, total_samples - len(d)), (0, 0)))
    return d[:total_samples]


def load_aligned(path, src_start, total_samples, sr=TARGET_SR):
    """Place a clip so that its sample 0 sits at src_start seconds of the song."""
    if not (path and os.path.exists(path)):
        return None
    d = _read_stereo(path, sr)
    out = np.zeros((total_samples, 2), dtype=np.float32)
    off = int(round(float(src_start) * sr))
    a, b = max(0, off), min(total_samples, off + len(d))
    if b > a:
        out[a:b] = d[a - off:b - off]
    return out


def apply_replace(base, m, src, keep_mask, sr=TARGET_SR, fade_s=0.05):
    """Replace base[start:end] by src (50 ms fades); match=True levels src to the base."""
    n = len(base)
    env = mask_envelope(n, [(m["start"], m["end"])], sr, fade_s)
    scale = 1.0
    if m.get("match", True):
        a, b = max(0, int(m["start"] * sr)), min(n, int(m["end"] * sr))
        seg = src[a:b]
        active = np.abs(seg).max(axis=1) > 1e-4 if seg.size else np.zeros(0, bool)
        r_src = _rms(seg[active]) if active.any() else 0.0
        r_ref = _rms(base[a:b]) if m.get("target") == "mix" else _rms(base[keep_mask])
        if r_src > 1e-6 and r_ref > 1e-6:
            scale = float(np.clip(r_ref / r_src, 0.1, 10.0))
    return base * (1.0 - env)[:, None] + src * scale * env[:, None]


def apply_vocal_masks(v_data, masks, orig_data=None, sr=TARGET_SR, log: Callable[[str], None] = _noop):
    n = len(v_data)
    masks = [m for m in masks if not (m.get("mode") == "replace" and m.get("target") in ("mix", "bgm"))]
    mute_env = mask_envelope(n, [(m["start"], m["end"]) for m in masks if m.get("mode") == "mute"], sr)
    orig_ranges = [(m["start"], m["end"]) for m in masks if m.get("mode") == "original"]
    out = v_data * (1.0 - mute_env)[:, None]
    if orig_ranges:
        orig_env = mask_envelope(n, orig_ranges, sr)
        if orig_data is None:
            out = out * (1.0 - orig_env)[:, None]
            log("original vocal track missing: 'original' sections are muted")
        else:
            keep = (mute_env < 0.5) & (orig_env < 0.5)
            r_ai, r_or = _rms(v_data[keep]), _rms(orig_data[keep])
            scale = float(np.clip((r_ai / r_or) if r_or > 1e-6 and r_ai > 1e-6 else 1.0, 0.25, 4.0))
            out = out * (1.0 - orig_env)[:, None] + orig_data * scale * orig_env[:, None]
    rep_masks = [m for m in masks if m.get("mode") == "replace" and m.get("target", "vocal") == "vocal"]
    if rep_masks:
        keep = mask_envelope(n, [(m["start"], m["end"]) for m in masks], sr) < 0.5
        for m in rep_masks:
            src = load_aligned(m.get("src"), m.get("src_start", m["start"]), n, sr)
            if src is None:
                log(f"replacement clip missing: {m.get('src')}; section muted")
                out = out * (1.0 - mask_envelope(n, [(m["start"], m["end"])], sr))[:, None]
                continue
            out = apply_replace(out, m, src, keep if keep.any() else np.ones(n, bool), sr)
    return out


def gain_envelope(total_samples, segments, sr=TARGET_SR, fade_s=0.08):
    env = np.ones(total_samples, dtype=np.float32)
    for sgm in segments:
        g = float(sgm.get("gain", 1.0))
        if abs(g - 1.0) < 1e-6:
            continue
        env *= (1.0 + (g - 1.0) * mask_envelope(total_samples, [(sgm["start"], sgm["end"])], sr, fade_s))
    return env


def mix_master_audio(vocal_path, bgm_path, out_mp3_path, *, soundfonts: Path, vocal_vol=0.95, bgm_vol=0.85,
                     inst_vol=0.0, instrument="none", midi_path=None, octave_shift=99, reverb_wet=0.10,
                     limiter_ceiling=0.96, vocal_masks=None, orig_vocal_path=None, vol_segments=None,
                     backing_paths=None, log: Callable[[str], None] = _noop,
                     progress: Callable[[str], None] = _noop) -> dict:
    for p, what in ((vocal_path, "vocal"), (bgm_path, "accompaniment")):
        if not os.path.exists(p):
            raise FileNotFoundError(f"{what} input not found: {p}")
    progress("mix_read")
    v_data = _read_stereo(vocal_path)
    b_data = _read_stereo(bgm_path)
    sr = TARGET_SR
    total_samples = max(len(v_data), len(b_data))
    v_data = _fit(v_data, total_samples)
    b_data = _fit(b_data, total_samples)

    if vocal_masks:
        progress("mix_sections")
        o_data = None
        if orig_vocal_path and os.path.exists(orig_vocal_path):
            o_data = _fit(_read_stereo(orig_vocal_path), total_samples).astype(np.float32)
        v_data = apply_vocal_masks(v_data.astype(np.float32), vocal_masks, o_data, sr, log)

    progress("mix_balance")
    sos = scipy.signal.butter(4, 80, btype='highpass', fs=sr, output='sos')
    v_filtered = np.zeros_like(v_data)
    v_filtered[:, 0] = scipy.signal.sosfilt(sos, v_data[:, 0])
    v_filtered[:, 1] = scipy.signal.sosfilt(sos, v_data[:, 1])

    segs = vol_segments or []
    bk_data = None
    for bp in (backing_paths or []):
        if bp and os.path.exists(bp):
            d = _fit(_read_stereo(bp), total_samples)
            bk_data = d if bk_data is None else bk_data + d
    if any(sg.get("track") == "backing" for sg in segs) and bk_data is None:
        log("this version has no separate backing-vocal track; 'backing' volume sections skipped")

    for m in (vocal_masks or []):
        if m.get("mode") == "replace" and m.get("target") == "bgm":
            src = load_aligned(m.get("src"), m.get("src_start", m["start"]), total_samples, sr)
            if src is None:
                continue
            b_data = apply_replace(b_data, m, src, None, sr)
            if bk_data is not None:   # the new accompaniment already contains this section's backing vocals
                bk_data = bk_data * (1.0 - mask_envelope(total_samples, [(m["start"], m["end"])], sr, 0.05))[:, None]

    v_norm = v_filtered / (np.max(np.abs(v_filtered)) + 1e-6)
    b_base = b_data if bk_data is None else b_data + bk_data
    b_peak = np.max(np.abs(b_base)) + 1e-6   # peak of the unadjusted accompaniment
    if segs:
        env_v = gain_envelope(total_samples, [sg for sg in segs if sg.get("track") == "vocal"], sr)
        env_b = gain_envelope(total_samples, [sg for sg in segs if sg.get("track") == "bgm"], sr)
        v_norm = v_norm * env_v[:, None]
        if bk_data is not None:
            env_k = gain_envelope(total_samples, [sg for sg in segs if sg.get("track") == "backing"], sr)
            b_base = b_data * env_b[:, None] + bk_data * env_k[:, None]
        else:
            b_base = b_data * env_b[:, None]
    b_norm = b_base / b_peak

    mixed = v_norm * (vocal_vol * 0.86) + b_norm * (bgm_vol * 0.88)

    inst_used = False
    if instrument != "none" and inst_vol > 0 and midi_path and os.path.exists(midi_path):
        progress("mix_instrument")
        inst_audio = render_instrument(instrument, midi_path, total_samples, soundfonts, sr=sr,
                                       octave_shift=octave_shift, reverb_wet=reverb_wet)
        if inst_audio is not None:
            mixed += inst_audio / (np.max(np.abs(inst_audio)) + 1e-6) * (inst_vol * 0.85)
            inst_used = True

    for m in (vocal_masks or []):
        if m.get("mode") == "replace" and m.get("target") == "mix":
            src = load_aligned(m.get("src"), m.get("src_start", m["start"]), total_samples, sr)
            if src is not None:
                mixed = apply_replace(mixed, m, src, None, sr)

    fade_len = int(1.5 * sr)
    if len(mixed) > fade_len:
        mixed[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)[:, None]

    out_mp3_path = Path(out_mp3_path)
    out_mp3_path.parent.mkdir(parents=True, exist_ok=True)
    temp_wav = out_mp3_path.with_name(out_mp3_path.stem + "_temp.wav")
    progress("mix_master")
    sf.write(str(temp_wav), mixed.astype(np.float32), sr, subtype='FLOAT')   # float keeps peaks for the limiter
    try:
        res = subprocess.run([ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", str(temp_wav),
                              "-af", f"alimiter=limit={limiter_ceiling}:attack=5:release=50:asc=0:level=0",
                              "-c:a", "libmp3lame", "-b:a", "320k", str(out_mp3_path)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             creationflags=NO_WINDOW)
        if res.returncode != 0 or not out_mp3_path.is_file():
            raise RuntimeError((res.stderr or "ffmpeg failed")[-500:])
    finally:
        temp_wav.unlink(missing_ok=True)
    return {"duration": total_samples / sr, "instrument_used": inst_used}
