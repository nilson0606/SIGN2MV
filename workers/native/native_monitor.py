"""Optional speaker branch. Capture PCM is never changed or consumed here."""
from collections import deque
from contextlib import contextmanager
import ctypes
import math
import sys
import threading
import time
import numpy as np


class BoundedSpeakerPlayer:
    """Submit only real frames, never the unused tail of the Windows buffer.

    SoundCard 0.4.6's Windows play() reserves all available frames even when
    the input packet is shorter. Use its pinned WASAPI transport here only;
    capture and the installed dependency remain untouched.
    """
    def __init__(self, player, copy_bytes, clock=time.monotonic, sleep=time.sleep):
        self.player, self.copy_bytes, self.clock, self.sleep = player, copy_bytes, clock, sleep

    @property
    def buffersize(self):
        return self.player.buffersize

    def play(self, mono):
        data = np.repeat(np.asarray(mono, dtype=np.float32)[:, None], 2, axis=1)
        offset, deadline = 0, self.clock() + .1
        while offset < len(data):
            if self.clock() >= deadline:
                raise TimeoutError("Speaker buffer stopped consuming audio")
            count = min(self.player._render_available_frames(), len(data) - offset, 480)
            if count <= 0:
                self.sleep(.001)
                continue
            packet = data[offset:offset + count].tobytes()
            buffer = self.player._render_buffer(count)
            self.copy_bytes(buffer[0], packet, len(packet))
            self.player._render_release(count)
            offset += count


@contextmanager
def speaker_player(device_id):
    # SoundCard initializes COM only on its importing thread.
    initialized = False
    if sys.platform == "win32":
        result = ctypes.windll.ole32.CoInitializeEx(None, 0)
        if result not in (0, 1):
            raise RuntimeError("Could not initialize speaker thread")
        initialized = True
    try:
        import soundcard as sc
        speaker = next((s for s in sc.all_speakers() if s.id == device_id), None) if device_id else sc.default_speaker()
        if speaker is None:
            raise RuntimeError("Speaker disconnected")
        # Shared mode allows YouTube and this voice output to play together.
        from soundcard.mediafoundation import _ffi
        with speaker.player(samplerate=48000, channels=2, blocksize=480, exclusive_mode=False) as player:
            yield BoundedSpeakerPlayer(player, _ffi.memmove)
    finally:
        if initialized:
            ctypes.windll.ole32.CoUninitialize()


class NativeMonitor:
    def __init__(self, report, factory=speaker_player, clock=time.monotonic, lease=5.0):
        self.report, self.factory, self.clock, self.lease = report, factory, clock, lease
        self.condition = threading.Condition()
        self.queue = deque(maxlen=2)  # At most 40 ms; only the monitor may discard audio.
        self.sequence, self.generation = -1, 0
        self.enabled, self.closed = False, False
        self.device, self.volume, self.deadline = "", 0.3, 0
        self.state, self.error = "off", ""
        self.thread = threading.Thread(target=self._run, daemon=True, name="speaker-monitor")
        self.thread.start()

    def _report(self):
        self.report({"monitor": True, "sequence": self.sequence, "state": self.state, "error": self.error})

    def command(self, command):
        with self.condition:
            sequence = command.get("sequence")
            if self.closed or not isinstance(sequence, int) or isinstance(sequence, bool):
                return
            if command.get("action") == "keepalive":
                if sequence == self.sequence and self.enabled:
                    self.deadline = self.clock() + self.lease
                self._report()
                return
            if sequence <= self.sequence:
                return
            enabled, device, volume = command.get("enabled"), command.get("deviceId"), command.get("volume")
            if not isinstance(enabled, bool) or not isinstance(device, str) or len(device) > 512:
                return
            if not isinstance(volume, (int, float)) or not math.isfinite(volume) or not 0 <= volume <= 1:
                return
            changed = enabled != self.enabled or device != self.device
            self.sequence, self.enabled, self.device, self.volume = sequence, enabled, device, volume
            self.deadline = self.clock() + self.lease
            self.error = ""
            if changed:
                self.generation += 1
                self.queue.clear()
                self.state = "starting" if enabled else "off"
            elif not enabled:
                self.state = "off"
            self._report()
            self.condition.notify_all()

    def feed(self, mono):
        with self.condition:
            if self.enabled and not self.closed:
                self.queue.append((self.clock(), mono.copy()))
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed, self.enabled = True, False
            self.generation += 1
            self.queue.clear()
            self.condition.notify_all()
        self.thread.join(timeout=0.5)

    def _valid(self, generation):
        return not self.closed and self.enabled and self.generation == generation

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.enabled)
                if self.closed:
                    return
                generation, device = self.generation, self.device
            try:
                with self.factory(device) as player:
                    with self.condition:
                        if not self._valid(generation):
                            continue
                        self.queue.clear()  # Never replay samples accumulated while opening the device.
                        self.state = "running"
                        self._report()
                    while True:
                        with self.condition:
                            if not self._valid(generation):
                                break
                            if self.clock() >= self.deadline:
                                raise TimeoutError("Monitor lease expired")
                            while self.queue and self.clock() - self.queue[0][0] > 0.060:
                                self.queue.popleft()
                            if not self.queue:
                                self.condition.wait(timeout=0.01)
                                continue
                            _, pcm = self.queue.popleft()
                            volume = self.volume
                        # New array; the original recording samples and gain stay unchanged.
                        player.play(np.asarray(pcm * volume, dtype=np.float32))
            except Exception:
                with self.condition:
                    if self._valid(generation):
                        self.enabled = False
                        self.queue.clear()
                        self.state = "error"
                        self.error = "喇叭輸出中斷或逾時，請確認裝置後重新開啟；錄音仍持續。"
                        self._report()
