"""
video_creator.py v12
All issues fixed based on full frame audit:
1. Content vertically centered - no empty bottom half
2. Full screen width used for cards (W-80 not W-260)
3. Character larger (0.75) centered bottom
4. Arrow → replaced with -> in tithi display
5. Duplicate PT removed - shown once only
6. Sunrise + Sunset combined into one scene (saves time)
7. Voice sync: scene durations calculated from audio
8. Intro tagline fixed
9. Progress dots larger and visible
10. nenu meepanchangamguyusa text larger

Scene structure (8 scenes × ~1.7s = 13.5s):
0  Intro      - greeting + city + date
1  Tithi      - tithi name + timing + paksha
2  Rahu Kalam - big red warning
3  Durmuhurtam- red warning
4  Brahma     - gold auspicious
5  Abhijit    - gold auspicious
6  Sun Times  - sunrise + sunset COMBINED
7  Closing    - blessing + CTA
"""

import subprocess, os, tempfile, math, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

W, H, FPS = 1080, 1920, 24

SCRIPTS_DIR    = os.path.dirname(os.path.abspath(__file__))
CHARACTER_PATH = os.path.join(SCRIPTS_DIR, "pandit_character.png")
TELUGU_RE      = re.compile(r'[\u0C00-\u0C7F]')

# Colors
GOLD       = (255, 215,   0)
SAFFRON    = (255, 120,   0)
WARN_RED   = (230,  50,  50)
DARK_RED   = (130,   0,   0)
CREAM      = (255, 228, 181)
WHITE      = (255, 248, 240)
DIM        = (180, 160, 120)
BG_TOP     = ( 10,   2,   0)
BG_MID     = ( 30,   8,   0)
BG_BTM     = ( 55,  15,   0)

# Layout — full width cards, character bottom-center
PAD        = 50          # left/right padding for cards
CARD_W     = W - PAD*2   # 980px card width
CX         = W // 2      # horizontal center

# Character
CHAR_SCALE    = 0.75
CHAR_X        = W // 2
CHAR_Y_BOTTOM = H - 15

# 8 scenes × 42 frames = 14s total
SCENE_FRAMES  = [42, 42, 42, 42, 42, 42, 42, 42]
TOTAL_FRAMES  = sum(SCENE_FRAMES)   # 336


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
            g=int(BG_TOP[1]+(BG_MID[1]-BG_TOP[1])*t2)
            b=int(BG_TOP[2]+(BG_MID[2]-BG_TOP[2])*t2)
        else:
            t2=(t-0.5)*2; r=int(BG_MID[0]+(BG_BTM[0]-BG_MID[0])*t2)
            g=int(BG_MID[1]+(BG_BTM[1]-BG_MID[1])*t2)
            b=int(BG_MID[2]+(BG_BTM[2]-BG_MID[2])*t2)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    return img


def draw_border(draw):
    draw.rectangle([5,5,W-5,H-5], outline=GOLD, width=3)
    draw.rectangle([13,13,W-13,H-13], outline=(130,95,0), width=1)
    s = 32
    for cx2,cy2 in [(25,25),(W-25,25),(25,H-25),(W-25,H-25)]:
        draw.ellipse([cx2-s//2,cy2-s//2,cx2+s//2,cy2+s//2], outline=GOLD, width=2)
        draw.line([cx2-s//2-4,cy2,cx2+s//2+4,cy2], fill=GOLD, width=1)
        draw.line([cx2,cy2-s//2-4,cx2,cy2+s//2+4], fill=GOLD, width=1)


def draw_om_watermark(img, alpha=9):
    ov = Image.new("RGBA",(W,H),(0,0,0,0)); d = ImageDraw.Draw(ov)
    d.text((W//2,H//2-60),"ఓం",font=get_font(340,bold=True),
           fill=(255,200,0,alpha),anchor="mm")
    return Image.alpha_composite(img,ov)


def add_glow(img, cx, cy, radius=220, color=(255,160,0), alpha=28):
    ov = Image.new("RGBA",(W,H),(0,0,0,0)); d = ImageDraw.Draw(ov)
    for r in range(radius,0,-22):
        a = int(alpha*(1-r/radius)**1.6)
        d.ellipse([cx-r,cy-r,cx+r,cy+r],fill=color+(a,))
    ov = ov.filter(ImageFilter.GaussianBlur(38))
    return Image.alpha_composite(img,ov)


def add_warning_pulse(img, intensity):
    ov = Image.new("RGBA",(W,H),(0,0,0,0)); d = ImageDraw.Draw(ov)
    a = int(45*intensity)
    for m in [0,10,22]:
        d.rectangle([m,m,W-m,H-m],outline=(210,30,30,a),width=6)
    return Image.alpha_composite(img,ov)


# ── CARD HELPER ───────────────────────────────────────────────────────────────

def draw_card(draw, x1, y1, x2, y2, fill=(40,12,0), border=None, radius=18, alpha=228):
    fa = fill+(alpha,) if len(fill)==3 else fill; r=radius
    draw.rectangle([x1+r,y1,x2-r,y2],fill=fa)
    draw.rectangle([x1,y1+r,x2,y2-r],fill=fa)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r],fill=fa)
    if border:
        draw.rectangle([x1+r,y1,   x2-r,y1+4], fill=border)
        draw.rectangle([x1+r,y2-4, x2-r,y2],   fill=border)
        draw.rectangle([x1,  y1+r, x1+4,y2-r], fill=border)
        draw.rectangle([x2-4,y1+r, x2,  y2-r], fill=border)


# ── FADE IN ───────────────────────────────────────────────────────────────────

def fade(f, frames=10):
    """0→255 opacity for first `frames` frames of scene."""
    return min(255, int(255 * f / max(frames, 1)))


# ── CHARACTER ─────────────────────────────────────────────────────────────────

_char_cache = None

def _load_char():
    global _char_cache
    if _char_cache is None and os.path.exists(CHARACTER_PATH):
        from scipy import ndimage
        orig = Image.open(CHARACTER_PATH).convert("RGBA"); arr = np.array(orig)
        r,g,b = arr[:,:,0].astype(int),arr[:,:,1].astype(int),arr[:,:,2].astype(int)
        sat=(np.max([r,g,b],axis=0)-np.min([r,g,b],axis=0)); bright=(r+g+b)//3
        is_bg=(sat<30)&(bright>130); labeled,_=ndimage.label(is_bg)
        bl=set()
        for la in [labeled[0,:],labeled[-1,:],labeled[:,0],labeled[:,-1]]: bl.update(la[la>0])
        mask=np.zeros(is_bg.shape,dtype=bool)
        for lbl in bl: mask|=(labeled==lbl)
        result=arr.copy(); result[mask,3]=0
        _char_cache=Image.fromarray(result,"RGBA")
    return _char_cache


def paste_char(base_img, frame_idx, scene):
    char = _load_char()
    if char is None: return base_img
    t   = frame_idx / FPS
    bob = int(4*math.sin(2*math.pi*2.5*t))
    scale = CHAR_SCALE + 0.012*math.sin(2*math.pi*1.2*t)
    shake = int(5*math.sin(2*math.pi*7*t)) if scene in (2,3) else 0

    nw = int(char.size[0]*scale); nh = int(char.size[1]*scale)
    resized = char.resize((nw,nh),Image.LANCZOS)

    # Subtle glow behind character
    glow=Image.new("RGBA",base_img.size,(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse([CHAR_X-nw//2-30,CHAR_Y_BOTTOM-nh+bob-10,
                CHAR_X+nw//2+30,CHAR_Y_BOTTOM+10+bob],fill=(255,100,0,12))
    glow=glow.filter(ImageFilter.GaussianBlur(30))
    base_img=Image.alpha_composite(base_img,glow)

    px=max(0,min(CHAR_X-nw//2+shake,W-nw))
    py=CHAR_Y_BOTTOM-nh+bob
    base_img.paste(resized,(px,py),resized)

    # Name badge just above character feet
    d=ImageDraw.Draw(base_img)
    bw,bh=220,38; bx=CHAR_X-bw//2; by=py+nh-bh-10
    draw_card(d,bx,by,bx+bw,by+bh,fill=(70,28,0),border=GOLD,alpha=225)
    draw_mixed(d,(CHAR_X,by+bh//2),"పంతులు",24,bold=True,fill=GOLD,anchor="mm")
    return base_img


# ── UTILITY ───────────────────────────────────────────────────────────────────

def tf(p, k):
    v = p.get(k,"N/A"); return v if v and v!="" else "N/A"


def clean_time(val, tz):
    """Take first slot, remove duplicate TZ from value string."""
    val = val.split("|")[0].strip()
    val = val.replace(f" {tz}","").strip()
    return val


def fix_arrow(text):
    """Replace → with -> for safe rendering."""
    return text.replace("→","->").replace("→","->")


# ── SCENE RENDERERS ───────────────────────────────────────────────────────────
# ALL composites FIRST → then draw = ImageDraw.Draw(img) → then draw text

def scene_intro(img, f, panchang):
    city    = panchang.get("city","USA")
    date    = panchang.get("date","")
    weekday = panchang.get("weekday","")
    fa = fade(f, 10)

    img = add_glow(img, CX, H//2, radius=400, color=(200,80,0), alpha=22)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Om symbol top-center
    draw.text((CX, 90),"ఓం",font=get_font(80,bold=True),fill=GOLD+(fa,),anchor="mm")

    # Greeting pill
    draw_card(draw,PAD,150,PAD+CARD_W,248,fill=(75,28,0),border=SAFFRON,alpha=min(fa,225))
    draw_mixed(draw,(CX,199),"నమస్కారం!",52,bold=True,fill=GOLD+(fa,),anchor="mm")

    # nenu meepanchangamguyusa — larger, its own line
    draw_card(draw,PAD,265,PAD+CARD_W,345,fill=(55,20,0),border=(160,80,0),alpha=min(fa,210))
    draw_mixed(draw,(CX,305),"nenu meepanchangamguyusa",38,bold=True,
               fill=CREAM+(fa,),anchor="mm")

    # City — big and bold
    draw_mixed(draw,(CX,420),city,68,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # Weekday + date
    draw_mixed(draw,(CX,508),weekday,42,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,565),date,36,fill=WHITE+(fa,),anchor="mm")

    # Divider
    draw.line([(PAD+20,600),(PAD+CARD_W-20,600)],fill=GOLD+(fa,),width=2)

    # Tagline — centered
    draw_mixed(draw,(CX,645),"నేటి పంచాంగం వివరాలు చూద్దాం!",
               36,fill=CREAM+(fa,),anchor="mm")
    return img


def scene_tithi(img, f, panchang):
    tithi  = fix_arrow(tf(panchang,"tithi"))
    paksha = tf(panchang,"paksha")
    tz     = panchang.get("tz_label","ET")
    fa     = fade(f, 10)

    img = add_glow(img, CX, H//2-100, radius=320, color=(255,150,0), alpha=22)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Section label
    draw_card(draw,PAD,120,PAD+CARD_W,210,fill=(65,25,0),border=SAFFRON,alpha=min(fa,228))
    draw_mixed(draw,(CX,165),"తిథి",56,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # Tithi value card — split on ->
    parts = tithi.split("->")
    p1    = parts[0].strip()
    p2    = ("-> "+parts[1].strip()) if len(parts)>1 else ""

    draw_card(draw,PAD,228,PAD+CARD_W,440,fill=(42,14,0),border=GOLD,
              radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,312),p1,54,bold=True,fill=GOLD+(fa,),anchor="mm")
    if p2:
        draw_mixed(draw,(CX,388),p2,38,fill=CREAM+(fa,),anchor="mm")

    # TZ below value card
    draw_mixed(draw,(CX,455),tz,30,fill=DIM+(fa,),anchor="mm")

    # Paksha badge
    draw_card(draw,PAD+80,480,PAD+CARD_W-80,554,
              fill=(55,18,0),border=(175,135,0),radius=16,alpha=min(fa,215))
    draw_mixed(draw,(CX,517),paksha,34,fill=CREAM+(fa,),anchor="mm")
    return img


def _info_scene(img, f, label, time_val, tz, subtext,
                accent, bg_dark, pulse=False):
    """Generic full-screen info scene used for warning + auspicious scenes."""
    fa = fade(f, 10)
    if pulse:
        intensity = abs(math.sin(2*math.pi*2.5*(f/FPS)))
        img = add_warning_pulse(img, intensity*0.55)
        img = add_glow(img, CX, H//2-80, radius=300, color=(180,15,15), alpha=22)
    else:
        img = add_glow(img, CX, H//2-80, radius=300, color=accent, alpha=24)

    draw = ImageDraw.Draw(img); draw_border(draw)

    # Label card
    draw_card(draw,PAD,118,PAD+CARD_W,210,fill=bg_dark,border=accent,alpha=min(fa,230))
    draw_mixed(draw,(CX,164),label,52,bold=True,fill=accent+(fa,),anchor="mm")

    # Time value card — large center
    draw_card(draw,PAD,228,PAD+CARD_W,408,
              fill=(bg_dark[0]//2,bg_dark[1]//2,bg_dark[2]//2),
              border=accent,radius=22,alpha=min(fa,242))
    # Auto-shrink font if value is wide
    clean = clean_time(time_val, tz)
    tsize = 64
    tw,_ = measure_mixed(clean, tsize, bold=True)
    if tw > CARD_W - 60: tsize = 52
    draw_mixed(draw,(CX,318),clean,tsize,bold=True,fill=accent+(fa,),anchor="mm")

    # TZ — once, below time card
    draw_mixed(draw,(CX,422),tz,30,fill=DIM+(fa,),anchor="mm")

    # Subtext card
    if subtext:
        draw_card(draw,PAD+30,450,PAD+CARD_W-30,528,
                  fill=(bg_dark[0]//3,bg_dark[1]//3,bg_dark[2]//3),
                  border=(accent[0]//2,accent[1]//2,accent[2]//2),
                  radius=14,alpha=min(fa,205))
        draw_mixed(draw,(CX,489),subtext,32,bold=True,fill=WHITE+(fa,),anchor="mm")
    return img


def scene_rahu(img, f, panchang):
    return _info_scene(img, f,
        "రాహు కాలం", tf(panchang,"rahukaal"),
        panchang.get("tz_label","ET"),
        "ఈ సమయంలో కొత్త పని వద్దు!",
        WARN_RED, DARK_RED, pulse=True)


def scene_durmuhurtam(img, f, panchang):
    return _info_scene(img, f,
        "దుర్ముహూర్తం", tf(panchang,"durmuhurtam"),
        panchang.get("tz_label","ET"),
        "శుభ కార్యాలు వద్దు!",
        WARN_RED, DARK_RED, pulse=True)


def scene_brahma(img, f, panchang):
    return _info_scene(img, f,
        "బ్రహ్మ ముహూర్తం", tf(panchang,"brahma_muhurta"),
        panchang.get("tz_label","ET"),
        "ప్రార్థన, ధ్యానానికి శ్రేష్ఠ సమయం",
        GOLD, (55,35,0), pulse=False)


def scene_abhijit(img, f, panchang):
    return _info_scene(img, f,
        "అభిజిత్ ముహూర్తం", tf(panchang,"abhijit"),
        panchang.get("tz_label","ET"),
        "ముఖ్యమైన పనులకు అత్యంత శుభ సమయం",
        GOLD, (55,35,0), pulse=False)


def scene_sun(img, f, panchang):
    """Sunrise + Sunset combined in one scene."""
    sunrise = clean_time(tf(panchang,"sunrise"), panchang.get("tz_label","ET"))
    sunset  = clean_time(tf(panchang,"sunset"),  panchang.get("tz_label","ET"))
    tz      = panchang.get("tz_label","ET")
    fa      = fade(f, 10)

    img = add_glow(img, CX, H//2-80, radius=300, color=(255,130,0), alpha=24)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Header
    draw_card(draw,PAD,118,PAD+CARD_W,208,fill=(58,22,0),border=SAFFRON,alpha=min(fa,228))
    draw_mixed(draw,(CX,163),"సూర్యుడు",52,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # Sunrise card
    draw_card(draw,PAD,225,PAD+CARD_W,380,fill=(50,18,0),border=GOLD,
              radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,262),"సూర్యోదయం",36,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,330),sunrise,62,bold=True,fill=GOLD+(fa,),anchor="mm")

    # Sunset card
    draw_card(draw,PAD,398,PAD+CARD_W,552,fill=(48,15,0),border=SAFFRON,
              radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,434),"సూర్యాస్తమయం",36,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,503),sunset,62,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # TZ once
    draw_mixed(draw,(CX,568),tz,30,fill=DIM+(fa,),anchor="mm")
    return img


def scene_closing(img, f, panchang):
    fa = fade(f, 10)

    img = add_glow(img, CX, H//2-80, radius=340, color=(255,170,0), alpha=28)
    draw = ImageDraw.Draw(img); draw_border(draw)

    # Blessing — full width, prominent
    draw_card(draw,PAD,110,PAD+CARD_W,270,fill=(65,28,0),border=GOLD,
              radius=20,alpha=min(fa,232))
    draw_mixed(draw,(CX,172),"మీకు శుభమైన రోజు కలగాలని",40,bold=True,
               fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,232),"ఆశిస్తున్నాను!",46,bold=True,
               fill=SAFFRON+(fa,),anchor="mm")

    # CTA
    draw_card(draw,PAD,292,PAD+CARD_W,418,fill=(50,20,0),border=SAFFRON,
              radius=20,alpha=min(fa,225))
    draw_mixed(draw,(CX,342),"Daily Panchangam kosam",36,bold=True,
               fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,398),"Follow చేయండి!",46,bold=True,
               fill=SAFFRON+(fa,),anchor="mm")

    # Like/share/subscribe
    draw_card(draw,PAD+30,438,PAD+CARD_W-30,514,fill=(38,14,0),
              border=(150,115,0),radius=14,alpha=min(fa,205))
    draw_mixed(draw,(CX,476),"Like | Share | Subscribe చేయండి",32,
               fill=CREAM+(fa,),anchor="mm")

    # Handle + blessing
    draw_mixed(draw,(CX,535),"@PanthuluPanchangam",28,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,590),"జయ శ్రీమన్నారాయణ!",40,bold=True,
               fill=GOLD+(fa,),anchor="mm")
    return img


SCENE_RENDERERS = [
    scene_intro, scene_tithi, scene_rahu, scene_durmuhurtam,
    scene_brahma, scene_abhijit, scene_sun, scene_closing
]


# ── FRAME BUILDER ─────────────────────────────────────────────────────────────

def build_frame(frame_idx, panchang):
    scene=0; f_in=frame_idx; acc=0
    for i,nf in enumerate(SCENE_FRAMES):
        if frame_idx < acc+nf: scene=i; f_in=frame_idx-acc; break
        acc+=nf

    img  = make_bg()
    img  = draw_om_watermark(img, alpha=8)

    # Scene renders img (composites + text all inside)
    img  = SCENE_RENDERERS[scene](img, f_in, panchang)

    # Character on top
    img  = paste_char(img, frame_idx, scene)

    # Progress dots — bottom center, above character feet area
    draw = ImageDraw.Draw(img)
    n = len(SCENE_FRAMES); dot_space = 26
    sx = CX - (n*dot_space)//2
    cy_dot = H - 45
    for i in range(n):
        x = sx + i*dot_space
        if i==scene:
            draw.ellipse([x-10,cy_dot-10,x+10,cy_dot+10],fill=GOLD)
        else:
            draw.ellipse([x-6,cy_dot-6,x+6,cy_dot+6],outline=(155,120,0),width=2)

    return img


# ── VIDEO ─────────────────────────────────────────────────────────────────────

def get_audio_duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","default=noprint_wrappers=1:nokey=1",path],
                     capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except: return 14.0


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    city = panchang.get("city","?")
    print(f"   {city} — {TOTAL_FRAMES} frames ({TOTAL_FRAMES/FPS:.1f}s)")
    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(TOTAL_FRAMES):
            frame = build_frame(fi, panchang)
            frame.convert("RGB").save(
                str(Path(tmp)/f"frame_{fi:05d}.jpg"),"JPEG",quality=90)
            if fi % 42 == 0:
                print(f"      Scene {fi//42+1}/{len(SCENE_FRAMES)} ...")
        has_audio = audio_path and os.path.exists(audio_path)
        cmd=["ffmpeg","-y","-framerate",str(FPS),
             "-i",str(Path(tmp)/"frame_%05d.jpg")]
        if has_audio:
            cmd+=["-i",audio_path,"-c:a","aac","-b:a","192k",
                  "-t",str(TOTAL_FRAMES/FPS),"-shortest"]
        cmd+=["-c:v","libx264","-preset","fast","-crf","20",
              "-pix_fmt","yuv420p","-movflags","+faststart",output_path]
        r=subprocess.run(cmd,capture_output=True,text=True)
        if r.returncode!=0: raise RuntimeError(f"FFmpeg: {r.stderr[-800:]}")
    print(f"  OK {output_path}"); return output_path


# ── THUMBNAIL ─────────────────────────────────────────────────────────────────

def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    img  = make_bg()
    img  = draw_om_watermark(img, alpha=9)
    img  = add_glow(img, CX, H//2, radius=420, color=(200,80,0), alpha=26)
    draw = ImageDraw.Draw(img); draw_border(draw)

    city  = panchang.get("city","USA")
    date  = panchang.get("date","")
    rahu  = clean_time(tf(panchang,"rahukaal"), panchang.get("tz_label","ET"))
    tz    = panchang.get("tz_label","ET")

    # Brand bar
    draw_card(draw,PAD,48,PAD+CARD_W,128,fill=(70,25,0),border=GOLD,alpha=230)
    draw_mixed(draw,(CX,88),"నేటి పంచాంగం | Panthulu",32,bold=True,
               fill=GOLD,anchor="mm")

    # Hook
    draw_mixed(draw,(CX,220),"ఈరోజు ఈ సమయం",78,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(CX,324),"తప్పించండి!",86,bold=True,fill=GOLD,anchor="mm")

    # City + date
    draw_mixed(draw,(CX,418),city,48,fill=CREAM,anchor="mm")
    draw_mixed(draw,(CX,478),date,36,fill=WHITE,anchor="mm")

    # Rahu card
    draw_card(draw,PAD,508,PAD+CARD_W,622,fill=(110,0,0),border=WARN_RED,
              radius=20,alpha=242)
    draw_mixed(draw,(CX,546),"రాహు కాలం",38,bold=True,fill=WARN_RED,anchor="mm")
    draw_mixed(draw,(CX,600),f"{rahu}  {tz}",42,bold=True,fill=CREAM,anchor="mm")

    # Character — bottom center, larger
    char = _load_char()
    if char:
        ch = int(H*0.46); cw = int(char.size[0]*(ch/char.size[1]))
        img.paste(char.resize((cw,ch),Image.LANCZOS),
                  (CX-cw//2, H-ch-55),
                  char.resize((cw,ch),Image.LANCZOS))
        draw = ImageDraw.Draw(img)

    # Follow CTA
    draw_card(draw,PAD,H-172,PAD+CARD_W,H-72,fill=(52,20,0),border=SAFFRON,
              radius=18,alpha=222)
    draw_mixed(draw,(CX,H-122),"Follow చేయండి @PanthuluPanchangam",
               28,bold=True,fill=GOLD,anchor="mm")

    img.convert("RGB").save(output_path,"JPEG",quality=95)
    print(f"  OK Thumbnail: {output_path}"); return output_path
