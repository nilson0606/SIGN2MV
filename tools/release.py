"""Publish a GitHub release with SIGN2MV.zip (run from a clean, pushed main; needs git and an authenticated gh).

    python tools/release.py            # release today's version
    python tools/release.py --dry-run  # show what would happen, change nothing

What it does:
1. The release name is today's date in Taiwan, e.g. 2026.11.12; a second release on the same day is 2026.11.12.2.
2. CHANGELOG.md: the "## Unreleased" entries move under "## <name>" (the release notes); "## Unreleased" stays,
   empty. This is committed as "Release <name>", tagged <name> and pushed.
3. SIGN2MV.zip is made with git archive (so app/BUILD.txt carries the code date), with everything inside a
   SIGN2MV folder: extracting it to D:\\ gives D:\\SIGN2MV. It is attached to the release.

The README links to releases/latest/download/SIGN2MV.zip, so the newest release is always the download, and
GitHub counts each release's downloads (`gh release view <name> --json assets`). The home page's "check for
updates" compares the install with the latest release (app/build.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
NOTES_LIMIT = 20000   # longer notes (the first release: everything since 0.1.0) point to CHANGELOG.md instead


def git(*args: str, capture: bool = True) -> str:
    res = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=capture)
    return res.stdout.strip() if capture else ""


def release_name(existing: set[str], today: dt.date) -> str:
    base = today.strftime("%Y.%m.%d")
    if base not in existing:
        return base
    n = 2
    while f"{base}.{n}" in existing:
        n += 1
    return f"{base}.{n}"


def move_unreleased(text: str, name: str) -> tuple[str, str]:
    """Return (new changelog, release notes)."""
    m = re.search(r"^## Unreleased\n(.*?)(?=^## )", text, flags=re.S | re.M)
    if not m or not m.group(1).strip():
        raise SystemExit("Nothing under '## Unreleased' in CHANGELOG.md: nothing to release.")
    notes = m.group(1).strip()
    new = text[:m.start()] + f"## Unreleased\n\n## {name}\n\n{notes}\n\n" + text[m.end():]
    return new, notes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if git("status", "--porcelain"):
        raise SystemExit("The working tree has changes: commit them first.")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise SystemExit("Release from main.")
    git("fetch", "-q", "origin", "--tags")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise SystemExit("main is not the same as origin/main: push (or pull) first.")
    name = release_name(set(git("tag", "-l").split()), dt.datetime.now(ZoneInfo("Asia/Taipei")).date())
    text, notes = move_unreleased(CHANGELOG.read_text(encoding="utf-8"), name)
    if len(notes) > NOTES_LIMIT:
        notes = ("Everything since 0.1.0 is listed in [CHANGELOG.md]"
                 f"(https://github.com/nilson0606/SIGN2MV/blob/{name}/CHANGELOG.md).")
    notes += ("\n\n**Download:** SIGN2MV.zip below. New install: extract it to D:\\ (you get D:\\SIGN2MV) and run "
              "install.bat. Update: see \"Updating\" in the README.")
    print(f"Release {name}\n---\n{notes[:1500]}{'…' if len(notes) > 1500 else ''}\n---")
    if a.dry_run:
        print("Dry run: nothing changed.")
        return
    CHANGELOG.write_text(text, encoding="utf-8")
    git("commit", "-q", "-am", f"Release {name}")
    git("tag", "-a", name, "-m", f"SIGN2MV {name}")
    git("push", "-q", "origin", "main", name, capture=False)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "SIGN2MV.zip"
        notes_path = Path(tmp) / "notes.md"
        git("archive", "--format=zip", "--prefix=SIGN2MV/", "-o", str(zip_path), name)
        notes_path.write_text(notes, encoding="utf-8")
        subprocess.run(["gh", "release", "create", name, str(zip_path), "--repo", "nilson0606/SIGN2MV",
                        "--title", f"SIGN2MV {name}", "--notes-file", str(notes_path), "--verify-tag"],
                       cwd=ROOT, check=True)
    print(f"Published https://github.com/nilson0606/SIGN2MV/releases/tag/{name}")


if __name__ == "__main__":
    sys.exit(main())
