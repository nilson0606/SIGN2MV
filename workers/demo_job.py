"""Demo worker used to check the queue: counts up for N seconds.

Input: {"seconds": 1-600, "fail": false}
It uses no graphics card and touches no files; it exists so the queue,
progress, cancel and timeout can be tried before the real engines exist.
"""
from __future__ import annotations

import time

import protocol


def main() -> None:
    data = protocol.read_input()
    seconds = float(data.get("seconds", 10))
    seconds = max(0.2, min(600.0, seconds))
    steps = max(1, int(seconds * 4))
    for i in range(steps):
        time.sleep(seconds / steps)
        protocol.progress(round((i + 1) * 100 / steps, 1), "demo", f"{i + 1}/{steps}")
    if data.get("fail"):
        protocol.fail("demo_failure", "requested failure")
    protocol.result({"seconds": seconds})


if __name__ == "__main__":
    main()
