"""SIGN2MV installer (step 2; install.bat already set up uv, Python and the server env).

Runs with the server environment's Python and only uses the standard library.
Every step is resumable: finished steps are recorded in runtime/install_state.json
and skipped next time, so if the network drops you just run install.bat again.

All files go under the application folder. Before/after free space on C: is
measured and reported, to prove nothing large was written there.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.childenv import cache_vars, child_env, ensure_dirs  # noqa: E402
from app.paths import Paths  # noqa: E402

PATHS = Paths(ROOT)
RT = PATHS.runtime
MANIFEST = json.loads((ROOT / "installer" / "manifest.json").read_text(encoding="utf-8"))
STATE_FILE = RT / "install_state.json"
LOG_FILE = PATHS.logs / "install.log"
IS_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------- output
def log(msg: str = "") -> None:
    line = msg.encode("ascii", "replace").decode("ascii")
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def banner(msg: str) -> None:
    log("")
    log("=" * 64)
    log(" " + msg)
    log("=" * 64)


class InstallError(Exception):
    pass


# ---------------------------------------------------------------- state
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"steps": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def step_key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- helpers
def env() -> dict:
    e = child_env(PATHS)
    e.pop("PYTHONHOME", None)
    e.pop("VIRTUAL_ENV", None)
    return e


def run(args: list, *, cwd: Path | None = None, check: bool = True, capture: bool = False,
        extra_env: dict | None = None) -> subprocess.CompletedProcess:
    log("> " + " ".join(str(a) for a in args))
    e = env()
    if extra_env:
        e.update(extra_env)
    res = subprocess.run([str(a) for a in args], cwd=str(cwd) if cwd else None, env=e,
                         capture_output=capture, text=capture, encoding="utf-8" if capture else None,
                         errors="replace" if capture else None)
    if check and res.returncode != 0:
        tail = ((res.stdout or "") + (res.stderr or ""))[-2000:] if capture else ""
        raise InstallError(f"command failed (exit {res.returncode}): {args[0]}\n{tail}")
    return res


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, sha256: str | None = None, size: int | None = None,
             attempts: int = 6) -> Path:
    """Download with resume. The file only gets its final name when complete and verified."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and (sha256 is None or sha256_of(dest) == sha256) and (size is None or dest.stat().st_size == size):
        log(f"  already downloaded: {dest.name}")
        return dest
    part = dest.with_name(dest.name + ".part")
    for attempt in range(1, attempts + 1):
        try:
            have = part.stat().st_size if part.exists() else 0
            req = urllib.request.Request(url, headers={"User-Agent": "SIGN2MV-installer"})
            if have:
                req.add_header("Range", f"bytes={have}-")
            with urllib.request.urlopen(req, timeout=60) as resp:
                if have and resp.status != 206:
                    have = 0  # server ignored the range request; start over
                total = resp.headers.get("Content-Length")
                total = (int(total) + have) if total else None
                mode = "ab" if have else "wb"
                done = have
                last = time.time()
                with open(part, mode) as out:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                        done += len(chunk)
                        if time.time() - last > 2:
                            last = time.time()
                            pct = f"{done * 100 / total:5.1f}%" if total else ""
                            print(f"    {dest.name}: {done / 1048576:8.1f} MB {pct}", flush=True)
            if total and part.stat().st_size < total:
                raise InstallError("incomplete download")
            if size is not None and part.stat().st_size != size:
                raise InstallError(f"size mismatch: got {part.stat().st_size}, expected {size}")
            if sha256 and sha256_of(part) != sha256:
                part.unlink(missing_ok=True)
                raise InstallError("checksum mismatch (file corrupted or changed upstream)")
            os.replace(part, dest)
            log(f"  downloaded {dest.name} ({dest.stat().st_size / 1048576:.1f} MB)")
            return dest
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404, 410):   # the file is not there: retrying cannot help
                part.unlink(missing_ok=True)
                raise InstallError(f"not found ({exc.code}): {url}") from exc
            log(f"  attempt {attempt}/{attempts} failed: {exc}")
            time.sleep(min(30, 3 * attempt))
        except (urllib.error.URLError, OSError, InstallError) as exc:
            log(f"  attempt {attempt}/{attempts} failed: {exc}")
            if isinstance(exc, InstallError) and "checksum" in str(exc):
                pass
            time.sleep(min(30, 3 * attempt))
    raise InstallError(f"could not download {url}")


def extract_zip(archive: Path, target: Path, strip_top: bool = True) -> None:
    tmp = target.with_name(target.name + ".extracting")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(tmp)
    src = tmp
    entries = list(tmp.iterdir())
    if strip_top and len(entries) == 1 and entries[0].is_dir():
        src = entries[0]
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(src), str(target))
    shutil.rmtree(tmp, ignore_errors=True)


def uv() -> str:
    exe = RT / "uv" / ("uv.exe" if IS_WINDOWS else "uv")
    return str(exe) if exe.exists() else (shutil.which("uv") or "uv")


def detect_gpu() -> tuple[str, str]:
    """('cuda', name) when an NVIDIA driver answers, else ('cpu', '')."""
    if os.environ.get("SIGN2MV_FORCE_CPU"):
        return "cpu", ""
    smi = shutil.which("nvidia-smi")
    if not smi and IS_WINDOWS:
        cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        smi = str(cand) if cand.exists() else None
    if not smi:
        return "cpu", ""
    try:
        out = subprocess.run([smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=20)
        line = out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else ""
    except (OSError, subprocess.TimeoutExpired, IndexError):
        line = ""
    return ("cuda", line) if line else ("cpu", "")


def c_drive_free() -> int | None:
    if not IS_WINDOWS:
        return None
    try:
        return shutil.disk_usage("C:\\").free
    except OSError:
        return None


# ---------------------------------------------------------------- steps
def step_ffmpeg(state: dict) -> None:
    target = RT / "ffmpeg"
    archive = PATHS.cache / "downloads" / "ffmpeg-win64-gpl.zip"
    download(MANIFEST["ffmpeg"]["url"], archive)
    extract_zip(archive, target)
    exe = target / "bin" / ("ffmpeg.exe" if IS_WINDOWS else "ffmpeg")
    res = run([exe, "-hide_banner", "-filters"], capture=True)
    if "rubberband" not in res.stdout:
        raise InstallError("this ffmpeg build has no 'rubberband' filter (needed for key shifting)")
    archive.unlink(missing_ok=True)


def step_deno(state: dict) -> None:
    m = MANIFEST["deno"]
    archive = PATHS.cache / "downloads" / "deno.zip"
    download(m["url"], archive, sha256=m["sha256"])
    extract_zip(archive, RT / "deno", strip_top=False)
    run([RT / "deno" / ("deno.exe" if IS_WINDOWS else "deno"), "--version"])
    archive.unlink(missing_ok=True)


def _venv(name: str) -> Path:
    py = PATHS.env_python(name)
    if not py.exists():
        run([uv(), "venv", PATHS.envs / name, "--python", MANIFEST["python"], "--seed"])
    return py


def _pip_install(py: Path, args: list, lock: Path | None = None, fallback: Path | None = None,
                 extra: list | None = None) -> None:
    base = [uv(), "pip", "install", "--python", py]
    if lock is not None:
        try:
            run(base + ["-r", lock] + (extra or []))
            return
        except InstallError as exc:
            log(f"  locked install failed ({exc}); retrying with the unlocked requirement list")
            if fallback is None:
                raise
            run(base + ["-r", fallback] + (extra or []))
            return
    run(base + args + (extra or []))


def step_engine_env(state: dict) -> None:
    device = state["device"]
    py = _venv("engine")
    tv = MANIFEST["torch"]["engine"]
    index = MANIFEST["torch"]["cuda_index"] if device == "cuda" else MANIFEST["torch"]["cpu_index"]
    log(f"Installing PyTorch {tv['torch']} ({'CUDA 12.8' if device == 'cuda' else 'CPU'}); this download is several GB...")
    run([uv(), "pip", "install", "--python", py, f"torch=={tv['torch']}", f"torchaudio=={tv['torchaudio']}",
         f"torchvision=={tv['torchvision']}", "--index-url", index])
    req = ROOT / "installer" / "requirements"
    _pip_install(py, [], lock=req / "engine.lock.txt", fallback=req / "engine.txt")
    # basic-pitch (cover melody track) without its TensorFlow dependency: SIGN2MV runs its ONNX model.
    run([uv(), "pip", "install", "--python", py, "--no-deps", f"basic-pitch=={MANIFEST['basic_pitch']['version']}"])
    run([py, "-c", "import torch, demucs, audio_separator, faster_whisper, soundfile, librosa, yt_dlp, pretty_midi, "
                   "tinysoundfont, basic_pitch.inference; print('engine imports OK', torch.__version__)"])


def step_engine_models(state: dict) -> None:
    py = PATHS.env_python("engine")
    args = [py, ROOT / "installer" / "fetch_models.py"]
    if state.get("sucial_accepted"):
        args.append("--with-sucial")
    run(args)


def step_applio(state: dict) -> None:
    m = MANIFEST["applio"]
    target = PATHS.applio
    archive = PATHS.cache / "downloads" / f"applio-{m['version']}.zip"
    if not (target / "core.py").exists() or state.get("applio_version") != m["version"]:
        download(m["url"], archive)
        extract_zip(archive, target)
        state["applio_version"] = m["version"]
        save_state(state)
        archive.unlink(missing_ok=True)
    py = _venv("applio")
    index = MANIFEST["torch"]["cuda_index"] if state["device"] == "cuda" else MANIFEST["torch"]["cpu_index"]
    log("Installing Applio's requirements (its own PyTorch build); this download is several GB...")
    run([uv(), "pip", "install", "--python", py, "-r", target / "requirements-engine.txt",
         "--extra-index-url", index, "--index-strategy", "unsafe-best-match"])
    log("Downloading Applio's pretrained models (into runtime/applio, not C:)...")
    run([py, "core.py", "prerequisites", "--pretraineds-hifigan", "--models", "--no-exe"], cwd=target)


def step_selfcheck(state: dict) -> None:
    report = {"checks": {}}
    py = PATHS.env_python("engine")
    res = run([py, ROOT / "installer" / "selfcheck.py"], capture=True, check=False)
    try:
        data = json.loads(res.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        data = {"error": (res.stdout + res.stderr)[-1500:]}
    log("Engine self-check: " + json.dumps(data))
    report.update({k: v for k, v in data.items() if k != "checks"})
    report["checks"].update(data.get("checks", {}))
    apy = PATHS.env_python("applio")
    ares = run([apy, "-c", "import torch,sys; print(torch.__version__, torch.cuda.is_available())"],
               capture=True, check=False, cwd=PATHS.applio)
    report["checks"]["applio"] = ares.returncode == 0 and (PATHS.applio / "rvc" / "models" / "predictors" / "rmvpe.pt").exists()
    report["applio_torch"] = ares.stdout.strip()
    state["selfcheck"] = report
    save_state(state)


STEPS = [
    ("ffmpeg", step_ffmpeg, lambda: step_key(MANIFEST["ffmpeg"]["url"], 1)),
    ("deno", step_deno, lambda: step_key(MANIFEST["deno"])),
    ("engine_env", step_engine_env, lambda: step_key(MANIFEST["torch"],
        (ROOT / "installer" / "requirements" / "engine.lock.txt").read_text(encoding="utf-8"))),
    ("engine_models", step_engine_models, lambda: step_key(MANIFEST["models"], 2)),
    ("applio", step_applio, lambda: step_key(MANIFEST["applio"], 1)),
    ("selfcheck", step_selfcheck, lambda: step_key(time.strftime("%Y%m%d%H%M%S"))),
]


def ask_sucial(state: dict, assume: str | None) -> None:
    if "sucial_accepted" in state:
        return
    if assume is not None:
        state["sucial_accepted"] = assume == "yes"
        return
    print()
    print("Optional model: 'Sucial' male/female voice separation (used for duet AI covers).")
    print("Its licence is CC BY-NC-SA 4.0: NON-COMMERCIAL use only.")
    print("Without it you can still use the 'aufr33' male/female model.")
    try:
        ans = input("Download the Sucial model? [y/N]: ").strip().lower()
    except EOFError:
        ans = ""
    state["sucial_accepted"] = ans in ("y", "yes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sucial", choices=["yes", "no"], help="answer the optional-model question")
    parser.add_argument("--only", help="run only this step (for maintenance)")
    parser.add_argument("--redo", action="append", default=[], help="force a step to run again")
    args = parser.parse_args()

    for d in (RT, PATHS.cache / "downloads", PATHS.tmp, PATHS.models, PATHS.logs, PATHS.config):
        d.mkdir(parents=True, exist_ok=True)
    os.environ.update(cache_vars(PATHS))
    ensure_dirs(PATHS)

    state = load_state()
    if "c_free_before" not in state:
        before_file = RT / "c_free_before.txt"
        try:
            state["c_free_before"] = int(before_file.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            state["c_free_before"] = c_drive_free()
    device, gpu = detect_gpu()
    if state.get("device") != device:
        state["device"] = device
        state["steps"].pop("engine_env", None)
        state["steps"].pop("applio", None)
    state["gpu_name"] = gpu
    ask_sucial(state, args.sucial)
    save_state(state)

    banner(f"SIGN2MV installer - folder: {ROOT}")
    log(f"Compute device: {'NVIDIA GPU (' + gpu + ')' if device == 'cuda' else 'CPU only (no NVIDIA GPU found)'}")

    for name, func, keyfn in STEPS:
        if args.only and name != args.only:
            continue
        key = keyfn()
        if state["steps"].get(name) == key and name not in args.redo and name != "selfcheck":
            log(f"[skip] {name} (already done)")
            continue
        banner(f"Step: {name}")
        t0 = time.time()
        try:
            func(state)
        except InstallError as exc:
            log(f"ERROR in step '{name}': {exc}")
            log("Fix the problem (usually the internet connection) and double-click install.bat again;")
            log("finished steps will be skipped.")
            save_state(state)
            return 1
        state["steps"][name] = key
        save_state(state)
        log(f"[done] {name} in {time.time() - t0:.0f} s")

    after = c_drive_free()
    before = state.get("c_free_before")
    delta = (before - after) if (before is not None and after is not None) else None
    sc = state.get("selfcheck", {})
    report = {
        "completed": all(n in state["steps"] for n, _, _ in STEPS),
        "device": "cuda" if sc.get("cuda") else "cpu",
        "gpu_name": sc.get("gpu_name") or state.get("gpu_name"),
        "checks": sc.get("checks", {}),
        "torch": sc.get("torch"),
        "applio_torch": sc.get("applio_torch"),
        "c_drive_delta_bytes": delta,
        "finished_at": time.time(),
        "sucial": bool(state.get("sucial_accepted")),
    }
    (RT / "install_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    banner("Installation finished" if report["completed"] else "Installation incomplete")
    for k, v in report["checks"].items():
        log(f"  {'OK  ' if v else 'FAIL'} {k}")
    if state["device"] == "cuda" and not sc.get("cuda"):
        log("  NOTE: an NVIDIA GPU was found but PyTorch cannot use it. Update the NVIDIA driver")
        log("        (CUDA 12.8 needs a recent driver), then run install.bat again. CPU mode works meanwhile.")
    if delta is not None:
        log(f"  C: drive free space change during install: {delta / 1048576:+.1f} MB used"
            " (other programs may also write to C: at the same time)")
    log("Next: double-click start.bat")
    return 0 if report["completed"] else 1


if __name__ == "__main__":
    sys.exit(main())
