"""Child-process control.

Windows:
  * The server puts itself into a Job Object with KILL_ON_JOB_CLOSE. Every
    process it starts (workers, ffmpeg, the Edge app window) inherits the job,
    so when the server exits for any reason - normal shutdown, crash, the
    console window being closed - Windows kills all of them. Nothing is left
    running in the background.
  * Each worker additionally gets its own nested Job Object, so cancelling a
    worker kills its whole process tree (e.g. Python plus the ffmpeg it
    started) without touching anything else.

Other systems (used only for development and tests): each worker runs in its
own process group, which is killed on cancel.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Sequence

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_TERMINATE = 0x0001

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _BASIC_LIMIT(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BASIC_LIMIT),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE

    def _new_kill_on_close_job() -> int:
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        info = _EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _kernel32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                                 ctypes.byref(info), ctypes.sizeof(info)):
            err = ctypes.get_last_error()
            _kernel32.CloseHandle(job)
            raise ctypes.WinError(err)
        return job


_SERVER_JOB = None


def adopt_self_into_job() -> bool:
    """Put the server process into a kill-on-close job (Windows only).

    The handle is intentionally kept open for the lifetime of the process;
    Windows closes it when the process ends, which kills every descendant.
    """
    global _SERVER_JOB
    if not IS_WINDOWS or _SERVER_JOB is not None:
        return _SERVER_JOB is not None
    try:
        job = _new_kill_on_close_job()
        if not _kernel32.AssignProcessToJobObject(job, _kernel32.GetCurrentProcess()):
            _kernel32.CloseHandle(job)
            return False
        _SERVER_JOB = job
        return True
    except OSError:
        return False


class ManagedProcess:
    """A child process whose whole tree can be killed reliably."""

    def __init__(self, args: Sequence[str], *, env: dict[str, str] | None = None,
                 cwd: str | None = None, stdin_data: bytes | None = None):
        self._job = None
        kwargs: dict = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                            env=env, cwd=cwd)
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.popen = subprocess.Popen(list(args), **kwargs)
        if IS_WINDOWS:
            try:
                job = _new_kill_on_close_job()
                handle = _kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, self.popen.pid)
                if handle:
                    if _kernel32.AssignProcessToJobObject(job, handle):
                        self._job = job
                    else:
                        _kernel32.CloseHandle(job)
                    _kernel32.CloseHandle(handle)
                else:
                    _kernel32.CloseHandle(job)
            except OSError:
                self._job = None
        if stdin_data is not None and self.popen.stdin:
            try:
                self.popen.stdin.write(stdin_data)
                self.popen.stdin.close()
            except OSError:
                pass

    @property
    def pid(self) -> int:
        return self.popen.pid

    def kill_tree(self) -> None:
        if self.popen.poll() is not None and self._job is None:
            return
        if IS_WINDOWS:
            if self._job is not None:
                _kernel32.TerminateJobObject(self._job, 1)
            else:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.popen.pid)],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            try:
                os.killpg(self.popen.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    def close(self) -> None:
        if IS_WINDOWS and self._job is not None:
            _kernel32.CloseHandle(self._job)
            self._job = None


def python_unbuffered(python: str) -> list[str]:
    return [python, "-u"]


def current_python() -> str:
    return sys.executable
