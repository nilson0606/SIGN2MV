"""[SIGN2MV 2026-11-27] Camera motion (運鏡) on the photos of a full MV.

Asked for by the user: an option, off by default (old and new projects alike); when it is on, the photos move
slowly while the title, the subtitles, the golden karaoke strip and the spectrum stay where they are.

* A "run" is one photo on screen without a photo transition in between: consecutive lines that use the same
  photo are one run (their subtitles change, the photo does not). The motion of a run goes from the first
  frame the photo is seen (the start of the transition that brings it in) to the last one (the end of the
  transition that takes it away), at an even speed: a photo that stays longer moves more slowly.
* Nine kinds: push in, pull out, pan left/right, pan up/down, push in while drifting to a corner, and since
  2026-11-28 pan corner to corner, pull out from a corner, push in while turning a little, push in then pull
  back. The project chooses them like the transitions (one kind for every photo / all in turn / random with a
  seed); a photo can have its own kind, or none, kept under the photo's fingerprint so the choice follows the
  photo when it is moved and is forgotten when it is replaced.
* How far: light (the picture enlarged by 5 %), medium (10 %), strong (20 %). The turn follows the amount
  (about 1.4, 2.6 and 4.8 degrees), small enough for the turned window to stay inside the photo.
* Ease in and out (2026-11-28, an option): the motion starts and ends slowly instead of at an even speed.

The picture of a pose is the part of the 1920x1080 photo inside a window (same aspect ratio, maybe turned)
stretched to the frame. In the encoder the window is moved by ffmpeg's perspective filter (sub-pixel: its
own zoompan filter only moves by whole pixels and stutters at these speeds), one short filter per moving piece (photo_chain);
the transition frames drawn by Python use warp(), which samples the photo at exactly the same points, so the two meet without a jump.
corners() is written once for both: with a number it gives the window's corners, with an Ex (the frame
counter in ffmpeg's expression language) it gives the expressions ffmpeg evaluates on every frame.
The MV page's live preview (web/mv/index.html, motionPlan/motionCorners) uses the same definitions: change
them together.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from PIL import Image

MOTION_STYLES = [("zoomin", "推近"), ("zoomout", "拉遠"), ("pan_lr", "左右平移"), ("pan_ud", "上下平移"),
                 ("zoompan", "推近加平移"), ("pan_diag", "斜向平移"), ("zoomout_pan", "拉遠加平移"),
                 ("rotate", "旋轉推近"), ("breathe", "推近再拉遠")]
MOTION_KEYS = [k for k, _ in MOTION_STYLES]
MOTION_MODES = ("fixed", "sequence", "random")
MOTION_AMOUNTS = {"light": 0.05, "medium": 0.10, "strong": 0.20}
PHOTO_CHOICES = tuple(MOTION_KEYS) + ("none",)     # what a photo may have of its own ("follow" = not stored)
NONE = ("none", 0)
# where "push in while drifting" ends (and "pull out from a corner" or the diagonal pan starts or ends):
# right/left, up/down (the vertical drift of the drifting kinds is smaller)
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


def ease(proj: Dict[str, Any]) -> bool:
    return bool(proj.get("motion_ease"))


def normalize(proj: Dict[str, Any]) -> None:
    """Clean the motion fields of a project before it is saved (only the fields that are there)."""
    if "motion_enabled" in proj:
        proj["motion_enabled"] = bool(proj["motion_enabled"])
    if "motion_ease" in proj:
        proj["motion_ease"] = bool(proj["motion_ease"])
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


class Ex:
    """A value in ffmpeg's expression language with the arithmetic corners() uses: corners() given an Ex for
    p writes the expressions ffmpeg evaluates on every frame, given a float it computes the numbers."""
    __slots__ = ("t",)

    def __init__(self, t: str):
        self.t = t

    @staticmethod
    def _of(v: "Num") -> str:
        return v.t if isinstance(v, Ex) else _num(float(v))

    def _op(self, op: str, other: "Num", swap: bool = False) -> "Ex":
        a, b = (Ex._of(other), self.t) if swap else (self.t, Ex._of(other))
        return Ex(f"({a}{op}{b})")

    def __add__(self, o): return self._op("+", o)
    def __radd__(self, o): return self._op("+", o, True)
    def __sub__(self, o): return self._op("-", o)
    def __rsub__(self, o): return self._op("-", o, True)
    def __mul__(self, o): return self._op("*", o)
    def __rmul__(self, o): return self._op("*", o, True)
    def __truediv__(self, o): return self._op("/", o)
    def __neg__(self): return Ex(f"(-{self.t})")


Num = Union[float, Ex]


def _sin(v: Num) -> Num:
    return Ex(f"sin({v.t})") if isinstance(v, Ex) else math.sin(v)


def _cos(v: Num) -> Num:
    return Ex(f"cos({v.t})") if isinstance(v, Ex) else math.cos(v)


def turn_max(amt: float, w: int = 1920, h: int = 1080) -> float:
    """How far "push in while turning" turns at the end (radians): 0.9 of what keeps the turned window
    inside the photo while it grows from the full frame (first order: s*(w/h*sin t + cos t) <= 1)."""
    return 0.9 * (1 - 1 / (1 + amt)) * h / w


def corners(kind: str, variant: int, amt: float, p: Num, eased: bool, w: int, h: int) -> Tuple[Num, ...]:
    """The window at p (0..1 through the run) in pixels of the w x h photo: x0, y0 (top left), x1, y1 (top
    right), x2, y2 (bottom left), x3, y3 (bottom right). A float p is clamped to 0..1; an Ex is used as it is
    (the frames it is used on keep it in 0..1). Size s (share of the photo's width and height), centre
    (cx, cy) and turn t:
      zoomin     s 1 -> f              zoomout     s f -> 1                 (f = 1 / (1 + amount))
      pan_lr/ud  s f, centre across    zoompan     s 1 -> f, to a corner    pan_diag  s f, corner to corner
      zoomout_pan s f -> 1, from a corner           rotate  s 1 -> f, t 0 -> +-turn_max
      breathe    s 1 -> f -> 1 (sine)
    With eased, p becomes (1 - cos(pi p)) / 2."""
    if not isinstance(p, Ex):
        p = min(1.0, max(0.0, float(p)))
    q: Num = (1 - _cos(p * math.pi)) / 2 if eased else p
    f = 1.0 / (1.0 + amt)
    dx, dy = _CORNERS[variant % 4]
    s: Num = 1.0
    cx: Num = 0.5
    cy: Num = 0.5
    t: Num = 0.0
    if kind == "zoomin":
        s = 1 + (f - 1) * q
    elif kind == "zoomout":
        s = f + (1 - f) * q
    elif kind in ("pan_lr", "pan_ud"):
        s = f
        c = f / 2 + (1 - f) * (q if variant % 2 == 0 else 1 - q)
        cx, cy = (c, 0.5) if kind == "pan_lr" else (0.5, c)
    elif kind == "zoompan":
        s = 1 + (f - 1) * q
        cx, cy = 0.5 + 0.5 * dx * (1 - s), 0.5 + 0.3 * dy * (1 - s)
    elif kind == "pan_diag":
        s = f
        cx, cy = 0.5 + dx * (1 - f) / 2 * (2 * q - 1), 0.5 + dy * (1 - f) / 2 * (2 * q - 1)
    elif kind == "zoomout_pan":
        s = f + (1 - f) * q
        cx, cy = 0.5 + 0.5 * dx * (1 - s), 0.5 + 0.3 * dy * (1 - s)
    elif kind == "rotate":
        s = 1 + (f - 1) * q
        t = (1 if variant % 2 == 0 else -1) * turn_max(amt, w, h) * q
    elif kind == "breathe":
        s = 1 + (f - 1) * _sin(q * math.pi)
    hw, hh = s * (w / 2), s * (h / 2)
    mx, my = cx * w, cy * h
    if isinstance(t, float) and t == 0.0:
        return (mx - hw, my - hh, mx + hw, my - hh, mx - hw, my + hh, mx + hw, my + hh)
    co, si = _cos(t), _sin(t)
    ax, ay = hw * co, hw * si          # half the top edge, turned
    bx, by = -(hh * si), hh * co       # half the left edge, turned
    return (mx - ax - bx, my - ay - by, mx + ax - bx, my + ay - by,
            mx - ax + bx, my - ay + by, mx + ax + bx, my + ay + by)


def full(w: int, h: int) -> Tuple[float, ...]:
    return (0.0, 0.0, float(w), 0.0, 0.0, float(h), float(w), float(h))


def warp(img: Image.Image, c: Sequence[float]) -> Image.Image:
    """The photo seen through the window with corners c (from corners()), the size of the photo. Output pixel
    (x, y) samples the photo at c0 + x * (c1 - c0) / width + y * (c2 - c0) / height (pixel indices), as
    ffmpeg's perspective filter does for these windows (parallelograms: its projective map is affine)."""
    w, h = img.size
    if max(abs(a - b) for a, b in zip(c, full(w, h))) < 1e-6:
        return img
    x0, y0, x1, y1, x2, y2 = c[:6]
    a, b = (x1 - x0) / w, (x2 - x0) / h
    d, e = (y1 - y0) / w, (y2 - y0) / h
    # PIL samples at a*(x+0.5)+b*(y+0.5)+c in pixel-centre coordinates, i.e. at index a*x + b*y + (a+b)/2 + c - 0.5
    return img.transform((w, h), Image.Transform.AFFINE,
                         (a, b, x0 - (a + b) / 2 + 0.5, d, e, y0 - (d + e) / 2 + 0.5),
                         resample=Image.Resampling.BILINEAR)


# ---- the encoder side --------------------------------------------------------------------------------------

def _num(v: float) -> str:
    return f"{v:.9f}".rstrip("0").rstrip(".") if abs(v) >= 1e-12 else "0"


def _persp(spec: Tuple[str, int, int, int], f0: int, amt: float, eased: bool, w: int, h: int) -> str:
    """The perspective filter of one moving piece that starts at frame f0 of the video. Its frame counter
    "in" is 1 on the piece's first frame (it counts the frames taken in, this one included), so frame
    f0 + in - 1 of the video: the window of that frame is corners(kind, variant, amt, (f - r0) / den, eased)."""
    kind, var, r0, den = spec
    vals = corners(kind, var, amt, Ex(f"((in+{f0 - 1 - r0})/{max(1, den)})"), eased, w, h)
    txt = [(v.t if isinstance(v, Ex) else _num(v)).replace(",", "\\,") for v in vals]
    names = ("x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3")
    return "perspective=" + ":".join(f"{n}={t}" for n, t in zip(names, txt)) + ":interpolation=linear:eval=frame"


def photo_chain(head: str, pieces: Sequence[Tuple[int, int, Optional[Tuple[str, int, int, int]]]], amt: float,
                eased: bool, w: int, h: int, out: str) -> str:
    """The filter text that moves the photo stream made by head (e.g. "[0:v]format=yuv420p,fps=60": whole
    frames at 60 fps) and names the result out. pieces: (first frame, end frame, spec) in order, covering the
    video; spec = (kind, variant, r0, den) for a moving piece, None for frames shown as they are (the
    transition frames, already drawn, and the photos that do not move).
    Each moving piece gets its own short perspective filter on its own branch (split, trim to its frames,
    concat back). One filter for the whole song would be shorter to write but slow: perspective reads its
    expressions again on every frame, so its cost grows with their length (a 3:49 song with turning, eased
    windows took about 60 % longer per frame than with one short expression)."""
    chunks: List[Tuple[int, int, Optional[Tuple[str, int, int, int]]]] = []
    for f0, f1, spec in pieces:
        if f1 <= f0:
            continue
        if spec is None and chunks and chunks[-1][2] is None and chunks[-1][1] == f0:
            chunks[-1] = (chunks[-1][0], f1, None)              # still frames side by side: one branch
        else:
            chunks.append((f0, f1, spec))
    if len(chunks) == 1:
        f0, f1, spec = chunks[0]
        return head + ("," + _persp(spec, f0, amt, eased, w, h) if spec else ",null") + out
    k = len(chunks)
    parts = [head + f",split={k}" + "".join(f"[mvs{i}]" for i in range(k))]
    for i, (f0, f1, spec) in enumerate(chunks):
        c = f"[mvs{i}]trim=start_frame={f0}:end_frame={f1},setpts=PTS-STARTPTS"
        if spec:
            c += "," + _persp(spec, f0, amt, eased, w, h)
        parts.append(c + f"[mvc{i}]")
    parts.append("".join(f"[mvc{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0{out}")
    return ";".join(parts)
