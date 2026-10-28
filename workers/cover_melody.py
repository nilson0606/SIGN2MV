"""AI cover: melody MIDI of the converted vocal for the optional instrument track.

Port of AI_COVER_MV scripts/extract_melody_midi.py: Basic Pitch (ONNX model,
CPU) with the same thresholds, then same-pitch merging, noise removal and
monophonic legato so a solo instrument can play it.
"""
from __future__ import annotations

import os
from pathlib import Path


def merge_and_quantize_notes(notes, max_gap=0.08, min_dur=0.12):
    if not notes:
        return []
    sorted_notes = sorted(notes, key=lambda n: n.start)
    merged = []
    cur = sorted_notes[0]
    for n in sorted_notes[1:]:
        if n.pitch == cur.pitch and (n.start - cur.end) <= max_gap:
            cur.end = max(cur.end, n.end)
            cur.velocity = max(cur.velocity, n.velocity)
        elif n.start < cur.end and n.pitch == cur.pitch:
            cur.end = max(cur.end, n.end)
        else:
            if (cur.end - cur.start) >= min_dur and 36 <= cur.pitch <= 96:
                merged.append(cur)
            cur = n
    if (cur.end - cur.start) >= min_dur and 36 <= cur.pitch <= 96:
        merged.append(cur)
    final_notes = []
    for i, n in enumerate(merged):
        if i < len(merged) - 1 and n.end > merged[i + 1].start:
            n.end = merged[i + 1].start
        if (n.end - n.start) >= 0.08:
            final_notes.append(n)
    return final_notes


def onnx_model_path() -> Path:
    import basic_pitch
    return Path(basic_pitch.__file__).parent / "saved_models" / "icassp_2022" / "nmp.onnx"


def transcribe_vocal_to_midi(vocal_wav_path: str, output_midi_path: str) -> int:
    """Returns the number of notes written."""
    import logging
    logging.getLogger().setLevel(logging.ERROR)   # basic-pitch warns about optional backends
    import pretty_midi
    from basic_pitch.inference import predict
    if not os.path.exists(vocal_wav_path):
        raise FileNotFoundError(vocal_wav_path)
    _, midi_data, _ = predict(audio_path=vocal_wav_path, model_or_model_path=str(onnx_model_path()),
                              onset_threshold=0.60, frame_threshold=0.35, minimum_note_length=140,
                              minimum_frequency=120.0, maximum_frequency=900.0, melodia_trick=True)
    raw_notes = midi_data.instruments[0].notes if midi_data.instruments else []
    clean_notes = merge_and_quantize_notes(raw_notes, max_gap=0.10, min_dur=0.12)
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=107, name="Melody")
    inst.notes = clean_notes
    pm.instruments.append(inst)
    out = Path(output_midi_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mid")
    pm.write(str(tmp))
    os.replace(tmp, out)
    return len(clean_notes)
