"""[SIGN2MV 2026-11-27] Camera motion (運鏡) on the photos of a full MV.

Asked for by the user: an option, off by default (old and new projects alike); when it is on, the photos move
slowly while the title, the subtitles, the golden karaoke strip and the spectrum stay where they are.

* A "run" is one photo on screen without a photo transition in between: consecutive lines that use the same
  photo are one run (their subtitles change, the photo does not). The motion of a run goes from the first
  frame the photo is seen (the start of the transition that brings it in) to the last one (the end of the
  transition that takes it away), at an even speed: a photo that stays longer moves more slowly.
* Five kinds: push in, pull out, pan left/right, pan up/down, push in while drifting to a corner. The project
  chooses them like the transitions (one kind for every photo / the five in turn / random with a seed); a
  photo can have its own kind, or none, kept under the photo's fingerprint so the choice follows the photo
  when it is moved and is forgotten when it is replaced.
* How far: light (the picture enlarged by 5 %), medium (10 %), strong (20 %).

The picture of a pose is the part of the 1920x1080 photo inside a window (same aspect ratio) stretched to
the frame. In the encoder the window is moved by ffmpeg's perspective filter (sub-pixel, linear: its own
zoompan filter only moves by whole pixels and stutters at these speeds); the transition frames drawn by
Python use warp(), which samples the photo at exactly the same points, so the two meet without a jump.
The MV page's live preview (web/mv/index.html, motionPlan/motionPose) uses the same definitions: change
them together.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

MOTION_STYLES = [("zoomin", "推近"), ("zoomout", "拉遠"), ("pan_lr", "左右平移"), ("pan_ud", "上下平移"),
                 ("zoompan", "推近加平移")]
MOTION_KEYS = [k for k, _ in MOTION_STYLES]
MOTION_MODES = ("fixed", "sequence", "random")
MOTION_AMOUNTS = {"light": 0.05, "medium": 0.10, "strong": 0.20}
PHOTO_CHOICES = tuple(MOTION_KEYS) + ("none",)     # what a photo may have of its own ("follow" = not stored)
NONE = ("none", 0)
# where "push in while drifting" ends: right/left, up/down (the vertical drift is smaller)
_CORNERS = ((1, -1), (-1, -1), (1, 1), (-1, 1))


def _mix32(x: int) -> int:
    x &= 0xFFFFFFFF
    x = ((x ^ (x >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    x = ((x ^ (x >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    return (x ^ (x >> 16)) & 0xFFFFFFFF


def enabled(proj: Dict[str, Any]) -> bool:
    return bool(proj.get("motion_enabled"))


def amount(proj: Dict[str, Any]) -> float:
    return MOTION_AMOUNTS.get(str(proj.get("motion_amount") or "light"), MOTION_AMOUNTS["light"])


def normalize(proj: Dict[str, Any]) -> None:
    """Clean the motion fields of a project before it is saved (only the fields that are there)."""
    if "motion_enabled" in proj:
        proj["motion_enabled"] = bool(proj["motion_enabled"])
    if proj.get("motion_mode") is not None and proj["motion_mode"] not in MOTION_MODES:
        proj["motion_mode"] = "random"
    if proj.get("motion_style") is not None and proj["motion_style"] not in MOTION_KEYS:
        proj["motion_style"] = "zoomin"
    if proj.get("motion_amount") is not None and proj["motion_amount"] not in MOTION_AMOUNTS:
        proj["motion_amount"] = "light"
    if proj.get("motion_seed") is not None:
        try:
            proj["motion_seed"] = int(proj["motion_seed"]) & 0x7FFFFFFF
        except (TypeError, ValueError):
            proj["motion_seed"] = 1
    if "photo_motion" in proj:
        pm = proj["photo_motion"] if isinstance(proj["photo_motion"], dict) else {}
        proj["photo_motion"] = {str(k): v for k, v in pm.items() if v in PHOTO_CHOICES}


def plan(proj: Dict[str, Any], prints: Sequence[Optional[str]]) -> List[Tuple[str, int]]:
    """(kind, variant) of every run in order; prints[k] is the fingerprint of run k's photo (None: no photo,
    which never moves). The variant picks the direction of a pan or the corner of a drift. Off: all none."""
    if not enabled(proj):
        return [NONE for _ in prints]
    mode = proj.get("motion_mode") if proj.get("motion_mode") in MOTION_MODES else "random"
    style = proj.get("motion_style") if proj.get("motion_style") in MOTION_KEYS else "zoomin"
    seed = int(proj.get("motion_seed") or 1) & 0xFFFFFFFF
    own = proj.get("photo_motion") if isinstance(proj.get("photo_motion"), dict) else {}
    n = len(MOTION_KEYS)
    out: List[Tuple[str, int]] = []
    prev = -1
    for k, pr in enumerate(prints):
        if not pr:
            out.append(NONE)
            continue
        mine = own.get(pr)
        if mine == "none":
            out.append(NONE)
            continue
        if mine in MOTION_KEYS:
            out.append((mine, k))
            continue
        if mode == "sequence":
            out.append((MOTION_KEYS[k % n], k // n))
        elif mode == "random":
            idx = _mix32(seed * 0x9E3779B1 + k * 0x85EBCA77 + 7) % n
            if idx == prev:
                idx = (idx + 1) % n
            prev = idx
            out.append((MOTION_KEYS[idx], _mix32(seed * 0x85EBCA77 + k * 0x9E3779B1 + 11) & 3))
        else:
            out.append((style, k))
    return out


def pose(kind: str, variant: int, amt: float, p: float) -> Tuple[float, float, float]:
    """The window at p (0..1 through the run): its size s (share of the photo's width and height) and its
    centre (cx, cy) as shares of the photo. Every value is linear in p."""
    p = min(1.0, max(0.0, p))
    f = 1.0 / (1.0 + amt)
    if kind == "zoomin":
        return 1 + (f - 1) * p, 0.5, 0.5
    if kind == "zoomout":
        return f + (1 - f) * p, 0.5, 0.5
    if kind in ("pan_lr", "pan_ud"):
        q = p if variant % 2 == 0 else 1 - p
        c = f / 2 + (1 - f) * q
        return (f, c, 0.5) if kind == "pan_lr" else (f, 0.5, c)
    if kind == "zoompan":
        s = 1 + (f - 1) * p
        dx, dy = _CORNERS[variant % 4]
        return s, 0.5 + 0.5 * dx * (1 - s), 0.5 + 0.3 * dy * (1 - s)
    return 1.0, 0.5, 0.5


def rect(kind: str, variant: int, amt: float, p: float, w: int, h: int) -> Tuple[float, float, float, float]:
    """The window at p in pixels: left, top, right, bottom (the full frame is 0, 0, w, h)."""
    s, cx, cy = pose(kind, variant, amt, p)
    return (cx - s / 2) * w, (cy - s / 2) * h, (cx + s / 2) * w, (cy + s / 2) * h


def warp(img: Image.Image, r: Tuple[float, float, float, float]) -> Image.Image:
    """The photo seen through window r, the size of the photo. Output pixel x samples the photo at
    left + x * (right - left) / width (pixel indices), as ffmpeg's perspective filter does."""
    w, h = img.size
    left, top, right, bottom = r
    if abs(left) < 1e-6 and abs(top) < 1e-6 and abs(right - w) < 1e-6 and abs(bottom - h) < 1e-6:
        return img
    a, e = (right - left) / w, (bottom - top) / h
    # PIL samples at a*(x+0.5)+c in pixel-centre coordinates, i.e. at index a*x + a/2 + c - 0.5
    return img.transform((w, h), Image.Transform.AFFINE, (a, 0, left - a / 2 + 0.5, 0, e, top - e / 2 + 0.5),
                         resample=Image.Resampling.BILINEAR)


# ---- the encoder side --------------------------------------------------------------------------------------

def _num(v: float) -> str:
    return f"{v:.9f}".rstrip("0").rstrip(".") if abs(v) >= 1e-12 else "0"


def perspective_filter(pieces: Sequence[Tuple[int, int, Optional[Tuple[float, ...]]]], w: int, h: int) -> str:
    """ffmpeg's perspective filter for the photo stream. pieces: (first frame, end frame, line) in order,
    covering the video; line = (l0, l1, t0, t1, r0, r1, b0, b1, f0, f1): the window's left/top/right/bottom at
    frames f0 and f1 (linear in between), or None for frames shown as they are (the transition frames,
    already drawn, and the photos that do not move). The pieces are found by halving (if/lt on the frame
    number), so the expressions stay shallow however long the song is.
    The filter's frame counter "in" is 1 on the first frame (it counts the frames taken in, this one
    included), so frame f is in = f + 1 (checked by tests/test_mv_motion.py with the ffmpeg in use)."""
    def piece_value(line: Optional[Tuple[float, ...]], which: int, full: float) -> str:
        if line is None:
            return _num(full)
        v0, v1, f0, f1 = line[2 * which], line[2 * which + 1], line[8], line[9]
        if f1 <= f0 or abs(v1 - v0) < 1e-9:
            return _num(v0)
        slope = (v1 - v0) / (f1 - f0)
        return f"({_num(v0 - slope * (f0 + 1))}+{_num(slope)}*in)"

    def tree(lo: int, hi: int, which: int, full: float) -> str:
        if hi - lo == 1:
            return piece_value(pieces[lo][2], which, full)
        mid = (lo + hi) // 2
        a, b = tree(lo, mid, which, full), tree(mid, hi, which, full)
        return a if a == b else f"if(lt(in\\,{pieces[mid][0] + 1})\\,{a}\\,{b})"

    n = len(pieces)
    left, top = tree(0, n, 0, 0.0), tree(0, n, 1, 0.0)
    right, bottom = tree(0, n, 2, float(w)), tree(0, n, 3, float(h))
    return (f"perspective=x0={left}:y0={top}:x1={right}:y1={top}:x2={left}:y2={bottom}:x3={right}:y3={bottom}"
            ":interpolation=linear:eval=frame")
