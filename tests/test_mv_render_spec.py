"""MV output size and frame rate (2026-11-28): 1080p or 720p, 60 or 30 fps, saved in the project, 1080p 60 fps
unless it says otherwise. The pictures are always made at 1920x1080; 720p is scaled down just before encoding;
30 fps runs the whole render at 30 (transition frames, camera motion, every list)."""
import json
import subprocess
import time

import numpy as np
import pytest

from app.mvstudio import core
from test_mv_motion import png_bytes, textured
from test_mv_photos import _aligned_project


def test_spec_defaults_and_cleaning(client, root):
    assert core.render_spec({}) == (1080, 60)
    assert core.render_spec({"render_height": "720", "render_fps": "30"}) == (720, 30)
    assert core.render_spec({"render_height": 999, "render_fps": "x"}) == (1080, 60)
    assert core.render_label({"render_height": 720}) == "720p 60fps"
    sid, slug, pdir = _aligned_project(client, root)
    proj = client.get(f"/api/mv/project/{slug}").json()["project"]
    assert "render_height" not in proj                                       # an old project: nothing added
    client.post("/api/mv/project/save", json=dict(proj, render_height="720", render_fps=25))
    stored = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    assert stored["render_height"] == 720 and stored["render_fps"] == 60


def test_bit_rate_and_transition_frames_follow_the_spec():
    nv = ["-c:v", "h264_nvenc", "-preset", "p5", "-b:v", "8M"]
    amf = ["-c:v", "h264_amf", "-quality", "quality", "-rc", "vbr_peak", "-b:v", "8M", "-maxrate", "12M"]
    assert core.encoder_args(nv, 1080, 60) == nv
    assert core.encoder_args(nv, 1080, 30)[-1] == "6M" and core.encoder_args(nv, 720, 60)[-1] == "5M"
    assert core.encoder_args(amf, 720, 30)[-3:] == ["4M", "-maxrate", "6M"]
    assert core.transition_steps(0.4, 60) == 16 and core.transition_steps(0.4, 30) == 12
    assert core.transition_steps(0.4) == 16


def test_video_filter_per_spec():
    assert core.build_video_filter(None) is None                             # 1080p 60, nothing to add: as before
    f = core.build_video_filter(None, out_h=720)
    assert f == "[0:v]format=yuv420p,fps=60[vbig];[vbig]scale=1280:720:flags=lanczos[vout]"
    g = core.build_video_filter([(1.0, 2.0)], karaoke=True, fps=30, out_h=720)
    assert "fps=30[v0]" in g and "rate=30:" in g and g.endswith("[vbig]scale=1280:720:flags=lanczos[vout]")
    assert g.count("[vout]") == 1
    h = core.build_video_filter([(1.0, 2.0)], fps=30)
    assert h.endswith("[vout]") and "lanczos" not in h and "[vbig]" not in h and "rate=30:" in h


def _probe(mv):
    out = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                                     "stream=width,height,r_frame_rate,nb_read_frames:format=duration", "-of", "json", str(mv)],
                                    capture_output=True, text=True, check=True).stdout)
    s = out["streams"][0]
    return s["width"], s["height"], s["r_frame_rate"], int(s["nb_read_frames"]), float(out["format"]["duration"])


def _frames(mv, a, b, w, h):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(mv), "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out = []
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        out.append(np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32))
    p.wait()
    return out


def test_render_in_each_size_and_rate(client, root, monkeypatch):
    """The four choices on one project: the size and rate asked for, the whole length, every frame there, the
    lists at the render's rate, and at 30 fps each of the 12 transition pictures is one frame of the video."""
    fonts = sorted(__import__("pathlib").Path("/usr/share/fonts/opentype/noto").glob("NotoSansCJK-Regular.ttc"))
    if not fonts:
        pytest.skip("no CJK font in this environment")
    monkeypatch.setenv("SIGN2MV_MV_FONT", str(fonts[0]))
    monkeypatch.setenv("SIGN2MV_FORCE_CPU", "1")
    sid, slug, pdir = _aligned_project(client, root)
    for n in (1, 2, 3):
        client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": str(n)},
                    files={"file": (f"{n}.png", png_bytes(textured(n)), "image/png")})
    proj = client.get(f"/api/mv/project/{slug}").json()["project"]
    proj.update(transition_mode="fixed", transition_style="slideleft")
    frames = pdir / "frames"
    took = {}
    for h, fps in ((1080, 60), (1080, 30), (720, 60), (720, 30)):
        client.post("/api/mv/project/save", json=dict(proj, render_height=h, render_fps=fps))
        p = core.load_project_dict(slug)
        stages = []
        monkeypatch.setattr(core, "update_progress", lambda active, task, pct, stage, detail="": stages.append(stage))
        t0 = time.time()
        out = core.execute_mv_render_pipeline(p)
        took[(h, fps)] = round(time.time() - t0, 1)
        assert out["status"] == "ok" and out["spec"] == f"{h}p {fps}fps"
        assert any(f"{h}p {fps}fps" in s for s in stages if "階段 3/4" in s) and any(f"{h}p {fps}fps MV 合成渲染" in s for s in stages)
        w_, h_, rate, n, dur = _probe(out["output_mv"])
        assert (w_, h_, rate) == (h * 16 // 9, h, f"{fps}/1")
        assert abs(dur - 24) < 0.3 and abs(n - dur * fps) <= 2, (n, dur)
        lst = (frames / "concat.txt").read_text(encoding="utf-8")
        assert lst.count("file '") == lst.count(f"option framerate {fps}\n")
        trans = [x for x in lst.split("file '")[1:] if "trans_" in x]
        assert trans and len(trans) % (16 if fps == 60 else 12) == 0
        if fps == 30:
            # a transition between two photos: each of its 12 pictures is a frame of its own
            tl = p["timeline"]
            TR = 0.40
            pos, starts = 0.0, []
            for i, s in enumerate(tl):
                d = max(0.1, s["end"] - s["start"])
                starts.append(pos)
                pos += (max(0.05, d - TR) + TR) if i < len(tl) - 1 else d
            i = next(k for k in range(len(tl) - 1) if tl[k].get("scene") in (1, 2) and tl[k + 1].get("scene") in (2, 3)
                     and tl[k].get("scene") != tl[k + 1].get("scene"))
            edge = starts[i + 1] - TR
            fr = _frames(out["output_mv"], edge - 2 / 30, edge + TR + 2 / 30, w_, h_)
            band = (slice(h_ * 260 // 1080, h_ * 800 // 1080), slice(w_ * 100 // 1920, w_ * 1820 // 1920))
            steps = [np.abs(x[band] - y[band]).mean() for x, y in zip(fr, fr[1:])]
            changes = [k for k, d in enumerate(steps) if d > 1.0]
            assert len(changes) >= 12, (len(changes), [round(x, 1) for x in steps])
    print("render seconds (CPU, 24 s song):", took)


def test_render_with_motion_at_720p_30(client, root, monkeypatch):
    """Camera motion at 30 fps: its pieces start on whole frames at 30 fps and the filter runs at 30."""
    fonts = sorted(__import__("pathlib").Path("/usr/share/fonts/opentype/noto").glob("NotoSansCJK-Regular.ttc"))
    if not fonts:
        pytest.skip("no CJK font in this environment")
    monkeypatch.setenv("SIGN2MV_MV_FONT", str(fonts[0]))
    monkeypatch.setenv("SIGN2MV_FORCE_CPU", "1")
    sid, slug, pdir = _aligned_project(client, root)
    for n in (1, 2, 3):
        client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": str(n)},
                    files={"file": (f"{n}.png", png_bytes(textured(n)), "image/png")})
    proj = client.get(f"/api/mv/project/{slug}").json()["project"]
    proj.update(motion_enabled=True, motion_mode="fixed", motion_style="rotate", motion_amount="strong", motion_ease=True,
                render_height=720, render_fps=30)
    client.post("/api/mv/project/save", json=proj)
    out = core.execute_mv_render_pipeline(core.load_project_dict(slug))
    assert out["status"] == "ok"
    frames = pdir / "frames"
    flt = (frames / "motion_filter.txt").read_text(encoding="utf-8")
    assert "fps=30" in flt and "fps=60" not in flt and flt.endswith("scale=1280:720:flags=lanczos[vout]")
    w_, h_, rate, n, dur = _probe(out["output_mv"])
    assert (w_, h_, rate) == (1280, 720, "30/1") and abs(dur - 24) < 0.3 and abs(n - dur * 30) <= 2
    t = 0.0
    for block in (frames / "concat.txt").read_text(encoding="utf-8").split("file '")[1:]:
        assert "option framerate 30\n" in block
        if "duration" in block:
            t += float(block.split("duration")[1])
            assert abs(t * 30 - round(t * 30)) < 0.02                              # every piece ends on a frame
    # the photo moves from frame to frame
    i = next(k for k, s in enumerate(core.load_project_dict(slug)["timeline"]) if s.get("scene") in (1, 2) and s["end"] - s["start"] > 1.2)
    tl = core.load_project_dict(slug)["timeline"]
    pos = 0.0
    for k in range(i):
        pos += max(0.05, max(0.1, tl[k]["end"] - tl[k]["start"]) - 0.4) + 0.4
    fr = _frames(out["output_mv"], pos + 0.1, pos + 0.6, 1280, 720)
    band = (slice(173, 533), slice(67, 1213))
    assert len(fr) >= 10 and min(np.abs(x[band] - y[band]).mean() for x, y in zip(fr, fr[1:])) > 0.05
