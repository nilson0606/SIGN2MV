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
    prints = ["a", "b", None, "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    n = len(prints)
    assert len(motion.MOTION_KEYS) == 9
    assert motion.plan({}, prints) == [motion.NONE] * n                       # off unless asked for
    assert motion.plan({"motion_enabled": False, "motion_mode": "fixed"}, prints) == [motion.NONE] * n
    fixed = motion.plan({"motion_enabled": True, "motion_mode": "fixed", "motion_style": "pan_lr"}, prints)
    assert [k for k, _ in fixed] == ["none" if x is None else "pan_lr" for x in prints]
    assert fixed[0][1] % 2 != fixed[1][1] % 2                                  # the pans take turns in direction
    seq = motion.plan({"motion_enabled": True, "motion_mode": "sequence"}, prints)
    assert [k for k, _ in seq][:2] == ["zoomin", "zoomout"] and seq[2] == motion.NONE
    assert [k for k, _ in seq][3:9] == motion.MOTION_KEYS[3:9] and seq[9][0] == "zoomin"   # all nine in turn
    rnd = {"motion_enabled": True, "motion_mode": "random", "motion_seed": 12345}
    a, b = motion.plan(rnd, prints), motion.plan(dict(rnd), prints)
    assert a == b                                                              # the same seed, the same motion
    kinds = [k for k, _ in a if k != "none"]
    assert all(x != y for x, y in zip(kinds, kinds[1:])) and len(set(kinds)) >= 5
    assert motion.plan(dict(rnd, motion_seed=999), prints) != a
    own = dict(rnd, photo_motion={"b": "breathe", "c": "none"})
    mine = motion.plan(own, prints)
    assert mine[1][0] == "breathe" and mine[3] == motion.NONE and mine[0] == a[0]
    # what is saved is cleaned
    p = {"motion_enabled": 1, "motion_ease": 0, "motion_mode": "x", "motion_style": "y", "motion_amount": "z",
         "motion_seed": "7", "photo_motion": {"a": "pan_ud", "b": "spin", "c": "none", "d": "rotate"}}
    motion.normalize(p)
    assert p == {"motion_enabled": True, "motion_ease": False, "motion_mode": "random", "motion_style": "zoomin",
                 "motion_amount": "light", "motion_seed": 7, "photo_motion": {"a": "pan_ud", "c": "none", "d": "rotate"}}


def _shape(c):
    """width and height shares, the angle between the edges and the turn of a window from corners()."""
    x0, y0, x1, y1, x2, y2, x3, y3 = c
    top = np.hypot(x1 - x0, y1 - y0) / W
    left = np.hypot(x2 - x0, y2 - y0) / H
    dot = (x1 - x0) * (x2 - x0) + (y1 - y0) * (y2 - y0)
    return top, left, dot, np.arctan2(y1 - y0, x1 - x0), (x3 - (x1 + x2 - x0), y3 - (y1 + y2 - y0))


def test_every_window_stays_inside_the_photo():
    for kind in motion.MOTION_KEYS:
        for var in range(4):
            for amt in motion.MOTION_AMOUNTS.values():
                for eased in (False, True):
                    sizes = []
                    for p in np.linspace(0, 1, 41):
                        c = motion.corners(kind, var, amt, float(p), eased, W, H)
                        xs, ys = c[0::2], c[1::2]
                        assert min(xs) >= -1e-6 and max(xs) <= W + 1e-6 and min(ys) >= -1e-6 and max(ys) <= H + 1e-6, (kind, var, amt, p)
                        top, left, dot, turn, off = _shape(c)
                        assert abs(top - left) < 1e-9 and abs(dot) < 1e-6 and max(map(abs, off)) < 1e-6   # never stretched
                        if kind != "rotate":
                            assert abs(turn) < 1e-12
                        sizes.append(top)
                    assert abs(min(sizes) - 1 / (1 + amt)) < 1e-9, (kind, amt)                        # enlarged by the amount
                    c0 = motion.corners(kind, var, amt, 0.0, eased, W, H)
                    c1 = motion.corners(kind, var, amt, 1.0, eased, W, H)
                    if kind == "breathe":
                        assert max(abs(a - b) for a, b in zip(c0, motion.full(W, H))) < 1e-6
                        assert max(abs(a - b) for a, b in zip(c1, motion.full(W, H))) < 1e-6
                    if kind == "rotate":
                        assert abs(abs(_shape(c1)[3]) - motion.turn_max(amt)) < 1e-9
    # the turn follows the amount: about 1.4, 2.6 and 4.8 degrees
    assert [round(np.degrees(motion.turn_max(a)), 1) for a in (0.05, 0.10, 0.20)] == [1.4, 2.6, 4.8]
    # easing: the same ends, slower at both ends, faster in the middle
    a = [motion.corners("pan_lr", 0, 0.1, p, False, W, H)[0] for p in (0, 0.05, 0.5, 1)]
    e = [motion.corners("pan_lr", 0, 0.1, p, True, W, H)[0] for p in (0, 0.05, 0.5, 1)]
    assert abs(a[0] - e[0]) < 1e-9 and abs(a[3] - e[3]) < 1e-9 and abs(a[2] - e[2]) < 1e-9 and e[1] - e[0] < 0.2 * (a[1] - a[0])


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="no ffmpeg")
def test_python_warp_samples_where_ffmpeg_does(tmp_path):
    """A transition frame (Python) and the frame before it (ffmpeg) see the photo through the same window,
    turned or not."""
    im = textured(3)
    src = tmp_path / "src.png"
    im.save(src)
    windows = [(40.3, 22.7, 1868.9, 22.7, 40.3, 1073.6, 1868.9, 1073.6), motion.corners("zoomin", 0, 0.05, 1.0, False, W, H),
               motion.corners("pan_lr", 1, 0.05, 1.0, False, W, H), motion.corners("rotate", 0, 0.2, 0.7, False, W, H),
               motion.corners("rotate", 1, 0.1, 0.4, True, W, H), motion.corners("pan_diag", 2, 0.2, 0.3, False, W, H)]
    for c in windows:
        out = tmp_path / "ff.png"
        pts = ":".join(f"{n}={v}" for n, v in zip(("x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3"), c))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"format=gbrp,perspective={pts}:interpolation=linear,format=rgb24",
                        "-frames:v", "1", str(out)], check=True)
        ff = np.asarray(Image.open(out).convert("RGB"), dtype=np.float32)
        py = np.asarray(motion.warp(im, c), dtype=np.float32)
        d = np.abs(ff - py)[2:-2, 2:-2]
        assert d.mean() < 0.6 and np.percentile(d, 99.9) < 4, (c, d.mean(), np.percentile(d, 99.9))
        # half a pixel off would show: the check is sharp enough to see it
        moved = tuple(v + (0.5 if k % 2 == 0 else 0) for k, v in enumerate(c))
        off = np.asarray(motion.warp(im, moved), dtype=np.float32)
        assert np.abs(ff - off)[2:-2, 2:-2].mean() > 3 * d.mean()


def test_photo_chain_has_one_short_filter_per_moving_piece():
    """perspective reads its expressions again on every frame: each moving piece gets its own short one, still
    frames side by side share one branch without it."""
    pieces = [(0, 10, ("pan_lr", 0, 0, 9)), (10, 20, None), (20, 30, None), (30, 40, ("rotate", 1, 20, 19))]
    f = motion.photo_chain("[0:v]fps=60", pieces, 0.1, True, W, H, "[o]")
    assert f.count("perspective=") == 2 and "concat=n=3:v=1:a=0[o]" in f and "split=3" in f
    assert "trim=start_frame=10:end_frame=30" in f                       # the two still pieces: one branch
    assert "(in+-1)" in f and "(in+9)" in f                              # frame f0 + in - 1, counted from the run's start
    # a long song: the expressions stay short whatever its length
    many = [(i * 10, i * 10 + 10, (motion.MOTION_KEYS[i % 9], i, i * 10, 9) if i % 2 == 0 else None) for i in range(400)]
    flt = motion.photo_chain("[0:v]fps=60", many, 0.2, True, W, H, "[o]")
    assert flt.count("perspective=") == 200
    assert max(len(x) for x in flt.split("perspective=")[1:]) < 6000
    one = motion.photo_chain("[0:v]fps=60", [(0, 50, ("zoomin", 0, 0, 49))], 0.1, False, W, H, "[o]")
    assert "split" not in one and one.endswith("[o]") and one.count("perspective=") == 1


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="no ffmpeg")
def test_ffmpeg_moves_each_frame_where_python_expects(tmp_path):
    """The ffmpeg in use: a picture listed for one frame is that frame (the concat list's 60 fps), and the
    window of frame f is the one photo_chain wrote for f (split, trim, each piece's perspective with its own
    frame counter starting at 1, concat): turned, eased and straight."""
    w, h = 64, 36
    pic = textured(5, (w, h))
    pic.save(tmp_path / "p.png")
    Image.new("RGB", (w, h), (0, 0, 255)).save(tmp_path / "m.png")
    rate = core.M_RATE
    lst = tmp_path / "c.txt"
    lst.write_text(f"file 'p.png'\n{rate}duration {30 / 60:.6f}\nfile 'm.png'\n{rate}duration {1 / 60:.6f}\n"
                   f"file 'p.png'\n{rate}duration {30 / 60:.6f}\nfile 'p.png'\n{rate}", encoding="utf-8")
    for amt, eased, a, b in ((0.2, False, ("pan_lr", 0, 0, 29), ("zoomin", 0, 31, 29)),
                             (0.2, True, ("rotate", 1, 0, 29), ("breathe", 0, 25, 40)),
                             (0.1, True, ("pan_diag", 3, 0, 29), ("zoomout_pan", 2, 31, 29))):
        flt = motion.photo_chain("[0:v]format=gbrp,fps=60", [(0, 30, a), (30, 31, None), (31, 61, b), (61, 70, None)],
                                 amt, eased, w, h, "[m]") + ";[m]format=rgb24[o]"
        raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-filter_complex", flt,
                              "-map", "[o]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True, cwd=tmp_path).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32)
        assert len(fr) >= 61           # (the list's last picture, repeated as concat wants, adds a frame at the end)
        assert fr[30][..., 2].min() > 200 and fr[29][..., 2].mean() < 200 and fr[31][..., 2].mean() < 200

        def want(spec, f):
            kind, var, r0, den = spec
            return np.asarray(motion.warp(pic, motion.corners(kind, var, amt, (f - r0) / den, eased, w, h)), dtype=np.float32)
        for f, spec in ((0, a), (8, a), (15, a), (29, a), (31, b), (45, b), (60, b)):
            errs = {k: np.abs(fr[f] - want(spec, f + k))[1:-1, 1:-1].mean() for k in range(-2, 3)}
            # frame f matches its own window best (where an eased motion barely moves, neighbours tie)
            assert errs[0] <= min(errs.values()) + 0.05, (amt, eased, spec, f, errs)
            assert errs[0] < 2.0, (amt, eased, spec, f, errs)

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

    # on: push in while turning, strong; scene 3 does not move (its own choice)
    # (cross-fades: a slide or a wipe moves the picture by itself, which would hide a jump of the photo)
    proj.update(motion_enabled=True, motion_mode="fixed", motion_style="rotate", motion_amount="strong",
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


def test_render_without_motion_shows_every_transition_frame(client, root, monkeypatch):
    """[2026-11-28] The render without motion lists its pictures at 60 fps too: before, the concat input rounded
    every start to 1/25 s, so of the 16 frames drawn for a 0.4 s transition only about 10 reached the video,
    and each line changed up to 20 ms off its time."""
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
    client.post("/api/mv/project/save", json=proj)
    p = core.load_project_dict(slug)
    out = core.execute_mv_render_pipeline(p)
    assert out["status"] == "ok"
    frames = pdir / "frames"
    assert not list(frames.glob("mbg_*.png"))                                  # the path without motion
    lst = (frames / "concat.txt").read_text(encoding="utf-8")
    assert lst.count("file '") == lst.count(core.M_RATE)                       # every picture at 60 fps
    # a transition between two photos: every one of its 16 drawn frames is in the video, in order
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
    fr = _frames(out["output_mv"], edge - 2 / 60, edge + TR + 2 / 60)
    band = (slice(260, 800), slice(100, 1820))
    steps = [np.abs(x[band] - y[band]).mean() for x, y in zip(fr, fr[1:])]
    changes = [k for k, d in enumerate(steps) if d > 1.0]
    assert len(changes) >= 16, (len(changes), [round(x, 1) for x in steps])
    # and it starts on its frame (the frame after the last held one), not up to 20 ms off
    assert abs(changes[0] - 1) <= 1, changes[:3]


def test_encoding_shows_its_progress(client, root, monkeypatch):
    """[2026-11-28] The encoding step reports how far it is: the bar goes from 70 towards 91 % and the detail line
    says how much is encoded, the speed and the time left (it stood still at 70 % for minutes)."""
    import re
    fonts = sorted(__import__("pathlib").Path("/usr/share/fonts/opentype/noto").glob("NotoSansCJK-Regular.ttc"))
    if not fonts:
        pytest.skip("no CJK font in this environment")
    monkeypatch.setenv("SIGN2MV_MV_FONT", str(fonts[0]))
    monkeypatch.setenv("SIGN2MV_FORCE_CPU", "1")
    sid, slug, pdir = _aligned_project(client, root)
    client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": "1"},
                files={"file": ("1.png", png_bytes(textured(1)), "image/png")})
    seen = []
    monkeypatch.setattr(core, "PROGRESS_HOOK", lambda active, task, pct, stage, detail="": seen.append((pct, stage, detail)))
    out = core.execute_mv_render_pipeline(core.load_project_dict(slug))
    assert out["status"] == "ok"
    enc = [(p, d) for p, s, d in seen if "[階段 3/4]" in s and d.startswith("已編碼")]
    assert len(enc) >= 2, [x for x in seen if "[階段 3/4]" in x[1]]
    pcts = [p for p, _ in enc]
    assert pcts == sorted(pcts) and 70 <= pcts[0] and pcts[-1] <= 91 and pcts[-1] >= 85
    assert all(re.fullmatch(r"已編碼 \d+:\d\d／0:24（\d+%）( · 速度 \d+\.\d 倍 · 約再 (\d+ 分 )?\d+ 秒)?", d) for _, d in enc), enc
    assert enc[-1][1].startswith("已編碼 0:24／0:24（100%）")
    # one stage line through the step (the job log writes a line per stage, not per update)
    assert len({s for p, s, d in seen if "[階段 3/4]" in s}) == 1


def test_stopping_during_encoding_still_stops(client, root, monkeypatch):
    """Reading ffmpeg's progress does not keep a stopped render going: killing the encoder (what a stop does)
    ends the step at once."""
    import threading as th
    import time as tm
    fonts = sorted(__import__("pathlib").Path("/usr/share/fonts/opentype/noto").glob("NotoSansCJK-Regular.ttc"))
    if not fonts:
        pytest.skip("no CJK font in this environment")
    monkeypatch.setenv("SIGN2MV_MV_FONT", str(fonts[0]))
    monkeypatch.setenv("SIGN2MV_FORCE_CPU", "1")
    sid, slug, pdir = _aligned_project(client, root)
    client.post("/api/mv/upload_scene", data={"slug": slug, "scene_id": "1"},
                files={"file": ("1.png", png_bytes(textured(1)), "image/png")})
    started = th.Event()

    def hook(active, task, pct, stage, detail=""):
        if "[階段 3/4]" in stage and str(detail).startswith("已編碼"):
            started.set()
    monkeypatch.setattr(core, "PROGRESS_HOOK", hook)
    res = {}

    def run():
        try:
            res["out"] = core.execute_mv_render_pipeline(core.load_project_dict(slug))
        except Exception as exc:  # noqa: BLE001
            res["err"] = exc
    t = th.Thread(target=run)
    t.start()
    assert started.wait(120)
    t0 = tm.time()
    core.CANCEL_REQUESTED = True
    core.ACTIVE_RENDER_PROC.kill()
    t.join(30)
    assert not t.is_alive() and tm.time() - t0 < 10
    assert "err" in res and "out" not in res
    core.CANCEL_REQUESTED = False
