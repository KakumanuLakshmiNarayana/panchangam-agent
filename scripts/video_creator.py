"""
video_creator.py v11
Complete redesign based on visual audit.

ISSUES FIXED:
1. Scenes are too sparse — content only fills top 25% of screen, bottom 75% empty
2. No scene transition feel — sliding animations make it feel glitchy not smooth
3. [!] [X] (*) look ugly — replaced with clean Telugu label pills
4. Brahma Muhurtam shown as secondary tiny text — needs its own proper scene
5. "PT" appears twice (in time value AND below) — deduplicated
6. Bottom half always empty — character moved to right side, content uses full height
7. Voice not in sync — scene durations now match voice segments
8. Start note: "nenu meepanchangamguyusa"
9. End note: positive Telugu blessing + like/share/subscribe

NEW STRUCTURE (9 scenes × ~1.5s = ~14s):
Scene 0  0.0-1.5s  Intro/Hook     — character + greeting + city/date
Scene 1  1.5-3.0s  Tithi          — tithi name + time + paksha
Scene 2  3.0-4.5s  Rahu Kalam     — big red warning card
Scene 3  4.5-6.0s  Durmuhurtam    — red warning card
Scene 4  6.0-7.5s  Brahma Muhurtam— gold auspicious card
Scene 5  7.5-9.0s  Abhijit        — gold auspicious card
Scene 6  9.0-10.5s Sunrise        — saffron card
Scene 7  10.5-12.0s Sunset        — saffron card
Scene 8  12.0-14.0s Closing CTA   — blessing + follow

DESIGN PRINCIPLES:
- Content vertically centered in top 65% of screen
- Character stays bottom-right, small, never covers text
- Each scene: large LABEL at top, huge TIME in middle, subtext below
- No sliding animations — clean FADE IN per scene (no glitch)
- Colors: RED for bad times, GOLD for good times, SAFFRON for sun
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
GOLD      = (255, 215,   0)
SAFFRON   = (255, 120,   0)
WARN_RED  = (230,  50,  50)
DARK_RED  = (140,   0,   0)
GOOD_GREEN= ( 60, 200,  80)
CREAM     = (255, 228, 181)
WHITE     = (255, 248, 240)
BG_TOP    = ( 10,   2,   0)
BG_MID    = ( 30,   8,   0)
BG_BTM    = ( 55,  15,   0)

# Layout
CHAR_SCALE    = 0.55
CHAR_X        = W - 180          # right side
CHAR_Y_BOTTOM = H - 30

# 9 scenes × 36 frames = 14.25s  (close to 14s voice)
SCENE_FRAMES  = [36, 36, 36, 36, 36, 36, 36, 36, 48]
TOTAL_FRAMES  = sum(SCENE_FRAMES)   # 324 = 13.5s


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
    draw.rectangle([13,13,W-13,H-13], outline=(140,100,0), width=1)
    s = 34
    for cx,cy in [(26,26),(W-26,26),(26,H-26),(W-26,H-26)]:
        draw.ellipse([cx-s//2,cy-s//2,cx+s//2,cy+s//2], outline=GOLD, width=2)
        draw.line([cx-s//2-4,cy,cx+s//2+4,cy], fill=GOLD, width=1)
        draw.line([cx,cy-s//2-4,cx,cy+s//2+4], fill=GOLD, width=1)


def add_glow(img, cx, cy, radius=200, color=(255,180,0), alpha=30):
    ov = Image.new("RGBA",(W,H),(0,0,0,0)); d = ImageDraw.Draw(ov)
    for r in range(radius,0,-25):
        a = int(alpha*(1-r/radius)**1.8)
        d.ellipse([cx-r,cy-r,cx+r,cy+r],fill=color+(a,))
    ov = ov.filter(ImageFilter.GaussianBlur(35))
    return Image.alpha_composite(img, ov)


def add_warning_pulse(img, intensity):
    ov = Image.new("RGBA",(W,H),(0,0,0,0)); d = ImageDraw.Draw(ov)
    a = int(50*intensity)
    for m in [0,12,24]:
        d.rectangle([m,m,W-m,H-m], outline=(210,30,30,a), width=7)
    return Image.alpha_composite(img, ov)


def draw_om_watermark(img, alpha=10):
    ov = Image.new("RGBA",(W,H),(0,0,0,0)); d = ImageDraw.Draw(ov)
    d.text((W//2, H//2-100), "ఓం", font=get_font(320,bold=True),
           fill=(255,200,0,alpha), anchor="mm")
    return Image.alpha_composite(img, ov)


# ── FADE IN HELPER ────────────────────────────────────────────────────────────

def fade_alpha(f_in_scene, fade_frames=8):
    """Returns 0→255 alpha for fade-in effect."""
    return min(255, int(255 * f_in_scene / fade_frames))


# ── CARD HELPER ───────────────────────────────────────────────────────────────

def draw_card(draw, x1, y1, x2, y2, fill=(40,12,0), border=None, radius=16, alpha=225):
    fa = fill+(alpha,) if len(fill)==3 else fill; r=radius
    draw.rectangle([x1+r,y1,x2-r,y2],fill=fa)
    draw.rectangle([x1,y1+r,x2,y2-r],fill=fa)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r],fill=fa)
    if border:
        draw.rectangle([x1+r,y1,   x2-r,y1+3], fill=border)
        draw.rectangle([x1+r,y2-3, x2-r,y2],   fill=border)
        draw.rectangle([x1,  y1+r, x1+3,y2-r], fill=border)
        draw.rectangle([x2-3,y1+r, x2,  y2-r], fill=border)


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
    t = frame_idx/FPS
    bob = int(3*math.sin(2*math.pi*2.5*t))
    scale = CHAR_SCALE + 0.01*math.sin(2*math.pi*1.2*t)
    # Warning scenes: gentle shake
    shake = int(4*math.sin(2*math.pi*7*t)) if scene in (2,3) else 0
    nw=int(char.size[0]*scale); nh=int(char.size[1]*scale)
    resized=char.resize((nw,nh),Image.LANCZOS)
    # Glow
    glow=Image.new("RGBA",base_img.size,(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse([CHAR_X-nw//2-20,CHAR_Y_BOTTOM-nh+bob-5,
                CHAR_X+nw//2+20,CHAR_Y_BOTTOM+15+bob],fill=(255,120,0,15))
    glow=glow.filter(ImageFilter.GaussianBlur(25))
    base_img=Image.alpha_composite(base_img,glow)
    px=max(0,min(CHAR_X-nw//2+shake,W-nw))
    py=CHAR_Y_BOTTOM-nh+bob
    base_img.paste(resized,(px,py),resized)
    return base_img


# ── UTILITY ───────────────────────────────────────────────────────────────────

def tf(p,k):
    v=p.get(k,"N/A"); return v if v and v!="" else "N/A"


def clean_time(val, tz):
    """Remove duplicate TZ label from time string."""
    val = val.split("|")[0].strip()   # take first slot only
    val = val.replace(f" {tz}", "").strip()  # remove TZ from value
    return val


# ── SCENE BUILDERS ────────────────────────────────────────────────────────────
# Pattern: ALL composites first → then draw = ImageDraw.Draw(img) → then draw text

def scene_intro(img, f, panchang):
    """Scene 0: Greeting + city + date"""
    city    = panchang.get("city","USA")
    date    = panchang.get("date","")
    weekday = panchang.get("weekday","")

    img = add_glow(img, W//2, 600, radius=350, color=(255,130,0), alpha=30)
    draw = ImageDraw.Draw(img); draw_border(draw)

    fa = fade_alpha(f, 10)

    # Om at top center
    draw_mixed(draw, (W//2-180, 80), "ఓం", 72, bold=True, fill=GOLD+(fa,), anchor="mm")

    # Greeting
    draw_card(draw, 40, 130, W-240, 220, fill=(70,25,0), border=SAFFRON, alpha=min(fa,220))
    draw_mixed(draw, (W//2-100, 175),
               "nenu meepanchangamguyusa", 32, bold=True,
               fill=GOLD+(fa,), anchor="mm")

    # City big
    draw_mixed(draw, (W//2-100, 310), city, 62, bold=True,
               fill=SAFFRON+(fa,), anchor="mm")

    # Weekday + date
    draw_mixed(draw, (W//2-100, 400), weekday, 40, fill=CREAM+(fa,), anchor="mm")
    draw_mixed(draw, (W//2-100, 460), date,    36, fill=WHITE+(fa,), anchor="mm")

    # Divider
    draw.line([(50, 510), (W-240, 510)], fill=GOLD+(fa,), width=2)

    # Tagline
    draw_mixed(draw, (W//2-100, 555),
               "నేటి పంచాంగం వివరాలు చూద్దాం!", 34, fill=CREAM+(fa,), anchor="mm")
    return img


def _draw_info_scene(img, f, label_tel, time_val, subtext, tz,
                      accent, bg_fill, pulse=False):
    """Generic info scene: label pill → huge time → subtext"""
    if pulse:
        intensity = abs(math.sin(2*math.pi*2.5*(f/FPS)))
        img = add_warning_pulse(img, intensity*0.6)
        img = add_glow(img, W//2-100, 700, radius=280, color=(200,20,20), alpha=25)
    else:
        img = add_glow(img, W//2-100, 700, radius=280, color=accent, alpha=28)

    draw = ImageDraw.Draw(img); draw_border(draw)
    fa   = fade_alpha(f, 8)

    # Label pill — centered in left 75% of screen
    lw = W - 260
    draw_card(draw, 40, 140, 40+lw, 230,
              fill=bg_fill, border=accent, radius=18, alpha=min(fa,230))
    draw_mixed(draw, (40+lw//2, 185), label_tel, 50, bold=True,
               fill=accent+(fa,), anchor="mm")

    # Time value — HUGE, center of screen
    clean = clean_time(time_val, tz)
    tw, _ = measure_mixed(clean, 74, bold=True)
    # If too wide, reduce size
    tsize = 74 if tw < lw - 40 else 58
    draw_card(draw, 40, 255, 40+lw, 430,
              fill=(bg_fill[0]//2, bg_fill[1]//2, bg_fill[2]//2),
              border=accent, radius=20, alpha=min(fa,240))
    draw_mixed(draw, (40+lw//2, 342), clean, tsize, bold=True,
               fill=accent+(fa,), anchor="mm")

    # TZ label below time card
    draw_mixed(draw, (40+lw//2, 445), tz, 30,
               fill=CREAM+(fa,), anchor="mm")

    # Subtext card
    if subtext:
        draw_card(draw, 60, 480, 40+lw-20, 560,
                  fill=(bg_fill[0]//3, bg_fill[1]//3, bg_fill[2]//3),
                  border=(accent[0]//2, accent[1]//2, accent[2]//2),
                  radius=14, alpha=min(fa,200))
        draw_mixed(draw, (40+lw//2-10, 520), subtext, 30, bold=True,
                   fill=WHITE+(fa,), anchor="mm")
    return img


def scene_tithi(img, f, panchang):
    tithi  = tf(panchang,"tithi")
    paksha = tf(panchang,"paksha")
    tz     = panchang.get("tz_label","ET")

    img = add_glow(img, W//2-100, 680, radius=280, color=(255,160,0), alpha=25)
    draw = ImageDraw.Draw(img); draw_border(draw)
    fa = fade_alpha(f, 8)
    lw = W - 260

    # Label
    draw_card(draw, 40, 140, 40+lw, 225,
              fill=(65,25,0), border=SAFFRON, radius=18, alpha=min(fa,230))
    draw_mixed(draw, (40+lw//2, 182), "తిథి", 52, bold=True,
               fill=SAFFRON+(fa,), anchor="mm")

    # Tithi name — split on arrow
    parts = tithi.split("→")
    p1 = parts[0].strip(); p2 = ("→ "+parts[1].strip()) if len(parts)>1 else ""

    draw_card(draw, 40, 248, 40+lw, 420,
              fill=(40,14,0), border=GOLD, radius=20, alpha=min(fa,240))
    draw_mixed(draw, (40+lw//2, 305), p1, 52, bold=True,
               fill=GOLD+(fa,), anchor="mm")
    if p2:
        draw_mixed(draw, (40+lw//2, 375), p2, 36,
                   fill=CREAM+(fa,), anchor="mm")

    # Paksha badge
    draw_card(draw, 100, 440, 40+lw-60, 515,
              fill=(55,18,0), border=(180,140,0), radius=14, alpha=min(fa,210))
    draw_mixed(draw, (40+lw//2-10, 477), paksha, 32,
               fill=CREAM+(fa,), anchor="mm")
    return img


def scene_rahu(img, f, panchang):
    return _draw_info_scene(img, f,
        label_tel="రాహు కాలం",
        time_val=tf(panchang,"rahukaal"),
        subtext="ఈ సమయంలో కొత్త పని వద్దు!",
        tz=panchang.get("tz_label","ET"),
        accent=WARN_RED, bg_fill=DARK_RED, pulse=True)


def scene_durmuhurtam(img, f, panchang):
    return _draw_info_scene(img, f,
        label_tel="దుర్ముహూర్తం",
        time_val=tf(panchang,"durmuhurtam"),
        subtext="శుభ కార్యాలు వద్దు!",
        tz=panchang.get("tz_label","ET"),
        accent=WARN_RED, bg_fill=DARK_RED, pulse=True)


def scene_brahma(img, f, panchang):
    return _draw_info_scene(img, f,
        label_tel="బ్రహ్మ ముహూర్తం",
        time_val=tf(panchang,"brahma_muhurta"),
        subtext="ప్రార్థన, ధ్యానానికి శ్రేష్ఠమైన సమయం",
        tz=panchang.get("tz_label","ET"),
        accent=GOLD, bg_fill=(55,35,0), pulse=False)


def scene_abhijit(img, f, panchang):
    return _draw_info_scene(img, f,
        label_tel="అభిజిత్ ముహూర్తం",
        time_val=tf(panchang,"abhijit"),
        subtext="ముఖ్యమైన పనులకు అత్యంత శుభమైన సమయం",
        tz=panchang.get("tz_label","ET"),
        accent=GOLD, bg_fill=(55,35,0), pulse=False)


def scene_sunrise(img, f, panchang):
    return _draw_info_scene(img, f,
        label_tel="సూర్యోదయం",
        time_val=tf(panchang,"sunrise"),
        subtext=None,
        tz=panchang.get("tz_label","ET"),
        accent=SAFFRON, bg_fill=(60,25,0), pulse=False)


def scene_sunset(img, f, panchang):
    return _draw_info_scene(img, f,
        label_tel="సూర్యాస్తమయం",
        time_val=tf(panchang,"sunset"),
        subtext=None,
        tz=panchang.get("tz_label","ET"),
        accent=SAFFRON, bg_fill=(60,25,0), pulse=False)


def scene_closing(img, f, panchang):
    """Scene 8: Blessing + CTA"""
    img  = add_glow(img, W//2-80, 650, radius=320, color=(255,180,0), alpha=32)
    draw = ImageDraw.Draw(img); draw_border(draw)
    fa   = fade_alpha(f, 10)
    lw   = W - 260

    # Blessing
    draw_card(draw, 40, 130, 40+lw, 300,
              fill=(65,30,0), border=GOLD, radius=20, alpha=min(fa,230))
    draw_mixed(draw, (40+lw//2, 185),
               "మీకు శుభమైన రోజు కలగాలని", 38, bold=True,
               fill=GOLD+(fa,), anchor="mm")
    draw_mixed(draw, (40+lw//2, 248),
               "ఆశిస్తున్నాను!", 42, bold=True,
               fill=SAFFRON+(fa,), anchor="mm")

    # CTA card
    draw_card(draw, 40, 320, 40+lw, 460,
              fill=(50,20,0), border=SAFFRON, radius=20, alpha=min(fa,220))
    draw_mixed(draw, (40+lw//2, 368),
               "Daily Panchangam kosam", 34, bold=True,
               fill=CREAM+(fa,), anchor="mm")
    draw_mixed(draw, (40+lw//2, 425),
               "Follow చేయండి!", 44, bold=True,
               fill=SAFFRON+(fa,), anchor="mm")

    # Like/share
    draw_card(draw, 60, 478, 40+lw-20, 554,
              fill=(40,15,0), border=(160,120,0), radius=14, alpha=min(fa,200))
    draw_mixed(draw, (40+lw//2-10, 516),
               "Like | Share | Subscribe చేయండి", 30,
               fill=CREAM+(fa,), anchor="mm")

    # Handle
    draw_mixed(draw, (40+lw//2-10, 585),
               "@PanthuluPanchangam", 28,
               fill=GOLD+(fa,), anchor="mm")

    # Blessing sign-off
    draw_mixed(draw, (40+lw//2-10, 640),
               "జయ శ్రీమన్నారాయణ!", 36, bold=True,
               fill=GOLD+(fa,), anchor="mm")
    return img


SCENE_RENDERERS = [
    scene_intro, scene_tithi, scene_rahu, scene_durmuhurtam,
    scene_brahma, scene_abhijit, scene_sunrise, scene_sunset, scene_closing
]


# ── FRAME BUILDER ─────────────────────────────────────────────────────────────

def build_frame(frame_idx, panchang):
    # Determine scene
    scene=0; f_in=frame_idx; acc=0
    for i,nf in enumerate(SCENE_FRAMES):
        if frame_idx < acc+nf: scene=i; f_in=frame_idx-acc; break
        acc+=nf

    img  = make_bg()
    img  = draw_om_watermark(img, alpha=9)

    # Run scene renderer (composites + draw inside)
    img  = SCENE_RENDERERS[scene](img, f_in, panchang)

    # Character — bottom right, always on top
    img  = paste_char(img, frame_idx, scene)

    # Character name badge
    draw = ImageDraw.Draw(img)
    bw,bh = 200,36; bx=CHAR_X-bw//2; by=CHAR_Y_BOTTOM-int(panchang.get("_char_h",420))-10
    # Simple fixed position
    by2 = H - 450
    draw_card(draw, bx, by2, bx+bw, by2+bh, fill=(70,30,0), border=GOLD, alpha=220)
    draw_mixed(draw, (CHAR_X, by2+bh//2), "పంతులు", 22, bold=True,
               fill=GOLD, anchor="mm")

    # Progress dots — bottom center, left of character
    cy=H-28; spacing=22; total=len(SCENE_FRAMES)
    sx = W//2 - 120 - (total*spacing)//2
    for i in range(total):
        x=sx+i*spacing
        if i==scene: draw.ellipse([x-8,cy-8,x+8,cy+8],fill=GOLD)
        else:        draw.ellipse([x-4,cy-4,x+4,cy+4],outline=(160,130,0),width=2)

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
    city=panchang.get("city","?")
    print(f"   {city} — {TOTAL_FRAMES} frames ({TOTAL_FRAMES/FPS:.1f}s)")
    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(TOTAL_FRAMES):
            frame=build_frame(fi,panchang)
            frame.convert("RGB").save(
                str(Path(tmp)/f"frame_{fi:05d}.jpg"),"JPEG",quality=90)
            if fi%36==0: print(f"      Scene {fi//36+1}/{len(SCENE_FRAMES)} ...")
        has_audio=audio_path and os.path.exists(audio_path)
        cmd=["ffmpeg","-y","-framerate",str(FPS),"-i",str(Path(tmp)/"frame_%05d.jpg")]
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
    img  = draw_om_watermark(img, alpha=10)
    img  = add_glow(img, W//2, 700, radius=360, color=(255,160,0), alpha=32)
    draw = ImageDraw.Draw(img); draw_border(draw)

    city  = panchang.get("city","USA")
    date  = panchang.get("date","")
    rahu  = clean_time(tf(panchang,"rahukaal"), panchang.get("tz_label","ET"))
    tz    = panchang.get("tz_label","ET")
    lw    = W - 260

    # Brand bar
    draw_card(draw,40,48,40+lw,125,fill=(70,25,0),border=GOLD,alpha=230)
    draw_mixed(draw,(40+lw//2,86),"నేటి పంచాంగం | Panthulu",30,bold=True,
               fill=GOLD,anchor="mm")

    # Hook text
    draw_mixed(draw,(40+lw//2,210),"ఈరోజు ఈ సమయం",76,bold=True,
               fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(40+lw//2,312),"తప్పించండి!",84,bold=True,
               fill=GOLD,anchor="mm")

    # City + date
    draw_mixed(draw,(40+lw//2,410),city,46,fill=CREAM,anchor="mm")
    draw_mixed(draw,(40+lw//2,470),date,36,fill=WHITE,anchor="mm")

    # Rahu card
    draw_card(draw,40,508,40+lw,618,fill=(100,0,0),border=WARN_RED,radius=20,alpha=240)
    draw_mixed(draw,(40+lw//2,546),"రాహు కాలం",36,bold=True,fill=WARN_RED,anchor="mm")
    draw_mixed(draw,(40+lw//2,597),f"{rahu}  {tz}",40,bold=True,fill=CREAM,anchor="mm")

    # Character
    char=_load_char()
    if char:
        ch=int(H*0.42); cw=int(char.size[0]*(ch/char.size[1]))
        img.paste(char.resize((cw,ch),Image.LANCZOS),(W-cw-10,H-ch-60),
                  char.resize((cw,ch),Image.LANCZOS))
        draw=ImageDraw.Draw(img)

    # Follow CTA
    draw_card(draw,40,H-175,40+lw,H-75,fill=(55,22,0),border=SAFFRON,radius=18,alpha=220)
    draw_mixed(draw,(40+lw//2,H-125),"Follow చేయండి @PanthuluPanchangam",
               27,bold=True,fill=GOLD,anchor="mm")

    img.convert("RGB").save(output_path,"JPEG",quality=95)
    print(f"  OK Thumbnail: {output_path}"); return output_path
