"""
video_creator.py — presenter-style rewrite
Scenes:
  0  Intro    — city, date, tithi, nakshatra, rahu preview
  1  Bad      — Rahu Kalam + Durmuhurtam (red)
  2  Good     — Brahma Muhurtam + Abhijit (gold)
  3  Closing  — Sunrise/Sunset + Save/Share CTA

Presenter features:
- Warm Hindu temple arch background with marigold garlands
- Animated character: breathing, sway, bob, hand-glow, sound-wave rings
- Narration subtitles displayed per-scene at bottom of frame
- Drifting marigold petal particles
"""

import subprocess, os, tempfile, math, re
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

from presenter_animator import (
    PresenterAnimator, make_temple_bg, draw_subtitle,
)
from camera_system import CameraMotion, SCENE_CAMERA_PRESETS
from cinematic_grader import CinematicGrader

# Module-level cinematic grader (warm devotional grade, created once)
_grader = CinematicGrader(warmth=0.20, contrast=0.14, saturation=1.08, vignette=0.30)

W, H, FPS = 1080, 1920, 24
SCRIPTS_DIR    = os.path.dirname(os.path.abspath(__file__))
CHARACTER_PATH = os.path.join(SCRIPTS_DIR, "pandit_character.png")
TELUGU_RE      = re.compile(r'[\u0C00-\u0C7F]')

GOLD      = (255, 215,   0)
SAFFRON   = (255, 120,   0)
WARN_RED  = (230,  50,  50)
DARK_RED  = (130,   0,   0)
CREAM     = (255, 228, 181)
WHITE     = (255, 248, 240)
DIM       = (160, 140, 100)
BG_TOP    = ( 10,   2,   0)
BG_MID    = ( 30,   8,   0)
BG_BTM    = ( 55,  15,   0)

PAD    = 45
CX     = W // 2
CARD_W = W - PAD * 2

CHAR_SCALE    = 0.72          # character height relative to H for presenter style
CHAR_X        = W // 2
CHAR_Y_BOTTOM = H - 8

# Module-level temple background cache and animator (initialised lazily)
_temple_bg:  Image.Image | None = None
_animator:   PresenterAnimator | None = None


def _get_temple_bg() -> Image.Image:
    global _temple_bg
    if _temple_bg is None:
        _temple_bg = make_temple_bg(W, H)
    return _temple_bg


def _get_animator() -> PresenterAnimator:
    global _animator
    if _animator is None:
        _animator = PresenterAnimator(CHARACTER_PATH, W, H,
                                      scale=CHAR_SCALE,
                                      cx=CHAR_X,
                                      bottom_y=CHAR_Y_BOTTOM)
    return _animator


# Word counts per scene — must match script_generator narration segments exactly
SCENE_WORD_COUNTS = [12, 9, 8, 10]
N_SCENES = 4
MIN_SCENE_SECS = 3            # each scene stays on screen at least 3 seconds

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
    "Magha": "మఘ", "Purva Phalguni": "పూర్వ ఫల్గుణి", "Uttara Phalguni": "ఉత్తర ఫల్గుణి",
    "Hasta": "హస్త", "Chitra": "చిత్త", "Swati": "స్వాతి",
    "Vishakha": "విశాఖ", "Anuradha": "అనూరాధ", "Jyeshtha": "జ్యేష్ఠ",
    "Moola": "మూల", "Purva Ashadha": "పూర్వాషాఢ", "Uttara Ashadha": "ఉత్తరాషాఢ",
    "Shravana": "శ్రవణం", "Dhanishtha": "ధనిష్ఠ", "Shatabhisha": "శతభిష",
    "Purva Bhadrapada": "పూర్వ భాద్రపద", "Uttara Bhadrapada": "ఉత్తర భాద్రపద",
    "Revati": "రేవతి",
}


# ── SCENE TIMING ──────────────────────────────────────────────────────────────

def compute_scene_frames(audio_duration):
    """Each scene gets frames proportional to word count, min MIN_SCENE_SECS."""
    total_words = sum(SCENE_WORD_COUNTS)
    frames = []
    for words in SCENE_WORD_COUNTS:
        dur = (words / total_words) * audio_duration
        frames.append(max(int(dur * FPS), MIN_SCENE_SECS * FPS))
    return frames


# ── FONTS ─────────────────────────────────────────────────────────────────────

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
    if anchor == "mm": x -= tw//2; y -= th//2
    elif anchor == "ra": x -= tw
    for is_tel, run in runs:
        f = tel if is_tel else lat
        draw.text((x, y), run, font=f, fill=fill)
        bb = f.getbbox(run); x += bb[2]-bb[0]


# ── BACKGROUND ────────────────────────────────────────────────────────────────

def make_bg():
    img = Image.new("RGBA", (W, H), (0,0,0,255))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y/H
        if t < 0.5:
            t2=t*2; r=int(BG_TOP[0]+(BG_MID[0]-BG_TOP[0])*t2)
            g=int(BG_TOP[1]+(BG_MID[1]-BG_TOP[1])*t2); b=int(BG_TOP[2]+(BG_MID[2]-BG_TOP[2])*t2)
        else:
            t2=(t-0.5)*2; r=int(BG_MID[0]+(BG_BTM[0]-BG_MID[0])*t2)
            g=int(BG_MID[1]+(BG_BTM[1]-BG_MID[1])*t2); b=int(BG_MID[2]+(BG_BTM[2]-BG_MID[2])*t2)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    return img


def draw_border(draw):
    draw.rectangle([5,5,W-5,H-5], outline=GOLD, width=3)
    draw.rectangle([13,13,W-13,H-13], outline=(130,95,0), width=1)
    s=32
    for cx2,cy2 in [(25,25),(W-25,25),(25,H-25),(W-25,H-25)]:
        draw.ellipse([cx2-s//2,cy2-s//2,cx2+s//2,cy2+s//2], outline=GOLD, width=2)
        draw.line([cx2-s//2-4,cy2,cx2+s//2+4,cy2], fill=GOLD, width=1)
        draw.line([cx2,cy2-s//2-4,cx2,cy2+s//2+4], fill=GOLD, width=1)


def draw_om_watermark(img, alpha=7):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    d.text((W//2,H//2-60),"ఓం",font=get_font(340,bold=True),fill=(255,200,0,alpha),anchor="mm")
    return Image.alpha_composite(img,ov)


def add_glow(img, cx, cy, radius=220, color=(255,160,0), alpha=28):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    for r in range(radius,0,-22):
        a=int(alpha*(1-r/radius)**1.6)
        d.ellipse([cx-r,cy-r,cx+r,cy+r],fill=color+(a,))
    ov=ov.filter(ImageFilter.GaussianBlur(38))
    return Image.alpha_composite(img,ov)


def add_warning_pulse(img, intensity):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    a=int(90*intensity)
    for m in [0,10,22]:
        d.rectangle([m,m,W-m,H-m],outline=(210,30,30,a),width=8)
    return Image.alpha_composite(img,ov)


def add_scene_fade(img, f_in_scene, fade_frames=10):
    """Subtle dark fade-in — replaces the old bright flash that caused cream background."""
    if f_in_scene >= fade_frames: return img
    alpha = int(200 * (1 - f_in_scene / fade_frames))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, alpha))
    return Image.alpha_composite(img, ov)


def draw_card(draw, x1,y1,x2,y2, fill=(40,12,0), border=None, radius=18, alpha=228):
    fa=fill+(alpha,) if len(fill)==3 else fill; r=radius
    draw.rectangle([x1+r,y1,x2-r,y2],fill=fa); draw.rectangle([x1,y1+r,x2,y2-r],fill=fa)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r],fill=fa)
    if border:
        draw.rectangle([x1+r,y1,x2-r,y1+4],fill=border)
        draw.rectangle([x1+r,y2-4,x2-r,y2],fill=border)
        draw.rectangle([x1,y1+r,x1+4,y2-r],fill=border)
        draw.rectangle([x2-4,y1+r,x2,y2-r],fill=border)


def fade(f, frames=10):
    return min(255, int(255*f/max(frames,1)))


def fmt_date(date_str):
    try: return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except: return date_str


def telugu_tithi_full(tithi_raw, tz=""):
    """Convert tithi string to Telugu, strip tz, use | as separator."""
    result = tithi_raw
    if tz:
        result = result.replace(f" {tz}", "")
    for eng, tel in TITHI_MAP.items():
        result = result.replace(eng, tel)
    result = result.replace("upto", "వరకు").replace("Upto", "వరకు")
    result = result.replace("\u2192", "|").replace("->", "|")
    return result


def telugu_tithi_short(tithi_raw):
    for eng, tel in TITHI_MAP.items():
        if eng.lower() in tithi_raw.lower():
            return tel
    return tithi_raw.split()[0]


def telugu_paksha(paksha_val):
    return PAKSHA_MAP.get(paksha_val, paksha_val)


def telugu_nakshatra(nakshatra_raw):
    if not nakshatra_raw or nakshatra_raw == "N/A":
        return "N/A"
    name = nakshatra_raw.split()[0]
    # Try multi-word match first
    for eng, tel in NAKSHATRA_MAP.items():
        if nakshatra_raw.startswith(eng):
            return tel
    return NAKSHATRA_MAP.get(name, name)


# ── CHARACTER — handled by PresenterAnimator (presenter_animator.py) ──────────
# The old _load_char / paste_char are replaced by PresenterAnimator.composite().


def tf(p, k):
    v = p.get(k,"N/A"); return v if v and v != "" else "N/A"


def clean_time(val, tz):
    """Take first slot and strip embedded tz label."""
    val = val.split("|")[0].strip()
    val = val.replace(f" {tz}","").strip()
    return val


def time_with_tz(val, tz):
    """Return clean time string with tz appended once."""
    return f"{clean_time(val, tz)} {tz}"


# ── SCENE 0: INTRO ────────────────────────────────────────────────────────────

def scene_intro(img, f, panchang):
    """City + date + tithi + nakshatra + rahu kalam preview."""
    city     = panchang.get("city","USA")
    date     = fmt_date(panchang.get("date",""))
    weekday  = panchang.get("weekday","")
    tz       = panchang.get("tz_label","ET")
    tithi_raw = tf(panchang,"tithi")
    tithi_val = telugu_tithi_full(tithi_raw, tz)
    parts     = tithi_val.split("|")
    tithi_name = parts[0].strip()
    tithi_next = parts[1].strip() if len(parts) > 1 else ""
    paksha    = telugu_paksha(tf(panchang,"paksha"))
    nak_name  = telugu_nakshatra(tf(panchang,"nakshatra"))
    rahu      = time_with_tz(tf(panchang,"rahukaal"), tz)
    fa        = fade(f, 10)

    img = add_glow(img, CX, 420, radius=460, color=(200,80,0), alpha=18)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # City
    draw_mixed(draw,(CX,100),city,58,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_mixed(draw,(CX,158),weekday,32,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,200),date,26,fill=WHITE+(fa,),anchor="mm")
    draw.line([(PAD+30,224),(PAD+CARD_W-30,224)],fill=GOLD+(fa,),width=2)

    # Tithi card
    draw_card(draw,PAD,238,PAD+CARD_W,370,fill=(55,18,0),border=GOLD,radius=16,alpha=min(fa,235))
    draw_mixed(draw,(CX,260),"తిథి",22,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    tsize = 46; tw,_ = measure_mixed(tithi_name, tsize, bold=True)
    if tw > CARD_W-60: tsize = 36
    draw_mixed(draw,(CX,322),tithi_name,tsize,bold=True,fill=GOLD+(fa,),anchor="mm")
    if tithi_next:
        draw_mixed(draw,(CX,360),f"తరువాత: {tithi_next}",20,fill=DIM+(fa,),anchor="mm")

    # Nakshatra card
    draw_card(draw,PAD,384,PAD+CARD_W,490,fill=(48,16,0),border=(175,135,0),radius=16,alpha=min(fa,228))
    draw_mixed(draw,(CX,406),"నక్షత్రం",22,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_mixed(draw,(CX,454),nak_name,42,bold=True,fill=GOLD+(fa,),anchor="mm")

    # Paksha
    draw_card(draw,PAD+60,504,PAD+CARD_W-60,564,fill=(42,14,0),border=(150,115,0),radius=12,alpha=min(fa,218))
    draw_mixed(draw,(CX,534),paksha,30,fill=CREAM+(fa,),anchor="mm")

    # Rahu preview — small warning at bottom of content area
    draw_card(draw,PAD,578,PAD+CARD_W,660,fill=(110,0,0),border=WARN_RED,radius=14,alpha=min(fa,228))
    draw_mixed(draw,(CX,600),"రాహు కాలం",22,bold=True,fill=WARN_RED+(fa,),anchor="mm")
    draw_mixed(draw,(CX,638),rahu,30,bold=True,fill=CREAM+(fa,),anchor="mm")

    return img


# ── SCENE 1: BAD TIMINGS ──────────────────────────────────────────────────────

def scene_bad_timings(img, f, panchang):
    """Rahu Kalam + Durmuhurtam — red warning scene."""
    tz   = panchang.get("tz_label","ET")
    rahu = time_with_tz(tf(panchang,"rahukaal"), tz)
    dur  = time_with_tz(tf(panchang,"durmuhurtam"), tz)
    fa   = fade(f, 10)

    intensity = abs(math.sin(2*math.pi*2.0*(f/FPS)))
    img = add_warning_pulse(img, intensity*0.7)
    img = add_glow(img, CX, 500, radius=420, color=(180,15,15), alpha=20)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Header
    draw_card(draw,PAD,88,PAD+CARD_W,174,fill=(130,0,0),border=WARN_RED,alpha=min(fa,238))
    draw_mixed(draw,(CX,131),"జాగ్రత్త! నివారించండి",46,bold=True,fill=WARN_RED+(fa,),anchor="mm")

    # Rahu Kalam — big block
    draw_card(draw,PAD,190,PAD+CARD_W,410,fill=(100,0,0),border=WARN_RED,radius=20,alpha=min(fa,248))
    draw_mixed(draw,(CX,222),"రాహు కాలం",32,bold=True,fill=WARN_RED+(fa,),anchor="mm")
    rsize = 52; tw,_ = measure_mixed(rahu, rsize, bold=True)
    if tw > CARD_W-60: rsize = 40
    draw_mixed(draw,(CX,316),rahu,rsize,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,382),"కొత్త పని మొదలు పెట్టకండి",24,fill=WHITE+(fa,),anchor="mm")

    # Durmuhurtam
    draw_card(draw,PAD,426,PAD+CARD_W,630,fill=(80,0,0),border=(200,60,60),radius=18,alpha=min(fa,242))
    draw_mixed(draw,(CX,458),"దుర్ముహూర్తం",32,bold=True,fill=(220,80,80)+(fa,),anchor="mm")
    dsize = 48; tw,_ = measure_mixed(dur, dsize, bold=True)
    if tw > CARD_W-60: dsize = 38
    draw_mixed(draw,(CX,546),dur,dsize,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,606),"శుభ కార్యాలు ఈ వేళ వద్దు",24,fill=WHITE+(fa,),anchor="mm")

    # Warning footer
    draw_card(draw,PAD+40,646,PAD+CARD_W-40,712,fill=(60,0,0),border=(160,30,30),radius=12,alpha=min(fa,212))
    draw_mixed(draw,(CX,679),"ఈ సమయాలలో ముఖ్య పనులు వాయిదా వేయండి",22,fill=CREAM+(fa,),anchor="mm")

    return img


# ── SCENE 2: GOOD TIMINGS ─────────────────────────────────────────────────────

def scene_good_timings(img, f, panchang):
    """Brahma Muhurtam + Abhijit — gold auspicious scene."""
    tz     = panchang.get("tz_label","ET")
    brahma = time_with_tz(tf(panchang,"brahma_muhurta"), tz)
    abhijit = time_with_tz(tf(panchang,"abhijit"), tz)
    fa     = fade(f, 10)

    img = add_glow(img, CX, 500, radius=440, color=(255,170,0), alpha=22)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Header
    draw_card(draw,PAD,88,PAD+CARD_W,174,fill=(65,28,0),border=GOLD,alpha=min(fa,238))
    draw_mixed(draw,(CX,131),"శుభ ముహూర్తాలు",48,bold=True,fill=GOLD+(fa,),anchor="mm")

    # Brahma Muhurtam
    draw_card(draw,PAD,190,PAD+CARD_W,390,fill=(55,22,0),border=GOLD,radius=20,alpha=min(fa,248))
    draw_mixed(draw,(CX,222),"బ్రహ్మ ముహూర్తం",30,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    bsize = 48; tw,_ = measure_mixed(brahma, bsize, bold=True)
    if tw > CARD_W-60: bsize = 38
    draw_mixed(draw,(CX,308),brahma,bsize,bold=True,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,372),"ప్రార్థన & ధ్యానానికి ఉత్తమ సమయం",24,fill=CREAM+(fa,),anchor="mm")

    # Abhijit
    draw_card(draw,PAD,406,PAD+CARD_W,604,fill=(48,18,0),border=(200,160,0),radius=18,alpha=min(fa,242))
    draw_mixed(draw,(CX,438),"అభిజిత్ ముహూర్తం",30,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    asize = 48; tw,_ = measure_mixed(abhijit, asize, bold=True)
    if tw > CARD_W-60: asize = 38
    draw_mixed(draw,(CX,522),abhijit,asize,bold=True,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,582),"ముఖ్య పనులకు అత్యంత శుభ సమయం",24,fill=CREAM+(fa,),anchor="mm")

    # Blessing footer
    draw_card(draw,PAD+40,620,PAD+CARD_W-40,686,fill=(40,16,0),border=(150,115,0),radius=12,alpha=min(fa,212))
    draw_mixed(draw,(CX,653),"ఈ సమయాలను సద్వినియోగం చేసుకోండి",22,fill=CREAM+(fa,),anchor="mm")

    return img


# ── SCENE 3: CLOSING ──────────────────────────────────────────────────────────

def scene_closing(img, f, panchang):
    """Sunrise/Sunset + blessing + Save/Share CTA."""
    tz      = panchang.get("tz_label","ET")
    sunrise = time_with_tz(tf(panchang,"sunrise"), tz)
    sunset  = time_with_tz(tf(panchang,"sunset"),  tz)
    fa      = fade(f, 10)

    img = add_glow(img, CX, 420, radius=420, color=(255,130,0), alpha=22)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Sunrise
    draw_card(draw,PAD,88,PAD+CARD_W,240,fill=(50,18,0),border=GOLD,radius=18,alpha=min(fa,242))
    draw_mixed(draw,(CX,116),"సూర్యోదయం",30,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,182),sunrise,52,bold=True,fill=GOLD+(fa,),anchor="mm")

    # Sunset
    draw_card(draw,PAD,256,PAD+CARD_W,408,fill=(48,15,0),border=SAFFRON,radius=18,alpha=min(fa,242))
    draw_mixed(draw,(CX,284),"సూర్యాస్తమయం",30,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,350),sunset,52,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # Blessing
    draw_card(draw,PAD,424,PAD+CARD_W,536,fill=(65,28,0),border=GOLD,radius=16,alpha=min(fa,235))
    draw_mixed(draw,(CX,458),"మీకు శుభమైన రోజు కలగాలని",32,bold=True,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,514),"ఆశిస్తున్నాను!",36,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # Save/Share CTA — Instagram language
    draw_card(draw,PAD,552,PAD+CARD_W,646,fill=(50,20,0),border=SAFFRON,radius=16,alpha=min(fa,228))
    draw_mixed(draw,(CX,582),"Save చేయండి | Share చేయండి",36,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_mixed(draw,(CX,630),"Family WhatsApp లో పంచుకోండి!",22,fill=CREAM+(fa,),anchor="mm")

    draw_card(draw,PAD+60,660,PAD+CARD_W-60,718,fill=(40,16,0),border=(150,115,0),radius=12,alpha=min(fa,212))
    draw_mixed(draw,(CX,689),"@PanthuluPanchangam",26,fill=GOLD+(fa,),anchor="mm")

    draw_card(draw,PAD,730,PAD+CARD_W,784,fill=(32,10,0),border=(100,78,0),radius=10,alpha=min(fa,185))
    draw_mixed(draw,(CX,757),"జయ శ్రీమన్నారాయణ!",30,bold=True,fill=GOLD+(fa,),anchor="mm")

    return img


SCENE_RENDERERS = [scene_intro, scene_bad_timings, scene_good_timings, scene_closing]
assert len(SCENE_RENDERERS) == N_SCENES


def _split_narration(narration: str) -> list[str]:
    """
    Split full narration into 4 scene segments using SCENE_WORD_COUNTS weights.
    Returns list of 4 subtitle strings (one per scene).
    """
    words  = narration.split()
    total  = sum(SCENE_WORD_COUNTS)
    segs   = []
    idx    = 0
    for wc in SCENE_WORD_COUNTS:
        n = max(1, round(wc * len(words) / total))
        segs.append(" ".join(words[idx: idx + n]))
        idx += n
    # put any leftover words in the last segment
    if idx < len(words):
        segs[-1] += " " + " ".join(words[idx:])
    while len(segs) < N_SCENES:
        segs.append("")
    return segs[:N_SCENES]


# ── FRAME BUILDER ─────────────────────────────────────────────────────────────

def build_frame(frame_idx: int, panchang: dict, scene_frames: list,
                scene_subtitles: list | None = None,
                cameras: list | None = None) -> Image.Image:
    """
    Build one video frame.

    scene_subtitles : list of N_SCENES strings, one subtitle per scene.
                      Pass None to skip subtitle rendering.
    cameras         : list of CameraMotion, one per scene (created in
                      create_panchang_video).  Pass None to skip camera.
    """
    # ── Determine current scene + frame within scene ──────────────────────────
    scene = 0
    f_in  = frame_idx
    acc   = 0
    for i, nf in enumerate(scene_frames):
        if frame_idx < acc + nf:
            scene = i
            f_in  = frame_idx - acc
            break
        acc += nf

    t_global = frame_idx / FPS        # global clock (seconds)
    t_scene  = f_in      / FPS        # clock within this scene
    scene_nf = scene_frames[scene]    # total frames in this scene

    # ── Background: warm temple arch ─────────────────────────────────────────
    img = _get_temple_bg().copy()
    img = draw_om_watermark(img, alpha=5)

    # ── Info cards (scene-specific) ───────────────────────────────────────────
    img = SCENE_RENDERERS[scene](img, f_in, panchang)

    # ── Animated presenter character ──────────────────────────────────────────
    animator = _get_animator()
    img = animator.composite(img, t=t_global, talking=True,
                             scene=scene, petals=True)

    # ── Subtitle ──────────────────────────────────────────────────────────────
    if scene_subtitles and scene < len(scene_subtitles):
        sub_text  = scene_subtitles[scene]
        scene_dur = scene_nf / FPS
        img = draw_subtitle(
            img, sub_text, t_scene, W, H,
            font_fn=lambda sz, bold=False: get_font(sz, bold),
            y_ratio=0.90,
            fade_in=0.5,
            fade_out=0.5,
            duration=scene_dur,
            start_t=0.0,
        )

    # ── Camera motion (scene-aware push-in / drift) ───────────────────────────
    if cameras and scene < len(cameras):
        img = cameras[scene].apply(img, t_scene)

    # ── Scene crossfade transitions ───────────────────────────────────────────
    FADE_F = 8                   # 8 frames = ~0.33 s at 24 fps
    # Fade-in from black at scene start (overrides the existing add_scene_fade)
    if f_in < FADE_F:
        fade_alpha = int(220 * (1.0 - f_in / FADE_F))
        ov = Image.new("RGBA", img.size, (0, 0, 0, fade_alpha))
        img = Image.alpha_composite(img, ov)
    # Fade-out to black at scene end
    elif f_in >= scene_nf - FADE_F:
        fade_alpha = int(200 * (1.0 - (scene_nf - f_in - 1) / FADE_F))
        ov = Image.new("RGBA", img.size, (0, 0, 0, min(fade_alpha, 220)))
        img = Image.alpha_composite(img, ov)

    # ── Cinematic grade (warm tone + contrast + vignette) ─────────────────────
    img = _grader.grade(img)

    return img


# ── VIDEO ─────────────────────────────────────────────────────────────────────

def get_audio_duration(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","default=noprint_wrappers=1:nokey=1",path],
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
    video_dur    = total_frames / FPS
    print(f"   {city} — audio={audio_dur:.2f}s  video={video_dur:.2f}s")
    print(f"   scene_frames={scene_frames}")

    # Pre-warm temple background and animator (avoids per-frame init cost)
    _get_temple_bg()
    _get_animator()

    # Build one CameraMotion per scene (duration = scene length in seconds)
    scene_cameras = [
        CameraMotion(
            SCENE_CAMERA_PRESETS[i] if i < len(SCENE_CAMERA_PRESETS) else "drift",
            duration=scene_frames[i] / FPS,
        )
        for i in range(N_SCENES)
    ]

    # Compute per-scene subtitle text from narration
    narration = script.get("full_narration", "") if script else ""
    scene_subtitles = _split_narration(narration) if narration else None

    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(total_frames):
            frame = build_frame(fi, panchang, scene_frames, scene_subtitles,
                                cameras=scene_cameras)
            frame.convert("RGB").save(
                str(Path(tmp) / f"frame_{fi:05d}.jpg"), "JPEG", quality=92)
            if fi % 80 == 0:
                sc = 0; acc = 0
                for i, nf in enumerate(scene_frames):
                    if fi < acc + nf:
                        sc = i; break
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


# ── THUMBNAIL ─────────────────────────────────────────────────────────────────

def _modern_font(size, bold=False):
    """Load a clean Latin font for modern thumbnail text."""
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
    """Deep dark gradient with subtle warm star field."""
    import random as _random
    img  = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(img)
    # Gradient: deep charcoal-blue -> near-black
    for y in range(H):
        t = y / H
        r = int(14 - 6 * t)
        g = int(9  - 4 * t)
        b = int(32 - 14 * t)
        draw.line([(0, y), (W, y)], fill=(max(r,0), max(g,0), max(b,0), 255))
    # Subtle warm star specks in upper half
    rng = _random.Random(77)
    for _ in range(220):
        sx = rng.randint(0, W)
        sy = rng.randint(0, int(H * 0.6))
        sr = rng.choice([1, 1, 2])
        sa = rng.randint(18, 55)
        draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(255, 210, 130, sa))
    return img


def _rrect(draw, x1, y1, x2, y2, radius, fill=None, outline=None, width=2):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius,
                           fill=fill, outline=outline, width=width)


def create_thumbnail(panchang, output_path):
    """Modern, bold thumbnail — clean dark gradient, English text, high contrast."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # ── Data ──────────────────────────────────────────────────────────────────
    city    = panchang.get("city", "USA")
    date    = fmt_date(panchang.get("date", ""))
    weekday = panchang.get("weekday", "")
    tz      = panchang.get("tz_label", "CT")
    rahu    = time_with_tz(tf(panchang, "rahukaal"), tz)
    brahma  = time_with_tz(tf(panchang, "brahma_muhurta"), tz)

    # Clean English-only tithi & nakshatra (strip "upto …" and arrows)
    tithi_raw  = tf(panchang, "tithi")
    tithi_eng  = re.split(r"\s+upto|\s*->|\s*\u2192", tithi_raw)[0].strip()
    naksh_raw  = tf(panchang, "nakshatra")
    naksh_eng  = re.split(r"\s+upto|\s*->|\s*\u2192", naksh_raw)[0].strip()

    # ── Background ────────────────────────────────────────────────────────────
    img  = _make_modern_bg(W, H)

    # Warm central glow (behind character area)
    img  = add_glow(img, CX, int(H * 0.72), radius=480, color=(255, 120, 20), alpha=22)

    # ── Palette ───────────────────────────────────────────────────────────────
    ORANGE = (255, 110, 15)
    GOLD2  = (255, 210, 55)
    RED2   = (255, 55,  55)
    WHITE2 = (255, 250, 245)
    MUTED  = (170, 155, 135)
    CARD_D = (22,  12,  5,  235)   # dark card fill
    CARD_R = (55,  6,   6,  245)   # red card fill

    draw = ImageDraw.Draw(img)
    fB = lambda sz: _modern_font(sz, bold=True)
    fR = lambda sz: _modern_font(sz, bold=False)

    # ── Brand badge ───────────────────────────────────────────────────────────
    _rrect(draw, CX-230, 34, CX+230, 92, radius=30,
           fill=(38, 18, 4, 210), outline=ORANGE, width=2)
    draw.text((CX, 63), "@PanthuluPanchangam", font=fB(27), fill=ORANGE, anchor="mm")

    # ── City name ─────────────────────────────────────────────────────────────
    csize = 88 if len(city) <= 12 else 68
    draw.text((CX, 175), city, font=fB(csize), fill=WHITE2, anchor="mm")

    # Weekday + date
    draw.text((CX, 254), f"{weekday}  \u2022  {date}", font=fR(33), fill=MUTED, anchor="mm")

    # Thin accent divider
    dpad = PAD + 80
    draw.line([(dpad, 284), (W - dpad, 284)], fill=(255, 140, 40, 90), width=2)
    draw.ellipse([CX-6, 278, CX+6, 290], fill=ORANGE)

    # ── Tithi + Nakshatra cards (side by side) ────────────────────────────────
    cy1, cy2 = 302, 458
    mid = W // 2 - 8
    # Left: Tithi
    _rrect(draw, PAD, cy1, mid, cy2, radius=18, fill=CARD_D,
           outline=(200, 155, 40, 200), width=2)
    draw.text(((PAD + mid) // 2, cy1 + 36), "TITHI", font=fB(23), fill=GOLD2, anchor="mm")
    draw.line([(PAD+24, cy1+58), (mid-24, cy1+58)], fill=(200,155,40,80), width=1)
    tsize = 42 if len(tithi_eng) <= 10 else 33
    draw.text(((PAD + mid) // 2, cy1 + 118), tithi_eng, font=fB(tsize), fill=WHITE2, anchor="mm")

    # Right: Nakshatra
    _rrect(draw, mid + 16, cy1, W - PAD, cy2, radius=18, fill=CARD_D,
           outline=(200, 155, 40, 200), width=2)
    rx = (mid + 16 + W - PAD) // 2
    draw.text((rx, cy1 + 36), "NAKSHATRA", font=fB(23), fill=GOLD2, anchor="mm")
    draw.line([(mid+40, cy1+58), (W-PAD-24, cy1+58)], fill=(200,155,40,80), width=1)
    nsize = 38 if len(naksh_eng) <= 10 else 28
    draw.text((rx, cy1 + 118), naksh_eng, font=fB(nsize), fill=WHITE2, anchor="mm")

    # ── Rahu Kalam warning card ────────────────────────────────────────────────
    # Red glow behind the card
    rg_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rgd   = ImageDraw.Draw(rg_ov)
    for gr in range(260, 0, -26):
        ga = int(28 * (1 - gr / 260) ** 1.8)
        rgd.ellipse([CX - gr*2, 476 + 130 - gr, CX + gr*2, 476 + 130 + gr],
                    fill=(255, 30, 30, ga))
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

    # ── Brahma Muhurta auspicious card ────────────────────────────────────────
    by1, by2 = 758, 940
    _rrect(draw, PAD, by1, W - PAD, by2, radius=20,
           fill=(28, 18, 4, 235), outline=(200, 165, 30, 210), width=2)
    draw.text((CX, by1 + 46), "BRAHMA MUHURTAM", font=fB(36), fill=GOLD2, anchor="mm")
    draw.line([(PAD + 70, by1 + 76), (W - PAD - 70, by1 + 76)],
              fill=(200, 165, 30, 80), width=1)
    bsize = 52 if len(brahma) <= 22 else 40
    draw.text((CX, by1 + 146), brahma, font=fB(bsize), fill=WHITE2, anchor="mm")

    # ── Character with spotlight ──────────────────────────────────────────────
    from presenter_animator import load_character
    char = load_character(CHARACTER_PATH)
    if char:
        ch  = int(H * 0.52)
        cw  = int(char.size[0] * (ch / char.size[1]))
        resized = char.resize((cw, ch), Image.LANCZOS)
        char_y  = H - ch - 6

        # Warm spotlight under character
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
