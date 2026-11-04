"""RMVPE pitch for sing & record scoring, served by one long-lived worker process.

The song reference is built with RMVPE; scoring the take with the same model keeps the
two sides comparable (the browser's own detector stays for the live pitch line). The
model takes a while to load, so the process is started ahead of time (/sr/live-pitch/warm)
and kept until it has been idle for IDLE_S seconds.
"""
from __future__ import annotations

import base64
import json
import threading
import time
from typing import Any

from .proc import ManagedProcess

IDLE_S = 5 * 60   # release the graphics card soon after singing (covers and separation need it)
LOAD_TIMEOUT_S = 180
# [SIGN2MV] longest wait for one piece: the page gives up after 30 s (live) or 120 s (a saved take), so a
# worker that has not answered by then is stuck. It is stopped, which ends the blocked write / readline and
# frees the lock; the next piece starts a new worker (an outside review, Gemini P2).
PIECE_TIMEOUT_S = 120


class LivePitch:
    def __init__(self, ctx):
        self.ctx = ctx
        self._lock = threading.Lock()        # one piece at a time
        self._state_lock = threading.Lock()
        self._proc: ManagedProcess | None = None
        self._ready = threading.Event()
        self._error = ""
        self.device = ""
        self._seq = 0
        self._last_used = time.monotonic()
        threading.Thread(target=self._reaper, daemon=True, name="live-pitch-reaper").start()

    # ---------- process ----------
    def state(self) -> dict[str, Any]:
        with self._state_lock:
            if self._proc and self._proc.popen.poll() is None:
                return {"state": "ready" if self._ready.is_set() else "loading", "device": self.device}
            return {"state": "failed" if self._error else "stopped", "error": self._error}

    def warm(self) -> dict[str, Any]:
        with self._state_lock:
            self._last_used = time.monotonic()
            if self._proc and self._proc.popen.poll() is None:
                return self.state_unlocked()
            from .childenv import child_env
            args = [self.ctx.python("engine"), "-u", str(self.ctx.paths.workers / "sing_live_pitch.py")]
            self._ready.clear()
            self._error = ""
            self.device = ""
            self._proc = ManagedProcess(args, env=child_env(self.ctx.paths), cwd=str(self.ctx.paths.workers),
                                        keep_stdin=True)
            proc = self._proc
        threading.Thread(target=self._wait_ready, args=(proc,), daemon=True, name="live-pitch-load").start()
        threading.Thread(target=self._drain_stderr, args=(proc,), daemon=True, name="live-pitch-stderr").start()
        return {"state": "loading"}

    def state_unlocked(self) -> dict[str, Any]:
        return {"state": "ready" if self._ready.is_set() else "loading", "device": self.device}

    def _wait_ready(self, proc: ManagedProcess) -> None:
        line = proc.popen.stdout.readline() if proc.popen.stdout else b""
        try:
            msg = json.loads(line.decode("utf-8", "replace") or "{}")
        except ValueError:
            msg = {}
        with self._state_lock:
            if proc is not self._proc:
                return
            if msg.get("ready"):
                self.device = msg.get("device", "")
                self._ready.set()
            else:
                self._error = msg.get("error") or "live_pitch_start_failed"
                proc.kill_tree()

    @staticmethod
    def _drain_stderr(proc: ManagedProcess) -> None:
        if proc.popen.stderr:
            for _ in proc.popen.stderr:
                pass

    def stop(self) -> None:
        with self._state_lock:
            proc, self._proc = self._proc, None
            self._ready.clear()
        if proc:
            proc.kill_tree()

    def _reaper(self) -> None:
        while True:
            time.sleep(30)
            if self._proc and time.monotonic() - self._last_used > IDLE_S and not self._lock.locked():
                self.stop()

    # ---------- pitch ----------
    def pitch(self, pcm: bytes, rate: int) -> dict[str, Any]:
        """pcm: int16 little-endian mono at `rate`. Returns {"f0": [...], "hop": 0.01, ...}."""
        if not self._ready.is_set():
            self.warm()
            if not self._ready.wait(LOAD_TIMEOUT_S):
                return {"error": self._error or "live_pitch_not_ready"}
        with self._lock:
            proc = self._proc
            if not proc or proc.popen.poll() is not None or not proc.popen.stdin or not proc.popen.stdout:
                self.stop()
                return {"error": "live_pitch_stopped"}
            self._seq += 1
            seq = self._seq
            self._last_used = time.monotonic()
            req = {"id": seq, "rate": rate, "pcm": base64.b64encode(pcm).decode("ascii")}
            stuck = threading.Event()
            watchdog = threading.Timer(PIECE_TIMEOUT_S, self._stop_stuck, args=(proc, stuck))
            watchdog.daemon = True
            watchdog.start()
            try:
                proc.popen.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
                proc.popen.stdin.flush()
                while True:
                    line = proc.popen.stdout.readline()
                    if not line:
                        self.stop()
                        return {"error": "live_pitch_timeout" if stuck.is_set() else "live_pitch_stopped"}
                    msg = json.loads(line.decode("utf-8", "replace"))
                    if msg.get("id") == seq:
                        self._last_used = time.monotonic()
                        return msg
            except (OSError, ValueError) as exc:
                self.stop()
                return {"error": "live_pitch_timeout" if stuck.is_set() else f"live_pitch_failed: {exc}"}
            finally:
                watchdog.cancel()

    def _stop_stuck(self, proc: ManagedProcess, stuck: threading.Event) -> None:
        """A piece got no answer within PIECE_TIMEOUT_S: stop that worker (only if it is still the current one)."""
        with self._state_lock:
            if proc is not self._proc:
                return
        stuck.set()
        self.stop()
