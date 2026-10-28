"""MV workspace engine: projects, timeline helpers, frame rendering and the
1080p 60 fps render pipeline.

Ported from the MV Studio of AI_COVER_MV (mv_studio_server.py, 2026-10-27).
Rendering logic, transitions, karaoke timing and timeline rules are unchanged.
What changed for SIGN2MV:
  * projects live in the song library: songs/<song id>/mv/<name>/
      project.json, scenes/ (photos), whisper.json, frames/ (render cache),
      verify/ (check frames), previews/, audio/ (uploaded audio), output/ (MP4)
    and the project "slug" is "<song id>_<name>";
  * the name card / badge defaults come from the settings (cover singer name,
    studio name) instead of fixed names, and credits can be English;
  * fonts are looked up (Microsoft YaHei / JhengHei on Windows, Noto CJK elsewhere);
  * progress goes through PROGRESS_HOOK (the render runs as a queue worker).
Imported by the server (numpy + Pillow are in the server environment) and by
workers/mv_render.py (engine environment).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .align import TRAD_TO_SIMP, build_guaranteed_fallback_timeline

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

SONG_ID = r"s[0-9a-z]{10}"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
SLUG_RE = re.compile(rf"^({SONG_ID})_([a-z0-9][a-z0-9_-]{{0,39}})$")

# ---------------------------------------------------------------------------
# configuration (set by the server / the render worker)
# ---------------------------------------------------------------------------
LIBRARY_ROOT: Path = Path(".")
BRAND: Dict[str, str] = {"singer": "", "studio": "", "lang": "zh"}
PROGRESS_HOOK: Callable[[bool, str, int, str, str], None] = lambda *a: None
CANCEL_REQUESTED = False
ACTIVE_RENDER_PROC: Optional[subprocess.Popen] = None


def configure(library_root: Any, singer: str = "", studio: str = "", lang: str = "zh",
              progress: Optional[Callable[[bool, str, int, str, str], None]] = None) -> None:
    global LIBRARY_ROOT, FFMPEG, FFPROBE, PROGRESS_HOOK
    LIBRARY_ROOT = Path(library_root)
    BRAND.update({"singer": str(singer or "").strip(), "studio": str(studio or "").strip(),
                  "lang": "en" if lang == "en" else "zh"})
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
    FFPROBE = shutil.which("ffprobe") or "ffprobe"
    if progress is not None:
        PROGRESS_HOOK = progress


class RenderCancelled(Exception):
    pass


class ProjectNotFound(LookupError):
    pass


def _check_cancel():
    if CANCEL_REQUESTED:
        raise RenderCancelled("已由使用者取消")


def update_progress(active: bool, task_type: str, percent: int, stage: str, detail: str = ""):
    try:
        PROGRESS_HOOK(active, task_type, int(percent), stage, detail)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# branding: no "AI" on screen; names come from the settings
# ---------------------------------------------------------------------------
LABELS = {
    "zh": {"lyricist": "作詞：", "composer": "作曲：", "original": "原唱：", "cover": "翻唱者：", "studio": "錄音混音："},
    "en": {"lyricist": "Lyrics: ", "composer": "Music: ", "original": "Original: ", "cover": "Cover: ",
           "studio": "Recording & Mix: "},
}


def credit_lang(proj: Optional[Dict[str, Any]] = None) -> str:
    lang = (proj or {}).get("credit_lang") or BRAND["lang"]
    return "en" if lang == "en" else "zh"


def L(proj: Dict[str, Any], key: str) -> str:
    return LABELS[credit_lang(proj)][key]


def default_badge(lang: Optional[str] = None) -> str:
    singer = BRAND["singer"]
    if (lang or BRAND["lang"]) == "en":
        return f"Cover by {singer}" if singer else "Cover"
    return f"{singer} 翻唱" if singer else "翻唱"


def default_outro(proj: Optional[Dict[str, Any]] = None) -> str:
    studio = sanitize_no_ai((proj or {}).get("studio") or BRAND["studio"], "")
    if credit_lang(proj) == "en":
        return f"Presented by {studio} · Thank you for listening" if studio else "Thank you for listening"
    return f"{studio} 榮譽呈獻 · 感謝聆聽" if studio else "感謝聆聽"


def default_intro(lang: Optional[str] = None) -> str:
    if (lang or BRAND["lang"]) == "en":
        return "Narrative storyboard · Stereo master"
    return "高畫質敘事分鏡與空鏡美學 · 立體聲珍藏母帶"


def credits_line(proj: Dict[str, Any], orig: str, cover: str, studio: str) -> str:
    parts = [f"{L(proj, 'original')}{orig}"]
    if cover:
        parts.append(f"{L(proj, 'cover')}{cover}")
    if studio:
        parts.append(f"{L(proj, 'studio')}{studio}")
    return "  |  ".join(parts)


def card_singers_line(proj: Dict[str, Any], orig: str, cover: str) -> str:
    line = f"{L(proj, 'original')}{orig}"
    return f"{line}        {L(proj, 'cover')}{cover}" if cover else line


def sanitize_no_ai(text: str, default_val: str = "") -> str:
    """Golden rule #1 of the MV workspace: the video never shows "AI" / "AI 翻唱" / "AI Cover"."""
    if not text:
        return default_val
    singer = BRAND["singer"]
    cover_word = f"{singer} 翻唱" if singer else "翻唱"
    cleaned = re.sub(r'(?i)AI\s*翻唱', cover_word, str(text))
    cleaned = re.sub(r'(?i)AI\s*Cover', cover_word, cleaned)
    cleaned = re.sub(r'(?i)(?<![a-zA-Z])AI(?![a-zA-Z])', singer, cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned) if not singer else cleaned
    return cleaned.strip() or default_val


# ---------------------------------------------------------------------------
# fonts
# ---------------------------------------------------------------------------
_FONT_CANDIDATES = {
    True: ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
           "C:/Windows/Fonts/msjh.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/PingFang.ttc"],
    False: ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/PingFang.ttc"],
}


@lru_cache(maxsize=64)
def _font(bold: bool, size: int):
    override = os.environ.get("SIGN2MV_MV_FONT_BOLD" if bold else "SIGN2MV_MV_FONT")
    for path in ([override] if override else []) + _FONT_CANDIDATES[bool(bold)]:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


# ---------------------------------------------------------------------------
# projects in the song library
# ---------------------------------------------------------------------------
def parse_slug(slug: str) -> Tuple[str, str]:
    m = SLUG_RE.match(str(slug or ""))
    if not m:
        raise ProjectNotFound(f"Project '{slug}' not found")
    return m.group(1), m.group(2)


def song_dir(song_id: str) -> Path:
    return LIBRARY_ROOT / "songs" / song_id


def project_dir(slug: str) -> str:
    sid, name = parse_slug(slug)
    return str(song_dir(sid) / "mv" / name)


def safe_file_title(title: str, fallback: str) -> str:
    t = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(title or "")).strip().strip(".")
    return t[:80] or fallback


def default_output_mv(proj: Dict[str, Any]) -> str:
    title = safe_file_title(proj.get("title", ""), parse_slug(proj["slug"])[1])
    return os.path.join(project_dir(proj["slug"]), "output", f"{title}_MV.mp4")


def _abs_audio(sid: str, value: str) -> str:
    if not value:
        return ""
    p = Path(value)
    return str(p if p.is_absolute() else song_dir(sid) / p)


def _rel_audio(sid: str, value: str) -> str:
    if not value:
        return ""
    try:
        return Path(value).resolve().relative_to(song_dir(sid).resolve()).as_posix()
    except (ValueError, OSError):
        return str(value)


def _resolve(proj: Dict[str, Any]) -> Dict[str, Any]:
    sid, name = parse_slug(proj["slug"])
    pdir = Path(project_dir(proj["slug"]))
    proj["song_id"], proj["name"] = sid, name
    proj["illust_dir"] = str(pdir / "scenes")
    proj["whisper_json"] = str(pdir / "whisper.json")
    proj["audio_file"] = _abs_audio(sid, str(proj.get("audio_file") or ""))
    out = str(proj.get("output_mv") or "")
    proj["output_mv"] = str(pdir / "output" / os.path.basename(out)) if out else default_output_mv(proj)
    return proj


def _apply_brand_defaults(proj: Dict[str, Any]) -> None:
    proj["badge"] = sanitize_no_ai(proj.get("badge", default_badge(credit_lang(proj))), default_badge(credit_lang(proj)))
    proj["cover_singer"] = sanitize_no_ai(proj.get("cover_singer", BRAND["singer"]), BRAND["singer"])
    proj["studio"] = sanitize_no_ai(proj.get("studio", BRAND["studio"]), BRAND["studio"])
    proj["outro_desc"] = sanitize_no_ai(proj.get("outro_desc", default_outro(proj)), default_outro(proj))


def load_project_dict(slug: str) -> Dict[str, Any]:
    fp = Path(project_dir(slug)) / "project.json"
    if not fp.is_file():
        raise ProjectNotFound(f"Project '{slug}' not found")
    with open(fp, "r", encoding="utf-8") as f:
        proj = json.load(f)
    proj["slug"] = slug
    _apply_brand_defaults(proj)
    return _resolve(proj)


def list_project_slugs() -> List[str]:
    out = []
    songs = LIBRARY_ROOT / "songs"
    if not songs.is_dir():
        return out
    for sd in songs.iterdir():
        mv = sd / "mv"
        if not re.fullmatch(SONG_ID, sd.name) or not mv.is_dir():
            continue
        for pd in mv.iterdir():
            if NAME_RE.match(pd.name) and (pd / "project.json").is_file():
                out.append(f"{sd.name}_{pd.name}")
    return sorted(out)


def save_project_dict(proj: Dict[str, Any]) -> Dict[str, Any]:
    slug = str(proj.get("slug") or "")
    parse_slug(slug)
    proj["slug"] = slug
    _apply_brand_defaults(proj)
    proj["intro_desc"] = sanitize_no_ai(proj.get("intro_desc", ""), "")
    for seg in proj.get("timeline", []):
        seg["text"] = sanitize_no_ai(str(seg.get("text", "")), str(seg.get("text", "")))
    normalize_instrumental_fields(proj.get("timeline", []))
    # transitions: mode fixed / sequence / random; style one of TRANSITION_KEYS; seed for random
    if proj.get("transition_mode") not in (None, "fixed", "sequence", "random"):
        proj["transition_mode"] = "fixed"
    if proj.get("transition_style") is not None and proj.get("transition_style") not in TRANSITION_KEYS:
        proj["transition_style"] = "fade"
    if "spectrum_enabled" in proj:
        proj["spectrum_enabled"] = bool(proj["spectrum_enabled"])
    if "karaoke_enabled" in proj:
        proj["karaoke_enabled"] = bool(proj["karaoke_enabled"])
    if "whisper_lead_only" in proj:
        proj["whisper_lead_only"] = bool(proj["whisper_lead_only"])
    if proj.get("karaoke_timing") is not None and proj.get("karaoke_timing") not in KARAOKE_TIMING_MODES:
        proj["karaoke_timing"] = "voice"
    if "karaoke_advance" in proj:
        proj["karaoke_advance"] = karaoke_advance(proj)
    if "spectrum_color" in proj:
        proj["spectrum_color"] = spectrum_color_hex(proj)
    if proj.get("transition_seed") is not None:
        try:
            proj["transition_seed"] = int(proj["transition_seed"]) & 0x7FFFFFFF
        except (TypeError, ValueError):
            proj["transition_seed"] = 1
    if proj.get("credit_lang") not in (None, "zh", "en"):
        proj["credit_lang"] = "zh"
    sid, _ = parse_slug(slug)
    stored = {k: v for k, v in proj.items() if k not in ("illust_dir", "whisper_json", "song_id", "name", "slug")}
    stored["audio_file"] = _rel_audio(sid, str(proj.get("audio_file") or ""))
    stored["output_mv"] = os.path.basename(str(proj.get("output_mv") or "")) or os.path.basename(default_output_mv(proj))
    stored["schema_version"] = 1
    pdir = Path(project_dir(slug))
    pdir.mkdir(parents=True, exist_ok=True)
    tmp = pdir / ("project.json." + secrets.token_hex(4) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stored, f, ensure_ascii=False, indent=2)
    os.replace(tmp, pdir / "project.json")
    return _resolve(dict(stored, slug=slug))


# ==== probe ====
def probe_media_file(filepath: str) -> Dict[str, Any]:
    if not filepath or not os.path.exists(filepath):
        return {"exists": False}
    cmd = [
        FFPROBE, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", filepath
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace", timeout=10, creationflags=NO_WINDOW)
        data = json.loads(res.stdout or "{}")
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        info = {
            "exists": True,
            "path": filepath,
            "size_bytes": os.path.getsize(filepath),
            "size_mb": round(os.path.getsize(filepath) / (1024 * 1024), 2),
            "duration": round(float(fmt.get("duration", 0.0)), 3),
        }
        if v_stream:
            info["video_codec"] = v_stream.get("codec_name", "")
            info["width"] = int(v_stream.get("width", 0))
            info["height"] = int(v_stream.get("height", 0))
            info["r_frame_rate"] = v_stream.get("r_frame_rate", "")
        if a_stream:
            info["audio_codec"] = a_stream.get("codec_name", "")
            info["sample_rate"] = int(a_stream.get("sample_rate", 0))
            info["channels"] = int(a_stream.get("channels", 0))
        if filepath.lower().endswith(".wav") and info.get("duration", 0) > 20:
            try:
                import wave
                import numpy as np
                with wave.open(filepath, "rb") as wf:
                    sr = wf.getframerate()
                    ch = wf.getnchannels()
                    raw15 = np.frombuffer(wf.readframes(int(15 * sr)), dtype=np.int16).reshape(-1, ch)
                    intro_rms = round(float(np.sqrt(np.mean(raw15.astype(float) ** 2))), 1)
                    info["intro_rms"] = intro_rms
                    info["has_bgm"] = bool(intro_rms >= 120.0)
            except Exception:
                pass
        return info
    except Exception as e:
        return {"exists": True, "path": filepath, "error": str(e)}


# ==== scenes_render ====
def resolve_scene_image_path(illust_dir: str, scene_id: int) -> Optional[str]:
    if not illust_dir or not os.path.exists(illust_dir):
        return None
    direct = os.path.join(illust_dir, f"scene_{scene_id:02d}.png")
    if os.path.exists(direct):
        return direct
    prefix = f"scene_{scene_id:02d}_"
    for fn in sorted(os.listdir(illust_dir)):
        if fn.startswith(prefix) and fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            return os.path.join(illust_dir, fn)
    return None


def count_existing_scene_images(illust_dir: str) -> int:
    if not illust_dir or not os.path.exists(illust_dir):
        return 0
    max_sid = 0
    for sid in range(1, 37):
        if resolve_scene_image_path(illust_dir, sid):
            max_sid = sid
    return max_sid


def list_scene_images(illust_dir: str, max_scene: int = 24) -> List[Dict[str, Any]]:
    scenes = []
    for sid in range(1, max_scene + 1):
        p = resolve_scene_image_path(illust_dir, sid)
        if p and os.path.exists(p):
            scenes.append({
                "scene_id": sid,
                "exists": True,
                "path": p,
                "filename": os.path.basename(p),
                "size_kb": round(os.path.getsize(p) / 1024, 1),
                "mtime": int(os.path.getmtime(p))
            })
        else:
            scenes.append({
                "scene_id": sid,
                "exists": False,
                "path": "",
                "filename": f"scene_{sid:02d}.png",
                "size_kb": 0,
                "mtime": 0
            })
    return scenes


def create_fallback_scene_image(w: int, h: int, scene_id: int, title: str, text: str) -> Image.Image:
    img = Image.new("RGB", (w, h), (14, 20, 34))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        r = int(14 + 24 * (y / h))
        g = int(20 + 28 * (y / h))
        b = int(34 + 45 * (y / h))
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    try:
        f_lg = _font(True, 46)
        f_sm = _font(False, 28)
        draw.text((w // 2 - 180, h // 2 - 60), f"Scene {scene_id:02d} · {title}", font=f_lg, fill=(235, 205, 135))
        draw.text((w // 2 - 220, h // 2 + 10), text[:32], font=f_sm, fill=(180, 195, 215))
    except Exception:
        pass
    return img


# ---------------------------------------------------------------------------
# [Claude 2026-10-26] 畫面拆成「照片層」與「文字層」：轉場只作用在照片，標題／字幕用淡入淡出（使用者決定）
# ---------------------------------------------------------------------------
FRAME_W, FRAME_H = 1920, 1080


# [Claude 2026-10-26] 前奏／間奏／尾奏的專屬照片：<illust_dir>/inst_<key>.png
# key：intro、outro、interlude_<6碼id>。還沒上傳專屬照片時沿用該段 Scene 的照片。
INST_KEY_RE = re.compile(r"^(intro|outro|interlude_[0-9a-f]{6})$")
INTERLUDE_TYPES = ("interlude", "solo")


def instrumental_key(seg: Dict[str, Any]) -> Optional[str]:
    tp = str(seg.get("type", "lyric"))
    if tp in ("intro", "outro"):
        return tp
    if tp in INTERLUDE_TYPES and re.fullmatch(r"[0-9a-f]{6}", str(seg.get("id", ""))):
        return f"interlude_{seg['id']}"
    return None


def instrumental_photo_path(illust_dir: str, key: str) -> str:
    return os.path.join(illust_dir or "", f"inst_{key}.png")


def seg_photo_path(proj: Dict[str, Any], seg: Dict[str, Any]) -> str:
    """這一段實際用的照片檔（專屬照片優先，否則 Scene 照片；都沒有回傳空字串）"""
    illust_dir = proj.get("illust_dir", "")
    key = instrumental_key(seg)
    if key:
        ip = instrumental_photo_path(illust_dir, key)
        if illust_dir and os.path.exists(ip):
            return ip
    return resolve_scene_image_path(illust_dir, int(seg.get("scene", 1))) or ""


def list_instrumental_photos(illust_dir: str, timeline: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for seg in timeline or []:
        key = instrumental_key(seg)
        if key and key not in out:
            ip = instrumental_photo_path(illust_dir, key)
            if illust_dir and os.path.exists(ip):
                out[key] = {"path": ip, "mtime": int(os.path.getmtime(ip))}
    return out


def render_background(proj: Dict[str, Any], seg: Dict[str, Any], bg_cache: Optional[Dict[Any, Image.Image]] = None) -> Image.Image:
    """這一段的照片（1920x1080 RGB）；沒有照片時用深色底＋場景名"""
    sc_id = int(seg.get("scene", 1))
    img_path = seg_photo_path(proj, seg)
    ck = img_path or sc_id
    if bg_cache is not None and ck in bg_cache:
        return bg_cache[ck]
    if img_path and os.path.exists(img_path):
        with Image.open(img_path) as raw_im:
            bg = raw_im.convert("RGB").resize((FRAME_W, FRAME_H), Image.Resampling.LANCZOS)
    else:
        bg = create_fallback_scene_image(FRAME_W, FRAME_H, sc_id, proj.get("title", ""), str(seg.get("text", "")))
    if bg_cache is not None:
        bg_cache[ck] = bg
    return bg


def _layer() -> Image.Image:
    return Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))


def render_overlay_rgba(proj: Dict[str, Any], seg: Dict[str, Any]) -> Image.Image:
    """這一段的文字層（透明底 RGBA）：上下漸層暗角、歌名＋徽章、作詞作曲、前奏／片尾卡、底部金框字幕。
    樣式與原本 render_single_styled_frame 相同，只是畫在透明層上。"""
    w, h = FRAME_W, FRAME_H
    text = str(seg.get("text", ""))
    seg_type = str(seg.get("type", "lyric"))
    ov = _layer()

    grad = _layer()
    d_ol = ImageDraw.Draw(grad)
    for y in range(220):
        a = int(140 * (1.0 - y / 220.0))
        d_ol.line([(0, y), (w, y)], fill=(8, 12, 22, a))
    for y in range(h - 260, h):
        ratio = (y - (h - 260)) / 260.0
        a = int(170 * ratio)
        d_ol.line([(0, y), (w, y)], fill=(6, 10, 20, a))
    ov = Image.alpha_composite(ov, grad)

    font_title_hero = _font(True, 84)
    font_title = _font(True, 60)
    font_badge = _font(True, 28)
    font_sub = _font(False, 24)
    font_credits = _font(False, 20)
    font_card_sub = _font(True, 38)
    font_card_desc = _font(False, 26)

    en = credit_lang(proj) == "en"
    unknown, untitled, orig_default = ("Unknown", "Untitled", "Unknown") if en else ("未知", "未命名歌曲", "原唱")
    title_str = sanitize_no_ai(proj.get("title", untitled), untitled)
    badge_text = sanitize_no_ai(proj.get("badge", default_badge()), default_badge())
    lyricist = sanitize_no_ai(proj.get("lyricist", unknown), unknown)
    composer = sanitize_no_ai(proj.get("composer", unknown), unknown)
    orig_singer = sanitize_no_ai(proj.get("original_singer", orig_default), orig_default)
    cover_singer = sanitize_no_ai(proj.get("cover_singer", BRAND["singer"]), BRAND["singer"])
    studio_name = sanitize_no_ai(proj.get("studio", BRAND["studio"]), BRAND["studio"])

    head = _layer()
    draw = ImageDraw.Draw(head)
    bbox_title = draw.textbbox((90, 50), title_str, font=font_title)
    draw.text((90, 50), title_str, font=font_title, fill=(255, 255, 255, 255))
    bbox_b = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox_b[2] - bbox_b[0]
    bh = bbox_b[3] - bbox_b[1]
    bx = bbox_title[2] + 28
    by = 58
    pad_bx, pad_by = 16, 6
    draw.rounded_rectangle([bx - pad_bx, by - pad_by, bx + bw + pad_bx, by + bh + pad_by], radius=8, fill=(168, 38, 48, 255), outline=(255, 225, 140, 255), width=2)
    draw.text((bx, by - 1), badge_text, font=font_badge, fill=(255, 250, 235, 255))
    draw.text((92, 128), f"{L(proj, 'lyricist')}{lyricist}    {L(proj, 'composer')}{composer}", font=font_sub, fill=(255, 220, 150, 255))
    draw.text((92, 164), credits_line(proj, orig_singer, cover_singer, studio_name), font=font_credits, fill=(225, 235, 248, 255))
    ov = Image.alpha_composite(ov, head)

    t_hero = sanitize_no_ai(proj.get("title_spaced") or "  ".join(list(title_str)), title_str)
    if seg_type in ("intro", "outro") and seg.get("display", "card") != "photo_text":
        card_w, card_h = 980, 380
        cx = (w - card_w) // 2
        cy = (h - card_h) // 2 - 30
        card = _layer()
        d_card = ImageDraw.Draw(card)
        d_card.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=24, fill=(12, 16, 28, 220), outline=(245, 215, 135, 240), width=3)
        ov = Image.alpha_composite(ov, card)
        ctext = _layer()
        draw = ImageDraw.Draw(ctext)
        bbox_h = draw.textbbox((0, 0), t_hero, font=font_title_hero)
        draw.text(((w - (bbox_h[2] - bbox_h[0])) // 2, cy + 30), t_hero, font=font_title_hero, fill=(255, 248, 225, 255))
        c_text1 = f"{L(proj, 'lyricist')}{lyricist}        {L(proj, 'composer')}{composer}"
        bbox_c1 = draw.textbbox((0, 0), c_text1, font=font_card_desc)
        draw.text(((w - (bbox_c1[2] - bbox_c1[0])) // 2, cy + 140), c_text1, font=font_card_desc, fill=(225, 220, 205, 255))
        c_text2 = card_singers_line(proj, orig_singer, cover_singer)
        bbox_c2 = draw.textbbox((0, 0), c_text2, font=font_card_sub)
        draw.text(((w - (bbox_c2[2] - bbox_c2[0])) // 2, cy + 195), c_text2, font=font_card_sub, fill=(255, 215, 120, 255))
        if seg_type == "intro":
            c_text3 = sanitize_no_ai(proj.get("intro_desc", default_intro(credit_lang(proj))), default_intro(credit_lang(proj)))
        else:
            c_text3 = sanitize_no_ai(proj.get("outro_desc", default_outro(proj)), default_outro(proj))
        bbox_c3 = draw.textbbox((0, 0), c_text3, font=font_card_desc)
        draw.text(((w - (bbox_c3[2] - bbox_c3[0])) // 2, cy + 275), c_text3, font=font_card_desc, fill=(185, 215, 240, 255))
        ov = Image.alpha_composite(ov, ctext)

    if text.strip():
        # [Claude 2026-10-26] 位置計算抽成 subtitle_layout，逐字跳金的金字條用同一套，才會剛好蓋在白字上
        clean_lyric, curr_font, lx, ly = subtitle_layout(text, seg_type)
        is_instrumental = clean_lyric.startswith("～") or seg_type in ("intro", "interlude", "outro", "solo")
        bbox = ImageDraw.Draw(_layer()).textbbox((0, 0), clean_lyric, font=curr_font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        pad_x, pad_y = 52, 16
        sub_box = _layer()
        ImageDraw.Draw(sub_box).rounded_rectangle([lx - pad_x, ly - pad_y, lx + lw + pad_x, ly + lh + pad_y + 4], radius=16, fill=(10, 14, 24, 215), outline=(235, 195, 115, 240), width=2)
        ov = Image.alpha_composite(ov, sub_box)
        stext = _layer()
        draw = ImageDraw.Draw(stext)
        draw.text((lx + 2, ly + 2), clean_lyric, font=curr_font, fill=(0, 0, 0, 255))
        text_color = (255, 235, 160, 255) if is_instrumental else (255, 255, 255, 255)
        draw.text((lx, ly), clean_lyric, font=curr_font, fill=text_color)
        ov = Image.alpha_composite(ov, stext)
    return ov


def compose_frame(bg: Image.Image, ov: Image.Image) -> Image.Image:
    return Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")


def render_single_styled_frame(proj: Dict[str, Any], seg: Dict[str, Any], bg_cache: Optional[Dict[int, Image.Image]] = None) -> Image.Image:
    """單張畫面（照片＋文字層）；給合成與「合成單幀預覽」用"""
    return compose_frame(render_background(proj, seg, bg_cache), render_overlay_rgba(proj, seg))


# ---------------------------------------------------------------------------
# [Claude 2026-10-26] 20 種照片轉場（使用者要求：固定／依序／隨機；隨機用固定亂數＋「重新抽」）
# 網頁「即時對字幕」用同樣的定義在 canvas 上畫（mv_studio.html liveDrawTransition），改這裡要一起改。
# ---------------------------------------------------------------------------
TRANSITION_STYLES = [
    ("fade", "交叉淡化"), ("fadeblack", "黑場"), ("fadewhite", "白光閃"),
    ("slideleft", "向左推"), ("slideright", "向右推"), ("slideup", "向上推"), ("slidedown", "向下推"),
    ("wipe_lr", "由左往右擦除"), ("wipe_rl", "由右往左擦除"), ("wipe_tb", "由上往下擦除"),
    ("circleopen", "圓形展開"), ("circleclose", "圓形收合"), ("zoomin", "推近溶解"), ("zoomout", "拉遠溶解"),
    ("hblinds", "橫百葉窗"), ("vblinds", "直百葉窗"), ("diagonal", "斜角擦除"), ("radial", "時鐘掃描"),
    ("dooropen", "中間開門"), ("blur", "模糊溶解"),
]
TRANSITION_KEYS = [k for k, _ in TRANSITION_STYLES]
BLINDS_N = 10
BLUR_MAX_PX = 20.0   # 1920 寬時的最大模糊半徑


def _mix32(x: int) -> int:
    x &= 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x45D9F3B) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x45D9F3B) & 0xFFFFFFFF
    x ^= x >> 16
    return x


def transition_plan(proj: Dict[str, Any], n_boundaries: int) -> List[str]:
    """每個交界用哪種轉場。固定：全片一種；依序：1..20 循環；隨機：用專案的 transition_seed 算（同一個種子結果永遠一樣，
    連續兩個不重複）。舊專案沒有這些欄位 → 固定、交叉淡化（跟原本一樣）。"""
    mode = str(proj.get("transition_mode") or "fixed")
    style = str(proj.get("transition_style") or "fade")
    if style not in TRANSITION_KEYS:
        style = "fade"
    n = len(TRANSITION_KEYS)
    out: List[str] = []
    if mode == "sequence":
        out = [TRANSITION_KEYS[k % n] for k in range(n_boundaries)]
    elif mode == "random":
        seed = int(proj.get("transition_seed") or 1) & 0xFFFFFFFF
        prev = -1
        for k in range(n_boundaries):
            idx = _mix32(seed * 0x9E3779B1 + k * 0x85EBCA77 + 1) % n
            if idx == prev:
                idx = (idx + 1) % n
            out.append(TRANSITION_KEYS[idx])
            prev = idx
    else:
        out = [style] * n_boundaries
    return out


def transition_steps(trans_duration: float) -> int:
    """轉場格數跟著秒數走（每秒 40 格；0.4 秒＝16 格，跟原本一樣）"""
    return max(8, min(60, int(round(float(trans_duration) * 40))))


def _scale_center(arr: np.ndarray, sc: float) -> np.ndarray:
    """以畫面中心放大 sc 倍（sc>=1），輸出同尺寸"""
    if sc <= 1.0001:
        return arr
    h, w = arr.shape[:2]
    cw, ch = w / sc, h / sc
    x0, y0 = (w - cw) / 2, (h - ch) / 2
    im = Image.fromarray(arr.astype(np.uint8))
    im = im.resize((w, h), Image.Resampling.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    return np.asarray(im, dtype=np.float32)


def _blur(arr: np.ndarray, px: float) -> np.ndarray:
    if px < 0.3:
        return arr
    from PIL import ImageFilter
    im = Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=px))
    return np.asarray(im, dtype=np.float32)


_GRID_CACHE: Dict[Any, Any] = {}


def _grids(h: int, w: int):
    key = (h, w)
    if key not in _GRID_CACHE:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2.0, h / 2.0
        dist = np.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
        theta = (np.arctan2(xx + 0.5 - cx, -(yy + 0.5 - cy)) % (2 * np.pi)) / (2 * np.pi)
        _GRID_CACHE[key] = (xx, yy, dist, theta)
    return _GRID_CACHE[key]


def apply_bg_transition(style: str, A: np.ndarray, B: np.ndarray, s: float) -> np.ndarray:
    """照片轉場：A＝前一張、B＝下一張（float32 HxWx3），s＝0..1（已平滑）。回傳 float32。"""
    h, w = A.shape[:2]
    if style == "fade":
        return A * (1 - s) + B * s
    if style == "fadeblack":
        return A * (1 - 2 * s) if s < 0.5 else B * (2 * s - 1)
    if style == "fadewhite":
        return A + (255.0 - A) * (2 * s) if s < 0.5 else 255.0 + (B - 255.0) * (2 * s - 1)
    if style in ("slideleft", "slideright"):
        off = int(round(s * w))
        out = np.empty_like(A)
        if style == "slideleft":
            out[:, :w - off] = A[:, off:]
            out[:, w - off:] = B[:, :off]
        else:
            out[:, off:] = A[:, :w - off]
            out[:, :off] = B[:, w - off:]
        return out
    if style in ("slideup", "slidedown"):
        off = int(round(s * h))
        out = np.empty_like(A)
        if style == "slideup":
            out[:h - off] = A[off:]
            out[h - off:] = B[:off]
        else:
            out[off:] = A[:h - off]
            out[:off] = B[h - off:]
        return out
    if style in ("dooropen",):
        out = B.copy()
        half = w // 2
        off = int(round(s * half))
        if off < half:
            out[:, 0:half - off] = A[:, off:half]
            out[:, half + off:] = A[:, half:w - off]
        return out
    if style == "zoomin":
        return _scale_center(A, 1.0 + 0.3 * s) * (1 - s) + B * s
    if style == "zoomout":
        return A * (1 - s) + _scale_center(B, 1.3 - 0.3 * s) * s
    if style == "blur":
        return _blur(A, s * BLUR_MAX_PX * w / 1920.0) * (1 - s) + _blur(B, (1 - s) * BLUR_MAX_PX * w / 1920.0) * s
    xx, yy, dist, theta = _grids(h, w)
    R = float(np.hypot(w / 2.0, h / 2.0))
    if style == "wipe_lr":
        m = xx + 0.5 < s * w
    elif style == "wipe_rl":
        m = xx + 0.5 > (1 - s) * w
    elif style == "wipe_tb":
        m = yy + 0.5 < s * h
    elif style == "circleopen":
        m = dist < s * R
    elif style == "circleclose":
        m = ~(dist < (1 - s) * R)
    elif style == "hblinds":
        band = h / BLINDS_N
        m = np.mod(yy + 0.5, band) < s * band
    elif style == "vblinds":
        band = w / BLINDS_N
        m = np.mod(xx + 0.5, band) < s * band
    elif style == "diagonal":
        m = ((xx + 0.5) / w + (yy + 0.5) / h) < 2 * s
    elif style == "radial":
        m = theta < s
    else:
        return A * (1 - s) + B * s
    return np.where(m[..., None], B, A)


def compose_transition_frame(style: str, bgA: Image.Image, bgB: Image.Image, ovA: Image.Image, ovB: Image.Image,
                             s: float, same_photo: bool) -> Image.Image:
    """轉場中的一格：照片依樣式轉場（同一張照片就不轉），文字層用淡入淡出（premultiplied 混合，標題不會閃）"""
    A = np.asarray(bgA, dtype=np.float32)
    if same_photo:
        bg = A
    else:
        bg = apply_bg_transition(style, A, np.asarray(bgB, dtype=np.float32), s)
    oa = np.asarray(ovA, dtype=np.float32)
    ob = np.asarray(ovB, dtype=np.float32)
    aa, ab = oa[..., 3:4] / 255.0, ob[..., 3:4] / 255.0
    prem = oa[..., :3] * aa * (1 - s) + ob[..., :3] * ab * s
    alpha = aa * (1 - s) + ab * s
    out = bg * (1 - alpha) + prem
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8))



# ==== normalize ====
def normalize_instrumental_fields(timeline: List[Dict[str, Any]]) -> bool:
    """[Claude 2026-10-26] 間奏段補上不重複的 6 碼 id（專屬照片用）；前奏／尾奏的 display 只能是 card 或 photo_text。
    有改動回傳 True。"""
    changed = False
    all_ids = {str(x.get("id")) for x in timeline or [] if x.get("id")}
    seen = set()
    for seg in timeline or []:
        tp = seg.get("type")
        if tp in INTERLUDE_TYPES:
            sid = str(seg.get("id", ""))
            if not re.fullmatch(r"[0-9a-f]{6}", sid) or sid in seen:
                nid = secrets.token_hex(3)
                while nid in all_ids or nid in seen:
                    nid = secrets.token_hex(3)
                seg["id"] = sid = nid
                changed = True
            seen.add(sid)
        if tp in ("intro", "outro") and seg.get("display") not in (None, "card", "photo_text"):
            seg["display"] = "card"
            changed = True
    return changed


# ==== spectrum_to_verify ====
# [Claude 2026-10-26] 唱歌時字幕下方的頻譜跳動（跟 AI 翻唱 MV 一樣用 ffmpeg showfreqs，使用者可關）
# 位置：字幕金框下緣約在 y≈975，頻譜放 y=992 起、高 72、寬 720 置中，不會蓋到字幕
SPECTRUM_X, SPECTRUM_Y, SPECTRUM_W, SPECTRUM_H = 600, 992, 720, 72
SPECTRUM_COLOR = "0xf5d787"


def spectrum_ranges(timeline: List[Dict[str, Any]], positions: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """歌詞段在成品影片裡的時間範圍（相鄰的併成一段）"""
    out: List[Tuple[float, float]] = []
    for seg, (a, b) in zip(timeline, positions):
        if seg.get("type", "lyric") != "lyric" or str(seg.get("text", "")).startswith("～") or not str(seg.get("text", "")).strip():
            continue
        if out and abs(out[-1][1] - a) < 1e-3:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


SPECTRUM_PRESETS = {"gold": "#f5d787", "green": "#34d399", "blue": "#38bdf8", "pink": "#f472b6", "white": "#ffffff"}


def spectrum_color_hex(proj: Dict[str, Any]) -> str:
    """[Claude 2026-10-26] 頻譜顏色（使用者：預設色＋自訂色盤）。太暗會被去背吃掉，最暗拉到 #303030"""
    c = str(proj.get("spectrum_color") or SPECTRUM_PRESETS["gold"]).strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
        c = SPECTRUM_PRESETS["gold"]
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    if max(r, g, b) < 0x30:
        r, g, b = max(r, 0x30), max(g, 0x30), max(b, 0x30)
    return f"#{r:02x}{g:02x}{b:02x}"


def build_video_filter(spec_ranges: Optional[List[Tuple[float, float]]], color_hex: str = "#f5d787",
                       karaoke: bool = False) -> Optional[str]:
    """合成最後一步的影片濾鏡：[0:v] 照片串 →（逐字金色字條 [2:v]）→（頻譜 [1:a]）→ [vout]。都沒有就回傳 None"""
    if not spec_ranges and not karaoke:
        return None
    # 照片段是「一張圖停幾秒」：先轉 yuv420p 再補成每秒 60 格（顏色轉換每張圖只做一次），頻譜才會一直跳
    parts = ["[0:v]format=yuv420p,fps=60[v0]"]
    cur = "[v0]"
    if karaoke:
        parts.append("[2:v]format=rgba[kara]")
        parts.append(f"{cur}[kara]overlay=x=0:y={KARAOKE_STRIP_Y}:eof_action=pass:format=yuv420[v1]")
        cur = "[v1]"
    if spec_ranges:
        enable = "+".join(f"gte(t,{a:.3f})*lt(t,{b:.3f})" for a, b in spec_ranges)
        col = "0x" + color_hex.lstrip("#")
        parts.append("[1:a]aformat=channel_layouts=mono,"
                     f"showfreqs=s=60x36:rate=60:mode=bar:ascale=cbrt:fscale=log:win_size=2048:colors={col},"
                     # 放大後每 12px 畫一條 3px 黑線當柱子間隔，再把黑色去背
                     f"scale={SPECTRUM_W}:{SPECTRUM_H}:flags=neighbor,drawgrid=w=12:h={SPECTRUM_H * 4}:t=3:c=black,"
                     "format=rgba,colorkey=black:0.05:0.0[spec]")
        parts.append(f"{cur}[spec]overlay=x={SPECTRUM_X}:y={SPECTRUM_Y}:eof_action=pass:format=yuv420:enable='{enable}'[vout]")
    else:
        parts[-1] = parts[-1][:-len("[v1]")] + "[vout]"
    return ";".join(parts)


def spectrum_filter(ranges: List[Tuple[float, float]], color_hex: str = "#f5d787") -> Optional[str]:
    return build_video_filter(ranges, color_hex) if ranges else None


# ---------------------------------------------------------------------------
# [Claude 2026-10-26] Whisper 逐字時間：自動找間奏、字幕逐字跳金
# ---------------------------------------------------------------------------
_WHISPER_CACHE: Dict[str, Any] = {}


def load_whisper_words(proj: Dict[str, Any], min_prob: float = 0.1) -> List[Dict[str, Any]]:
    """Whisper 結果攤平成一個個字（只留有長度的字；機率低於 min_prob 的略過）。
    [Claude 2026-10-27] 找間奏用 0.1（略過器樂段幻聽）；逐字變金用 0——台語被聽成國語時句首常是低把握的字，
    但那是真的有唱的音（《南都夜曲》：人、電、天…），丟掉會讓整句金色從錯的位置開始。"""
    w_path = str(proj.get("whisper_json") or "")
    if not w_path or not os.path.exists(w_path):
        return []
    key = f"{w_path}|{os.path.getmtime(w_path)}|{min_prob}"
    if key in _WHISPER_CACHE:
        return _WHISPER_CACHE[key]
    try:
        with open(w_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []
    segs = raw.get("segments", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    words = []
    for sg in segs:
        for w in (sg.get("words") or []):
            try:
                st, et = float(w.get("start", 0)), float(w.get("end", 0))
            except (TypeError, ValueError):
                continue
            txt = str(w.get("word", "")).strip()
            if et - st < 0.02 or not txt or float(w.get("probability", 1.0) or 0) < min_prob:
                continue
            words.append({"word": txt, "start": st, "end": et})
    words.sort(key=lambda x: x["start"])
    if len(_WHISPER_CACHE) > 8:
        _WHISPER_CACHE.clear()
    _WHISPER_CACHE[key] = words
    return words


def detect_interlude_candidates(words: List[Dict[str, Any]], timeline: List[Dict[str, Any]], min_gap: float = 8.0,
                                tail_ext: float = 2.5, early_lead: float = -0.7) -> List[Dict[str, Any]]:
    """人聲停 min_gap 秒以上（第一個字之前＝前奏、最後一個字之後＝尾奏，不算）＝間奏候選。
    間奏從「前一個字結束＋尾韻延展」開始，到「下一個字開始＋提前量」結束（跟歌詞對齊規則一樣）。"""
    out = []
    for a, b in zip(words, words[1:]):
        gap = b["start"] - a["end"]
        if gap < min_gap:
            continue
        st = round(a["end"] + min(max(0.0, tail_ext), gap * 0.3), 2)
        et = round(b["start"] + min(0.0, early_lead), 2)
        if et - st < 1.0:
            continue
        cand = {"start": st, "end": et, "gap": round(gap, 1), "voice_end": round(a["end"], 2), "voice_start": round(b["start"], 2),
                "locked_overlap": [], "lyric_overlap": [], "existing": False}
        for i, s in enumerate(timeline or []):
            ov = min(et, float(s["end"])) - max(st, float(s["start"]))
            if ov <= 0.01:
                continue
            if s.get("type") in INTERLUDE_TYPES and ov >= 0.5 * min(et - st, float(s["end"]) - float(s["start"])):
                cand["existing"] = True
            if s.get("locked"):
                cand["locked_overlap"].append(i)
            elif _is_plain_lyric(s) and ov >= 0.5 * (float(s["end"]) - float(s["start"])):
                cand["lyric_overlap"].append(i)
        out.append(cand)
    return out


def _sig_char(ch: str) -> bool:
    return bool(re.match(r"[\u3400-\u9fff\uf900-\ufaffA-Za-z0-9\u3040-\u30ff\uac00-\ud7af]", ch))


KARAOKE_TIMING_MODES = ("voice", "even")


def _align_positions(a: List[str], b: List[str]) -> List[Optional[int]]:
    """歌詞字 a 對唱出來的音 b：編輯距離對齊，同字 0 分、不同字也照位置配對（0.6 分）、多唱或少唱一個 1 分。
    回傳 a 每個字配到 b 的哪一個（沒配到是 None）。台語被聽成國語同音字時，字不同但位置對得上。"""
    n, m = len(a), len(b)
    INF = float("inf")
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    B: List[List[Any]] = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            d = D[i][j]
            if d == INF:
                continue
            if i < n and j < m:
                c = d + (0.0 if a[i] == b[j] else 0.6)
                if c < D[i + 1][j + 1]:
                    D[i + 1][j + 1], B[i + 1][j + 1] = c, (i, j, True)
            # [Claude 2026-10-27] Whisper 漏聽一個音（例：「啊～啊～」只聽到一個啊）時，同分的情況下寧可讓「後面的字」沒配到：
            # 沒配到的字會在前後兩個音中間平均亮起；原本會讓第一個字沒配到，結果兩個「啊」同時亮
            # 跟前一個字一樣的字（「啊～啊～」「亂亂」）最可能是 Whisper 併成一個音：讓它沒配到的代價低一點
            dc = ((0.9 if i > 0 and a[i] == a[i - 1] else 1.0) + 0.01 * (n - i) / max(1, n)) if i < n else 0.0
            if i < n and d + dc < D[i + 1][j]:
                D[i + 1][j], B[i + 1][j] = d + dc, (i, j, False)
            if j < m and d + 1.0 < D[i][j + 1]:
                D[i][j + 1], B[i][j + 1] = d + 1.0, (i, j, False)
    out: List[Optional[int]] = [None] * n
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, paired = B[i][j]
        if paired:
            out[pi] = pj
        i, j = pi, pj
    return out


KARAOKE_ADVANCE_DEFAULT = 0.30   # [Claude 2026-10-27] 使用者：金色比人聲提前 300ms，看的人有反應延遲


def karaoke_advance(proj: Dict[str, Any]) -> float:
    try:
        v = float(proj.get("karaoke_advance", KARAOKE_ADVANCE_DEFAULT))
    except (TypeError, ValueError):
        v = KARAOKE_ADVANCE_DEFAULT
    return round(min(1.0, max(0.0, v)), 2)


def karaoke_char_times(text: str, seg_start: float, seg_end: float, words: List[Dict[str, Any]],
                       lead_abs: float = 0.7, mode: str = "voice", advance: float = 0.0) -> List[Optional[float]]:
    """字幕每個字什麼時候變金色（跟 text 一樣長；標點空白是 None，跟著前一個字）。
    mode="voice"（跟著人聲）：歌詞第幾個字對到這段時間內唱出來的第幾個音（_align_positions），沒對到的字前後內插。
    mode="even"（平均分散）：第一個字在人聲開始時亮、最後一個字在最後一個音時亮，中間平均分配（使用者提的選項）。
    這段時間 Whisper 沒有字 → 兩種都整句平均分配（從提前量之後開始）。"""
    idx = [i for i, ch in enumerate(text) if _sig_char(ch)]
    res: List[Optional[float]] = [None] * len(text)
    if not idx:
        return res
    wch = []
    last_end = None
    for w in words:
        if w["start"] < seg_start - 0.05 or w["start"] >= seg_end:
            continue
        chs = [c for c in w["word"] if _sig_char(c)]
        if not chs:
            continue
        last_end = w["end"] if last_end is None else max(last_end, w["end"])
        step = (w["end"] - w["start"]) / len(chs)
        for k, c in enumerate(chs):
            wch.append((TRAD_TO_SIMP.get(c, c).lower(), w["start"] + k * step))
    n = len(idx)
    t: List[Optional[float]] = [None] * n
    if wch and mode == "even":
        first, last = wch[0][1], wch[-1][1]
        for k in range(n):
            t[k] = first + (last - first) * (k / max(1, n - 1))
    elif wch:
        a = [TRAD_TO_SIMP.get(text[i], text[i]).lower() for i in idx]
        for k, j in enumerate(_align_positions(a, [c for c, _ in wch])):
            if j is not None:
                t[k] = wch[j][1]
        # 句尾沒配到的字：在最後一個音唱的期間平均亮完（原本全部擠在最後一個音開始的瞬間）
        first, last = wch[0][1], max(wch[-1][1], min(seg_end, float(last_end)) - 0.25)
    else:
        first = min(seg_end, seg_start + max(0.0, lead_abs))
        last = first + 0.85 * max(0.0, seg_end - first)
        for k in range(n):
            t[k] = first + (last - first) * (k / max(1, n - 1))
    known = [k for k in range(n) if t[k] is not None]
    for k in range(n):
        if t[k] is not None:
            continue
        lo = max((j for j in known if j < k), default=None)
        hi = min((j for j in known if j > k), default=None)
        if lo is not None and hi is not None:
            t[k] = t[lo] + (t[hi] - t[lo]) * (k - lo) / (hi - lo)
        elif hi is not None:      # 開頭沒比到：從 first 拉到第一個比到的字
            t[k] = first + (t[hi] - first) * (k / hi) if hi else t[hi]
        elif lo is not None:      # 結尾沒比到：從最後比到的字拉到 last
            span = max(1, n - 1 - lo)
            t[k] = t[lo] + (max(last, t[lo]) - t[lo]) * (k - lo) / span
    prev = seg_start
    for k in range(n):        # 提前 advance 秒；不倒退、在段落裡面
        v = min(max(float(t[k]) - max(0.0, advance), prev, seg_start), seg_end)
        t[k] = prev = round(v, 3)
    for k, i in enumerate(idx):
        res[i] = t[k]
    return res


def karaoke_steps(text: str, times: List[Optional[float]]) -> List[Tuple[float, int]]:
    """[(時間, 變金的字數)]：標點空白跟著前一個字一起變"""
    steps: List[Tuple[float, int]] = []
    for i, tm in enumerate(times):
        if tm is None:
            continue
        j = i + 1
        while j < len(text) and times[j] is None:
            j += 1
        if steps and abs(steps[-1][0] - tm) < 1e-6:
            steps[-1] = (tm, j)
        else:
            steps.append((tm, j))
    return steps


def karaoke_enabled_for(seg: Dict[str, Any]) -> bool:
    return _is_plain_lyric(seg) and bool(str(seg.get("text", "")).strip())


KARAOKE_STRIP_Y, KARAOKE_STRIP_H = 840, 150
KARAOKE_GOLD = (255, 205, 80, 255)


def subtitle_layout(text: str, seg_type: str):
    """字幕字型與位置（跟 render_overlay_rgba 完全一樣）"""
    clean = sanitize_no_ai(text, text)
    inst = clean.startswith("～") or seg_type in ("intro", "interlude", "outro", "solo")
    font = _font(False, 40) if inst else _font(True, 50)
    bbox = ImageDraw.Draw(Image.new("RGBA", (8, 8))).textbbox((0, 0), clean, font=font)
    return clean, font, (FRAME_W - (bbox[2] - bbox[0])) // 2, FRAME_H - 180


def render_karaoke_strip(text: str, seg_type: str, n_gold: int) -> Image.Image:
    """透明字條（1920×150，從 y=840 起）：前 n_gold 個字畫成金色，剛好蓋在白字上"""
    clean, font, lx, ly = subtitle_layout(text, seg_type)
    im = Image.new("RGBA", (FRAME_W, KARAOKE_STRIP_H), (0, 0, 0, 0))
    if n_gold > 0:
        ImageDraw.Draw(im).text((lx, ly - KARAOKE_STRIP_Y), clean[:n_gold], font=font, fill=KARAOKE_GOLD)
    return im


def _install_rendered_mv(tmp_out: str, output_mv: str) -> None:
    """[Claude 2026-10-26] 把編好的暫存檔換成正式成品。
    Windows 上舊 MV 若正被開著（網頁播放器透過 /media/file 讀取、外部播放器），改名會 WinError 5：
    先重試幾次；仍被占用就直接覆寫內容（別的程式以一般讀取方式開著時，Windows 允許覆寫但不允許改名）；
    真的寫不進去才報錯，並說明新檔在哪裡。"""
    last = None
    for _ in range(8):
        try:
            os.replace(tmp_out, output_mv)
            return
        except PermissionError as e:
            last = e
            time.sleep(0.5)
    try:
        with open(tmp_out, "rb") as src, open(output_mv, "wb") as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
    except OSError as e:
        raise RuntimeError(f"成品 MV 正被其他程式開著（例如影片播放器），無法覆寫：{output_mv}。"
                           f"新的 MV 已做好，在 {tmp_out}；關掉播放後再合成一次即可。（{e}）") from e
    try:
        os.remove(tmp_out)
    except OSError:
        pass
    print(f"[MV] 成品被占用無法改名（{last}），已改用覆寫內容：{output_mv}")


def execute_mv_render_pipeline(proj: Dict[str, Any]) -> Dict[str, Any]:
    """[Claude 2026-10-26] 包一層：取消或失敗時進度明確顯示「已取消／渲染失敗」，不會留在進行中或顯示完成"""
    global CANCEL_REQUESTED
    CANCEL_REQUESTED = False
    try:
        return _execute_mv_render_pipeline(proj)
    except RenderCancelled:
        update_progress(False, "render", 0, "⏹️ 已取消 MV 合成", "")
        raise
    except Exception as e:
        update_progress(False, "render", 0, "❌ MV 合成失敗", str(e)[:300])
        raise
    finally:
        CANCEL_REQUESTED = False


def _execute_mv_render_pipeline(proj: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    slug = proj["slug"]
    title = proj.get("title", slug)
    update_progress(True, "render", 2, f"🎬 準備合成《{title}》1080p 60fps MV...", "正在檢查母帶音源與分鏡資產")

    frames_dir = os.path.join(project_dir(slug), "frames")
    os.makedirs(frames_dir, exist_ok=True)
    sig_file = os.path.join(frames_dir, "frame_signatures.json")
    old_sigs = {}
    if os.path.exists(sig_file):
        try:
            with open(sig_file, "r", encoding="utf-8") as f:
                old_sigs = json.load(f)
        except Exception:
            old_sigs = {}

    output_mv = proj.get("output_mv") or default_output_mv(proj)
    os.makedirs(os.path.dirname(output_mv), exist_ok=True)
    audio_file = proj.get("audio_file", "")
    if not os.path.exists(audio_file):
        update_progress(False, "render", 0, "渲染失敗", f"找不到指定的音源檔案：{audio_file}")
        raise ValueError(f"找不到指定的音源檔案：{audio_file}")

    bg_cache: Dict[Any, Image.Image] = {}
    base_frames = []
    timeline = proj.get("timeline", [])
    if not timeline:
        au_probe = probe_media_file(audio_file)
        tot_d = float(au_probe.get("duration", 240.0) or 240.0)
        sc_cnt = count_existing_scene_images(proj.get("illust_dir", "")) or int(proj.get("scene_count", 12) or 12)
        timeline = build_guaranteed_fallback_timeline([], tot_d, -0.70, title, sc_cnt)
        proj["timeline"] = timeline
        save_project_dict(proj)

    # [Claude 2026-10-26] 簽名多含 title_spaced／studio／前奏片尾說明：改這些也會重畫（原本不會）
    header_sig = "|".join(str(proj.get(k)) for k in ("title", "badge", "lyricist", "composer", "original_singer", "cover_singer",
                                                      "studio", "title_spaced", "intro_desc", "outro_desc"))
    new_sigs = {}
    total_segs = len(timeline)
    ov_cache: Dict[int, Image.Image] = {}

    def _overlay(i: int) -> Image.Image:
        if i not in ov_cache:
            ov_cache[i] = render_overlay_rgba(proj, timeline[i])
        return ov_cache[i]

    for idx, seg in enumerate(timeline):
        _check_cancel()
        pct = 4 + int((idx + 1) / max(1, total_segs) * 26)
        short_lyric = str(seg.get("text", ""))[:20]
        update_progress(
            True, "render", pct,
            f"🖼️ [階段 1/4] 正在合成 1080p 漸層暗角與金框字幕底圖 ({idx + 1}/{total_segs})",
            f"Scene {seg.get('scene', 1):02d} | 「{short_lyric}」"
        )
        st = float(seg["start"])
        et = float(seg["end"])
        dur = max(0.1, et - st)
        sc_id = int(seg.get("scene", 1))
        sc_path = seg_photo_path(proj, seg)
        sc_mtime = int(os.path.getmtime(sc_path)) if sc_path and os.path.exists(sc_path) else 0
        # [Claude 2026-10-26] 用專屬照片或「照片＋字」時簽名多帶這些（沒用到時簽名跟以前一樣，舊專案不用重畫）
        extra_sig = ""
        if os.path.basename(sc_path).startswith("inst_") or seg.get("display", "card") != "card":
            extra_sig = f"|{os.path.basename(sc_path)}|{seg.get('display', 'card')}"
        seg_sig = hashlib.md5(f"{header_sig}|{sc_id}|{sc_mtime}|{seg.get('type')}|{seg.get('text')}{extra_sig}".encode("utf-8")).hexdigest()
        new_sigs[f"base_{idx:03d}"] = seg_sig

        frame_path = os.path.join(frames_dir, f"base_{idx:03d}.png")
        if not (old_sigs.get(f"base_{idx:03d}") == seg_sig and os.path.exists(frame_path)):
            compose_frame(render_background(proj, seg, bg_cache), _overlay(idx)).save(frame_path, compress_level=1)
        base_frames.append((frame_path, sc_id, sc_path, st, et, dur, seg_sig))

    # [Claude 2026-10-26] 轉場：照片層用 20 種樣式之一（固定／依序／隨機），文字層淡入淡出；
    # 格數跟秒數走（每秒 40 格）；前後同一張照片時照片不轉場。簽名含樣式、秒數、格數，換樣式才重畫。
    concat_lines = []
    TRANS_DURATION = max(0.1, float(proj.get("trans_duration", 0.40) or 0.40))
    TRANS_STEPS = transition_steps(TRANS_DURATION)
    total_trans_pairs = max(1, len(base_frames) - 1)
    plan = transition_plan(proj, max(0, len(base_frames) - 1))

    # [Claude 2026-10-26] 逐字跳金（使用者：一個字一個字跳金）：每句算出每個字變金的時間；
    # 停留畫面用另一條透明「金字條」影片疊上去（不用每個字重畫整張圖）；轉場畫面則把當下已變金的字畫進去
    kara_on = bool(proj.get("karaoke_enabled", True))
    kara_steps: Dict[int, List[Tuple[float, int]]] = {}
    kara_text: Dict[int, str] = {}
    if kara_on:
        _words = load_whisper_words(proj, 0.0)
        _lead = abs(float(proj.get("early_lead_applied", -0.70) or 0.0))
        _mode = proj.get("karaoke_timing") if proj.get("karaoke_timing") in KARAOKE_TIMING_MODES else "voice"
        for _i, _sg in enumerate(timeline):
            if karaoke_enabled_for(_sg):
                _clean = subtitle_layout(str(_sg.get("text", "")), str(_sg.get("type", "lyric")))[0]
                _tm = karaoke_char_times(_clean, float(_sg["start"]), float(_sg["end"]), _words, _lead, _mode, karaoke_advance(proj))
                _st = karaoke_steps(_clean, _tm)
                if _st:
                    kara_steps[_i], kara_text[_i] = _st, _clean
        kara_on = bool(kara_steps)

    def _gold_at(i: int, offset: float) -> int:
        n = 0
        for tm, k in kara_steps.get(i, []):
            if tm - float(timeline[i]["start"]) <= offset + 1e-6:
                n = k
        return n

    for idx in range(len(base_frames)):
        _check_cancel()
        curr_path, curr_sc, curr_scp, st, et, dur, curr_sig = base_frames[idx]
        if idx < len(base_frames) - 1:
            style = plan[idx]
            style_label = dict(TRANSITION_STYLES).get(style, style)
            pct = 30 + int((idx + 1) / total_trans_pairs * 35)
            update_progress(
                True, "render", pct,
                f"✨ [階段 2/4] 正在生成 {TRANS_DURATION:.2f}s 轉場（{style_label}）({idx + 1}/{total_trans_pairs} 組)",
                f"已合成 {(idx + 1) * TRANS_STEPS}/{total_trans_pairs * TRANS_STEPS} 張過渡幀"
            )
            next_path, next_sc, next_scp, _, _, _, next_sig = base_frames[idx + 1]
            # [Claude 2026-10-26] 以實際照片檔判斷（間奏用專屬照片時，跟同 Scene 的歌詞段要照常轉場）
            same_photo = (curr_scp == next_scp) if (curr_scp or next_scp) else (curr_sc == next_sc)
            hold_dur = max(0.05, dur - TRANS_DURATION)
            concat_lines.append(f"file '{curr_path}'\n")
            concat_lines.append(f"duration {hold_dur:.4f}\n")

            pair_sig = f"{curr_sig}_{next_sig}_{style}_{TRANS_DURATION:.3f}_{TRANS_STEPS}_{int(same_photo)}"
            gold_end = _gold_at(idx, hold_dur) if kara_on else 0
            if gold_end:
                pair_sig += f"_k{gold_end}"
            pair_key = f"trans_{idx:03d}"
            new_sigs[pair_key] = pair_sig
            step_dur = TRANS_DURATION / TRANS_STEPS
            trans_paths = [os.path.join(frames_dir, f"trans_{idx:03d}_{step:02d}.png") for step in range(1, TRANS_STEPS + 1)]
            if not (old_sigs.get(pair_key) == pair_sig and all(os.path.exists(tp) for tp in (trans_paths[0], trans_paths[-1]))):
                bgA = render_background(proj, timeline[idx], bg_cache)
                bgB = render_background(proj, timeline[idx + 1], bg_cache)
                ovA, ovB = _overlay(idx), _overlay(idx + 1)
                if gold_end:
                    ovA = ovA.copy()
                    ovA.alpha_composite(render_karaoke_strip(str(timeline[idx].get("text", "")), str(timeline[idx].get("type", "lyric")), gold_end), (0, KARAOKE_STRIP_Y))
                for step, tp in enumerate(trans_paths, start=1):
                    if step % 4 == 0:
                        _check_cancel()
                    sm = 0.5 - 0.5 * math.cos((step / float(TRANS_STEPS)) * math.pi)
                    compose_transition_frame(style, bgA, bgB, ovA, ovB, sm, same_photo).save(tp, compress_level=1)
            for tp in trans_paths:
                concat_lines.append(f"file '{tp}'\n")
                concat_lines.append(f"duration {step_dur:.4f}\n")
        else:
            concat_lines.append(f"file '{curr_path}'\n")
            concat_lines.append(f"duration {dur:.4f}\n")

    with open(sig_file, "w", encoding="utf-8") as f:
        json.dump(new_sigs, f, indent=2)

    concat_lines.append(f"file '{base_frames[-1][0]}'\n")
    concat_file = os.path.join(frames_dir, "concat.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        f.writelines(concat_lines)

    update_progress(
        True, "render", 70,
        "🎬 [階段 3/4] 正在執行 NVENC 1080p 60fps 硬體加速編碼封裝...",
        "h264_nvenc (-preset p5 -b:v 8M -r 60) + AAC 320k 高音質母帶"
    )
    # [Claude 2026-10-26] 先編到暫存檔，成功才取代正式成品：失敗時舊 MV 不會被當成新成品驗收。
    # 原本的備援把 cmd[9]（音檔路徑）換成 libx264、cmd[11] 換成 veryfast，必失敗；而且兩次都不檢查結果。
    tmp_out = os.path.splitext(output_mv)[0] + ".rendering.mp4"

    # 成品裡每段的位置（跟 concat 一樣從 0 累加）
    positions: List[Tuple[float, float]] = []
    _pos = 0.0
    for _i, _bf in enumerate(base_frames):
        _d = _bf[5]
        positions.append((_pos, _pos + _d))
        _pos += (max(0.05, _d - TRANS_DURATION) + TRANS_DURATION) if _i < len(base_frames) - 1 else _d
    spec_ranges = spectrum_ranges(timeline, positions) if proj.get("spectrum_enabled", True) else []

    # 金字條影片：跟照片串同樣的時間切法；停留時照每個字的時間換圖，轉場期間是空的（轉場畫面自己帶金字）
    kara_args: List[str] = []
    if kara_on:
        kdir = os.path.join(frames_dir, "karaoke")
        os.makedirs(kdir, exist_ok=True)
        empty_p = os.path.join(kdir, "k_empty.png")
        if not os.path.exists(empty_p):
            Image.new("RGBA", (FRAME_W, KARAOKE_STRIP_H), (0, 0, 0, 0)).save(empty_p)

        def _strip(i: int, n: int) -> str:
            if n <= 0:
                return empty_p
            sg = timeline[i]
            hsh = hashlib.md5(f"{kara_text[i]}|{sg.get('type')}|{n}".encode("utf-8")).hexdigest()[:16]
            kp = os.path.join(kdir, f"k_{hsh}.png")
            if not os.path.exists(kp):
                render_karaoke_strip(str(sg.get("text", "")), str(sg.get("type", "lyric")), n).save(kp)
            return kp

        k_lines: List[str] = []

        def _kadd(path: str, d: float):
            if d > 1e-4:
                k_lines.append(f"file '{path}'\nduration {d:.4f}\n")

        last_i = len(base_frames) - 1
        for i in range(len(base_frames)):
            if i % 8 == 0:
                _check_cancel()
            d = base_frames[i][5]
            hold = d if i == last_i else max(0.05, d - TRANS_DURATION)
            cur_t, cur_n = 0.0, 0
            for tm, n in kara_steps.get(i, []):
                o = min(max(0.0, tm - float(timeline[i]["start"])), hold)
                if o > cur_t:
                    _kadd(_strip(i, cur_n), o - cur_t)
                    cur_t = o
                cur_n = n
            _kadd(_strip(i, cur_n), hold - cur_t)
            if i != last_i:
                _kadd(empty_p, TRANS_DURATION)
        k_lines.append(f"file '{empty_p}'\n")
        kara_concat = os.path.join(frames_dir, "karaoke_concat.txt")
        with open(kara_concat, "w", encoding="utf-8") as f:
            f.writelines(k_lines)
        kara_args = ["-f", "concat", "-safe", "0", "-i", kara_concat]
    vfc = build_video_filter(spec_ranges, spectrum_color_hex(proj), karaoke=kara_on)

    def _encode_cmd(video_codec_args: List[str]) -> List[str]:
        vf_args = ["-filter_complex", vfc, "-map", "[vout]", "-map", "1:a"] if vfc else []
        return [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-i", audio_file, *kara_args, *vf_args,
                *video_codec_args, "-r", "60", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "320k", "-shortest", tmp_out]

    attempts = [
        ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p5", "-b:v", "8M"]),
        ("libx264", ["-c:v", "libx264", "-preset", "veryfast", "-b:v", "8M"]),
    ]
    encoder_used = ""
    last_err = ""
    global ACTIVE_RENDER_PROC
    for enc_name, enc_args in attempts:
        _check_cancel()
        if enc_name == "libx264":
            update_progress(True, "render", 72, "🎬 [階段 3/4] 顯示卡編碼失敗，改用 CPU（libx264）編碼，會比較慢...", last_err[-160:])
        try:
            proc = subprocess.Popen(_encode_cmd(enc_args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
            ACTIVE_RENDER_PROC = proc
            _, err_b = proc.communicate()
        finally:
            ACTIVE_RENDER_PROC = None
        _check_cancel()
        if proc.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
            encoder_used = enc_name
            break
        last_err = (err_b or b"").decode("utf-8", errors="replace").strip()
    if not encoder_used:
        raise RuntimeError(f"ffmpeg 編碼失敗（NVENC 與 libx264 都失敗）：{last_err[-300:]}")
    _install_rendered_mv(tmp_out, output_mv)

    update_progress(
        True, "render", 92,
        "🔍 [階段 4/4] 正在執行 ffprobe 物理規格檢驗與關鍵秒數抽幀驗收...",
        f"輸出檔案：{os.path.basename(output_mv)}"
    )
    elapsed = round(time.time() - t0, 2)
    verify_res = execute_mv_verification(proj, custom_timestamps=None)
    update_progress(
        False, "render", 100,
        f"🎉《{title}》1080p 60fps MV 合成渲染與驗收完成！(耗時 {elapsed}s)",
        f"編碼器：{encoder_used} | 輸出：{output_mv}"
    )
    return {
        "status": "ok",
        "elapsed_sec": elapsed,
        "encoder": encoder_used,
        "output_mv": output_mv,
        "verification": verify_res
    }


def execute_mv_verification(proj: Dict[str, Any], custom_timestamps: Optional[List[float]] = None) -> Dict[str, Any]:
    slug = proj["slug"]
    output_mv = proj.get("output_mv", "")
    probe = probe_media_file(output_mv)
    if not probe.get("exists"):
        return {"exists": False, "output_mv": output_mv}

    verify_dir = os.path.join(project_dir(slug), "verify")
    os.makedirs(verify_dir, exist_ok=True)
    report_json = os.path.join(verify_dir, "verify_report.json")

    timeline = proj.get("timeline", [])
    extract_targets = []
    if custom_timestamps:
        for i, ts in enumerate(custom_timestamps):
            extract_targets.append((float(ts), f"custom_{i+1}_{int(ts)}s.png", f"自訂檢驗點 {ts:.2f}s"))
    else:
        picks = []
        if len(timeline) > 0:
            picks.append((timeline[0], "開場名牌卡 (Intro)"))
        if len(timeline) > 1:
            picks.append((timeline[1], "第一句主歌進字"))
        for idx, seg in enumerate(timeline):
            if seg.get("type") in ("interlude", "solo"):
                if idx > 0:
                    prev_s = timeline[idx - 1]
                    tail_ts = max(float(prev_s["start"]) + 1.0, float(prev_s["end"]) - 1.5)
                    extract_targets.append((round(tail_ts, 2), f"{slug}_pre_interlude_{int(tail_ts)}s.png", f"間奏前延展包覆 ({tail_ts:.1f}s)"))
                mid_inter = (float(seg["start"]) + float(seg["end"])) / 2.0
                extract_targets.append((round(mid_inter, 2), f"{slug}_interlude_{int(mid_inter)}s.png", f"間奏空鏡 ({mid_inter:.1f}s)"))
                if idx + 1 < len(timeline):
                    nxt_s = timeline[idx + 1]
                    nxt_ts = float(nxt_s["start"]) + 1.0
                    extract_targets.append((round(nxt_ts, 2), f"{slug}_post_interlude_{int(nxt_ts)}s.png", f"間奏後副歌切換 ({nxt_ts:.1f}s)"))
                break
        if len(timeline) >= 2:
            last_lyric = timeline[-2]
            last_ts = max(float(last_lyric["start"]) + 1.0, float(last_lyric["end"]) - 1.5)
            extract_targets.append((round(last_ts, 2), f"{slug}_last_lyric_tail_{int(last_ts)}s.png", f"片尾前字幕延展 ({last_ts:.1f}s)"))
            outro_seg = timeline[-1]
            outro_ts = min(probe.get("duration", float(outro_seg["end"])) - 1.5, float(outro_seg["start"]) + 3.0)
            extract_targets.append((round(max(0.5, outro_ts), 2), f"{slug}_outro_card_{int(outro_ts)}s.png", f"片尾榮譽名牌卡 ({outro_ts:.1f}s)"))

        for seg, label in picks:
            ts = round(float(seg["start"]) + min(2.5, (float(seg["end"]) - float(seg["start"])) * 0.4), 2)
            extract_targets.insert(0, (ts, f"{slug}_pick_{int(ts)}s.png", f"{label} ({ts:.1f}s)"))

    frames_out = []
    seen_ts = set()
    for ts, fname, desc in extract_targets:
        if ts in seen_ts:
            continue
        seen_ts.add(ts)
        out_fp = os.path.join(verify_dir, fname)
        cmd_ext = [
            FFMPEG, "-y", "-ss", str(ts),
            "-i", output_mv,
            "-vframes", "1", "-q:v", "2",
            out_fp
        ]
        subprocess.run(cmd_ext, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
        if os.path.exists(out_fp):
            frames_out.append({
                "timestamp": ts,
                "mmss": f"{int(ts // 60):02d}:{ts % 60:05.2f}",
                "description": desc,
                "path": out_fp,
                "size_kb": round(os.path.getsize(out_fp) / 1024, 1)
            })

    frames_out.sort(key=lambda x: x["timestamp"])
    result = {
        "exists": True,
        "probe": probe,
        "frames": frames_out
    }
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ==== tilde ====
# ---------------------------------------------------------------------------
# [Claude 2026-10-26] 使用者自己加的間奏（user=True）在重新對齊／重貼歌詞時要保留：
# 時間照使用者設的，前後歌詞讓開（有 Whisper 時把間奏當固定區段重跑一次對齊；其他情況把相鄰段落裁短或等比例壓縮）
# ---------------------------------------------------------------------------
def normalize_tilde(txt: str) -> str:
    """[Claude 2026-10-27] 使用者打的半形 ~ 或 〜 當成全形 ～（前奏／間奏／尾奏行靠開頭的 ～ 辨認）"""
    t = re.sub(r"^[~〜]", "～", str(txt or "").strip())
    return re.sub(r"[~〜]$", "～", t)


def is_kept_instrumental_line(seg: Dict[str, Any]) -> bool:
    """[Claude 2026-10-27] 歌詞裡寫的「～ 間奏 ～」行（當一般場景用）：重新對齊沿用舊歌詞時要保留，不能當成前奏尾奏丟掉"""
    txt = str(seg.get("text", ""))
    return (seg.get("type", "lyric") in ("lyric",) + INTERLUDE_TYPES and not seg.get("user")
            and txt.startswith("～") and ("間奏" in txt or "间奏" in txt))


def is_user_interlude(seg: Dict[str, Any]) -> bool:
    return seg.get("type") in INTERLUDE_TYPES and bool(seg.get("user"))


def _is_plain_lyric(seg: Dict[str, Any]) -> bool:
    return seg.get("type", "lyric") == "lyric" and not str(seg.get("text", "")).startswith("～")


def _fit_run(run: List[Dict[str, Any]], w0: float, w1: float, min_dur: float = 0.40) -> None:
    """把一串（未鎖定）段落塞進 [w0, w1]：先只動兩端（裁短），塞不下再依原本比例壓縮"""
    if not run:
        return
    w0, w1 = round(w0, 2), round(w1, 2)
    old = [(float(x["start"]), float(x["end"])) for x in run]
    run[0]["start"] = w0
    run[-1]["end"] = w1
    for k in range(len(run) - 1):
        b = min(max(float(run[k]["end"]), w0), w1)
        run[k]["end"] = run[k + 1]["start"] = round(b, 2)
    if all(float(x["end"]) - float(x["start"]) >= min_dur - 1e-6 for x in run):
        return
    n = len(run)
    if w1 - w0 < n * min_dur:
        step = (w1 - w0) / n
        b = [w0 + step * k for k in range(n + 1)]
    else:
        durs = [max(0.0, e - s0) for s0, e in old]
        tot = sum(durs) or 1.0
        spare = (w1 - w0) - n * min_dur
        b = [w0]
        for d in durs:
            b.append(b[-1] + min_dur + spare * d / tot)
    b[-1] = w1
    for k in range(n):
        run[k]["start"] = round(b[k], 2)
        run[k]["end"] = round(b[k + 1], 2)


def splice_interlude(tl: List[Dict[str, Any]], iv: Dict[str, Any], total_dur: float, min_dur: float = 0.40) -> bool:
    """把一段間奏（固定時間）插回時間軸，前後未鎖定段落讓開；成功回傳 True"""
    s0 = max(0.0, float(iv["start"]))
    e0 = min(float(total_dur), float(iv["end"]))
    mid = (s0 + e0) / 2.0
    k = 0
    while k < len(tl) and (float(tl[k]["start"]) + float(tl[k]["end"])) / 2.0 < mid:
        k += 1
    j = k - 1
    while j >= 0 and not tl[j].get("locked"):
        j -= 1
    m = k
    while m < len(tl) and not tl[m].get("locked"):
        m += 1
    left_bound = float(tl[j]["end"]) if j >= 0 else 0.0
    right_bound = float(tl[m]["start"]) if m < len(tl) else float(total_dur)
    left_run, right_run = tl[j + 1:k], tl[k:m]
    s1 = max(s0, left_bound + len(left_run) * min_dur)
    e1 = min(e0, right_bound - len(right_run) * min_dur)
    if not left_run:
        s1 = left_bound
    if not right_run:
        e1 = right_bound
    if e1 - s1 < min_dur:
        return False
    _fit_run(left_run, left_bound, s1, min_dur)
    _fit_run(right_run, e1, right_bound, min_dur)
    d = dict(iv)
    d["start"], d["end"] = round(s1, 2), round(e1, 2)
    tl.insert(k, d)
    return True


def interlude_after_line(tl: List[Dict[str, Any]], iv: Dict[str, Any]) -> int:
    mid = (float(iv["start"]) + float(iv["end"])) / 2.0
    return sum(1 for x in tl if _is_plain_lyric(x) and (float(x["start"]) + float(x["end"])) / 2.0 < mid)


def restore_instrumentals(new_tl: List[Dict[str, Any]], old_tl: List[Dict[str, Any]], user_ivs: List[Dict[str, Any]],
                          total_dur: float, realign=None) -> (List[Dict[str, Any]], List[str]):
    """重新產生的時間軸：放回使用者的間奏、帶回前奏／尾奏的顯示方式與文字、舊間奏的 id（專屬照片對得上）"""
    notes: List[str] = []
    old_tl = old_tl or []
    ivs = sorted((dict(x) for x in user_ivs), key=lambda x: float(x["start"]))

    def _dup_of_user_iv(x):   # 例如貼回「含時間碼」歌詞時，間奏那行又被解析成一段間奏：跟使用者間奏重疊一半以上就視為同一段
        if x.get("type") not in INTERLUDE_TYPES or x.get("locked"):
            return False
        xs, xe = float(x["start"]), float(x["end"])
        for iv in ivs:
            ov = min(xe, float(iv["end"])) - max(xs, float(iv["start"]))
            if ov > 0 and ov >= 0.5 * min(xe - xs, float(iv["end"]) - float(iv["start"])):
                return True
        return False

    tl = [s for s in (new_tl or []) if not is_user_interlude(s) and not _dup_of_user_iv(s)]
    if ivs and realign is not None:
        try:
            anchors = []
            for iv in ivs:
                a = dict(iv)
                a["after_line"] = interlude_after_line(tl, iv)
                a["_orig_locked"] = bool(iv.get("locked"))
                anchors.append(a)
            tl2 = realign(anchors)
            got = [x for x in tl2 if x.get("_ianchor")]
            if len(got) == len(ivs):
                for x in tl2:
                    if x.pop("_ianchor", None):
                        x["locked"] = bool(x.pop("_orig_locked", False))
                        x["user"] = True
                tl = tl2
                ivs = []
        except Exception as e:
            notes.append(f"（間奏改用簡易方式放回：{e}）")
    for iv in ivs:
        if not splice_interlude(tl, iv, total_dur):
            notes.append(f"⚠️ 間奏「{iv.get('text', '')}」{iv.get('start')}~{iv.get('end')}s 跟鎖定段落重疊，沒有放回")
    for x in tl:
        x.pop("_ianchor", None)
        x.pop("_orig_locked", None)
    for tp in ("intro", "outro"):
        old = next((x for x in old_tl if x.get("type") == tp), None)
        if old:
            for x in tl:
                if x.get("type") == tp:
                    if old.get("display"):
                        x["display"] = old["display"]
                    if old.get("custom_text"):
                        x["text"] = old.get("text", x.get("text"))
                        x["custom_text"] = True
    old_auto = [x for x in old_tl if x.get("type") in INTERLUDE_TYPES and not x.get("user") and x.get("id")]
    new_auto = [x for x in tl if x.get("type") in INTERLUDE_TYPES and not x.get("user") and not x.get("id")]
    for o, n in zip(old_auto, new_auto):
        n["id"] = o["id"]
    for i in range(len(tl) - 1):
        if abs(float(tl[i]["end"]) - float(tl[i + 1]["start"])) > 1e-6:
            if not tl[i + 1].get("locked"):
                tl[i + 1]["start"] = tl[i]["end"]
            elif not tl[i].get("locked"):
                tl[i]["end"] = tl[i + 1]["start"]
    normalize_instrumental_fields(tl)
    return tl, notes


# ==== renumber ====
# ---------------------------------------------------------------------------
# [Claude 2026-10-27] 中途刪一張／插一張（使用者：照片照歌詞順序放，要能刪某張或插到某個位置）：
# 照片檔改號、時間軸的 scene 一起改號，時間軸不清空；刪掉那張原本用它的段落改用前一句的照片（使用者選）
# ---------------------------------------------------------------------------
MAX_SCENES = 36


def _scene_files(illust_dir: str, sid: int) -> List[str]:
    if not illust_dir or not os.path.isdir(illust_dir):
        return []
    out = []
    for fn in os.listdir(illust_dir):
        if not fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        if fn.lower() == f"scene_{sid:02d}.png" or fn.startswith(f"scene_{sid:02d}_"):
            out.append(fn)
    return out


def renumber_scene_files(illust_dir: str, mapping: Dict[int, int]) -> int:
    """照片檔改號（先全部改成暫存名再改成新號，避免互相覆蓋）。回傳改了幾個檔"""
    moves = []
    for old, new in mapping.items():
        if old == new:
            continue
        for fn in _scene_files(illust_dir, old):
            tmp = f"__renum_{old:02d}_{fn}"
            os.replace(os.path.join(illust_dir, fn), os.path.join(illust_dir, tmp))
            moves.append((tmp, f"scene_{new:02d}" + fn[len(f"scene_{old:02d}"):]))
    now = time.time()
    for tmp, final in moves:
        fp = os.path.join(illust_dir, final)
        os.replace(os.path.join(illust_dir, tmp), fp)
        os.utime(fp, (now, now))      # 改修改時間：合成快取與網頁縮圖才會更新
    return len(moves)


def _scene_payload(proj: Dict[str, Any]) -> List[Dict[str, Any]]:
    illust_dir = proj.get("illust_dir", "")
    tl_max = max([int(s.get("scene", 1)) for s in proj.get("timeline", [])] + [0])
    max_sc = max(tl_max, count_existing_scene_images(illust_dir), int(proj.get("scene_count", 12) or 12), 12)
    return list_scene_images(illust_dir, max_scene=max_sc)


