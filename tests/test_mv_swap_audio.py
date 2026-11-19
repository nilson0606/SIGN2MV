"""[2026-11-19] 「只換音軌」: a rendered MV gets the song's audio as it is chosen now, without a render. The
picture is copied as it is (every frame the same), the sound is the new audio; a length that differs by more
than half a second is said first; with no MV yet nothing is done."""
import subprocess
from pathlib import Path

from app.mvstudio import core
from test_mv_photos import project


def _ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def _frames_md5(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "framemd5", "-"],
                         check=True, capture_output=True, text=True).stdout
    return [ln.split(",")[-1].strip() for ln in out.splitlines() if ln and not ln.startswith("#")]


def _audio_pitch(path, at=1.0):
    """The loudest frequency of the MV's sound around `at` seconds (Hz)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-t", "1", "-i", str(path), "-map", "0:a:0", "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"], check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(float)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return float(np.argmax(spec) * 16000 / len(x))


def _setup(client, root, tmp_path, new_secs):
    sid, slug, pdir = project(client, root, 12)
    proj = core.load_project_dict(slug)
    mv = Path(proj["output_mv"])
    mv.parent.mkdir(parents=True, exist_ok=True)
    # a small "rendered" MV: 10 s of moving picture with a 440 Hz sound
    _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=10", "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(mv))
    new = tmp_path / "new_take.wav"
    _ff("-f", "lavfi", "-i", f"sine=frequency=880:duration={new_secs}", str(new))
    r = client.post("/api/mv/select_audio", json={"slug": slug, "audio_file": str(new)}).json()
    assert r["status"] == "ok"
    return slug, mv


def test_swap_audio_keeps_the_picture_and_changes_the_sound(client, root, tmp_path):
    slug, mv = _setup(client, root, tmp_path, 10.2)
    before = _frames_md5(mv)
    assert abs(_audio_pitch(mv) - 440) < 10
    chk = client.post("/api/mv/swap_audio", json={"slug": slug, "check": True}).json()
    assert chk["status"] == "ok" and chk["warn"] is False and abs(chk["diff_sec"] - 0.2) < 0.1
    assert chk["audio_name"].endswith(".wav")
    assert _frames_md5(mv) == before                                   # the check changes nothing
    res = client.post("/api/mv/swap_audio", json={"slug": slug}).json()
    assert res["status"] == "ok" and Path(res["output_mv"]) == mv
    assert _frames_md5(mv) == before                                   # every frame as it was
    assert abs(_audio_pitch(mv) - 880) < 10                            # the new sound
    probe = core.probe_media_file(str(mv))
    assert probe["audio_codec"] == "aac" and abs(probe["duration"] - 10.0) < 0.15   # the MV keeps its length
    assert not list(mv.parent.glob("*.swap.tmp.mp4"))


def test_swap_audio_says_a_length_that_differs(client, root, tmp_path):
    slug, mv = _setup(client, root, tmp_path, 7.0)
    chk = client.post("/api/mv/swap_audio", json={"slug": slug, "check": True}).json()
    assert chk["warn"] is True and chk["diff_sec"] < -2.5
    res = client.post("/api/mv/swap_audio", json={"slug": slug}).json()
    assert res["status"] == "ok" and abs(core.probe_media_file(str(mv))["duration"] - 7.0) < 0.15   # shorter audio: shorter MV


def test_swap_audio_without_an_mv_does_nothing(client, root, tmp_path):
    sid, slug, pdir = project(client, root, 12)
    for body in ({"slug": slug, "check": True}, {"slug": slug}):
        r = client.post("/api/mv/swap_audio", json=body)
        assert r.status_code == 409 and "渲染" in r.json()["detail"]
    assert client.post("/api/mv/swap_audio", json={"slug": "nope_nope"}).status_code == 404

