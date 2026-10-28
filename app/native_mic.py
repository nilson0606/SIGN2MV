"""Native (WASAPI) microphone capture for sing & record.

Port of sign_record native-microphone-server.mjs. The capture program
(workers/native/native_microphone.py, engine environment) writes one JSON
header line and then raw float32 mono PCM at 48 kHz on stdout. Speaker
monitoring commands go to its stdin; acknowledgements and capture diagnostics
come back on stderr, so commands never share the PCM pipe.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
import uuid
from typing import Any

from fastapi.responses import JSONResponse, StreamingResponse

from .childenv import child_env
from .context import Context

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _json(code: int, data: dict[str, Any]) -> JSONResponse:
    return JSONResponse(data, status_code=code)


class MonitorControl:
    def __init__(self, proc: subprocess.Popen, on_capture):
        self.proc = proc
        self.on_capture = on_capture
        self.sequence = -1
        self.closed = False
        self.state: dict[str, Any] = {"state": "off", "sequence": -1}
        self.pending: dict[int, dict[str, Any]] = {}
        self.cv = threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            for raw in self.proc.stderr:
                if len(raw) > 4096:
                    continue
                try:
                    msg = json.loads(raw.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("capture") is True:
                    self.on_capture(msg)
                    continue
                with self.cv:
                    if msg.get("monitor") is not True or msg.get("sequence") != self.sequence:
                        continue
                    self.state = {"state": msg.get("state"), "sequence": self.sequence,
                                  "error": msg.get("error") if isinstance(msg.get("error"), str) else ""}
                    if self.state["state"] == "starting":
                        continue
                    p = self.pending.pop(self.sequence, None)
                    if p:
                        p["result"] = self.state
                        self.cv.notify_all()
        except (OSError, ValueError):
            pass
        finally:
            self.close()

    def close(self) -> None:
        with self.cv:
            if self.closed:
                return
            self.closed = True
            for p in self.pending.values():
                p["error"] = "本機收音已停止。"
            self.pending.clear()
            self.cv.notify_all()

    def _write(self, value: dict[str, Any]) -> None:
        try:
            self.proc.stdin.write((json.dumps(value) + "\n").encode())
            self.proc.stdin.flush()
        except (OSError, ValueError):
            self.close()

    def command(self, value: dict[str, Any]) -> dict[str, Any]:
        with self.cv:
            if self.closed:
                raise RuntimeError("本機收音已停止。")
            if value["action"] == "keepalive":
                if value["sequence"] != self.sequence:
                    raise RuntimeError("監聽設定已更新。")
                self._write(value)
                return self.state
            if value["sequence"] <= self.sequence:
                raise RuntimeError("監聽設定已更新。")
            self.sequence = value["sequence"]
            for p in self.pending.values():
                p["error"] = "監聽設定已更新。"
            self.pending.clear()
            entry: dict[str, Any] = {}
            self.pending[self.sequence] = entry
            self._write(value)
            deadline = time.monotonic() + 5
            while "result" not in entry and "error" not in entry:
                left = deadline - time.monotonic()
                if left <= 0:
                    self.pending.pop(self.sequence, None)
                    # A delayed device open must never produce sound after an apparent failed start.
                    self.sequence += 1
                    self._write({"action": "set", "sequence": self.sequence, "enabled": False, "deviceId": "", "volume": 0})
                    raise RuntimeError("喇叭輸出啟動逾時，請停止收音後重試。")
                self.cv.wait(left)
            if "error" in entry:
                raise RuntimeError(entry["error"])
            if entry["result"].get("state") == "error":
                raise RuntimeError(entry["result"].get("error") or "喇叭輸出失敗。")
            return entry["result"]


class NativeMicrophone:
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.state: dict[str, Any] = {"active": None}
        self.script = str(ctx.paths.workers / "native" / "native_microphone.py")
        self.log_file = ctx.paths.logs / "native-capture.jsonl"
        self.log_lock = threading.Lock()

    def _args(self, *extra: str) -> list[str]:
        return [self.ctx.python("engine"), "-X", "utf8", self.script, *extra]

    def _env(self) -> dict[str, str]:
        return child_env(self.ctx.paths)

    def _log(self, capture_id: str, event: dict[str, Any]) -> None:
        try:
            with self.log_lock:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                if self.log_file.exists() and self.log_file.stat().st_size > 1024 * 1024:
                    os.replace(self.log_file, self.log_file.with_name("native-capture.previous.jsonl"))
                with open(self.log_file, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "captureId": capture_id, **event}) + "\n")
        except OSError:
            pass

    def list_devices(self, flag: str):
        try:
            res = subprocess.run(self._args(flag), capture_output=True, timeout=20, env=self._env(),
                                 cwd=str(self.ctx.paths.workers / "native"), creationflags=NO_WINDOW)
            if res.returncode != 0:
                raise RuntimeError(res.stderr[-400:])
            return json.loads(res.stdout.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return _json(503, {"error": "本機音訊元件尚未就緒，請重新執行 install.bat。"})

    def monitor(self, value: dict[str, Any]):
        seq = value.get("sequence")
        if (not isinstance(seq, int) or isinstance(seq, bool) or seq < 0 or value.get("action") not in ("set", "keepalive")
                or (value.get("action") == "set" and (not isinstance(value.get("enabled"), bool)
                                                      or not isinstance(value.get("deviceId"), str)
                                                      or len(value["deviceId"]) > 512
                                                      or not isinstance(value.get("volume"), (int, float))
                                                      or not 0 <= value["volume"] <= 1))):
            return _json(400, {"error": "Invalid monitor control"})
        op = self.state["active"]
        if not op or value.get("captureId") != op["id"]:
            return _json(409, {"error": "這次收音已停止，請重新開啟麥克風。"})
        try:
            return op["monitor"].command(value)
        except RuntimeError as exc:
            return _json(409, {"error": str(exc)})

    async def stream(self, device_id: str):
        if len(device_id) > 512:
            return _json(400, {"error": "Invalid microphone"})
        if self.state["active"]:
            return _json(409, {"error": "本機麥克風已被另一個分頁使用，請先停止該頁收音。"})
        args = self._args("--device", device_id)
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env=self._env(), cwd=str(self.ctx.paths.workers / "native"), creationflags=NO_WINDOW)
        except OSError:
            return _json(503, {"error": "本機收音程式無法啟動。"})
        capture_id = str(uuid.uuid4())
        op: dict[str, Any] = {"id": capture_id, "proc": proc}
        op["monitor"] = MonitorControl(proc, lambda e: self._log(capture_id, e))
        self.state["active"] = op

        def stop() -> None:
            op["monitor"].close()
            try:
                proc.kill()
            except OSError:
                pass
            if self.state["active"] is op:
                self.state["active"] = None

        loop = asyncio.get_running_loop()
        header = await loop.run_in_executor(None, self._read_header, proc)
        if isinstance(header, str):
            stop()
            return _json(503, {"error": header})
        meta, rest = header
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)

        def pump() -> None:
            try:
                while True:
                    chunk = proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
                    if not chunk:
                        break
                    asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result(timeout=10)
            except Exception:  # noqa: BLE001
                pass
            finally:
                try:
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                except RuntimeError:
                    pass

        threading.Thread(target=pump, daemon=True).start()

        async def body():
            try:
                yield (json.dumps({**meta, "captureId": capture_id}) + "\n").encode()
                if rest:
                    yield rest
                while True:
                    try:
                        chunk = await asyncio.wait_for(queue.get(), timeout=5)
                    except asyncio.TimeoutError:
                        break  # capture stream stalled
                    if chunk is None:
                        break
                    yield chunk
            finally:
                stop()

        return StreamingResponse(body(), media_type="application/octet-stream",
                                 headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    @staticmethod
    def _read_header(proc: subprocess.Popen):
        buf = b""
        deadline = time.monotonic() + 25
        while b"\n" not in buf:
            if time.monotonic() > deadline:
                return "本機麥克風啟動逾時，請確認 Windows 麥克風權限。"
            chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(1)
            if not chunk:
                return "本機收音已中斷，請重新開啟。"
            buf += chunk
            if len(buf) > 4096 and b"\n" not in buf:
                return "本機收音回應不正確。"
        line, rest = buf.split(b"\n", 1)
        try:
            meta = json.loads(line)
            if meta.get("sampleRate") != 48000 or meta.get("channels") != 1 or not isinstance(meta.get("label"), str):
                raise ValueError
        except ValueError:
            return "本機收音格式不正確。"
        return meta, rest
