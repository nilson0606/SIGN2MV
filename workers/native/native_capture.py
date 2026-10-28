"""WASAPI capture without guessing silence from elapsed wall-clock time.

Use SoundCard 0.4.6 only to open/close the device. Its record() path fabricates
zeros after a delayed wakeup and on empty packets, so capture packets directly.
No recorded samples are repaired, dropped or synthesized except explicit
WASAPI SILENT packets, which Windows defines as silence.
"""
import time
import sys
import ctypes
import queue
import threading
from contextlib import contextmanager
from collections import deque

DISCONTINUITY = 1
SILENT = 2
TIMESTAMP_ERROR = 4
CAPTURE_POLICY = "wasapi-packets-v2"


class CaptureInterrupted(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@contextmanager
def audio_priority(report):
    """Register only the device-reading thread with Windows' audio scheduler."""
    handle = None
    avrt = None
    try:
        if sys.platform == 'win32':
            avrt = ctypes.WinDLL('avrt', use_last_error=True)
            avrt.AvSetMmThreadCharacteristicsW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
            avrt.AvSetMmThreadCharacteristicsW.restype = ctypes.c_void_p
            avrt.AvRevertMmThreadCharacteristics.argtypes = [ctypes.c_void_p]
            avrt.AvRevertMmThreadCharacteristics.restype = ctypes.c_int
            task = ctypes.c_ulong(0)
            handle = avrt.AvSetMmThreadCharacteristicsW('Audio', ctypes.byref(task))
            report({'capture': True, 'event': 'audio-scheduler', 'enabled': bool(handle),
                    'errorCode': 0 if handle else ctypes.get_last_error()})
    except OSError as error:
        report({'capture': True, 'event': 'audio-scheduler', 'enabled': False, 'error': str(error)})
    try:
        yield
    finally:
        if handle:
            avrt.AvRevertMmThreadCharacteristics(handle)


class PCMDelivery:
    """Keep pipe writes/monitor work off the WASAPI reading thread; never drop PCM."""
    def __init__(self, send, capacity=100):
        self.send = send
        self.queue = queue.Queue(maxsize=capacity)  # Up to 2 s at 20 ms/chunk.
        self.error = None
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name='pcm-delivery')
        self.thread.start()

    def _run(self):
        try:
            while True:
                try:
                    data = self.queue.get(timeout=.02)
                except queue.Empty:
                    if self.closed.is_set():
                        return
                    continue
                self.send(data)
        except Exception as error:
            self.error = error

    def submit(self, data):
        if self.error:
            raise self.error
        if self.closed.is_set():
            raise RuntimeError('PCM delivery is closed')
        if not data:
            return
        try:
            self.queue.put_nowait(data)
        except queue.Full:
            raise CaptureInterrupted('transport-backlog', '本機音訊傳送阻塞超過緩衝容量，已保留已錄部分。')

    def close(self):
        self.closed.set()
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            raise CaptureInterrupted('transport-timeout', '本機音訊傳送未回應，無法送完已收取資料。')
        if self.error:
            raise self.error


class WasapiPackets:
    def __init__(self, source):
        from soundcard.mediafoundation import _ffi, _com
        self.source, self.ffi, self.com = source, _ffi, _com
        self.channels = len(set(source.channelmap))
        self.sample_rate = source.samplerate
        self.last_qpc = None

    def available(self):
        return self.source._capture_available_frames()

    def take(self):
        ffi = self.ffi
        data, frames, flags = ffi.new("BYTE**"), ffi.new("UINT32*"), ffi.new("DWORD*")
        position, qpc = ffi.new("UINT64*"), ffi.new("UINT64*")
        client = self.source._ppCaptureClient
        result = client[0][0].lpVtbl.GetBuffer(client[0], data, frames, flags, position, qpc)
        self.com.check_error(result)
        self.last_qpc = int(qpc[0])
        count = int(frames[0])
        if not count:
            return (0, int(flags[0]), int(position[0]), b"")
        try:
            # SILENT packets may have a null/undefined data pointer.
            if flags[0] & SILENT:
                payload = b""
            elif data[0] == ffi.NULL:
                raise CaptureInterrupted("invalid-buffer", "Windows 收音緩衝區無效。")
            else:
                payload = bytes(ffi.buffer(data[0], count * self.channels * 4))
            return (count, int(flags[0]), int(position[0]), payload)
        finally:
            self.source._capture_release(count)


class ContinuousCapture:
    def __init__(self, packets, report=lambda event: None, clock=time.monotonic,
                 sleep=time.sleep, timeout=.1, startup_timeout=5):
        self.packets, self.report, self.clock, self.sleep = packets, report, clock, sleep
        self.timeout, self.startup_timeout = timeout, startup_timeout
        self.pending = bytearray()
        self.frames = 0
        self.expected_position = None
        self.position_difference_reported = False
        self.started = False
        self.silent = False
        self.failed = None
        self.last_packet_at = None
        self.recent_packets = deque(maxlen=12)
        self.discontinuities = 0

    def fail(self, code, message, **details):
        self.failed = CaptureInterrupted(code, message)
        self.report({"capture": True, "event": "error", "code": code,
                     "error": message, "frame": self.frames,
                     "recentPackets": list(self.recent_packets), **details})
        raise self.failed

    def packet(self):
        if self.failed:
            raise self.failed
        begin = self.clock()
        timeout = self.timeout if self.started else self.startup_timeout
        while True:
            # Always recheck readiness after waking, before considering timeout.
            if self.packets.available():
                try:
                    count, flags, position, payload = self.packets.take()
                except CaptureInterrupted as error:
                    self.fail(error.code, str(error))
                if count:
                    break
            if self.clock() - begin >= timeout:
                self.fail("capture-timeout", "Windows 收音資料未送達，已停止；未以靜音補入。",
                          waitedMs=round((self.clock() - begin) * 1000, 3))
            self.sleep(.001)
        waited = self.clock() - begin
        # Keep a bounded timing-only history. Device positions and client PCM
        # may use different rates; QPC timestamps allow comparison without
        # assuming their units match. Never log sample values.
        self.recent_packets.append({"f": self.frames, "n": count, "flags": flags,
                                    "pos": position, "qpc100ns": getattr(self.packets, 'last_qpc', None),
                                    "readGapMs": None if self.last_packet_at is None else
                                    round((self.clock() - self.last_packet_at) * 1000, 3)})
        if self.started and self.expected_position is not None and position != self.expected_position:
            # Device positions need not advance by the client PCM frame count:
            # shared-mode resampling can use different device/client rates.
            # For example, JAZZ-UB036 advances 444 device frames while delivering
            # 483/484 frames at 48 kHz (and a shorter first resampler packet).
            # Use WASAPI's DISCONTINUITY flag for loss detection, not this sum.
            if not self.position_difference_reported:
                self.report({"capture": True, "event": "device-position-units",
                             "frame": self.frames, "expectedPosition": self.expected_position,
                             "devicePosition": position, "flags": flags})
                self.position_difference_reported = True
        # A timestamp error makes position unreliable; never silently accept a
        # possibly shifted timeline after recording has started.
        if flags & TIMESTAMP_ERROR:
            self.fail("device-timestamp-error", "Windows 無法確認收音時間位置，已停止。", flags=flags)
        size = count * self.packets.channels * 4
        silent = bool(flags & SILENT)
        if silent:
            payload = bytes(size)
        elif len(payload) != size:
            self.fail("invalid-packet", "Windows 收音封包長度不正確，已停止。")
        if self.started and flags & DISCONTINUITY:
            # The notification does not make the returned PCM invalid. The
            # previous implementation aborted even with usable audio available.
            # Retain every real sample and report the potential gap; never
            # invent silence, duplicate samples or restart the device here.
            self.discontinuities += 1
            self.report({"capture": True, "event": "warning", "code": "device-discontinuity",
                         "message": "Windows 回報短暫收音不連續，已記錄並繼續接收有效音訊。",
                         "frame": self.frames, "devicePosition": position, "flags": flags,
                         "packetFrames": count, "count": self.discontinuities,
                         "recentPackets": list(self.recent_packets)})
        if not self.started:
            self.report({"capture": True, "event": "started", "policy": CAPTURE_POLICY,
                         "frame": 0, "devicePosition": position, "flags": flags})
        if silent != self.silent:
            self.report({"capture": True, "event": "device-silence" if silent else "device-audio",
                         "frame": self.frames, "devicePosition": position})
        if waited >= .04:
            self.report({"capture": True, "event": "delayed-packet", "frame": self.frames,
                         "waitedMs": round(waited * 1000, 3), "packetFrames": count})
        self.started, self.silent = True, silent
        self.expected_position = position + count
        self.frames += count
        self.last_packet_at = self.clock()
        return payload

    def read(self, frames):
        if self.failed:
            raise self.failed
        size = frames * self.packets.channels * 4
        while len(self.pending) < size:
            self.pending.extend(self.packet())
        result = bytes(self.pending[:size])
        del self.pending[:size]
        return result

    def drain(self):
        """Keep the last valid partial packet when a later packet fails."""
        result = bytes(self.pending)
        self.pending.clear()
        return result
