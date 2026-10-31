"""The finished-outputs folder: readable shortcuts to every result in the library.

Song folders in the library are named by id (songs/<id>/...), so the finished files are hard to
find in Explorer. This module keeps <library>/Finished (always English; 成品 in the UI) in step with the
library: one folder per song, named by its title, holding a shortcut to each cover version,
sing & record take, quick MV and full MV. Nothing is copied; the shortcuts point at the real files.

  Finished/童話/翻唱 #1 My_Voice_Ver8 -12 · Key -2.lnk
  Finished/童話/唱錄 10-31 09：05.lnk
  Finished/童話/快速MV 錄音室 1080p · 翻唱 #1 · 10-31 09：20.lnk
  Finished/童話/MV 童話.lnk

Two songs with the same title get the import date ("童話（10-29 匯入）"), and the import time
when that is the same too. Times use a full-width colon (09：05): Windows names cannot hold ":". Clashing shortcut names get " (2)", " (3)".

Only what this module created is ever removed. A manifest (<library>/finished_shortcuts.json)
lists the folders and shortcuts it made; files the user puts in the folders are left alone, and
a song folder is removed only when nothing else is in it. A renamed song renames its folder.

Shortcuts are Windows .lnk files written through IShellLinkW from PowerShell. On other systems (tests)
they are symbolic links.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("sign2mv.finished")

MANIFEST = "finished_shortcuts.json"
ROOT_NAMES = {"zh": "Finished", "en": "Finished"}   # one English name for every UI language
LEGACY_ROOTS = ("成品",)   # earlier name: moved to Finished
DEBOUNCE_S = 1.5
NAME_MAX = 80
_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RID = re.compile(r"^r[a-f0-9]{12}$")   # finished folders only (not "<id>.tmp" while a job writes)
_QID = re.compile(r"^q[a-f0-9]{12}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

TEXT = {
    "zh": {"cover": "翻唱", "sing": "唱錄", "quick": "快速MV", "mv": "MV", "original": "原曲",
           "card": "卡片", "studio": "錄音室", "imported": "（{d} 匯入）"},
    "en": {"cover": "Cover", "sing": "Sing", "quick": "Quick MV", "mv": "MV", "original": "Original",
           "card": "Card", "studio": "Studio", "imported": " (imported {d})"},
}


def lang_key(language: str | None) -> str:
    return "en" if str(language or "").lower().startswith("en") else "zh"


def safe_name(text: Any, fallback: str = "_") -> str:
    """A file or folder name Windows accepts."""
    t = _BAD.sub("_", str(text or "")).strip().rstrip(". ")
    t = re.sub(r"\s+", " ", t)[:NAME_MAX].rstrip(". ")
    if not t:
        t = fallback
    if t.split(".")[0].upper() in _RESERVED:
        t = "_" + t
    return t


# Windows file names cannot hold ":" -> the full-width colon in Chinese, a dot in English
TIME_SEP = {"zh": "：", "en": "."}


def _stamp(ts: Any, with_time: bool = True, lang: str = "zh") -> str:
    try:
        lt = time.localtime(float(ts))
    except (TypeError, ValueError, OverflowError, OSError):
        return ""
    return time.strftime("%m-%d %H" + TIME_SEP[lang] + "%M" if with_time else "%m-%d", lt)


def _read_json(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _unique(name: str, taken: set[str]) -> str:
    """name, or name (2), name (3)… — compared without case like Windows does."""
    out, n = name, 2
    while out.lower() in taken:
        out = f"{name} ({n})"
        n += 1
    taken.add(out.lower())
    return out


# ---------------------------------------------------------------- what should exist
def song_folders(songs: list[dict], lang: str) -> dict[str, str]:
    """song id -> folder name. Same titles get the import date, then the import time, then (2)."""
    fmt = TEXT[lang]["imported"]
    base = {s["song_id"]: safe_name(s.get("title"), s["song_id"]) for s in songs}
    groups: dict[str, list[dict]] = {}
    for s in songs:
        groups.setdefault(base[s["song_id"]].lower(), []).append(s)
    out: dict[str, str] = {}
    for group in groups.values():
        if len(group) == 1:
            out[group[0]["song_id"]] = base[group[0]["song_id"]]
            continue
        days = [_stamp(s.get("created_at"), False) for s in group]
        for s, day in zip(group, days):
            d = day if days.count(day) == 1 else _stamp(s.get("created_at"), True, lang)
            out[s["song_id"]] = base[s["song_id"]] + fmt.format(d=d)
    taken: set[str] = set()
    order = sorted(songs, key=lambda s: (float(s.get("created_at") or 0), s["song_id"]))
    return {s["song_id"]: _unique(out[s["song_id"]], taken) for s in order}


def _cover_ref(title: str) -> str:
    m = re.search(r"(#\d+)", str(title or ""))   # "#1 label" (older renders: "title · label #1")
    return m.group(1) if m else str(title or "").strip()


def song_items(song_dir: Path, lang: str) -> list[tuple[str, Path]]:
    """(shortcut name without extension, target file) for one song, oldest first."""
    T = TEXT[lang]
    items: list[tuple[float, str, Path]] = []
    renders = song_dir / "renders"
    version_of: dict[str, dict] = {}
    vbase = song_dir / "cover" / "versions"
    if vbase.is_dir():
        for d in vbase.iterdir():
            v = _read_json(d / "version.json")
            if isinstance(v, dict) and v.get("render_id"):
                version_of[str(v["render_id"])] = v
    if renders.is_dir():
        for d in renders.iterdir():
            info = _read_json(d / "render.json") if _RID.match(d.name) else None
            if not isinstance(info, dict) or not info.get("audio"):
                continue
            target = d / str(info["audio"])
            if not target.is_file():
                continue
            when = float(info.get("created_at") or 0) or target.stat().st_mtime
            if info.get("kind") == "cover":
                v = version_of.get(d.name) or {}
                title = v.get("title") or info.get("title") or d.name
                items.append((float(v.get("created_at") or when), f"{T['cover']} {title}", target))
            elif info.get("kind") == "sing":
                items.append((when, f"{T['sing']} {_stamp(when, True, lang)}", target))
    qbase = song_dir / "quickmv"
    if qbase.is_dir():
        for d in qbase.iterdir():
            target = d / "video.mp4"
            if not _QID.match(d.name) or not target.is_file():
                continue
            info = _read_json(d / "info.json") or {}
            kind = info.get("source_kind")
            src = (f"{T['cover']} {_cover_ref(info.get('source_title'))}" if kind == "cover"
                   else T["sing"] if kind == "sing" else T["original"])
            look = T["studio"] if info.get("style") == "studio" else T["card"]
            when = float(info.get("created_at") or 0) or target.stat().st_mtime   # older quick MVs: no created_at
            parts = [f"{T['quick']} {look} {info.get('resolution') or ''}".strip(), src, _stamp(when, True, lang)]
            items.append((when, " · ".join(p for p in parts if p), target))
    mbase = song_dir / "mv"
    if mbase.is_dir():
        for d in mbase.iterdir():
            proj = _read_json(d / "project.json")
            if not isinstance(proj, dict):
                continue
            out = os.path.basename(str(proj.get("output_mv") or ""))
            if not out:
                t = _BAD.sub("_", str(proj.get("title") or "")).strip().strip(".")[:80] or d.name
                out = f"{t}_MV.mp4"
            target = d / "output" / out
            if target.is_file():
                items.append((target.stat().st_mtime, f"{T['mv']} {proj.get('title') or d.name}", target))
    items.sort(key=lambda x: x[0])
    taken: set[str] = set()
    return [(_unique(safe_name(name), taken), target) for _, name, target in items]


def desired(library_root: Path, lang: str) -> dict[str, dict]:
    """song id -> {"folder": name, "links": {shortcut name: target path}}"""
    from .library import SONG_ID_RE
    songs = []
    sdir = library_root / "songs"
    if sdir.is_dir():
        for d in sdir.iterdir():
            if not (d.is_dir() and SONG_ID_RE.match(d.name)):
                continue
            meta = _read_json(d / "song.json")
            if not isinstance(meta, dict):
                continue
            title = meta.get("title")
            if meta.get("title_auto"):
                src = _read_json(d / "source" / "source.json") or {}
                title = src.get("youtube_title") or title
            songs.append({"song_id": d.name, "title": title, "created_at": meta.get("created_at", 0)})
    links = {s["song_id"]: {n: str(t) for n, t in song_items(sdir / s["song_id"], lang)} for s in songs}
    # songs with nothing finished get no folder and do not count as a duplicate title
    songs = [s for s in songs if links[s["song_id"]]]
    folders = song_folders(songs, lang)
    return {s["song_id"]: {"folder": folders[s["song_id"]], "links": links[s["song_id"]]} for s in songs}


# ---------------------------------------------------------------- making links
LINK_EXT = ".lnk" if os.name == "nt" else ""

# IShellLinkW (not WScript.Shell, whose shortcuts turn characters outside the ANSI code page into "?")
_PS = r"""
$ErrorActionPreference = 'Continue'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IShellLinkW {
  void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder f, int cch, IntPtr fd, int flags);
  void GetIDList(out IntPtr pidl);
  void SetIDList(IntPtr pidl);
  void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch);
  void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string s);
  void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch);
  void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string s);
  void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch);
  void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string s);
  void GetHotkey(out short k);
  void SetHotkey(short k);
  void GetShowCmd(out int c);
  void SetShowCmd(int c);
  void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder s, int cch, out int i);
  void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string s, int i);
  void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string s, int r);
  void Resolve(IntPtr hwnd, int flags);
  void SetPath([MarshalAs(UnmanagedType.LPWStr)] string s);
}
[ComImport, Guid("00021401-0000-0000-C000-000000000046")] class CShellLink {}
public static class Sign2mvLink {
  public static void Make(string link, string target) {
    IShellLinkW sl = (IShellLinkW)new CShellLink();
    try {
      sl.SetPath(target);
      sl.SetWorkingDirectory(System.IO.Path.GetDirectoryName(target));
      ((IPersistFile)sl).Save(link, true);
    } finally { Marshal.ReleaseComObject(sl); }
  }
}
'@
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# not "Get-Content | ConvertFrom-Json" inside @(): Windows PowerShell 5.1 passes the whole array as ONE
# object down the pipe, so every link name was joined into one path (IShellLinkW Save: E_FAIL)
$items = ConvertFrom-Json (Get-Content -LiteralPath $args[0] -Raw -Encoding UTF8)
foreach ($it in $items) {
  try { [Sign2mvLink]::Make([string]$it.link, [string]$it.target) }
  catch { [Console]::Error.WriteLine("$($it.link): $($_.Exception.Message)") }
}
"""


def link_target(link: Path) -> str | None:
    """Where an existing link points (None when it is not readable); .lnk files are trusted by the manifest."""
    if os.name == "nt":
        return None
    try:
        return os.readlink(link)
    except OSError:
        return None


def make_links(pairs: list[tuple[Path, str]], tmp_dir: Path) -> list[str]:
    """Create the links; returns error lines."""
    if not pairs:
        return []
    errors: list[str] = []
    if os.name != "nt":
        for link, target in pairs:
            try:
                if link.is_symlink() or link.exists():
                    link.unlink()
                os.symlink(target, link)
            except OSError as exc:
                errors.append(f"{link}: {exc}")
        return errors
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{os.getpid()}_{threading.get_ident()}"
    lst = tmp_dir / f"finished_links_{stamp}.json"
    ps1 = tmp_dir / f"finished_links_{stamp}.ps1"
    try:
        lst.write_text(json.dumps([{"link": str(l), "target": t} for l, t in pairs], ensure_ascii=False),
                       encoding="utf-8")
        ps1.write_text(_PS, encoding="utf-8-sig")
        # Add-Type compiles in TEMP: keep that in the app folder, not on C:
        env = {**os.environ, "TEMP": str(tmp_dir), "TMP": str(tmp_dir)}
        ps = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        proc = subprocess.run([str(ps) if ps.is_file() else "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                               "-File", str(ps1), str(lst)], capture_output=True, stdin=subprocess.DEVNULL,
                              timeout=120, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        text = proc.stderr.decode("utf-8", "replace").strip()
        if text:
            errors += text.splitlines()[-20:]
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"powershell: {exc}")
    finally:
        for f in (lst, ps1):
            try:
                f.unlink()
            except OSError:
                pass
    return errors


# ---------------------------------------------------------------- syncing
def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _remove_link(path: Path) -> None:
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
    except OSError:
        pass


def _rmdir_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


def sync(library_root: Path, language: str | None, tmp_dir: Path) -> dict[str, Any]:
    """Bring <library>/Finished in step with the library. Returns counts (for tests and the log)."""
    library_root = Path(library_root)
    lang = lang_key(language)
    if not (library_root / "songs").is_dir():
        return {"skipped": True}
    mpath = library_root / MANIFEST
    old = _read_json(mpath) or {}
    old_root_name = old.get("root") if isinstance(old.get("root"), str) else None
    root_name = ROOT_NAMES[lang]
    root = library_root / root_name
    # the UI language changed: move the folder to its new name (it may hold the user's own files)
    if old_root_name and old_root_name != root_name and old_root_name in (*ROOT_NAMES.values(), *LEGACY_ROOTS):
        old_root = library_root / old_root_name
        if old_root.is_dir() and not root.exists():
            try:
                os.replace(old_root, root)
            except OSError:
                root = old_root
                root_name = old_root_name
        elif old_root.is_dir():
            root, root_name = old_root, old_root_name
    want = desired(library_root, lang)
    old_songs: dict[str, dict] = old.get("songs") if isinstance(old.get("songs"), dict) else {}
    counts = {"created": 0, "removed": 0, "renamed": 0, "errors": []}
    root.mkdir(exist_ok=True)

    # 1. remove what we made and no longer want; rename folders of renamed songs
    for sid, rec in list(old_songs.items()):
        folder = root / str(rec.get("folder") or "")
        if not rec.get("folder") or not _is_inside(folder, root) or folder == root:
            continue
        links: dict[str, str] = rec.get("links") or {}
        new = want.get(sid)
        keep = set(new["links"]) if new else set()
        for name in links:
            if name not in keep or (new and new["links"][name] != links[name]):
                _remove_link(folder / (name + LINK_EXT))
                counts["removed"] += 1
        if not new:
            _rmdir_if_empty(folder)
            continue
        target = root / new["folder"]
        if folder != target and folder.is_dir():
            if not target.exists():
                try:
                    os.replace(folder, target)
                    counts["renamed"] += 1
                except OSError as exc:
                    counts["errors"].append(f"rename {folder.name}: {exc}")
                    new["folder"] = rec["folder"]
            else:
                # the new name is taken (by the user): keep the old folder name
                new["folder"] = rec["folder"]

    # 2. create the missing links
    pairs: list[tuple[Path, str]] = []
    for sid, rec in want.items():
        folder = root / rec["folder"]
        before = (old_songs.get(sid) or {}).get("links") or {}
        for name, target in list(rec["links"].items()):
            link = folder / (name + LINK_EXT)
            here = link.is_symlink() or link.exists()
            if here and name not in before:
                # a file of the user's with that name: leave it alone and do not claim it
                del rec["links"][name]
                continue
            if here and before.get(name) == target and (os.name == "nt" or link_target(link) == target):
                continue
            folder.mkdir(parents=True, exist_ok=True)
            pairs.append((link, target))
    counts["errors"] += make_links(pairs, tmp_dir)
    counts["created"] = len(pairs)

    manifest = {"schema_version": 1, "root": root_name, "language": lang, "songs": want, "updated_at": time.time()}
    tmp = mpath.with_name(mpath.name + ".tmp")
    try:
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, mpath)
    except OSError as exc:
        counts["errors"].append(f"manifest: {exc}")
    if old_root_name and old_root_name != root_name:
        _rmdir_if_empty(library_root / old_root_name)
    return counts


class FinishedSync:
    """Runs sync() on a background thread, a moment after something changed."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last: dict[str, Any] | None = None

    def request(self) -> None:
        self._event.set()
        if self._thread is None:
            with self._lock:
                if self._thread is None:
                    self._thread = threading.Thread(target=self._loop, name="finished-sync", daemon=True)
                    self._thread.start()

    def run_now(self) -> dict[str, Any]:
        with self._lock:
            return self._run()

    def _run(self) -> dict[str, Any]:
        try:
            cfg = self.ctx.settings()
            from .settings import effective_language
            self.last = sync(Path(cfg["library_dir"]), effective_language(cfg), self.ctx.paths.tmp)
            if self.last.get("errors"):
                log.warning("finished folder: %s", "; ".join(self.last["errors"][:5]))
        except Exception as exc:  # noqa: BLE001 - never let this break the app
            log.warning("finished folder sync failed: %s", exc)
            self.last = {"errors": [str(exc)]}
        return self.last

    def _loop(self) -> None:
        while True:
            self._event.wait()
            time.sleep(DEBOUNCE_S)
            self._event.clear()
            with self._lock:
                self._run()
