"""Optional recording diagnostics (port of sign_record recording-diagnostics-server.mjs).

Writes only under runtime/recording-diagnostics; never touches the song library.
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

UUID = re.compile(r"^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$")
FILE = re.compile(r"^(metadata\.json|events\.jsonl|\d{8}-\d\.bin)$")
B64 = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


class DiagnosticsStore:
    def __init__(self, root: Path, max_bytes: int = 2 * 1024 ** 3):
        self.root = Path(root)
        self.max_bytes = max_bytes
        self.token = secrets.token_hex(32)
        self.active: dict[str, dict[str, Any]] = {}
        self.total: int | None = None
        self.lock = threading.Lock()

    def _inventory(self) -> tuple[list[tuple[Path, list[Path]]], int]:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("診斷目錄不可使用連結")
        rows, total = [], 0
        for entry in self.root.iterdir():
            if not UUID.match(entry.name) or not entry.is_dir() or entry.is_symlink():
                continue
            files = []
            for f in entry.iterdir():
                if not FILE.match(f.name) or not f.is_file() or f.is_symlink():
                    raise ValueError("診斷目錄包含未知檔案，未清除")
                total += f.stat().st_size
                files.append(f)
            rows.append((entry, files))
        return rows, total

    def _recent(self) -> bool:
        return any(time.time() - s["touched"] < 120 for s in self.active.values())

    def inventory_summary(self) -> dict[str, Any]:
        with self.lock:
            rows, total = self._inventory()
            self.total = total
            return {"count": len(rows), "bytes": total, "path": str(self.root), "active": self._recent()}

    def clear(self) -> dict[str, Any]:
        with self.lock:
            if self._recent():
                raise ValueError("仍有錄音診斷進行中，請停止錄音後再清除")
            rows, _ = self._inventory()
            for d, files in rows:
                for f in files:
                    f.unlink()
                d.rmdir()
            self.active.clear()
            self.total = 0
            return {"cleared": len(rows)}

    def post(self, diag_id: str, action: str | None, data: dict[str, Any]) -> dict[str, Any]:
        if not UUID.match(diag_id) or action not in (None, "events", "finish") or not isinstance(data, dict):
            raise ValueError("Invalid diagnostic request")
        with self.lock:
            d = self.root / diag_id
            if self.total is None:
                self.total = self._inventory()[1]
            if action is None:
                if self.total >= self.max_bytes:
                    raise ValueError("診斷已達 2 GB，請先清除舊診斷")
                d.mkdir(parents=True)
                meta = {"id": diag_id, "title": str(data.get("title") or "")[:300], "created": int(time.time() * 1000),
                        "input": data.get("input"), "sampleRate": data.get("sampleRate"), "videoId": data.get("videoId"),
                        "recordingId": data.get("recordingId"), "status": "recording",
                        "formatVersion": 2 if data.get("formatVersion") == 2 else 1}
                text = json.dumps(meta, indent=2, ensure_ascii=False)
                (d / "metadata.json").write_text(text, encoding="utf-8")
                self.total += len(text.encode())
                self.active[diag_id] = {"metadata": meta, "touched": time.time(), "sequence": 0, "bytes": 0, "pcmFrames": 0,
                                        "probeFrames": 0, "mediaBytes": 0, "finishFrames": None, "error": ""}
                return {"id": diag_id}
            s = self.active.get(diag_id)
            if not s:
                raise ValueError("診斷已結束或服務已重啟")
            s["touched"] = time.time()
            meta = s["metadata"]
            if action == "finish":
                error = str(data.get("error") or s["error"] or "")
                if meta["formatVersion"] == 2 and not data.get("cancelled") and not error:
                    rf = data.get("recordedFrames")
                    if not isinstance(rf, int) or rf <= 0 or s["pcmFrames"] != rf or s["finishFrames"] != rf:
                        error = "診斷 PCM 未完整涵蓋錄音"
                    elif not s["probeFrames"]:
                        error = "缺少收音分析診斷"
                    elif meta.get("input") == "browser-media-stream" and not s["mediaBytes"]:
                        error = "缺少瀏覽器直接收音診斷"
                meta.update({"status": "cancelled" if data.get("cancelled") else ("incomplete" if error else "saved"),
                             "error": error[:500], "finished": int(time.time() * 1000), "bytes": s["bytes"],
                             "frames": s["pcmFrames"]})
                (d / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                self.active.pop(diag_id, None)
                return {"saved": meta["status"] == "saved", "error": meta["error"], "frames": s["pcmFrames"]}
            if data.get("kind") not in ("event", "media", "probe", "pcm"):
                raise ValueError("Invalid event kind")
            s["sequence"] += 1
            event = {**data, "sequence": s["sequence"]}
            buffers = []
            for value in data.get("buffers") or []:
                if not isinstance(value, str) or not B64.match(value):
                    raise ValueError("Invalid sample data")
                buffers.append(base64.b64decode(value))
            nbytes = sum(len(b) for b in buffers)
            files = [f"{s['sequence']:08d}-{i}.bin" for i in range(len(buffers))]
            if meta["formatVersion"] == 2 and data["kind"] == "pcm":
                frames = data.get("frames")
                if (not isinstance(frames, int) or frames <= 0 or len(buffers) != 1 or len(buffers[0]) != frames * 4
                        or data.get("recordedFrame") != s["pcmFrames"]):
                    s["error"] = "診斷 PCM 取樣不連續或資料長度錯誤"
                    raise ValueError(s["error"])
            event.pop("buffers", None)
            event["files"] = files
            line = json.dumps(event, ensure_ascii=False) + "\n"
            lb = len(line.encode())
            if (lb > 65536 or len(buffers) > 8 or s["sequence"] > 50000 or s["bytes"] + nbytes + lb > 512 * 1024 ** 2
                    or self.total + nbytes + lb > self.max_bytes):
                raise ValueError("診斷容量已滿，錄音仍會繼續；請停止後清除舊診斷")
            for name, b in zip(files, buffers):
                (d / name).write_bytes(b)
            self.total += nbytes + lb
            s["bytes"] += nbytes + lb
            with open(d / "events.jsonl", "a", encoding="utf-8") as fh:
                fh.write(line)
            if data["kind"] == "pcm":
                s["pcmFrames"] += data.get("frames") or 0
            if data["kind"] == "probe" and buffers:
                s["probeFrames"] += data.get("frames") or 0
            if data["kind"] == "media":
                s["mediaBytes"] += nbytes
            if data["kind"] == "event" and data.get("event") == "finish":
                s["finishFrames"] = data.get("recordedFrames")
            return {"saved": True}
