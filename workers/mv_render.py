"""MV workspace: render the 1080p 60 fps MV of a project (queue worker, GPU lane).

Input JSON: {"slug": "<song id>_<name>", "library_root": "...", "brand": {singer, studio, lang}}
Runs app/mvstudio/core.execute_mv_render_pipeline (frames -> transitions ->
NVENC/libx264 encode to a temporary file -> replace the finished MV -> check frames).
Cancelling the job kills this process and its ffmpeg child; the previous MV stays.
"""
from __future__ import annotations

import sys

import protocol
from common import ROOT

sys.path.insert(0, str(ROOT))


def main() -> None:
    data = protocol.read_input()
    from app.mvstudio import core

    def hook(active, task_type, percent, stage, detail=""):
        protocol.progress(percent, stage, detail)

    brand = data.get("brand") or {}
    core.configure(data["library_root"], brand.get("singer", ""), brand.get("studio", ""), brand.get("lang", "zh"),
                   progress=hook)
    try:
        proj = core.load_project_dict(data["slug"])
        for stale in (core.Path(core.project_dir(data["slug"])) / "output").glob("*.rendering.mp4"):
            stale.unlink(missing_ok=True)
        res = core.execute_mv_render_pipeline(proj)
    except core.ProjectNotFound as exc:
        protocol.fail("project_not_found", str(exc))
    except ValueError as exc:
        protocol.fail("audio_missing", str(exc))
    except Exception as exc:  # noqa: BLE001
        protocol.fail("render_failed", str(exc)[-800:])
    protocol.result(res)


if __name__ == "__main__":
    main()
