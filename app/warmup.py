"""Keep the big AI programs in the Windows file cache, so a cover or a separation starts in seconds.

On the PC, loading Applio took 89-165 s when its files (PyTorch and the rest, several GB) had dropped
out of the file cache, and 6-18 s when they were still in it. So right after start-up, and again every
15 minutes, a low-priority child process imports the same modules and exits: no graphics card
(CUDA_VISIBLE_DEVICES is empty), no models, nothing queued. Each run is timed into logs/jobs.log.
Set SIGN2MV_NO_WARMUP=1 to turn it off.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from .childenv import child_env
from .paths import Paths
from .proc import ManagedProcess

log = logging.getLogger("sign2mv.warmup")

INTERVAL_S = 15 * 60
FIRST_DELAY_S = 3.0
TIMEOUT_S = 900.0

# what each environment imports when a job starts (the modules that are slow to read from disk)
PLAN = {
    "applio": "import torch, librosa\nimport rvc.infer.infer",
    "engine": "import torch, librosa, demucs.apply\nimport audio_separator.separator",
}


class Warmup:
    def __init__(self, paths: Paths, gpu_busy, event_log: Path | None):
        self.paths, self.gpu_busy, self.event_log = paths, gpu_busy, event_log
        self._stop = threading.Event()

    def start(self) -> bool:
        if os.environ.get("SIGN2MV_NO_WARMUP") or not self._targets():
            return False
        threading.Thread(target=self._loop, name="warmup", daemon=True).start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _targets(self) -> list[tuple[str, str, Path]]:
        out = []
        for name, code in PLAN.items():
            py = self.paths.env_python(name)
            cwd = self.paths.applio if name == "applio" else self.paths.workers
            if py.is_file() and cwd.is_dir():
                out.append((name, str(py), cwd))
        return out

    def _loop(self) -> None:
        if self._stop.wait(FIRST_DELAY_S):
            return
        while not self._stop.is_set():
            for name, py, cwd in self._targets():
                if self._stop.is_set():
                    return
                if self.gpu_busy():          # a running cover or separation loads these itself
                    self._note(f"warm-up {name}: skipped (a graphics-card job is running)")
                    continue
                self._run(name, py, cwd)
            self._stop.wait(INTERVAL_S)

    def _run(self, name: str, py: str, cwd: Path) -> None:
        env = child_env(self.paths, {"CUDA_VISIBLE_DEVICES": ""})
        t0 = time.time()
        try:
            proc = ManagedProcess([py, "-c", PLAN[name]], env=env, cwd=str(cwd), low_priority=True)
            try:
                _, err = proc.popen.communicate(timeout=TIMEOUT_S)
                rc = proc.popen.returncode
            except subprocess.TimeoutExpired:
                proc.kill_tree()
                self._note(f"warm-up {name}: stopped after {TIMEOUT_S:.0f} s")
                return
            finally:
                proc.close()
        except OSError as exc:
            self._note(f"warm-up {name}: could not start ({exc})")
            return
        took = time.time() - t0
        tail = (err or b"").decode("utf-8", "replace").strip().splitlines()[-1:] if rc else []
        self._note(f"warm-up {name}: {took:.1f} s" + (f" (exit {rc}: {tail[0][:200]})" if tail else ""))

    def _note(self, text: str) -> None:
        log.info(text)
        if not self.event_log:
            return
        try:
            with open(self.event_log, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
        except OSError:
            pass
