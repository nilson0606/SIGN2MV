"""Durable sing & record recordings (port of sign_record recording-archive.mjs).

Layout: <library>/recordings/<uuid>/{metadata.json, mix.<ext>, voice.<ext>, export.mp3}
A deleted id is remembered in .deleted.json so an old browser copy is never re-imported.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

ID = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
MAX_AUDIO = 384 * 1024 * 1024
MAX_META = 16 * 1024 * 1024
FORMAT = "karaoke-recording-v1"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class ArchiveError(Exception):
    pass


def ext(mime: Any) -> str | None:
    if not isinstance(mime, str):
        return None
    if mime.startswith("audio/webm"):
        return "webm"
    if mime.startswith("audio/mp4"):
        return "m4a"
    if mime == "audio/wav":
        return "wav"
    return None


def _int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and abs(v) <= 2 ** 53 - 1


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate(meta: Any, rec_id: str) -> dict[str, Any]:
    if not isinstance(meta, dict):
        raise ArchiveError("錄音資料或大小無效。")
    raw_bytes = meta.get("rawBytes", 0) if meta.get("rawBytes") is not None else 0
    ok = (meta.get("id") == rec_id and ID.match(rec_id) and isinstance(meta.get("title"), str)
          and len(meta["title"]) <= 500 and ext(meta.get("mime"))
          and (not meta.get("rawMime") or ext(meta.get("rawMime")))
          and _num(meta.get("created")) and _num(meta.get("seconds")) and 0 <= meta["seconds"] <= 3601
          and _int(meta.get("bytes")) and 1 <= meta["bytes"] <= MAX_AUDIO
          and _int(raw_bytes) and 0 <= raw_bytes <= MAX_AUDIO)
    if not ok:
        raise ArchiveError("錄音資料或大小無效。")
    return {k: v for k, v in meta.items() if k != "_archiveRoot"}


def _regular(path: Path) -> os.stat_result:
    try:
        st = os.lstat(path)
    except OSError:
        raise ArchiveError("錄音檔案位置無效。")
    import stat as stat_mod
    if not stat_mod.S_ISREG(st.st_mode):
        raise ArchiveError("錄音檔案位置無效。")
    return st


class RecordingArchive:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ArchiveError("錄音目錄不能是連結。")

    def dir(self, rec_id: str) -> Path:
        if not ID.match(rec_id or ""):
            raise ArchiveError("錄音 ID 無效。")
        d = (self.root / rec_id)
        if d.parent != self.root:
            raise ArchiveError("錄音位置無效。")
        return d

    def owned(self, rec_id: str) -> Path:
        d = self.dir(rec_id)
        if d.is_symlink() or not d.is_dir():
            raise ArchiveError("錄音目錄無效。")
        return d

    def deleted(self) -> list[str]:
        f = self.root / ".deleted.json"
        if not f.exists():
            return []
        _regular(f)
        try:
            value = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return []
        return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []

    @staticmethod
    def atomic(file: Path, text: str) -> None:
        tmp = file.with_name(file.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, file)
        finally:
            tmp.unlink(missing_ok=True)

    def get(self, rec_id: str) -> dict[str, Any]:
        d = self.owned(rec_id)
        _regular(d / "metadata.json")
        try:
            value = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        except ValueError:
            raise ArchiveError("錄音資料損壞。")
        if not isinstance(value, dict) or value.get("format") != FORMAT:
            raise ArchiveError("這個目錄不是本工具的錄音。")
        meta = validate(value.get("recording"), rec_id)
        if _regular(d / f"mix.{ext(meta['mime'])}").st_size != meta["bytes"]:
            raise ArchiveError("錄音成品不完整。")
        if meta.get("rawBytes"):
            if _regular(d / f"voice.{ext(meta.get('rawMime') or meta['mime'])}").st_size != meta["rawBytes"]:
                raise ArchiveError("原始歌聲不完整。")
        return {**meta, "_archiveRoot": str(self.root)}

    def list(self) -> dict[str, Any]:
        self.ready()
        deleted = set(self.deleted())
        records = []
        for d in self.root.iterdir():
            if d.is_dir() and not d.is_symlink() and ID.match(d.name) and d.name not in deleted:
                try:
                    records.append(self.get(d.name))
                except ArchiveError:
                    pass  # incomplete or foreign folders are never exposed or removed
        records.sort(key=lambda r: r["created"], reverse=True)
        return {"path": str(self.root), "records": records, "deleted": sorted(deleted)}

    def import_bundle(self, rec_id: str, bundle: Path) -> dict[str, Any]:
        """bundle = uint32le(len(meta)) + meta JSON + mix bytes + voice bytes."""
        self.ready()
        if rec_id in self.deleted():
            raise ArchiveError("這筆錄音已刪除，不能從舊副本自動搬回。")
        target = self.dir(rec_id)
        if target.exists():
            return self.get(rec_id)  # a retry cannot overwrite newer results
        stage = Path(tempfile.mkdtemp(prefix=".incoming-", dir=self.root))
        try:
            size = bundle.stat().st_size
            with open(bundle, "rb") as fh:
                prefix = fh.read(4)
                if len(prefix) != 4:
                    raise ArchiveError("錄音封包不完整。")
                n = int.from_bytes(prefix, "little")
                if n < 2 or n > MAX_META:
                    raise ArchiveError("錄音資料太大。")
                raw = fh.read(n)
                if len(raw) != n:
                    raise ArchiveError("錄音資料不完整。")
                try:
                    meta = validate(json.loads(raw.decode("utf-8")), rec_id)
                except ValueError:
                    raise ArchiveError("錄音資料或大小無效。")
                if size != 4 + n + meta["bytes"] + (meta.get("rawBytes") or 0):
                    raise ArchiveError("音檔長度不符，保留瀏覽器原檔供重試。")
                for name, length in (("mix", meta["bytes"]), ("voice", meta.get("rawBytes") or 0)):
                    if not length:
                        continue
                    suffix = ext(meta.get("rawMime") or meta["mime"]) if name == "voice" else ext(meta["mime"])
                    with open(stage / f"{name}.{suffix}", "xb") as out:
                        left = length
                        while left:
                            chunk = fh.read(min(left, 1 << 20))
                            if not chunk:
                                raise ArchiveError("錄音封包不完整。")
                            out.write(chunk)
                            left -= len(chunk)
            (stage / "metadata.json").write_text(json.dumps({"format": FORMAT, "recording": meta}, ensure_ascii=False),
                                                encoding="utf-8")
            os.replace(stage, target)
            return self.get(rec_id)
        finally:
            if stage.exists() and stage.parent == self.root and stage.name.startswith(".incoming-"):
                shutil.rmtree(stage, ignore_errors=True)

    def update(self, rec_id: str, value: Any) -> dict[str, Any]:
        prior = self.get(rec_id)
        meta = validate(value, rec_id)
        if (meta["bytes"] != prior["bytes"] or (meta.get("rawBytes") or 0) != (prior.get("rawBytes") or 0)
                or meta["mime"] != prior["mime"]
                or (meta.get("rawMime") or meta["mime"]) != (prior.get("rawMime") or prior["mime"])):
            raise ArchiveError("不能在更新成績時改寫音檔資訊。")
        self.atomic(self.dir(rec_id) / "metadata.json", json.dumps({"format": FORMAT, "recording": meta}, ensure_ascii=False))
        return self.get(rec_id)

    # [SIGN2MV] change named fields of the stored metadata only, merged with what is on disk now, so a page
    # holding an older copy of the record cannot write it back over newer changes (e.g. a take saved to
    # post-production in the meantime). Called under the archive lock.
    PATCHABLE = {"post.rmvpeAnalysis"}

    def patch(self, rec_id: str, changes: Any) -> dict[str, Any]:
        if not isinstance(changes, dict) or not changes or any(k not in self.PATCHABLE for k in changes):
            raise ArchiveError("不支援的錄音資料修改。")
        meta = self.get(rec_id)
        for path, value in changes.items():
            head, field = path.split(".")
            if not isinstance(meta.get(head), dict):
                raise ArchiveError("錄音資料沒有可修改的欄位。")
            meta[head] = {**meta[head], field: value}
        return self.update(rec_id, meta)

    def audio(self, rec_id: str, track: str) -> tuple[Path, str]:
        meta = self.get(rec_id)
        if track not in ("mix", "voice", "mp3"):
            raise ArchiveError("無效音軌。")
        if track == "mp3":
            file, mime = self.dir(rec_id) / "export.mp3", "audio/mpeg"
        elif track == "voice":
            mime = meta.get("rawMime") or meta["mime"]
            file = self.dir(rec_id) / f"voice.{ext(mime)}"
        else:
            mime = meta["mime"]
            file = self.dir(rec_id) / f"mix.{ext(mime)}"
        _regular(file)
        return file, mime

    def save_mp3(self, rec_id: str, source: Path) -> dict[str, Any]:
        self.get(rec_id)
        size = source.stat().st_size
        if not size:
            raise ArchiveError("MP3 為空。")
        if size > MAX_AUDIO:
            raise ArchiveError("MP3 太大。")
        file = self.dir(rec_id) / "export.mp3"
        tmp = file.with_name(file.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            shutil.copyfile(source, tmp)
            os.replace(tmp, file)
        finally:
            tmp.unlink(missing_ok=True)
        return {"path": str(file)}

    def delete(self, rec_id: str) -> None:
        self.ready()
        d = self.dir(rec_id)
        deleted = self.deleted()
        if rec_id not in deleted:
            self.get(rec_id)
            deleted.append(rec_id)
            self.atomic(self.root / ".deleted.json", json.dumps(deleted))
        if d.exists() or d.is_symlink():
            self.owned(rec_id)
            shutil.rmtree(d, ignore_errors=True)


def sniff_format(head: bytes) -> str | None:
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == bytes([0x1A, 0x45, 0xDF, 0xA3]):
        return "matroska"
    if head[4:8] == b"ftyp":
        return "mov"
    return None


def export_mp3(source: Path, work_dir: Path, cancel=None) -> bytes:
    """Convert a recording (WebM/WAV/M4A) to 192 kbps MP3 with ffmpeg.
    `cancel` (threading.Event): set when the page went away; ffmpeg is stopped (sign_record did the same)."""
    with open(source, "rb") as fh:
        fmt = sniff_format(fh.read(16))
    if not fmt:
        raise ArchiveError("不支援的錄音格式，請選擇 WebM、WAV 或 M4A 錄音。")
    work_dir.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="recording-", dir=work_dir))
    try:
        out = d / "output.mp3"
        try:
            proc = subprocess.Popen([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-nostdin", "-protocol_whitelist",
                                     "file,pipe", "-f", fmt, "-i", str(source), "-map", "0:a:0", "-vn", "-threads", "2",
                                     "-c:a", "libmp3lame", "-b:a", "192k", str(out)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        except OSError:
            raise ArchiveError("無法啟動 FFmpeg，請檢查安裝。")
        deadline = time.monotonic() + 120
        while proc.poll() is None:
            if (cancel is not None and cancel.is_set()) or time.monotonic() > deadline:
                proc.kill()
                proc.wait()
                if cancel is not None and cancel.is_set():
                    raise ArchiveError("已取消 MP3 轉檔。")
                raise ArchiveError("MP3 轉檔逾時，請重試。")
            time.sleep(0.1)
        if proc.returncode != 0:
            raise ArchiveError("MP3 轉檔失敗，錄音可能不完整。")
        data = out.read_bytes()
        if not data:
            raise ArchiveError("MP3 輸出為空。")
        return data
    finally:
        shutil.rmtree(d, ignore_errors=True)
