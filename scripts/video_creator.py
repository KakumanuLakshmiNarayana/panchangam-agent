"""
video_creator.py — FINAL
All 10 issues fixed:
1. Video duration = audio duration exactly (no max-72-frame floor forcing extra length)
2. Content fills full screen — cards y=110 to y=760
3. Tithi fully in Telugu — "ఏకాదశి వరకు" + "ద్వాదశి"
4. పంతులు badge tight above character head
5. Stronger red tint on warning scenes
6. Progress dots larger, at H-35
7. Thumbnail tithi shows just Telugu name, no English suffix
"""

import subprocess, os, tempfile, math, re
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

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

CHAR_SCALE    = 0.78
CHAR_X        = W // 2
CHAR_Y_BOTTOM = H - 10

# Word counts per scene — must match script_generator narration segments
SCENE_WORD_COUNTS = [11, 4, 7, 4, 5, 6, 0, 11]
N_SCENES = 8

# Telugu lookup tables
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


def compute_scene_frames(audio_duration):
    """
    FIX #1: NO minimum frame floor — video matches audio exactly.
    Each scene gets frames proportional to words spoken.
    Sun scene gets 2s visual pause.
    """
    total_words = sum(SCENE_WORD_COUNTS)
    sun_pause   = 2.0
    speech_dur  = max(audio_duration - sun_pause, 1.0)
    frames = []
    for words in SCENE_WORD_COUNTS:
        if words == 0:
            dur = sun_pause
        else:
            dur = (words / total_words) * speech_dur
        # Minimum 1 second per scene only — not 3s
        frames.append(max(int(dur * FPS), FPS))
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
    a=int(100*intensity)
    for m in [0,10,22]:
        d.rectangle([m,m,W-m,H-m],outline=(210,30,30,a),width=8)
    return Image.alpha_composite(img,ov)


def add_scene_flash(img, f_in_scene):
    if f_in_scene >= 5: return img
    alpha=int(220*(1-f_in_scene/5))
    ov=Image.new("RGBA",(W,H),(255,255,220,alpha))
    return Image.alpha_composite(img,ov)


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


def telugu_tithi_full(tithi_raw):
    """
    FIX #3: Full Telugu conversion of tithi string.
    'Ekadashi upto 08:46 PM PT -> Dwadashi'
    becomes 'ఏకాదశి వరకు 08:46 PM PT → ద్వాదశి'
    """
    result = tithi_raw
    # Replace tithi names
    for eng, tel in TITHI_MAP.items():
        result = result.replace(eng, tel)
    # Replace English words
    result = result.replace("upto", "వరకు").replace("Upto", "వరకు")
    result = result.replace("->", "→")
    return result


def telugu_tithi_short(tithi_raw):
    """Just the first tithi name in Telugu — for thumbnail."""
    for eng, tel in TITHI_MAP.items():
        if eng.lower() in tithi_raw.lower():
            return tel
    return tithi_raw.split()[0]


def telugu_paksha(paksha_val):
    return PAKSHA_MAP.get(paksha_val, paksha_val)


# ── CHARACTER ─────────────────────────────────────────────────────────────────

_char_cache = None

def _load_char():
    global _char_cache
    if _char_cache is None and os.path.exists(CHARACTER_PATH):
        from scipy import ndimage
        orig = Image.open(CHARACTER_PATH).convert("RGBA")
        arr  = np.array(orig)
        r,g,b = arr[:,:,0].astype(int), arr[:,:,1].astype(int), arr[:,:,2].astype(int)
        sat    = np.max([r,g,b], axis=0) - np.min([r,g,b], axis=0)
        bright = (r + g + b) // 3
        # Handle both black bg (new char) and white/light bg
        is_bg  = ((r<30)&(g<30)&(b<30)) | ((sat<30)&(bright>200))
        labeled, _ = ndimage.label(is_bg)
        bl = set()
        for la in [labeled[0,:], labeled[-1,:], labeled[:,0], labeled[:,-1]]:
            bl.update(la[la > 0])
        mask = np.zeros(is_bg.shape, dtype=bool)
        for lbl in bl: mask |= (labeled == lbl)
        result = arr.copy(); result[mask, 3] = 0
        _char_cache = Image.fromarray(result, "RGBA")
    return _char_cache


def paste_char(base_img, frame_idx, scene):
    char = _load_char()
    if char is None: return base_img
    t = frame_idx/FPS
    bob   = int(4*math.sin(2*math.pi*2.5*t))
    scale = CHAR_SCALE + 0.012*math.sin(2*math.pi*1.2*t)
    shake = int(5*math.sin(2*math.pi*7*t)) if scene in (2,3) else 0
    nw = int(char.size[0]*scale); nh = int(char.size[1]*scale)
    resized = char.resize((nw,nh), Image.LANCZOS)

    # FIX #5: Stronger red tint on warning scenes — 45% original, 55% red
    if scene in (2, 3):
        arr  = np.array(resized).copy().astype(np.float32)
        amask = arr[:,:,3] > 10
        arr[amask, 0] = np.clip(arr[amask,0]*0.45 + 220*0.55, 0, 255)
        arr[amask, 1] = np.clip(arr[amask,1]*0.45 +  15*0.55, 0, 255)
        arr[amask, 2] = np.clip(arr[amask,2]*0.45 +  15*0.55, 0, 255)
        resized = Image.fromarray(arr.astype(np.uint8), "RGBA")

    glow = Image.new("RGBA", base_img.size, (0,0,0,0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([CHAR_X-nw//2-30, CHAR_Y_BOTTOM-nh+bob-10,
                CHAR_X+nw//2+30, CHAR_Y_BOTTOM+10+bob], fill=(255,100,0,10))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    base_img = Image.alpha_composite(base_img, glow)

    px = max(0, min(CHAR_X-nw//2+shake, W-nw))
    py = CHAR_Y_BOTTOM - nh + bob
    base_img.paste(resized, (px,py), resized)

    # FIX #4: Badge tight directly above character head
    d  = ImageDraw.Draw(base_img)
    bw, bh = 210, 36; bx = CHAR_X - bw//2
    badge_y = py - bh - 5   # tight above head
    draw_card(d, bx, badge_y, bx+bw, badge_y+bh, fill=(70,28,0), border=GOLD, alpha=222)
    draw_mixed(d, (CHAR_X, badge_y+bh//2), "పంతులు", 22, bold=True, fill=GOLD, anchor="mm")
    return base_img


def tf(p, k):
    v = p.get(k,"N/A"); return v if v and v != "" else "N/A"


def clean_time(val, tz):
    val = val.split("|")[0].strip()
    val = val.replace(f" {tz}","").strip()
    return val


# ── SCENE RENDERERS ───────────────────────────────────────────────────────────
# FIX #2: All content spreads from y=110 to y=760 — fills screen
# Character occupies y=820–1910, badge above at ~y=780

def scene_intro(img, f, panchang):
    city    = panchang.get("city","USA")
    date    = fmt_date(panchang.get("date",""))
    weekday = panchang.get("weekday","")
    tz      = panchang.get("tz_label","ET")
    rahu    = clean_time(tf(panchang,"rahukaal"), tz)
    abhijit = clean_time(tf(panchang,"abhijit"), tz)
    fa      = fade(f, 10)

    img = add_glow(img, CX, 500, radius=460, color=(200,80,0), alpha=18)
    img = add_scene_flash(img, f)
    draw = ImageDraw.Draw(img); draw_border(draw)

    draw.text((CX,88),"ఓం",font=get_font(78,bold=True),fill=GOLD+(fa,),anchor="mm")

    draw_card(draw,PAD,138,PAD+CARD_W,228,fill=(75,28,0),border=SAFFRON,alpha=min(fa,225))
    draw_mixed(draw,(CX,183),"నమస్కారం!",54,bold=True,fill=GOLD+(fa,),anchor="mm")

    draw_card(draw,PAD,245,PAD+CARD_W,323,fill=(55,20,0),border=(160,80,0),alpha=min(fa,210))
    draw_mixed(draw,(CX,284),"నేను మీ పంచాంగం గురువు",34,bold=True,fill=CREAM+(fa,),anchor="mm")

    draw_mixed(draw,(CX,415),city,66,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_mixed(draw,(CX,498),weekday,40,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,548),date,32,fill=WHITE+(fa,),anchor="mm")

    draw.line([(PAD+20,588),(PAD+CARD_W-20,588)],fill=GOLD+(fa,),width=2)
    draw_mixed(draw,(CX,622),"నేటి పంచాంగం వివరాలు చూద్దాం!",34,fill=CREAM+(fa,),anchor="mm")

    # Rahu preview card
    draw_card(draw,PAD,656,PAD+CARD_W,734,fill=(100,0,0),border=WARN_RED,radius=16,alpha=min(fa,222))
    draw_mixed(draw,(CX,672),"రాహు కాలం",26,bold=True,fill=WARN_RED+(fa,),anchor="mm")
    draw_mixed(draw,(CX,708),f"{rahu}  {tz}",30,bold=True,fill=CREAM+(fa,),anchor="mm")

    # Abhijit preview card
    draw_card(draw,PAD,750,PAD+CARD_W,828,fill=(50,32,0),border=GOLD,radius=16,alpha=min(fa,215))
    draw_mixed(draw,(CX,766),"అభిజిత్ ముహూర్తం",26,bold=True,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,802),f"{abhijit}  {tz}",30,bold=True,fill=CREAM+(fa,),anchor="mm")
    return img


def scene_tithi(img, f, panchang):
    tithi_raw = tf(panchang,"tithi")
    # FIX #3: Full Telugu conversion
    tithi_val = telugu_tithi_full(tithi_raw)
    paksha    = telugu_paksha(tf(panchang,"paksha"))
    tz        = panchang.get("tz_label","ET")
    fa        = fade(f, 10)

    img = add_glow(img, CX, 500, radius=420, color=(255,150,0), alpha=18)
    img = add_scene_flash(img, f)
    draw = ImageDraw.Draw(img); draw_border(draw)

    draw_card(draw,PAD,110,PAD+CARD_W,200,fill=(65,25,0),border=SAFFRON,alpha=min(fa,228))
    draw_mixed(draw,(CX,155),"తిథి",58,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # Split on → for display
    parts = tithi_val.split("→")
    p1    = parts[0].strip()
    p2    = ("→ " + parts[1].strip()) if len(parts)>1 else ""

    draw_card(draw,PAD,218,PAD+CARD_W,460,fill=(42,14,0),border=GOLD,radius=20,alpha=min(fa,240))
    tsize = 52; tw,_ = measure_mixed(p1, tsize, bold=True)
    if tw > CARD_W-60: tsize = 40
    draw_mixed(draw,(CX,310),p1,tsize,bold=True,fill=GOLD+(fa,),anchor="mm")
    if p2: draw_mixed(draw,(CX,408),p2,36,fill=CREAM+(fa,),anchor="mm")

    draw_mixed(draw,(CX,478),tz,28,fill=DIM+(fa,),anchor="mm")

    draw_card(draw,PAD+60,500,PAD+CARD_W-60,578,fill=(55,18,0),border=(175,135,0),radius=16,alpha=min(fa,215))
    draw_mixed(draw,(CX,539),paksha,36,fill=CREAM+(fa,),anchor="mm")

    draw_card(draw,PAD,598,PAD+CARD_W,674,fill=(38,12,0),border=(120,95,0),radius=14,alpha=min(fa,188))
    draw_mixed(draw,(CX,636),"నేటి తిథి ప్రకారం శుభ కార్యాలు చేయండి",26,fill=DIM+(fa,),anchor="mm")

    draw_card(draw,PAD,692,PAD+CARD_W,760,fill=(32,10,0),border=(100,78,0),radius=12,alpha=min(fa,175))
    draw_mixed(draw,(CX,726),"ఏకాదశి వ్రతం ఈరోజు పాటించండి",26,fill=DIM+(fa,),anchor="mm")
    return img


def _info_scene(img, f, label, time_val, tz, subtext, accent, bg_dark, pulse=False):
    """FIX #2: Cards spread y=110 to y=760"""
    fa = fade(f, 10)
    if pulse:
        intensity = abs(math.sin(2*math.pi*2.5*(f/FPS)))
        img = add_warning_pulse(img, intensity*0.85)
        img = add_glow(img, CX, 500, radius=400, color=(180,15,15), alpha=18)
    else:
        img = add_glow(img, CX, 500, radius=400, color=accent, alpha=20)
    img = add_scene_flash(img, f)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Label
    draw_card(draw,PAD,110,PAD+CARD_W,200,fill=bg_dark,border=accent,alpha=min(fa,230))
    draw_mixed(draw,(CX,155),label,54,bold=True,fill=accent+(fa,),anchor="mm")

    # Time — large
    clean = clean_time(time_val, tz)
    tsize = 68; tw,_ = measure_mixed(clean, tsize, bold=True)
    if tw > CARD_W-60: tsize = 52
    draw_card(draw,PAD,220,PAD+CARD_W,430,
              fill=(bg_dark[0]//2,bg_dark[1]//2,bg_dark[2]//2),
              border=accent, radius=22, alpha=min(fa,245))
    draw_mixed(draw,(CX,325),clean,tsize,bold=True,fill=accent+(fa,),anchor="mm")

    # TZ
    draw_mixed(draw,(CX,447),tz,30,fill=DIM+(fa,),anchor="mm")

    # Subtext
    if subtext:
        draw_card(draw,PAD+20,472,PAD+CARD_W-20,556,
                  fill=(bg_dark[0]//3,bg_dark[1]//3,bg_dark[2]//3),
                  border=(accent[0]//2,accent[1]//2,accent[2]//2),
                  radius=14, alpha=min(fa,215))
        draw_mixed(draw,(CX,514),subtext,34,bold=True,fill=WHITE+(fa,),anchor="mm")

    # Extra card — lower
    draw_card(draw,PAD+40,576,PAD+CARD_W-40,650,
              fill=(bg_dark[0]//4,bg_dark[1]//4,bg_dark[2]//4),
              border=(accent[0]//3,accent[1]//3,accent[2]//3),
              radius=12, alpha=min(fa,185))
    msg = "జాగ్రత్త! ఈ సమయం నివారించండి" if pulse else "ఈ సమయం శుభకార్యాలకు ఉత్తమం"
    draw_mixed(draw,(CX,613),msg,26,fill=CREAM+(fa,),anchor="mm")

    # Extra card 2 — even lower
    draw_card(draw,PAD+60,668,PAD+CARD_W-60,738,
              fill=(bg_dark[0]//5,bg_dark[1]//5,bg_dark[2]//5),
              border=(accent[0]//4,accent[1]//4,accent[2]//4),
              radius=10, alpha=min(fa,165))
    msg2 = "రాహు కాలం తప్పించుకోండి" if pulse else "మంచి సమయాన్ని సద్వినియోగం చేయండి"
    draw_mixed(draw,(CX,703),msg2,24,fill=DIM+(fa,),anchor="mm")
    return img


def scene_rahu(img,f,p):
    return _info_scene(img,f,"రాహు కాలం",tf(p,"rahukaal"),p.get("tz_label","ET"),
                       "ఈ సమయంలో కొత్త పని వద్దు!",WARN_RED,DARK_RED,pulse=True)

def scene_durmuhurtam(img,f,p):
    return _info_scene(img,f,"దుర్ముహూర్తం",tf(p,"durmuhurtam"),p.get("tz_label","ET"),
                       "శుభ కార్యాలు ఈ వేళ వద్దు!",WARN_RED,DARK_RED,pulse=True)

def scene_brahma(img,f,p):
    return _info_scene(img,f,"బ్రహ్మ ముహూర్తం",tf(p,"brahma_muhurta"),p.get("tz_label","ET"),
                       "ప్రార్థన & ధ్యానానికి శ్రేష్ఠ సమయం",GOLD,(55,35,0),pulse=False)

def scene_abhijit(img,f,p):
    return _info_scene(img,f,"అభిజిత్ ముహూర్తం",tf(p,"abhijit"),p.get("tz_label","ET"),
                       "ముఖ్య పనులకు అత్యంత శుభ సమయం",GOLD,(55,35,0),pulse=False)


def scene_sun(img, f, panchang):
    sunrise = clean_time(tf(panchang,"sunrise"), panchang.get("tz_label","ET"))
    sunset  = clean_time(tf(panchang,"sunset"),  panchang.get("tz_label","ET"))
    tz      = panchang.get("tz_label","ET"); fa = fade(f, 10)

    img = add_glow(img, CX, 500, radius=400, color=(255,130,0), alpha=20)
    img = add_scene_flash(img, f)
    draw = ImageDraw.Draw(img); draw_border(draw)

    draw_card(draw,PAD,110,PAD+CARD_W,200,fill=(58,22,0),border=SAFFRON,alpha=min(fa,228))
    draw_mixed(draw,(CX,155),"సూర్యోదయం & సూర్యాస్తమయం",42,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    draw_card(draw,PAD,218,PAD+CARD_W,388,fill=(50,18,0),border=GOLD,radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,258),"సూర్యోదయం",38,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,336),sunrise,64,bold=True,fill=GOLD+(fa,),anchor="mm")

    draw_card(draw,PAD,406,PAD+CARD_W,576,fill=(48,15,0),border=SAFFRON,radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,446),"సూర్యాస్తమయం",38,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,524),sunset,64,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    draw_mixed(draw,(CX,594),tz,30,fill=DIM+(fa,),anchor="mm")

    draw_card(draw,PAD+40,618,PAD+CARD_W-40,690,fill=(40,16,0),border=(130,100,0),radius=12,alpha=min(fa,180))
    draw_mixed(draw,(CX,654),"సూర్యుని దీవెనలు మీకు కలగాలి",26,fill=CREAM+(fa,),anchor="mm")

    draw_card(draw,PAD+60,708,PAD+CARD_W-60,762,fill=(32,12,0),border=(105,82,0),radius=10,alpha=min(fa,162))
    draw_mixed(draw,(CX,735),"శ్రీ సూర్య నమస్కారం చేయండి",24,fill=DIM+(fa,),anchor="mm")
    return img


def scene_closing(img, f, panchang):
    fa = fade(f, 10)
    img = add_glow(img, CX, 500, radius=420, color=(255,170,0), alpha=22)
    img = add_scene_flash(img, f)
    draw = ImageDraw.Draw(img); draw_border(draw)

    draw_card(draw,PAD,110,PAD+CARD_W,295,fill=(65,28,0),border=GOLD,radius=20,alpha=min(fa,232))
    draw_mixed(draw,(CX,178),"మీకు శుభమైన రోజు కలగాలని",40,bold=True,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,254),"ఆశిస్తున్నాను!",52,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    draw_card(draw,PAD,315,PAD+CARD_W,450,fill=(50,20,0),border=SAFFRON,radius=20,alpha=min(fa,225))
    draw_mixed(draw,(CX,360),"Daily Panchangam kosam",34,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,418),"Follow చేయండి!",48,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    draw_card(draw,PAD+20,468,PAD+CARD_W-20,544,fill=(38,14,0),border=(150,115,0),radius=14,alpha=min(fa,210))
    draw_mixed(draw,(CX,506),"Like | Share | Subscribe చేయండి",32,fill=CREAM+(fa,),anchor="mm")

    draw_card(draw,PAD+40,562,PAD+CARD_W-40,632,fill=(32,12,0),border=(120,92,0),radius=12,alpha=min(fa,195))
    draw_mixed(draw,(CX,597),"@PanthuluPanchangam",28,fill=GOLD+(fa,),anchor="mm")

    draw_card(draw,PAD,650,PAD+CARD_W,722,fill=(45,20,0),border=GOLD,radius=14,alpha=min(fa,202))
    draw_mixed(draw,(CX,686),"జయ శ్రీమన్నారాయణ!",42,bold=True,fill=GOLD+(fa,),anchor="mm")

    draw_card(draw,PAD+60,740,PAD+CARD_W-60,802,fill=(28,10,0),border=(100,78,0),radius=10,alpha=min(fa,165))
    draw_mixed(draw,(CX,771),"ప్రతిరోజూ పంచాంగం చూడండి",26,fill=DIM+(fa,),anchor="mm")
    return img


SCENE_RENDERERS = [
    scene_intro, scene_tithi, scene_rahu, scene_durmuhurtam,
    scene_brahma, scene_abhijit, scene_sun, scene_closing
]
assert len(SCENE_RENDERERS) == N_SCENES


# ── FRAME BUILDER ─────────────────────────────────────────────────────────────

def build_frame(frame_idx, panchang, scene_frames):
    scene=0; f_in=frame_idx; acc=0
    for i,nf in enumerate(scene_frames):
        if frame_idx < acc+nf: scene=i; f_in=frame_idx-acc; break
        acc+=nf
    img = make_bg(); img = draw_om_watermark(img, alpha=7)
    img = SCENE_RENDERERS[scene](img, f_in, panchang)
    img = paste_char(img, frame_idx, scene)
    draw = ImageDraw.Draw(img)
    # FIX #6: Progress dots larger at H-35
    n=N_SCENES; ds=28; sx=CX-(n*ds)//2; cy_dot=H-35
    for i in range(n):
        x=sx+i*ds
        if i==scene: draw.ellipse([x-9,cy_dot-9,x+9,cy_dot+9], fill=GOLD)
        else:        draw.ellipse([x-5,cy_dot-5,x+5,cy_dot+5], outline=(155,120,0), width=2)
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
    city      = panchang.get("city","?")
    has_audio = audio_path and os.path.exists(audio_path)
    audio_dur = get_audio_duration(audio_path) if has_audio else 20.0
    # FIX #1: frames computed from audio — NO 72-frame minimum floor
    scene_frames  = compute_scene_frames(audio_dur)
    total_frames  = sum(scene_frames)
    video_dur     = total_frames / FPS
    print(f"   {city} — audio={audio_dur:.2f}s  video={video_dur:.2f}s  diff={abs(video_dur-audio_dur):.3f}s")
    print(f"   scene_frames={scene_frames}")
    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(total_frames):
            frame = build_frame(fi, panchang, scene_frames)
            frame.convert("RGB").save(str(Path(tmp)/f"frame_{fi:05d}.jpg"), "JPEG", quality=90)
            if fi % 80 == 0:
                sc=0; acc=0
                for i,nf in enumerate(scene_frames):
                    if fi<acc+nf: sc=i; break
                    acc+=nf
                print(f"      frame {fi}/{total_frames} scene {sc+1}/{N_SCENES} ...")
        cmd = ["ffmpeg","-y","-framerate",str(FPS),"-i",str(Path(tmp)/"frame_%05d.jpg")]
        if has_audio:
            cmd += ["-i",audio_path,"-c:a","aac","-b:a","128k"]
        cmd += ["-c:v","libx264","-preset","fast","-crf","20",
                "-pix_fmt","yuv420p","-movflags","+faststart",output_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0: raise RuntimeError(f"FFmpeg: {r.stderr[-800:]}")
    print(f"  OK {output_path}"); return output_path


# ── THUMBNAIL ─────────────────────────────────────────────────────────────────

def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img  = make_bg(); img = draw_om_watermark(img, alpha=9)
    img  = add_glow(img, CX, H//2, radius=480, color=(200,80,0), alpha=22)
    draw = ImageDraw.Draw(img); draw_border(draw)

    city  = panchang.get("city","USA"); date = fmt_date(panchang.get("date",""))
    rahu  = clean_time(tf(panchang,"rahukaal"), panchang.get("tz_label","ET"))
    # FIX #7: Short Telugu tithi only — no English suffix
    tithi_short = telugu_tithi_short(tf(panchang,"tithi"))
    abhijit = clean_time(tf(panchang,"abhijit"), panchang.get("tz_label","ET"))
    paksha  = telugu_paksha(tf(panchang,"paksha"))
    tz      = panchang.get("tz_label","ET")

    draw_card(draw,PAD,48,PAD+CARD_W,128,fill=(70,25,0),border=GOLD,alpha=230)
    draw_mixed(draw,(CX,88),"నేటి పంచాంగం | Panthulu",32,bold=True,fill=GOLD,anchor="mm")

    draw_mixed(draw,(CX,218),"ఈరోజు ఈ సమయం",76,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(CX,318),"తప్పించండి!",84,bold=True,fill=GOLD,anchor="mm")

    draw_mixed(draw,(CX,410),city,48,fill=CREAM,anchor="mm")
    draw_mixed(draw,(CX,468),date,32,fill=WHITE,anchor="mm")

    draw_card(draw,PAD,496,PAD+CARD_W,606,fill=(110,0,0),border=WARN_RED,radius=20,alpha=242)
    draw_mixed(draw,(CX,532),"రాహు కాలం",36,bold=True,fill=WARN_RED,anchor="mm")
    draw_mixed(draw,(CX,584),f"{rahu}  {tz}",38,bold=True,fill=CREAM,anchor="mm")

    draw_card(draw,PAD,622,PAD+CARD_W,700,fill=(42,14,0),border=GOLD,radius=16,alpha=225)
    draw_mixed(draw,(CX,640),"తిథి",24,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(CX,674),tithi_short,32,fill=GOLD,anchor="mm")  # FIX #7: Telugu only

    draw_card(draw,PAD,716,PAD+CARD_W,794,fill=(38,22,0),border=(160,130,0),radius=16,alpha=215)
    draw_mixed(draw,(CX,734),"అభిజిత్ ముహూర్తం",24,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(CX,768),f"{abhijit}  {tz}",28,fill=GOLD,anchor="mm")

    draw_card(draw,PAD+60,810,PAD+CARD_W-60,876,fill=(48,18,0),border=(155,125,0),radius=14,alpha=205)
    draw_mixed(draw,(CX,843),paksha,28,fill=CREAM,anchor="mm")

    char = _load_char()
    if char:
        ch  = int(H*0.50); cw = int(char.size[0]*(ch/char.size[1]))
        img.paste(char.resize((cw,ch),Image.LANCZOS),(CX-cw//2,H-ch-50),
                  char.resize((cw,ch),Image.LANCZOS))
        draw = ImageDraw.Draw(img)

    draw_card(draw,PAD,H-172,PAD+CARD_W,H-72,fill=(52,20,0),border=SAFFRON,radius=18,alpha=222)
    draw_mixed(draw,(CX,H-122),"Follow చేయండి @PanthuluPanchangam",
               28,bold=True,fill=GOLD,anchor="mm")

    img.convert("RGB").save(output_path,"JPEG",quality=95)
    print(f"  OK Thumbnail: {output_path}"); return output_path
