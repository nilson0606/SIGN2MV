"""MV camera motion (運鏡): an option, off by default; when on, the photos move and the text does not.

The window of every pose stays inside the photo; the transition frames drawn by Python sample the photo at
the same points as ffmpeg's perspective filter, so a photo that moves into a transition does not jump; a
project without the option renders exactly as before.
"""
import io
import json
import os
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageFilter

from app.mvstudio import core, motion
from test_mv_photos import _aligned_project

W, H = 1920, 1080


def textured(seed, size=(W, H)):
    rng = np.random.default_rng(seed)
    a = (rng.random((size[1] // 8, size[0] // 8, 3)) * 255).astype("uint8")
    im = Image.fromarray(a).resize(size, Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(1.5))
    return im


def png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_plan_off_fixed_sequence_random_and_own_choice():
    prints = ["a", "b", None, "c", "d", "e", "f", "g"]
    assert motion.plan({}, prints) == [motion.NONE] * 8                       # off unless asked for
    assert motion.plan({"motion_enabled": False, "motion_mode": "fixed"}, prints) == [motion.NONE] * 8
    fixed = motion.plan({"motion_enabled": True, "motion_mode": "fixed", "motion_style": "pan_lr"}, prints)
    assert [k for k, _ in fixed] == ["pan_lr", "pan_lr", "none", "pan_lr", "pan_lr", "pan_lr", "pan_lr", "pan_lr"]
    assert fixed[0][1] % 2 != fixed[1][1] % 2                                  # the pans take turns in direction
    seq = motion.plan({"motion_enabled": True, "motion_mode": "sequence"}, prints)
    assert [k for k, _ in seq][:2] == ["zoomin", "zoomout"] and seq[2] == motion.NONE and seq[5][0] == "zoomin"
    rnd = {"motion_enabled": True, "motion_mode": "random", "motion_seed": 12345}
    a, b = motion.plan(rnd, prints), motion.plan(dict(rnd), prints)
    assert a == b                                                              # the same seed, the same motion
    kinds = [k for k, _ in a if k != "none"]
    assert all(x != y for x, y in zip(kinds, kinds[1:])) and len(set(kinds)) >= 3
    assert motion.plan(dict(rnd, motion_seed=999), prints) != a
    own = dict(rnd, photo_motion={"b": "zoomout", "c": "none"})
    mine = motion.plan(own, prints)
    assert mine[1][0] == "zoomout" and mine[3] == motion.NONE and mine[0] == a[0]
    # what is saved is cleaned
    p = {"motion_enabled": 1, "motion_mode": "x", "motion_style": "y", "motion_amount": "z", "motion_seed": "7",
         "photo_motion": {"a": "pan_ud", "b": "spin", "c": "none"}}
    motion.normalize(p)
    assert p == {"motion_enabled": True, "motion_mode": "random", "motion_style": "zoomin", "motion_amount": "light",
                 "motion_seed": 7, "photo_motion": {"a": "pan_ud", "c": "none"}}


def test_every_window_stays_inside_the_photo():
    for kind in motion.MOTION_KEYS:
        for var in range(4):
            for amt in motion.MOTION_AMOUNTS.values():
                for p in np.linspace(0, 1, 21):
                    left, top, right, bottom = motion.rect(kind, var, amt, float(p), W, H)
                    assert -1e-6 <= left < right <= W + 1e-6 and -1e-6 <= top < bottom <= H + 1e-6
                    assert abs((right - left) / W - (bottom - top) / H) < 1e-9          # never stretched
                s0, s1 = motion.pose(kind, var, amt, 0)[0], motion.pose(kind, var, amt, 1)[0]
                assert abs(min(s0, s1) - 1 / (1 + amt)) < 1e-9                         # enlarged by the amount


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="no ffmpeg")
def test_python_warp_samples_where_ffmpeg_does(tmp_path):
    """A transition frame (Python) and the frame before it (ffmpeg) see the photo through the same window."""
    im = textured(3)
    src = tmp_path / "src.png"
    im.save(src)
    for r in [(40.3, 22.7, 1868.9, 1073.6), (0, 0, 1828.57, 1028.57), (91.4, 51.4, 1920, 1080)]:
        out = tmp_path / "ff.png"
        flt = (f"format=gbrp,perspective=x0={r[0]}:y0={r[1]}:x1={r[2]}:y1={r[1]}:x2={r[0]}:y2={r[3]}:x3={r[2]}:y3={r[3]}"
               ":interpolation=linear,format=rgb24")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", flt, "-frames:v", "1", str(out)], check=True)
        ff = np.asarray(Image.open(out).convert("RGB"), dtype=np.float32)
        py = np.asarray(motion.warp(im, r), dtype=np.float32)
        d = np.abs(ff - py)[2:-2, 2:-2]
        assert d.mean() < 0.6 and np.percentile(d, 99.9) < 4, (r, d.mean(), np.percentile(d, 99.9))
        # half a pixel off would show: the check is sharp enough to see it
        off = np.asarray(motion.warp(im, (r[0] + 0.5, r[1], r[2] + 0.5, r[3])), dtype=np.float32)
        assert np.abs(ff - off)[2:-2, 2:-2].mean() > 3 * d.mean()


def test_perspective_filter_is_piecewise_and_shallow():
    pieces = [(0, 10, (0, 9, 0, 0, 1920, 1929, 1080, 1080, 0, 9)), (10, 20, None), (20, 30, None), (30, 40, None)]
    f = motion.perspective_filter(pieces, W, H)
    assert f.startswith("perspective=") and "eval=frame" in f and "interpolation=linear" in f
    assert "if(lt(in\\,11)" in f and "in\\,31" not in f          # (frame 10 is in = 11); identical neighbours merged
    # many lines: the expression is a balanced tree, not 200 levels deep
    many = [(i * 10, i * 10 + 10, (i, i + 1, 0, 0, W, W, H, H, i * 10, i * 10 + 9)) for i in range(200)]
    expr = motion.perspective_filter(many, W, H).split(":")[0]
    depth, worst = 0, 0
    for ch in expr:
        depth += ch == "("
        depth -= ch == ")"
        worst = max(worst, depth)
    assert worst < 40



@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="no ffmpeg")
def test_ffmpeg_moves_each_frame_where_python_expects(tmp_path):
    """The ffmpeg in use: a picture listed for one frame is that frame (the concat list's 60 fps), and the
    window of frame f is the one perspective_filter wrote for f (its frame counter starts at 1)."""
    w, h = 64, 36
    pic = textured(5, (w, h))
    pic.save(tmp_path / "p.png")
    Image.new("RGB", (w, h), (0, 0, 255)).save(tmp_path / "m.png")
    rate = core.M_RATE
    lst = tmp_path / "c.txt"
    lst.write_text(f"file 'p.png'\n{rate}duration {30 / 60:.6f}\nfile 'm.png'\n{rate}duration {1 / 60:.6f}\n"
                   f"file 'p.png'\n{rate}duration {30 / 60:.6f}\nfile 'p.png'\n{rate}", encoding="utf-8")
    a = (0.0, 6.0, 0.0, 3.0, 58.0, 64.0, 33.0, 36.0, 0, 29)           # left/top/right/bottom at frames 0 and 29
    b = (6.0, 0.0, 3.0, 0.0, 64.0, 58.0, 36.0, 33.0, 31, 60)
    flt = "format=gbrp,fps=60," + motion.perspective_filter([(0, 30, a), (30, 31, None), (31, 61, b)], w, h) + ",format=rgb24"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", flt, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True, cwd=tmp_path).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32)
    assert len(fr) >= 61           # (the list's last picture, repeated as concat wants, adds a frame at the end)
    assert fr[30][..., 2].min() > 200 and fr[29][..., 2].mean() < 200 and fr[31][..., 2].mean() < 200

    def want(line, f):
        t = (f - line[8]) / (line[9] - line[8])
        r = tuple(line[2 * k] + (line[2 * k + 1] - line[2 * k]) * t for k in range(4))
        return np.asarray(motion.warp(pic, (r[0], r[1], r[2], r[3])), dtype=np.float32)
    for f, line in ((0, a), (15, a), (29, a), (31, b), (45, b), (60, b)):
        best = min(range(-2, 3), key=lambda k: np.abs(fr[f] - want(line, f + k))[1:-1, 1:-1].mean())
        assert best == 0, (f, best)

def _frames(mv, a, b):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(mv), "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out = []
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        out.append(np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32))
    p.wait()
    return out


def test_render_with_motion(client, root, monkeypatch):
    fonts = sorted(__import__("pathlib").Path("/usr/share/fonts/opentype/noto").glob("NotoSansCJK-Regular.ttc"))
    if not fonts:
        pytest.skip("no CJK font in this environment")
    monkeypatch.setenv("SIGN2MV_MV_FONT", str(fonts[0]))
    monkeypatch.setenv("SIGN2MV_FORCE_CPU", "1")
    sid, slug, pdir = _aligned_project(client, root)
    for n in (1, 2, 3):
        up = client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": str(n)},
                         files={"file": (f"{n}.png", png_bytes(textured(n)), "image/png")}).json()
        assert up["status"] == "ok"
    data = client.get(f"/api/mv/project/{slug}").json()
    prints = {s["scene_id"]: s["print"] for s in data["scenes"] if s.get("exists")}
    assert len(set(prints.values())) == 3 and all(prints.values())
    proj = data["project"]

    # off (the default): the render of before, no motion frames
    out = core.execute_mv_render_pipeline(core.load_project_dict(slug))
    assert out["status"] == "ok"
    frames = pdir / "frames"
    assert list(frames.glob("base_*.png")) and not list(frames.glob("mbg_*.png")) and not (frames / "motion_filter.txt").exists()

    # on: pan left/right, medium; scene 3 does not move (its own choice)
    # (cross-fades: a slide or a wipe moves the picture by itself, which would hide a jump of the photo)
    proj.update(motion_enabled=True, motion_mode="fixed", motion_style="pan_lr", motion_amount="medium",
                photo_motion={prints[3]: "none"}, transition_mode="fixed", transition_style="fade")
    saved = client.post("/api/mv/project/save", json=proj).json()
    assert saved["status"] == "ok" and saved["project"]["photo_motion"] == {prints[3]: "none"}
    p = core.load_project_dict(slug)
    out = core.execute_mv_render_pipeline(p)
    assert out["status"] == "ok", out
    mv = out["output_mv"]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mv],
                               capture_output=True, text=True, check=True).stdout)
    assert abs(dur - 24) < 0.3
    assert list(frames.glob("mbg_*.png")) and list(frames.glob("mtrans_*.png")) and (frames / "motion_filter.txt").exists()

    tl = p["timeline"]
    TR = 0.40
    # where each line's hold starts in the video (the old path's rule) against the motion concat (whole frames)
    pos, starts = 0.0, []
    for i, s in enumerate(tl):
        d = max(0.1, s["end"] - s["start"])
        starts.append(pos)
        pos += (max(0.05, d - TR) + TR) if i < len(tl) - 1 else d
    t, got = 0.0, []
    for block in (frames / "concat.txt").read_text(encoding="utf-8").split("file '")[1:]:
        name = block.split("'")[0]
        if "mbg_" in name and "duration" in block:
            got.append(t)
        if "duration" in block:
            t += float(block.split("duration")[1])
    assert len(got) == len(tl) and all(abs(a - b) <= 1 / 60 + 1e-6 for a, b in zip(got, starts))
    assert abs(t - pos) <= 1 / 60 + 1e-6

    # a moving line: every frame of its hold changes, the opaque text does not
    moving = [i for i, s in enumerate(tl) if s.get("scene") in (1, 2) and s["end"] - s["start"] > 1.2]
    i = moving[0]
    a, b = starts[i] + 0.15, starts[i] + max(0.1, tl[i]["end"] - tl[i]["start"]) - TR - 0.15
    fr = _frames(mv, a, b)
    assert len(fr) >= 20
    ov = np.asarray(Image.open(frames / f"mov_{i:03d}.png"))
    text = ov[..., 3] == 255
    photo = np.zeros((H, W), bool)
    photo[260:800, 100:1820] = True
    photo &= ov[..., 3] < 10
    steps = [np.abs(x - y)[photo].mean() for x, y in zip(fr, fr[1:])]
    still = [np.abs(x - y)[text].mean() for x, y in zip(fr, fr[1:])]
    # (the text's own pixels only take a trace of the photo through the shared colour samples of yuv420 and
    # the encoder: under 1/5 of what the photo moves)
    assert min(steps) > 0.05 and max(still) < 0.2 * min(steps), (min(steps), max(still))
    assert np.abs(fr[0] - fr[-1])[photo].mean() > 5 * np.mean(steps)          # it went somewhere

    # into the transition after it: no jump (the change from the last held frame to the first transition
    # frame is like the change between two held frames)
    j = i
    edge = starts[j] + max(0.1, tl[j]["end"] - tl[j]["start"]) - TR
    fr2 = _frames(mv, edge - 6 / 60, edge + 3 / 60)
    d2 = [np.abs(x - y)[photo].mean() for x, y in zip(fr2, fr2[1:])]
    assert max(d2) < 6 * np.median(steps) + 1.0, (d2, np.median(steps))

    # a line on scene 3 (its own choice: no motion) holds still
    still_lines = [k for k, s in enumerate(tl) if s.get("scene") == 3 and s["end"] - s["start"] > 1.2]
    if still_lines:
        k = still_lines[0]
        fr3 = _frames(mv, starts[k] + 0.15, starts[k] + 0.6)
        assert max(np.abs(x - y)[photo].mean() for x, y in zip(fr3, fr3[1:])) < 0.3

    # switching it off again uses the old frames (their signatures were kept) and renders as before
    proj["motion_enabled"] = False
    client.post("/api/mv/project/save", json=proj)
    before = {f.name: f.stat().st_mtime_ns for f in frames.glob("base_*.png")}
    out = core.execute_mv_render_pipeline(core.load_project_dict(slug))
    assert out["status"] == "ok"
    assert {f.name: f.stat().st_mtime_ns for f in frames.glob("base_*.png")} == before
