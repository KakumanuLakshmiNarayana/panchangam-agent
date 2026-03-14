"""
video_creator.py v10
FIXES:
1. alpha_composite bug — draw object recreated after every glow/composite call
2. Character scale increased to 0.65
3. Special emoji replaced with safe text alternatives
4. Progress dots moved above character badge
5. ✦ replaced with | in brand bar
6. All 7 scenes render correctly with text visible
7 scenes: Hook -> Tithi -> Rahu Kalam -> Durmuhurtam -> Muhurtham -> Sunrise -> CTA
"""

import subprocess, os, tempfile, math, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

W, H, FPS = 1080, 1920, 24

SCRIPTS_DIR    = os.path.dirname(os.path.abspath(__file__))
CHARACTER_PATH = os.path.join(SCRIPTS_DIR, "pandit_character.png")
TELUGU_RE      = re.compile(r'[\u0C00-\u0C7F]')

GOLD      = (255, 215,   0)
SAFFRON   = (255, 107,   0)
WARN_RED  = (255,  60,  60)
CREAM     = (255, 228, 181)
WHITE     = (255, 248, 240)
BG_TOP    = ( 12,   3,   0)
BG_MID    = ( 35,  10,   0)
BG_BTM    = ( 60,  20,   0)

CHAR_SCALE    = 0.65
CHAR_X        = W // 2
CHAR_Y_BOTTOM = H - 20
CONTENT_Y_END = int(H * 0.68)

SCENE_FRAMES  = [48, 48, 48, 48, 48, 48, 48]   # 7 x 2s = 14s
TOTAL_FRAMES  = sum(SCENE_FRAMES)               # 336


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
    if anchor == "mm": x -= tw // 2; y -= th // 2
    elif anchor == "ra": x -= tw
    for is_tel, run in runs:
        f = tel if is_tel else lat
        draw.text((x, y), run, font=f, fill=fill)
        bb = f.getbbox(run); x += bb[2] - bb[0]


# ── BACKGROUND / BORDER ───────────────────────────────────────────────────────

def make_bg():
    img = Image.new("RGBA", (W, H), (0,0,0,255))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        if t < 0.5:
            t2=t*2; r=int(BG_TOP[0]+(BG_MID[0]-BG_TOP[0])*t2)
            g=int(BG_TOP[1]+(BG_MID[1]-BG_TOP[1])*t2); b=int(BG_TOP[2]+(BG_MID[2]-BG_TOP[2])*t2)
        else:
            t2=(t-0.5)*2; r=int(BG_MID[0]+(BG_BTM[0]-BG_MID[0])*t2)
            g=int(BG_MID[1]+(BG_BTM[1]-BG_MID[1])*t2); b=int(BG_MID[2]+(BG_BTM[2]-BG_MID[2])*t2)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    return img


def draw_border(draw):
    draw.rectangle([6,6,W-6,H-6], outline=GOLD, width=3)
    draw.rectangle([14,14,W-14,H-14], outline=(160,120,0), width=1)
    s = 38
    for cx, cy in [(28,28),(W-28,28),(28,H-28),(W-28,H-28)]:
        draw.ellipse([cx-s//2,cy-s//2,cx+s//2,cy+s//2], outline=GOLD, width=2)
        draw.line([cx-s//2-4,cy,cx+s//2+4,cy], fill=GOLD, width=1)
        draw.line([cx,cy-s//2-4,cx,cy+s//2+4], fill=GOLD, width=1)


def draw_card(draw, x1, y1, x2, y2, fill=(40,12,0), border=None, radius=20, alpha=220):
    fa = fill+(alpha,) if len(fill)==3 else fill; r = radius
    draw.rectangle([x1+r,y1,x2-r,y2], fill=fa)
    draw.rectangle([x1,y1+r,x2,y2-r], fill=fa)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r], fill=fa)
    if border:
        draw.rectangle([x1+r,y1,   x2-r,y1+3],   fill=border)
        draw.rectangle([x1+r,y2-3, x2-r,y2],     fill=border)
        draw.rectangle([x1,  y1+r, x1+3,y2-r],   fill=border)
        draw.rectangle([x2-3,y1+r, x2,  y2-r],   fill=border)


# ── FX HELPERS (return new img — caller must recreate draw after calling) ──────

def add_glow(img, cx, cy, radius=220, color=(255,200,0), alpha=35):
    ov = Image.new("RGBA", (W,H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    for r in range(radius, 0, -20):
        a = int(alpha * (1 - r/radius)**1.5)
        d.ellipse([cx-r,cy-r,cx+r,cy+r], fill=color+(a,))
    ov = ov.filter(ImageFilter.GaussianBlur(30))
    return Image.alpha_composite(img, ov)


def add_sparkles(img, cx, cy, n=8, t=0.0):
    ov = Image.new("RGBA", (W,H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    for i in range(n):
        angle = 2*math.pi*i/n + t*3
        dist  = 160 + 20*math.sin(t*4+i)
        sx,sy = int(cx+dist*math.cos(angle)), int(cy+dist*math.sin(angle))
        sz    = int(8+4*math.sin(t*5+i*1.3))
        d.ellipse([sx-sz,sy-sz,sx+sz,sy+sz], fill=(255,220,50,200))
    return Image.alpha_composite(img, ov)


def add_warning_pulse(img, intensity):
    ov = Image.new("RGBA", (W,H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    a  = int(60 * intensity)
    for margin in [0, 15, 30]:
        d.rectangle([margin,margin,W-margin,H-margin], outline=(220,40,40,a), width=8)
    return Image.alpha_composite(img, ov)


def draw_om_watermark(img, alpha=12):
    ov = Image.new("RGBA", (W,H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    d.text((W//2,H//2-180), "ఓం", font=get_font(360,bold=True),
           fill=(255,200,0,alpha), anchor="mm")
    return Image.alpha_composite(img, ov)


# ── ANIMATION HELPERS ─────────────────────────────────────────────────────────

def slide_offset(f, total=12, direction="left"):
    p = min(f/max(total,1), 1.0); e = 1-(1-p)**3
    if direction=="left":  return int((1-e)*300), 0
    if direction=="right": return int(-(1-e)*300), 0
    if direction=="up":    return 0, int((1-e)*200)
    if direction=="down":  return 0, int(-(1-e)*200)
    return 0, 0


def zoom_scale(f, total=20, from_s=1.35, to_s=1.0):
    p = min(f/max(total,1), 1.0); e = 1-(1-p)**3
    return from_s + (to_s - from_s)*e


# ── CHARACTER ─────────────────────────────────────────────────────────────────

_char_cache = None

def _load_char():
    global _char_cache
    if _char_cache is None and os.path.exists(CHARACTER_PATH):
        from scipy import ndimage
        orig = Image.open(CHARACTER_PATH).convert("RGBA")
        arr  = np.array(orig)
        r,g,b = arr[:,:,0].astype(int), arr[:,:,1].astype(int), arr[:,:,2].astype(int)
        sat   = np.max([r,g,b],axis=0) - np.min([r,g,b],axis=0)
        bright = (r+g+b)//3
        is_bg  = (sat<30) & (bright>130)
        labeled,_ = ndimage.label(is_bg)
        blabels = set()
        for la in [labeled[0,:],labeled[-1,:],labeled[:,0],labeled[:,-1]]:
            blabels.update(la[la>0])
        mask = np.zeros(is_bg.shape, dtype=bool)
        for lbl in blabels: mask |= (labeled==lbl)
        result = arr.copy(); result[mask,3] = 0
        _char_cache = Image.fromarray(result,"RGBA")
        print(f"  Panthulu loaded {_char_cache.size}")
    return _char_cache


def paste_char(base_img, frame_idx, scene):
    char = _load_char()
    if char is None: return base_img
    t   = frame_idx / FPS
    bob = int(3 * math.sin(2*math.pi*3.0*t))
    extra_bob = 0; scale = CHAR_SCALE

    if scene == 0:   # Hook — excited jump
        extra_bob = int(-14 * abs(math.sin(2*math.pi*2.0*t)))
        scale = CHAR_SCALE + 0.025*abs(math.sin(2*math.pi*1.5*t))
    elif scene == 3:  # Muhurtham — happy bounce
        extra_bob = int(-8 * abs(math.sin(2*math.pi*1.5*t)))

    nw = int(char.size[0]*scale); nh = int(char.size[1]*scale)
    resized = char.resize((nw,nh), Image.LANCZOS)

    # Glow behind character
    glow = Image.new("RGBA", base_img.size, (0,0,0,0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([CHAR_X-nw//2-25, CHAR_Y_BOTTOM-nh+bob+extra_bob-5,
                CHAR_X+nw//2+25, CHAR_Y_BOTTOM+20+bob+extra_bob],
               fill=(255,140,0,18))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    base_img = Image.alpha_composite(base_img, glow)

    # Shake on warning scenes (Rahu=2, Durmuhurtam=3)
    shake_x = int(5 * math.sin(2*math.pi*8*t)) if scene in (2,3) else 0

    px = max(0, min(CHAR_X - nw//2 + shake_x, W-nw))
    py = max(CONTENT_Y_END - nh, CHAR_Y_BOTTOM - nh + bob + extra_bob)
    base_img.paste(resized, (px, py), resized)

    # Name badge
    d  = ImageDraw.Draw(base_img)
    bw,bh = 240,40; bx = CHAR_X-bw//2; by = py - 50
    draw_card(d, bx, by, bx+bw, by+bh, fill=(80,40,0), border=GOLD, alpha=230)
    draw_mixed(d, (CHAR_X, by+bh//2), "పంతులు", 26, bold=True, fill=GOLD, anchor="mm")
    return base_img


# ── UTILITY ───────────────────────────────────────────────────────────────────

def tf(p, k):
    v = p.get(k,"N/A"); return v if v and v!="" else "N/A"


# ── SCENE RENDERERS ───────────────────────────────────────────────────────────
# CRITICAL RULE: all add_glow/add_sparkles/add_warning_pulse calls go FIRST,
# then create draw = ImageDraw.Draw(img), then draw all text/cards.

def scene_hook(img, f, panchang):
    city = panchang.get("city","USA")
    sc   = zoom_scale(f, total=18, from_s=1.4, to_s=1.0)

    # --- ALL composites first ---
    img = add_glow(img, W//2, 520, radius=320, color=(255,80,0), alpha=40)

    # --- NOW create draw ---
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    # Brand bar top
    draw_card(draw, 60, 50, W-60, 115, fill=(80,30,0), border=SAFFRON, alpha=210)
    draw_mixed(draw, (W//2, 82), "నేటి పంచాంగం | Panthulu", 30, bold=True,
               fill=GOLD, anchor="mm")

    # Hook text with zoom
    ox, oy = slide_offset(f, total=10, direction="up")
    s1, s2 = int(88*sc), int(98*sc)
    draw_mixed(draw, (W//2+ox, 310+oy), "ఈరోజు ఈ సమయం", s1, bold=True,
               fill=SAFFRON, anchor="mm")
    draw_mixed(draw, (W//2+ox, 430+oy), "తప్పించండి!", s2, bold=True,
               fill=GOLD, anchor="mm")

    # City + date
    sx, sy = slide_offset(f, total=16, direction="left")
    draw_mixed(draw, (W//2+sx, 548+sy), city, 42, fill=CREAM, anchor="mm")
    draw_mixed(draw, (W//2,    604),    panchang.get("date",""), 34,
               fill=WHITE, anchor="mm")
    return img


def scene_tithi(img, f, panchang):
    tithi  = tf(panchang, "tithi")
    paksha = tf(panchang, "paksha")

    img  = add_glow(img, W//2, 580, radius=260, color=(255,160,0), alpha=25)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    sx, sy = slide_offset(f, total=10, direction="left")
    draw_card(draw, 60+sx, 175+sy, W-60+sx, 258+sy,
              fill=(70,30,0), border=SAFFRON, alpha=220)
    draw_mixed(draw, (W//2+sx, 216+sy), "ఈరోజు తిథి", 46, bold=True,
               fill=SAFFRON, anchor="mm")

    vx, vy = slide_offset(max(f-6,0), total=12, direction="right")
    draw_card(draw, 50+vx, 280+vy, W-50+vx, 450+vy,
              fill=(50,15,0), border=GOLD, radius=24, alpha=230)
    parts = tithi.split("→")
    if len(parts) == 2:
        draw_mixed(draw, (W//2+vx, 335+vy), parts[0].strip(), 42,
                   bold=True, fill=GOLD, anchor="mm")
        draw_mixed(draw, (W//2+vx, 400+vy), "-> "+parts[1].strip(), 36,
                   fill=CREAM, anchor="mm")
    else:
        draw_mixed(draw, (W//2+vx, 365+vy), tithi[:40], 42,
                   bold=True, fill=GOLD, anchor="mm")

    px, py = slide_offset(max(f-10,0), total=10, direction="up")
    draw_card(draw, 200+px, 472+py, W-200+px, 534+py,
              fill=(60,20,0), border=(180,140,0), alpha=200)
    draw_mixed(draw, (W//2+px, 503+py), paksha, 30, fill=CREAM, anchor="mm")
    return img


def scene_rahu(img, f, panchang):
    rahu = tf(panchang, "rahukaal")
    tz   = panchang.get("tz_label","ET")
    pulse = abs(math.sin(2*math.pi*2.5*(f/FPS)))

    img  = add_warning_pulse(img, pulse*0.7)
    img  = add_glow(img, W//2, 530, radius=280, color=(220,30,30), alpha=30)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    sx, sy = slide_offset(f, total=10, direction="left")
    draw_card(draw, 40+sx, 165+sy, W-40+sx, 265+sy,
              fill=(120,0,0), border=WARN_RED, alpha=230)
    draw_mixed(draw, (W//2+sx, 215+sy), "[!]  రాహు కాలం  [!]", 44,
               bold=True, fill=WARN_RED, anchor="mm")

    vx, vy = slide_offset(max(f-6,0), total=12, direction="right")
    draw_card(draw, 40+vx, 288+vy, W-40+vx, 430+vy,
              fill=(70,0,0), border=WARN_RED, radius=24, alpha=245)
    rahu_display = rahu.split("|")[0].strip()
    draw_mixed(draw, (W//2+vx, 359+vy), rahu_display, 54, bold=True,
               fill=WARN_RED, anchor="mm")
    draw_mixed(draw, (W//2+vx, 415+vy), tz, 28, fill=CREAM, anchor="mm")

    wx, wy = slide_offset(max(f-10,0), total=12, direction="up")
    draw_card(draw, 60+wx, 452+wy, W-60+wx, 532+wy,
              fill=(80,10,10), border=(160,0,0), alpha=200)
    draw_mixed(draw, (W//2+wx, 492+wy), "ఈ సమయంలో కొత్త పని వద్దు!", 32,
               bold=True, fill=CREAM, anchor="mm")
    return img


def scene_durmuhurtam(img, f, panchang):
    dur  = tf(panchang, "durmuhurtam")
    tz   = panchang.get("tz_label","ET")
    pulse = abs(math.sin(2*math.pi*2.0*(f/FPS)))

    img  = add_warning_pulse(img, pulse*0.5)
    img  = add_glow(img, W//2, 530, radius=260, color=(180,20,20), alpha=25)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    sx, sy = slide_offset(f, total=10, direction="right")
    draw_card(draw, 40+sx, 165+sy, W-40+sx, 265+sy,
              fill=(110,0,0), border=WARN_RED, alpha=230)
    draw_mixed(draw, (W//2+sx, 215+sy), "[X]  దుర్ముహూర్తం  [X]", 42,
               bold=True, fill=WARN_RED, anchor="mm")

    vx, vy = slide_offset(max(f-6,0), total=12, direction="left")
    draw_card(draw, 40+vx, 288+vy, W-40+vx, 430+vy,
              fill=(65,0,0), border=WARN_RED, radius=24, alpha=245)
    draw_mixed(draw, (W//2+vx, 359+vy), dur, 54, bold=True,
               fill=WARN_RED, anchor="mm")
    draw_mixed(draw, (W//2+vx, 415+vy), tz, 28, fill=CREAM, anchor="mm")

    wx, wy = slide_offset(max(f-10,0), total=12, direction="up")
    draw_card(draw, 60+wx, 452+wy, W-60+wx, 532+wy,
              fill=(80,10,10), border=(160,0,0), alpha=200)
    draw_mixed(draw, (W//2+wx, 492+wy), "శుభ కార్యాలు వద్దు!", 34,
               bold=True, fill=CREAM, anchor="mm")
    return img


def scene_muhurtham(img, f, panchang):
    abhijit = tf(panchang, "abhijit")
    brahma  = tf(panchang, "brahma_muhurta")

    img  = add_glow(img, W//2, 500, radius=300, color=(255,210,0), alpha=45)
    img  = add_sparkles(img, W//2, 460, n=10, t=f/FPS)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    sx, sy = slide_offset(f, total=10, direction="left")
    draw_card(draw, 40+sx, 165+sy, W-40+sx, 258+sy,
              fill=(60,40,0), border=GOLD, alpha=230)
    draw_mixed(draw, (W//2+sx, 211+sy), "(*) శుభ ముహూర్తం (*)", 44,
               bold=True, fill=GOLD, anchor="mm")

    vx, vy = slide_offset(max(f-6,0), total=12, direction="right")
    draw_card(draw, 40+vx, 280+vy, W-40+vx, 430+vy,
              fill=(45,30,0), border=GOLD, radius=24, alpha=240)
    draw_mixed(draw, (W//2+vx, 318+vy), "అభిజిత్ ముహూర్తం", 34,
               bold=True, fill=CREAM, anchor="mm")
    draw_mixed(draw, (W//2+vx, 378+vy), abhijit, 48, bold=True,
               fill=GOLD, anchor="mm")

    bx, by = slide_offset(max(f-10,0), total=12, direction="up")
    draw_card(draw, 60+bx, 452+by, W-60+bx, 534+by,
              fill=(40,25,0), border=(180,150,0), alpha=200)
    draw_mixed(draw, (W//2+bx, 471+by), "బ్రహ్మ ముహూర్తం", 26,
               fill=CREAM, anchor="mm")
    draw_mixed(draw, (W//2+bx, 508+by), brahma.split("|")[0].strip(), 30,
               bold=True, fill=(220,200,80), anchor="mm")
    return img


def scene_sunrise(img, f, panchang):
    sunrise = tf(panchang, "sunrise")
    sunset  = tf(panchang, "sunset")
    tz      = panchang.get("tz_label","ET")

    img  = add_glow(img, W//2, 400, radius=260, color=(255,140,0), alpha=30)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    sx, sy = slide_offset(f, total=10, direction="up")
    draw_card(draw, 60+sx, 168+sy, W-60+sx, 250+sy,
              fill=(60,30,0), border=SAFFRON, alpha=220)
    draw_mixed(draw, (W//2+sx, 209+sy), "సూర్యుడు | చంద్రుడు", 38,
               bold=True, fill=SAFFRON, anchor="mm")

    vx, vy = slide_offset(max(f-6,0), total=12, direction="left")
    draw_card(draw, 40+vx, 272+vy, W-40+vx, 415+vy,
              fill=(55,22,0), border=GOLD, radius=22, alpha=235)
    draw_mixed(draw, (W//2+vx, 308+vy), "సూర్యోదయం", 36,
               bold=True, fill=CREAM, anchor="mm")
    draw_mixed(draw, (W//2+vx, 368+vy), sunrise, 60, bold=True,
               fill=GOLD, anchor="mm")

    tx, ty = slide_offset(max(f-10,0), total=12, direction="right")
    draw_card(draw, 40+tx, 438+ty, W-40+tx, 578+ty,
              fill=(50,15,0), border=SAFFRON, radius=22, alpha=230)
    draw_mixed(draw, (W//2+tx, 474+ty), "సూర్యాస్తమయం", 36,
               bold=True, fill=CREAM, anchor="mm")
    draw_mixed(draw, (W//2+tx, 535+ty), sunset, 60, bold=True,
               fill=SAFFRON, anchor="mm")

    draw_mixed(draw, (W//2, 598), tz, 28, fill=(180,160,100), anchor="mm")
    return img


def scene_cta(img, f, panchang):
    img  = add_glow(img, W//2, 480, radius=340, color=(255,180,0), alpha=35)
    img  = add_sparkles(img, W//2, 460, n=12, t=f/FPS)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    sx, sy = slide_offset(f, total=12, direction="up")
    draw_card(draw, 40+sx, 155+sy, W-40+sx, 315+sy,
              fill=(70,35,0), border=GOLD, radius=24, alpha=235)
    draw_mixed(draw, (W//2+sx, 198+sy), "Daily Panchangam", 40,
               bold=True, fill=GOLD, anchor="mm")
    draw_mixed(draw, (W//2+sx, 258+sy), "కోసం Follow చేయండి!", 46,
               bold=True, fill=SAFFRON, anchor="mm")

    vx, vy = slide_offset(max(f-8,0), total=12, direction="left")
    draw_card(draw, 60+vx, 338+vy, W-60+vx, 418+vy,
              fill=(50,25,0), border=SAFFRON, alpha=210)
    draw_mixed(draw, (W//2+vx, 378+vy), "Like | Share | Comment", 32,
               bold=True, fill=CREAM, anchor="mm")

    nx, ny = slide_offset(max(f-12,0), total=10, direction="up")
    draw_mixed(draw, (W//2+nx, 455+ny), "@PanthuluPanchangam", 30,
               fill=GOLD, anchor="mm")

    bx, by = slide_offset(max(f-14,0), total=10, direction="up")
    draw_mixed(draw, (W//2+bx, 520+by), "జయ శ్రీమన్నారాయణ!", 40,
               bold=True, fill=GOLD, anchor="mm")
    return img


SCENE_RENDERERS = [
    scene_hook, scene_tithi, scene_rahu, scene_durmuhurtam,
    scene_muhurtham, scene_sunrise, scene_cta
]


# ── FRAME BUILDER ─────────────────────────────────────────────────────────────

def build_frame(frame_idx, panchang):
    # Find scene
    scene = 0; f_in = frame_idx; acc = 0
    for i, nf in enumerate(SCENE_FRAMES):
        if frame_idx < acc + nf: scene = i; f_in = frame_idx - acc; break
        acc += nf

    # Base — composites done inside scene renderers
    img = make_bg()
    img = draw_om_watermark(img, alpha=11)

    # Draw border on base before scene (scene renderers also call draw_border
    # after their composites, which is fine — double border is invisible)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    # Run scene — returns img with all composites + text drawn
    img = SCENE_RENDERERS[scene](img, f_in, panchang)

    # Paste character on top
    img = paste_char(img, frame_idx, scene)

    # Progress dots — drawn last, above everything
    draw = ImageDraw.Draw(img)
    cy = H - 28; spacing = 24; sx2 = W//2 - (7*spacing)//2
    for i in range(7):
        x = sx2 + i*spacing
        if i == scene: draw.ellipse([x-9,cy-9,x+9,cy+9], fill=GOLD)
        else:          draw.ellipse([x-5,cy-5,x+5,cy+5], outline=(160,130,0), width=2)

    return img


# ── VIDEO ─────────────────────────────────────────────────────────────────────

def get_audio_duration(path):
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:    return float(r.stdout.strip())
    except: return 14.0


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    city = panchang.get("city","?")
    print(f"   {city} — {TOTAL_FRAMES} frames ({TOTAL_FRAMES/FPS:.1f}s)")

    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(TOTAL_FRAMES):
            frame = build_frame(fi, panchang)
            frame.convert("RGB").save(
                str(Path(tmp)/f"frame_{fi:05d}.jpg"), "JPEG", quality=90)
            if fi % 48 == 0:
                print(f"      Scene {fi//48+1}/7 rendered ...")

        has_audio = audio_path and os.path.exists(audio_path)
        cmd = ["ffmpeg","-y","-framerate",str(FPS),
               "-i", str(Path(tmp)/"frame_%05d.jpg")]
        if has_audio:
            cmd += ["-i", audio_path, "-c:a","aac","-b:a","192k",
                    "-t", str(TOTAL_FRAMES/FPS), "-shortest"]
        cmd += ["-c:v","libx264","-preset","fast","-crf","20",
                "-pix_fmt","yuv420p","-movflags","+faststart", output_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"FFmpeg: {r.stderr[-1000:]}")

    print(f"  OK {output_path}")
    return output_path


# ── THUMBNAIL ─────────────────────────────────────────────────────────────────

def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img  = make_bg()
    img  = draw_om_watermark(img, alpha=10)
    img  = add_glow(img, W//2, 680, radius=340, color=(255,180,0), alpha=35)
    # All composites done — now draw
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    city = panchang.get("city","USA")
    date = panchang.get("date","")
    rahu = tf(panchang,"rahukaal").split("|")[0].strip()
    tz   = panchang.get("tz_label","ET")

    draw_card(draw, 50, 55, W-50, 135, fill=(80,30,0), border=GOLD, alpha=230)
    draw_mixed(draw, (W//2, 95), "నేటి పంచాంగం | Panthulu", 32,
               bold=True, fill=GOLD, anchor="mm")

    draw_mixed(draw, (W//2, 228), "ఈరోజు ఈ సమయం", 78, bold=True,
               fill=SAFFRON, anchor="mm")
    draw_mixed(draw, (W//2, 338), "తప్పించండి!", 88, bold=True,
               fill=GOLD, anchor="mm")
    draw_mixed(draw, (W//2, 428), city, 44, fill=CREAM, anchor="mm")
    draw_mixed(draw, (W//2, 482), date, 36, fill=WHITE, anchor="mm")

    draw_card(draw, 60, 528, W-60, 638, fill=(100,0,0), border=WARN_RED,
              radius=22, alpha=235)
    draw_mixed(draw, (W//2, 560), "రాహు కాలం", 36, bold=True,
               fill=WARN_RED, anchor="mm")
    draw_mixed(draw, (W//2, 610), f"{rahu}  {tz}", 42, bold=True,
               fill=CREAM, anchor="mm")

    char = _load_char()
    if char:
        ch  = int(H * 0.44)
        cw  = int(char.size[0] * (ch/char.size[1]))
        img.paste(char.resize((cw,ch), Image.LANCZOS),
                  (W//2-cw//2, H-ch-70),
                  char.resize((cw,ch), Image.LANCZOS))
        draw = ImageDraw.Draw(img)

    draw_card(draw, 60, H-178, W-60, H-78, fill=(60,30,0), border=SAFFRON,
              radius=20, alpha=220)
    draw_mixed(draw, (W//2, H-128), "Follow చేయండి  @PanthuluPanchangam",
               28, bold=True, fill=GOLD, anchor="mm")

    img.convert("RGB").save(output_path, "JPEG", quality=95)
    print(f"  OK Thumbnail: {output_path}")
    return output_path
