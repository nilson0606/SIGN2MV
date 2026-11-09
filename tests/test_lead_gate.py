"""Lead/backing versions: backing vocals that leaked into the lead track are not scored as the melody."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "workers"))
import sing_reference  # noqa: E402

from app.api_sing import cache_key, needs_lead_gate, video_id_for  # noqa: E402

RATE, HOP = 16000, 1600


def tone(seconds: float, db: float) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    return (10 ** (db / 20) * np.sqrt(2) * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_runs_that_are_mostly_backing_become_rests():
    # 0-2 s: a leak (lead -40 dB under backing -20 dB); 2-3 s rest; 3-6 s: the lead sings (-18 dB) and its last
    # second fades under louder backing vocals; 6-7 s rest; 7-8 s: lead nearly silent (-70 dB)
    lead = np.concatenate([tone(2, -40), tone(1, -120), tone(2, -18), tone(1, -35), tone(1, -120), tone(1, -70)])
    back = np.concatenate([tone(2, -20), tone(1, -120), tone(2, -50), tone(1, -20), tone(1, -120), tone(1, -60)])
    frames = [440.0] * 20 + [None] * 10 + [220.0] * 30 + [None] * 10 + [330.0] * 10
    dropped = sing_reference.drop_backing_leaks(frames, lead, back)
    assert frames[:20] == [None] * 20                       # the leak
    assert frames[30:60] == [220.0] * 30                    # the lead's run, with its fading tail, stays
    assert frames[70:] == [None] * 10                       # nearly silent lead
    assert dropped == 3.0


def test_old_lead_references_are_made_again(client):
    assert needs_lead_gate({"vocalMode": "lead"}) and not needs_lead_gate({"vocalMode": "lead", "leadGate": {"version": 1}})
    assert not needs_lead_gate({"vocalMode": "all"})
    ctx = client.app.state.ctx
    sid = ctx.library().create("Lead")["song_id"]
    d = ctx.library().song_dir(sid)
    (d / "source").mkdir()
    (d / "source" / "audio.wav").write_bytes(b"RIFF")
    (d / "source" / "source.json").write_text(json.dumps({"audio": "source/audio.wav", "source_hash": "h",
                                                           "imported_at": time.time() - 100}), encoding="utf-8")
    vid = video_id_for(sid)
    key_id = cache_key(vid, 0, "lead", "demucs", "rmvpe", "single")
    (d / "sing" / key_id).mkdir(parents=True)
    ref = {"title": "Lead", "pitchShift": 0, "duration": 10, "frames": [None] * 10, "vocalMode": "lead",
           "sourceHash": "h", "stems": {}}
    (d / "sing" / key_id / "reference.json").write_text(json.dumps(ref), encoding="utf-8")
    h = {"X-Karaoke-Token": client.get("/sr/session").json()["token"]}
    body = {"videoId": vid, "seconds": 0, "vocalMode": "lead", "separationModel": "demucs", "pitchMethod": "rmvpe",
            "preview": False}
    job = client.post("/sr/jobs", headers=h, json=body).json()
    assert job["cacheId"] == key_id and job.get("cached") is not True                     # made again with the gate
    client.delete(f"/sr/jobs/{job['id']}", headers=h)
    (d / "sing" / key_id / "reference.json").write_text(json.dumps({**ref, "leadGate": {"version": 1}}),
                                                          encoding="utf-8")
    assert client.post("/sr/jobs", headers=h, json=body).json()["cached"] is True
