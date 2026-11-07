"""Local microphone capture: a page that goes away while the capture opens must not keep the microphone
(it used to answer 409 to every later request until SIGN2MV was restarted)."""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

from app import native_mic


def _mic(tmp_path, script: str) -> native_mic.NativeMicrophone:
    (tmp_path / "workers" / "native").mkdir(parents=True)
    ctx = SimpleNamespace(paths=SimpleNamespace(workers=tmp_path / "workers", logs=tmp_path / "logs"))
    m = native_mic.NativeMicrophone(ctx)
    fake = tmp_path / "fake_capture.py"
    fake.write_text(script, encoding="utf-8")
    m._args = lambda *extra: [sys.executable, str(fake)]
    m._env = lambda: None
    return m


SILENT = "import time\ntime.sleep(60)\n"
TALKING = ('import json, sys, time\n'
           'sys.stdout.buffer.write((json.dumps({"sampleRate": 48000, "channels": 1, "label": "x"}) + "\\n").encode())\n'
           'sys.stdout.flush()\ntime.sleep(60)\n')


def test_cancel_while_opening_frees_the_microphone(tmp_path):
    m = _mic(tmp_path, SILENT)

    async def run():
        task = asyncio.create_task(m.stream("dev"))
        await asyncio.sleep(0.5)
        proc = m.state["active"]["proc"]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return proc
    proc = asyncio.run(run())
    assert m.state["active"] is None and proc.poll() is not None


def test_new_request_replaces_one_still_opening(tmp_path):
    m = _mic(tmp_path, SILENT)

    async def run():
        first = asyncio.create_task(m.stream("dev"))
        await asyncio.sleep(0.5)
        old = m.state["active"]
        m._args = lambda *extra: [sys.executable, str(tmp_path / "talk.py")]
        (tmp_path / "talk.py").write_text(TALKING, encoding="utf-8")
        second = await m.stream("dev")
        res = await first
        new = m.state["active"]
        new["stop"]()
        return old, res, second
    old, res, second = asyncio.run(run())
    assert old["phase"] == "stopped" and old["proc"].poll() is not None
    assert res.status_code in (409, 503) and type(second).__name__ == "StreamingResponse"


def test_stream_never_read_is_stopped(tmp_path, monkeypatch):
    m = _mic(tmp_path, TALKING)
    monkeypatch.setattr(native_mic.NativeMicrophone, "OPEN_GRACE_S", 0.3)

    async def run():
        resp = await m.stream("dev")
        op = m.state["active"]
        await asyncio.sleep(0.8)
        return resp, op
    resp, op = asyncio.run(run())
    assert type(resp).__name__ == "StreamingResponse"
    assert m.state["active"] is None and op["proc"].poll() is not None
