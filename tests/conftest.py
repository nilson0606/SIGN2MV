"""Test fixtures: an isolated app root that links to the real code.

Engine tests (real separation etc.) need an environment with torch/demucs; set
SIGN2MV_TEST_ENGINE_PYTHON to its python and SIGN2MV_TEST_MODELS to a models
folder. Without them those tests are skipped.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

ENGINE_PY = os.environ.get("SIGN2MV_TEST_ENGINE_PYTHON", "")
MODELS = os.environ.get("SIGN2MV_TEST_MODELS", "")


def engine_available() -> bool:
    return bool(ENGINE_PY) and Path(ENGINE_PY).exists() and bool(MODELS) and Path(MODELS).is_dir()


@pytest.fixture()
def root(tmp_path, monkeypatch):
    r = tmp_path / "app"
    r.mkdir()
    for name in ("app", "workers", "web", "installer"):
        (r / name).symlink_to(REPO / name, target_is_directory=True)
    if MODELS and Path(MODELS).is_dir():
        (r / "models").symlink_to(Path(MODELS), target_is_directory=True)
    monkeypatch.setenv("SIGN2MV_ROOT", str(r))
    monkeypatch.setenv("SIGN2MV_NO_BROWSER", "1")
    if ENGINE_PY:
        monkeypatch.setenv("SIGN2MV_ENGINE_PYTHON", ENGINE_PY)
    monkeypatch.setenv("SIGN2MV_FORCE_CPU", "1")
    return r


@pytest.fixture()
def client(root):
    from fastapi.testclient import TestClient
    from app.paths import get_paths
    from app.server import create_app
    app = create_app(get_paths(), port=9700)
    c = TestClient(app, base_url="http://127.0.0.1:9700")
    c.headers.update({"X-SIGN2MV": "1"})
    yield c
    app.state.jobs.stop(wait_s=5)


def wait_job(client, job_id: str, timeout: float = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("succeeded", "failed", "cancelled", "timeout"):
            return job
        time.sleep(0.3)
    raise AssertionError(f"job {job_id} did not finish")


def make_song_media(path: Path, seconds: int = 20, video: bool = True) -> Path:
    """A synthetic 'song': a melodic voice-like tone over drums and bass."""
    melody = "+".join(f"0.25*sin(2*PI*{f}*t)*between(mod(t\\,4)\\,{i}\\,{i + 1})"
                      for i, f in enumerate((220, 262, 294, 330)))
    voice = f"aevalsrc='({melody})*(1+0.3*sin(2*PI*5*t))':s=44100:d={seconds}"
    drums = f"aevalsrc='0.4*exp(-30*mod(t\\,0.5))*sin(2*PI*60*t)+0.05*sin(2*PI*110*t)':s=44100:d={seconds}"
    args = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", voice, "-f", "lavfi", "-i", drums]
    if video:
        args += ["-f", "lavfi", "-i", f"testsrc=size=640x360:rate=25:duration={seconds}"]
    args += ["-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo[a]", "-map", "[a]"]
    if video:
        args += ["-map", "2:v", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    args += ["-c:a", "aac" if video else "pcm_s16le", str(path)]
    subprocess.run(args, check=True)
    return path
