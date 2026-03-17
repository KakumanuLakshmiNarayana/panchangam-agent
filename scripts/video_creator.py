"""
video_creator.py — minimal modern redesign

Scenes:
  0  Intro    — city, date, tithi, nakshatra, rahu preview
  1  Bad      — Rahu Kalam + Durmuhurtam  (red accent)
  2  Good     — Brahma Muhurtam + Abhijit  (gold accent)
  3  Closing  — Sunrise/Sunset + blessing + Save/Share CTA

Visual style:
- Near-black (#080808) background — no temple arch, no decorations
- Clean typography: large bold values, muted labels, thin dividers
- No character animation in video
- Crossfade scene transitions (8 frames ≈ 0.33 s)
"""

import subprocess, os, tempfile, re
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from presenter_animator import draw_subtitle

W, H, FPS    = 1080, 1920, 24
SCRIPTS_DIR  = os.path.dirname(os.path.abspath(__file__))
CHARACTER_PATH = os.path.join(SCRIPTS_DIR, "pandit_character.png")
TELUGU_RE    = re.compile(r'[\u0C00-\u0C7F]')

# ── Colour palette ─────────────────────────────────────────────────────────────
BLACK   = (8,   8,   8)
WHITE   = (255, 255, 255)
MUTED   = (120, 120, 120)
GOLD    = (255, 200, 30)
RED     = (230, 60,  60)
SAFFRON = (255, 120, 0)
DIV_DIM = (45,  45,  45)

PAD = 60
CX  = W // 2

# ── Scene timing ───────────────────────────────────────────────────────────────
SCENE_WORD_COUNTS = [12, 9, 8, 10]
N_SCENES          = 4
MIN_SCENE_SECS    = 3

# ── Translation maps ───────────────────────────────────────────────────────────
TITHI_MAP = {
    "Ekadashi":   "ఏకాదశి",   "Dwadashi":    "ద్వాదశి",
    "Trayodashi": "త్రయోదశి", "Chaturdashi": "చతుర్దశి",
    "Purnima":    "పూర్ణిమ",  "Amavasya":    "అమావాస్య",
    "Pratipada":  "పాడ్యమి",  "Dwitiya":     "విదియ",
    "Tritiya":    "తదియ",      "Chaturthi":   "చవితి",
    "Panchami":   "పంచమి",     "Shashthi":    "షష్ఠి",
    "Saptami":    "సప్తమి",    "Ashtami":     "అష్టమి",
    "Navami":     "నవమి",      "Dashami":     "దశమి",
}
PAKSHA_MAP = {
    "Krishna Paksha": "కృష్ణ పక్షం",
    "Shukla Paksha":  "శుక్ల పక్షం",
}
NAKSHATRA_MAP = {
    "Ashwini": "అశ్విని", "Bharani": "భరణి", "Krittika": "కృత్తిక",
    "Rohini": "రోహిణి", "Mrigashira": "మృగశిర", "Ardra": "ఆర్ద్ర",
    "Punarvasu": "పునర్వసు", "Pushya": "పుష్యమి", "Ashlesha": "ఆశ్లేష",
    "Magha": "మఘ", "Purva Phalguni": "పూర్వ ఫల్గుణి",
    "Uttara Phalguni": "ఉత్తర ఫల్గుణి", "Hasta": "హస్త",
    "Chitra": "చిత్త", "Swati": "స్వాతి", "Vishakha": "విశాఖ",
    "Anuradha": "అనూరాధ", "Jyeshtha": "జ్యేష్ఠ", "Moola": "మూల",
    "Purva Ashadha": "పూర్వాషాఢ", "Uttara Ashadha": "ఉత్తరాషాఢ",
    "Shravana": "శ్రవణం", "Dhanishtha": "ధనిష్ఠ",
    "Shatabhisha": "శతభిష", "Purva Bhadrapada": "పూర్వ భాద్రపద",
    "Uttara Bhadrapada": "ఉత్తర భాద్రపద", "Revati": "రేవతి",
}


# ── Scene timing ───────────────────────────────────────────────────────────────

def compute_scene_frames(audio_duration):
    total_words = sum(SCENE_WORD_COUNTS)
    frames = []
    for words in SCENE_WORD_COUNTS:
        dur = (words / total_words) * audio_duration
        frames.append(max(int(dur * FPS), MIN_SCENE_SECS * FPS))
    return frames


# ── Fonts ──────────────────────────────────────────────────────────────────────

def get_font(size, bold=False):
    suffix = "Bold" if bold else "Regular"
    for p in [
        f"/home/runner/fonts/telugu/NotoSansTelugu-{suffix}.ttf",
        os.path.join(SCRIPTS_DIR, f"NotoSansTelugu-{suffix}.ttf"),
        os.path.join(SCRIPTS_DIR, "NotoSansTelugu-Regular.ttf"),
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


def get_latin_font(size, bold=False):
    suffix = "Bold" if bold else "Regular"
    for p in [
        f"/home/runner/fonts/telugu/NotoSans-{suffix}.ttf",
        os.path.join(SCRIPTS_DIR, f"NotoSans-{suffix}.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return get_font(size, bold)


def measure_mixed(text, size, bold=False):
    tel = get_font(size, bold); lat = get_latin_font(size, bold)
    tw = th = 0
    for ch in text:
        f = tel if TELUGU_RE.match(ch) else lat
        bb = f.getbbox(ch); tw += bb[2]-bb[0]; th = max(th, bb[3]-bb[1])
    return tw, th


def draw_mixed(draw, pos, text, size, bold=False, fill=WHITE, anchor=None):
    if not text: return
    tel = get_font(size, bold); lat = get_latin_font(size, bold)
    runs, cur, cur_tel = [], [], None
    for ch in text:
        is_tel = bool(TELUGU_RE.match(ch))
        if cur_tel is None: cur_tel = is_tel
        if is_tel != cur_tel:
            runs.append((cur_tel, ''.join(cur))); cur = []; cur_tel = is_tel
        cur.append(ch)
    if cur: runs.append((cur_tel, ''.join(cur)))
    tw, th = measure_mixed(text, size, bold)
    x, y = pos
    if anchor == "mm": x -= tw // 2; y -= th // 2
    elif anchor == "ra": x -= tw
    for is_tel, run in runs:
        f = tel if is_tel else lat
        draw.text((x, y), run, font=f, fill=fill)
        bb = f.getbbox(run); x += bb[2]-bb[0]


# ── Data helpers ───────────────────────────────────────────────────────────────

def tf(p, k):
    v = p.get(k, "N/A"); return v if v and v != "" else "N/A"

def clean_time(val, tz):
    val = val.split("|")[0].strip()
    return val.replace(f" {tz}", "").strip()

def time_with_tz(val, tz):
    return f"{clean_time(val, tz)} {tz}"

def fmt_date(date_str):
    try: return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except: return date_str

def fade(f, frames=12):
    return min(255, int(255 * f / max(frames, 1)))

def telugu_tithi_short(tithi_raw):
    for eng, tel in TITHI_MAP.items():
        if eng.lower() in tithi_raw.lower(): return tel
    return tithi_raw.split()[0]

def telugu_tithi_full(tithi_raw, tz=""):
    result = tithi_raw
    if tz: result = result.replace(f" {tz}", "")
    for eng, tel in TITHI_MAP.items():
        result = result.replace(eng, tel)
    result = result.replace("upto", "వరకు").replace("Upto", "వరకు")
    result = result.replace("\u2192", "|").replace("->", "|")
    return result

def telugu_paksha(paksha_val):
    return PAKSHA_MAP.get(paksha_val, paksha_val)

def telugu_nakshatra(nakshatra_raw):
    if not nakshatra_raw or nakshatra_raw == "N/A": return "N/A"
    for eng, tel in NAKSHATRA_MAP.items():
        if nakshatra_raw.startswith(eng): return tel
    return NAKSHATRA_MAP.get(nakshatra_raw.split()[0], nakshatra_raw.split()[0])


# ── Background ─────────────────────────────────────────────────────────────────

def make_bg():
    """Near-black solid background — minimal modern."""
    return Image.new("RGBA", (W, H), BLACK + (255,))


# ── Shared layout helpers ──────────────────────────────────────────────────────

def _handle(draw, fa):
    draw.text((CX, 82), "@PanthuluPanchangam",
              font=get_latin_font(26), fill=(155, 125, 55, fa), anchor="mm")

def _footer(draw, fa):
    draw_mixed(draw, (CX, 1862), "జయ శ్రీమన్నారాయణ!", 28,
               fill=(125, 105, 45, fa), anchor="mm")

def _hline(draw, y, color, width=1, x1=PAD, x2=W-PAD):
    draw.line([(x1, y), (x2, y)], fill=color, width=width)


# ── Scene 0: Intro ─────────────────────────────────────────────────────────────

def scene_intro(img, f, panchang):
    city      = panchang.get("city", "USA")
    weekday   = panchang.get("weekday", "")
    tz        = panchang.get("tz_label", "ET")
    tithi_tel = telugu_tithi_short(tf(panchang, "tithi"))
    paksha    = telugu_paksha(tf(panchang, "paksha"))
    nak_name  = telugu_nakshatra(tf(panchang, "nakshatra"))
    rahu      = time_with_tz(tf(panchang, "rahukaal"), tz)
    fa        = fade(f, 12)

    draw = ImageDraw.Draw(img)
    _handle(draw, fa)

    # City hero
    csize = 92 if len(city) <= 9 else 72 if len(city) <= 14 else 56
    draw.text((CX, 205), city,
              font=get_latin_font(csize, bold=True), fill=WHITE + (fa,), anchor="mm")

    # Date
    draw.text((CX, 302), f"{weekday}  •  {fmt_date(panchang.get('date', ''))}",
              font=get_latin_font(28), fill=MUTED + (fa,), anchor="mm")

    _hline(draw, 352, color=(75, 60, 18, fa), width=2)

    # Tithi
    draw.text((PAD, 400), "తిథి", font=get_font(28), fill=MUTED + (fa,))
    ts = 70 if len(tithi_tel) <= 5 else 56
    draw_mixed(draw, (PAD, 452), tithi_tel, ts, bold=True, fill=GOLD + (fa,))

    _hline(draw, 574, color=DIV_DIM + (fa,))

    # Nakshatra
    draw.text((PAD, 618), "నక్షత్రం", font=get_font(28), fill=MUTED + (fa,))
    ns = 70 if len(nak_name) <= 5 else 56
    draw_mixed(draw, (PAD, 670), nak_name, ns, bold=True, fill=GOLD + (fa,))

    _hline(draw, 792, color=DIV_DIM + (fa,))

    # Paksha
    draw.text((PAD, 836), "పక్షం", font=get_font(28), fill=MUTED + (fa,))
    draw_mixed(draw, (PAD, 886), paksha, 44, fill=WHITE + (fa,))

    _hline(draw, 988, color=(95, 28, 28, fa), width=2)

    # Rahu preview
    draw_mixed(draw, (PAD, 1034), "రాహు కాలం", 34, bold=True, fill=RED + (fa,))
    rsize = 60 if len(rahu) <= 20 else 48
    draw.text((PAD, 1090), rahu,
              font=get_latin_font(rsize, bold=True), fill=WHITE + (fa,))
    draw.text((PAD, 1165), "Avoid starting new work",
              font=get_latin_font(26), fill=MUTED + (fa,))

    _footer(draw, fa)
    return img


# ── Scene 1: Bad timings ───────────────────────────────────────────────────────

def scene_bad_timings(img, f, panchang):
    tz   = panchang.get("tz_label", "ET")
    rahu = time_with_tz(tf(panchang, "rahukaal"), tz)
    dur  = time_with_tz(tf(panchang, "durmuhurtam"), tz)
    fa   = fade(f, 12)

    draw = ImageDraw.Draw(img)
    _handle(draw, fa)

    # Header
    draw_mixed(draw, (CX, 205), "జాగ్రత్త! నివారించండి", 46,
               bold=True, fill=RED + (fa,), anchor="mm")
    _hline(draw, 268, color=(145, 28, 28, fa), width=2)

    # Rahu Kalam
    draw_mixed(draw, (PAD, 334), "రాహు కాలం", 30, fill=MUTED + (fa,))
    rsize = 78 if len(rahu) <= 20 else 62
    draw.text((PAD, 390), rahu,
              font=get_latin_font(rsize, bold=True), fill=WHITE + (fa,))
    draw_mixed(draw, (PAD, 490), "కొత్త పని మొదలు పెట్టకండి", 26,
               fill=MUTED + (fa,))

    _hline(draw, 572, color=DIV_DIM + (fa,))

    # Durmuhurtam
    draw_mixed(draw, (PAD, 628), "దుర్ముహూర్తం", 30, fill=MUTED + (fa,))
    dsize = 70 if len(dur) <= 20 else 56
    draw.text((PAD, 684), dur,
              font=get_latin_font(dsize, bold=True), fill=WHITE + (fa,))
    draw_mixed(draw, (PAD, 776), "శుభ కార్యాలు వద్దు", 26, fill=MUTED + (fa,))

    _hline(draw, 856, color=DIV_DIM + (fa,))

    draw_mixed(draw, (PAD, 912), "ఈ సమయాలలో ముఖ్య పనులు వాయిదా వేయండి",
               26, fill=(145, 95, 95, fa))

    _footer(draw, fa)
    return img


# ── Scene 2: Good timings ──────────────────────────────────────────────────────

def scene_good_timings(img, f, panchang):
    tz      = panchang.get("tz_label", "ET")
    brahma  = time_with_tz(tf(panchang, "brahma_muhurta"), tz)
    abhijit = time_with_tz(tf(panchang, "abhijit"), tz)
    fa      = fade(f, 12)

    draw = ImageDraw.Draw(img)
    _handle(draw, fa)

    # Header
    draw_mixed(draw, (CX, 205), "శుభ ముహూర్తాలు", 50,
               bold=True, fill=GOLD + (fa,), anchor="mm")
    _hline(draw, 268, color=(145, 115, 18, fa), width=2)

    # Brahma Muhurtam
    draw_mixed(draw, (PAD, 334), "బ్రహ్మ ముహూర్తం", 30, fill=MUTED + (fa,))
    bsize = 76 if len(brahma) <= 20 else 60
    draw.text((PAD, 390), brahma,
              font=get_latin_font(bsize, bold=True), fill=WHITE + (fa,))
    draw_mixed(draw, (PAD, 488), "ప్రార్థన & ధ్యానానికి ఉత్తమ సమయం",
               26, fill=MUTED + (fa,))

    _hline(draw, 568, color=DIV_DIM + (fa,))

    # Abhijit
    draw_mixed(draw, (PAD, 624), "అభిజిత్ ముహూర్తం", 30, fill=MUTED + (fa,))
    asize = 70 if len(abhijit) <= 20 else 56
    draw.text((PAD, 680), abhijit,
              font=get_latin_font(asize, bold=True), fill=WHITE + (fa,))
    draw_mixed(draw, (PAD, 772), "ముఖ్య పనులకు అత్యంత శుభ సమయం",
               26, fill=MUTED + (fa,))

    _hline(draw, 852, color=DIV_DIM + (fa,))

    draw_mixed(draw, (PAD, 908), "ఈ సమయాలను సద్వినియోగం చేసుకోండి",
               26, fill=(115, 135, 75, fa))

    _footer(draw, fa)
    return img


# ── Scene 3: Closing ───────────────────────────────────────────────────────────

def scene_closing(img, f, panchang):
    tz      = panchang.get("tz_label", "ET")
    sunrise = time_with_tz(tf(panchang, "sunrise"), tz)
    sunset  = time_with_tz(tf(panchang, "sunset"), tz)
    fa      = fade(f, 12)

    draw = ImageDraw.Draw(img)
    _handle(draw, fa)

    # Header
    draw_mixed(draw, (CX, 205), "సూర్య సమయాలు", 48,
               bold=True, fill=GOLD + (fa,), anchor="mm")
    _hline(draw, 268, color=(145, 115, 18, fa), width=2)

    # Sunrise
    draw_mixed(draw, (PAD, 334), "సూర్యోదయం", 30, fill=MUTED + (fa,))
    draw.text((PAD, 390), sunrise,
              font=get_latin_font(66, bold=True), fill=WHITE + (fa,))

    _hline(draw, 498, color=DIV_DIM + (fa,))

    # Sunset
    draw_mixed(draw, (PAD, 548), "సూర్యాస్తమయం", 30, fill=MUTED + (fa,))
    draw.text((PAD, 604), sunset,
              font=get_latin_font(66, bold=True), fill=WHITE + (fa,))

    _hline(draw, 716, color=(75, 60, 18, fa), width=2)

    # Blessing
    draw_mixed(draw, (CX, 800), "మీకు శుభమైన రోజు కలగాలని",
               40, bold=True, fill=WHITE + (fa,), anchor="mm")
    draw_mixed(draw, (CX, 862), "ఆశిస్తున్నాము!", 46,
               bold=True, fill=GOLD + (fa,), anchor="mm")

    _hline(draw, 950, color=DIV_DIM + (fa,))

    # CTA
    draw_mixed(draw, (CX, 1012), "Save చేయండి  |  Share చేయండి",
               34, bold=True, fill=SAFFRON + (fa,), anchor="mm")
    draw_mixed(draw, (CX, 1072), "Family WhatsApp లో పంచుకోండి",
               26, fill=MUTED + (fa,), anchor="mm")

    draw.text((CX, 1160), "@PanthuluPanchangam",
              font=get_latin_font(30, bold=True), fill=GOLD + (fa,), anchor="mm")

    _footer(draw, fa)
    return img


SCENE_RENDERERS = [scene_intro, scene_bad_timings, scene_good_timings, scene_closing]
assert len(SCENE_RENDERERS) == N_SCENES


def _split_narration(narration: str) -> list[str]:
    words = narration.split()
    total = sum(SCENE_WORD_COUNTS)
    segs, idx = [], 0
    for wc in SCENE_WORD_COUNTS:
        n = max(1, round(wc * len(words) / total))
        segs.append(" ".join(words[idx: idx + n]))
        idx += n
    if idx < len(words):
        segs[-1] += " " + " ".join(words[idx:])
    while len(segs) < N_SCENES:
        segs.append("")
    return segs[:N_SCENES]


# ── Frame builder ──────────────────────────────────────────────────────────────

def build_frame(frame_idx: int, panchang: dict, scene_frames: list,
                scene_subtitles: list | None = None,
                cameras: list | None = None) -> Image.Image:
    # Determine scene and frame-within-scene
    scene, f_in, acc = 0, frame_idx, 0
    for i, nf in enumerate(scene_frames):
        if frame_idx < acc + nf:
            scene = i; f_in = frame_idx - acc; break
        acc += nf

    t_scene  = f_in / FPS
    scene_nf = scene_frames[scene]

    # Render
    img = make_bg()
    img = SCENE_RENDERERS[scene](img, f_in, panchang)

    # Subtitle
    if scene_subtitles and scene < len(scene_subtitles):
        img = draw_subtitle(
            img, scene_subtitles[scene], t_scene, W, H,
            font_fn=lambda sz, bold=False: get_font(sz, bold),
            y_ratio=0.90, fade_in=0.5, fade_out=0.5,
            duration=scene_nf / FPS, start_t=0.0,
        )

    # Crossfade transitions (8 frames ≈ 0.33 s)
    FADE_F = 8
    if f_in < FADE_F:
        alpha = int(220 * (1.0 - f_in / FADE_F))
        ov = Image.new("RGBA", img.size, (0, 0, 0, alpha))
        img = Image.alpha_composite(img, ov)
    elif f_in >= scene_nf - FADE_F:
        alpha = int(200 * (1.0 - (scene_nf - f_in - 1) / FADE_F))
        ov = Image.new("RGBA", img.size, (0, 0, 0, min(alpha, 220)))
        img = Image.alpha_composite(img, ov)

    return img


# ── Video encoder ──────────────────────────────────────────────────────────────

def get_audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return 20.0


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    city      = panchang.get("city", "?")
    has_audio = audio_path and os.path.exists(audio_path)
    audio_dur = get_audio_duration(audio_path) if has_audio else 20.0
    scene_frames = compute_scene_frames(audio_dur)
    total_frames = sum(scene_frames)
    print(f"   {city} — audio={audio_dur:.2f}s  video={total_frames/FPS:.2f}s  scenes={scene_frames}")

    narration = script.get("full_narration", "") if script else ""
    scene_subtitles = _split_narration(narration) if narration else None

    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(total_frames):
            frame = build_frame(fi, panchang, scene_frames, scene_subtitles)
            frame.convert("RGB").save(
                str(Path(tmp) / f"frame_{fi:05d}.jpg"), "JPEG", quality=92)
            if fi % 80 == 0:
                sc, acc = 0, 0
                for i, nf in enumerate(scene_frames):
                    if fi < acc + nf: sc = i; break
                    acc += nf
                print(f"      frame {fi}/{total_frames} scene {sc+1}/{N_SCENES} ...")

        cmd = ["ffmpeg", "-y", "-framerate", str(FPS),
               "-i", str(Path(tmp) / "frame_%05d.jpg")]
        if has_audio:
            cmd += ["-i", audio_path, "-c:a", "aac", "-b:a", "128k", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"FFmpeg: {r.stderr[-800:]}")

    print(f"  OK {output_path}")
    return output_path


# ── Thumbnail (keeps its own warmer dark-gradient style) ──────────────────────

def _modern_font(size, bold=False):
    candidates = (
        ["/home/user/panchangam-agent/scripts/FreeSansBold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if bold else
        ["/home/user/panchangam-agent/scripts/FreeSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


def _make_modern_bg(W, H):
    import random as _random
    from PIL import ImageFilter
    img  = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(14 - 6 * t); g = int(9 - 4 * t); b = int(32 - 14 * t)
        draw.line([(0, y), (W, y)], fill=(max(r, 0), max(g, 0), max(b, 0), 255))
    rng = _random.Random(77)
    for _ in range(220):
        sx = rng.randint(0, W); sy = rng.randint(0, int(H * 0.6))
        sr = rng.choice([1, 1, 2]); sa = rng.randint(18, 55)
        draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(255, 210, 130, sa))
    return img


def _add_glow(img, cx, cy, radius=220, color=(255, 160, 0), alpha=28):
    from PIL import ImageFilter
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for r in range(radius, 0, -22):
        a = int(alpha * (1 - r / radius) ** 1.6)
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color + (a,))
    ov = ov.filter(ImageFilter.GaussianBlur(38))
    return Image.alpha_composite(img, ov)


def _rrect(draw, x1, y1, x2, y2, radius, fill=None, outline=None, width=2):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius,
                           fill=fill, outline=outline, width=width)


def create_thumbnail(panchang, output_path):
    from PIL import ImageFilter
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    city    = panchang.get("city", "USA")
    date    = fmt_date(panchang.get("date", ""))
    weekday = panchang.get("weekday", "")
    tz      = panchang.get("tz_label", "CT")
    rahu    = time_with_tz(tf(panchang, "rahukaal"), tz)
    brahma  = time_with_tz(tf(panchang, "brahma_muhurta"), tz)
    tithi_eng = re.split(r"\s+upto|\s*->|\s*\u2192", tf(panchang, "tithi"))[0].strip()
    naksh_eng = re.split(r"\s+upto|\s*->|\s*\u2192", tf(panchang, "nakshatra"))[0].strip()

    img  = _make_modern_bg(W, H)
    img  = _add_glow(img, CX, int(H * 0.72), radius=480, color=(255, 120, 20), alpha=22)

    ORANGE = (255, 110, 15); GOLD2 = (255, 210, 55); RED2 = (255, 55, 55)
    WHITE2 = (255, 250, 245); MUTED2 = (170, 155, 135)
    CARD_D = (22, 12, 5, 235); CARD_R = (55, 6, 6, 245)

    draw = ImageDraw.Draw(img)
    fB = lambda sz: _modern_font(sz, bold=True)
    fR = lambda sz: _modern_font(sz, bold=False)

    _rrect(draw, CX-230, 34, CX+230, 92, radius=30,
           fill=(38, 18, 4, 210), outline=ORANGE, width=2)
    draw.text((CX, 63), "@PanthuluPanchangam", font=fB(27), fill=ORANGE, anchor="mm")

    csize = 88 if len(city) <= 12 else 68
    draw.text((CX, 175), city, font=fB(csize), fill=WHITE2, anchor="mm")
    draw.text((CX, 254), f"{weekday}  \u2022  {date}", font=fR(33), fill=MUTED2, anchor="mm")

    dpad = PAD + 80
    draw.line([(dpad, 284), (W - dpad, 284)], fill=(255, 140, 40, 90), width=2)
    draw.ellipse([CX-6, 278, CX+6, 290], fill=ORANGE)

    cy1, cy2 = 302, 458; mid = W // 2 - 8
    _rrect(draw, PAD, cy1, mid, cy2, radius=18, fill=CARD_D,
           outline=(200, 155, 40, 200), width=2)
    draw.text(((PAD + mid) // 2, cy1 + 36), "TITHI", font=fB(23), fill=GOLD2, anchor="mm")
    draw.line([(PAD+24, cy1+58), (mid-24, cy1+58)], fill=(200, 155, 40, 80), width=1)
    tsize = 42 if len(tithi_eng) <= 10 else 33
    draw.text(((PAD + mid) // 2, cy1 + 118), tithi_eng, font=fB(tsize), fill=WHITE2, anchor="mm")

    _rrect(draw, mid + 16, cy1, W - PAD, cy2, radius=18, fill=CARD_D,
           outline=(200, 155, 40, 200), width=2)
    rx = (mid + 16 + W - PAD) // 2
    draw.text((rx, cy1 + 36), "NAKSHATRA", font=fB(23), fill=GOLD2, anchor="mm")
    draw.line([(mid+40, cy1+58), (W-PAD-24, cy1+58)], fill=(200, 155, 40, 80), width=1)
    nsize = 38 if len(naksh_eng) <= 10 else 28
    draw.text((rx, cy1 + 118), naksh_eng, font=fB(nsize), fill=WHITE2, anchor="mm")

    rg_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rgd   = ImageDraw.Draw(rg_ov)
    for gr in range(260, 0, -26):
        ga = int(28 * (1 - gr / 260) ** 1.8)
        rgd.ellipse([CX - gr*2, 606 - gr, CX + gr*2, 606 + gr], fill=(255, 30, 30, ga))
    rg_ov = rg_ov.filter(ImageFilter.GaussianBlur(32))
    img   = Image.alpha_composite(img, rg_ov)
    draw  = ImageDraw.Draw(img)

    ry1, ry2 = 476, 740
    _rrect(draw, PAD, ry1, W - PAD, ry2, radius=24, fill=CARD_R,
           outline=(255, 60, 60, 230), width=3)
    draw.text((CX, ry1 + 52), "RAHU KALAM", font=fB(44), fill=RED2, anchor="mm")
    draw.line([(PAD + 70, ry1 + 86), (W - PAD - 70, ry1 + 86)],
              fill=(255, 60, 60, 100), width=1)
    rsize = 64 if len(rahu) <= 22 else 50
    draw.text((CX, ry1 + 162), rahu, font=fB(rsize), fill=WHITE2, anchor="mm")
    draw.text((CX, ry1 + 232), "Avoid starting new work", font=fR(30),
              fill=(255, 150, 150), anchor="mm")

    by1, by2 = 758, 940
    _rrect(draw, PAD, by1, W - PAD, by2, radius=20,
           fill=(28, 18, 4, 235), outline=(200, 165, 30, 210), width=2)
    draw.text((CX, by1 + 46), "BRAHMA MUHURTAM", font=fB(36), fill=GOLD2, anchor="mm")
    draw.line([(PAD + 70, by1 + 76), (W - PAD - 70, by1 + 76)],
              fill=(200, 165, 30, 80), width=1)
    bsize = 52 if len(brahma) <= 22 else 40
    draw.text((CX, by1 + 146), brahma, font=fB(bsize), fill=WHITE2, anchor="mm")

    from presenter_animator import load_character
    char = load_character(CHARACTER_PATH)
    if char:
        ch  = int(H * 0.52)
        cw  = int(char.size[0] * (ch / char.size[1]))
        resized = char.resize((cw, ch), Image.LANCZOS)
        char_y  = H - ch - 6
        sp_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        spd   = ImageDraw.Draw(sp_ov)
        for sr in range(300, 0, -24):
            sa = int(30 * (1 - sr / 300) ** 2)
            spd.ellipse([CX - sr, char_y + ch // 2 - sr // 2,
                         CX + sr, char_y + ch // 2 + sr // 2],
                        fill=(255, 165, 60, sa))
        sp_ov = sp_ov.filter(ImageFilter.GaussianBlur(38))
        img   = Image.alpha_composite(img, sp_ov)
        img.paste(resized, (CX - cw // 2, char_y), resized)

    img.convert("RGB").save(output_path, "JPEG", quality=95)
    print(f"  OK Thumbnail: {output_path}")
    return output_path
