"""
video_creator.py v15
Fixes:
1. Scene order corrected - tithi and brahma now appear
2. Content fills full screen height - cards distributed across full 1920px
3. పంతులు badge fixed to bottom of screen always
4. Character red tint on warning scenes
5. Progress dots moved to H-20, smaller
6. Scene flash increased to alpha=220, 5 frames
7. Thumbnail fills full height with extra info
8. Date formatted as "March 14, 2026"
9. Tagline centered properly
10. Voice pitch lowered in voice_generator
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

# Word counts per scene — must match script_generator narration segments exactly
# Segments: intro(11) tithi(4) rahu(7) durmuhurtam(4) brahma(5) abhijit(6) sun(0) closing(11)
SCENE_WORD_COUNTS = [11, 4, 7, 4, 5, 6, 0, 11]
N_SCENES = 8


def compute_scene_frames(audio_duration):
    total_words = sum(SCENE_WORD_COUNTS)
    sun_pause   = 2.0
    speech_dur  = max(audio_duration - sun_pause, 1.0)
    frames = []
    for words in SCENE_WORD_COUNTS:
        if words == 0:
            dur = sun_pause
        else:
            dur = (words / total_words) * speech_dur
        frames.append(max(int(dur * FPS), 36))
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
    a=int(45*intensity)
    for m in [0,10,22]:
        d.rectangle([m,m,W-m,H-m],outline=(210,30,30,a),width=6)
    return Image.alpha_composite(img,ov)


def add_scene_flash(img, f_in_scene):
    # Fix #6: alpha=220, 5 frames
    if f_in_scene >= 5: return img
    alpha = int(220*(1-f_in_scene/5))
    ov=Image.new("RGBA",(W,H),(255,255,220,alpha))
    return Image.alpha_composite(img,ov)


def draw_card(draw, x1,y1,x2,y2, fill=(40,12,0), border=None, radius=18, alpha=228):
    fa=fill+(alpha,) if len(fill)==3 else fill; r=radius
    draw.rectangle([x1+r,y1,x2-r,y2],fill=fa); draw.rectangle([x1,y1+r,x2,y2-r],fill=fa)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r],fill=fa)
    if border:
        draw.rectangle([x1+r,y1,x2-r,y1+4],fill=border); draw.rectangle([x1+r,y2-4,x2-r,y2],fill=border)
        draw.rectangle([x1,y1+r,x1+4,y2-r],fill=border); draw.rectangle([x2-4,y1+r,x2,y2-r],fill=border)


def fade(f, frames=10):
    return min(255, int(255*f/max(frames,1)))


def fmt_date(date_str):
    """Fix #9: Format 2026-03-14 as March 14, 2026"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except:
        return date_str


# ── CHARACTER ─────────────────────────────────────────────────────────────────

_char_cache = None

def _load_char():
    global _char_cache
    if _char_cache is None and os.path.exists(CHARACTER_PATH):
        from scipy import ndimage
        orig=Image.open(CHARACTER_PATH).convert("RGBA"); arr=np.array(orig)
        r,g,b=arr[:,:,0].astype(int),arr[:,:,1].astype(int),arr[:,:,2].astype(int)
        sat=np.max([r,g,b],axis=0)-np.min([r,g,b],axis=0); bright=(r+g+b)//3
        is_bg=(sat<30)&(bright>130); labeled,_=ndimage.label(is_bg)
        bl=set()
        for la in [labeled[0,:],labeled[-1,:],labeled[:,0],labeled[:,-1]]: bl.update(la[la>0])
        mask=np.zeros(is_bg.shape,dtype=bool)
        for lbl in bl: mask|=(labeled==lbl)
        result=arr.copy(); result[mask,3]=0
        _char_cache=Image.fromarray(result,"RGBA")
    return _char_cache


def paste_char(base_img, frame_idx, scene):
    char=_load_char()
    if char is None: return base_img
    t=frame_idx/FPS; bob=int(4*math.sin(2*math.pi*2.5*t))
    scale=CHAR_SCALE+0.012*math.sin(2*math.pi*1.2*t)
    shake=int(5*math.sin(2*math.pi*7*t)) if scene in (2,3) else 0
    nw=int(char.size[0]*scale); nh=int(char.size[1]*scale)
    resized=char.resize((nw,nh),Image.LANCZOS)

    # Fix #4: Red tint overlay on character during warning scenes
    if scene in (2, 3):
        tint = Image.new("RGBA", resized.size, (180, 0, 0, 60))
        resized = Image.alpha_composite(resized, tint)

    glow=Image.new("RGBA",base_img.size,(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse([CHAR_X-nw//2-30,CHAR_Y_BOTTOM-nh+bob-10,
                CHAR_X+nw//2+30,CHAR_Y_BOTTOM+10+bob],fill=(255,100,0,10))
    glow=glow.filter(ImageFilter.GaussianBlur(30))
    base_img=Image.alpha_composite(base_img,glow)

    px=max(0,min(CHAR_X-nw//2+shake,W-nw)); py=CHAR_Y_BOTTOM-nh+bob
    base_img.paste(resized,(px,py),resized)

    # Fix #3: Badge fixed to bottom of screen — not floating
    d=ImageDraw.Draw(base_img)
    bw,bh=210,36; bx=CHAR_X-bw//2
    badge_y = H - 120   # always anchored at bottom
    draw_card(d,bx,badge_y,bx+bw,badge_y+bh,fill=(70,28,0),border=GOLD,alpha=220)
    draw_mixed(d,(CHAR_X,badge_y+bh//2),"పంతులు",22,bold=True,fill=GOLD,anchor="mm")
    return base_img


def tf(p,k):
    v=p.get(k,"N/A"); return v if v and v!="" else "N/A"


def clean_time(val, tz):
    val=val.split("|")[0].strip(); val=val.replace(f" {tz}","").strip(); return val


def fix_arrow(text):
    return text.replace("→","->").replace("→","->")


# ── SCENE RENDERERS ───────────────────────────────────────────────────────────
# ALL composites FIRST → draw = ImageDraw.Draw(img) → draw text

def scene_intro(img, f, panchang):
    city=panchang.get("city","USA")
    date=fmt_date(panchang.get("date",""))   # Fix #9: formatted date
    weekday=panchang.get("weekday","")
    fa=fade(f,10)
    img=add_glow(img,CX,H//2,radius=420,color=(200,80,0),alpha=20)
    img=add_scene_flash(img,f); draw=ImageDraw.Draw(img); draw_border(draw)

    # Top: Om
    draw.text((CX,85),"ఓం",font=get_font(78,bold=True),fill=GOLD+(fa,),anchor="mm")

    # Namaskaram pill
    draw_card(draw,PAD,140,PAD+CARD_W,228,fill=(75,28,0),border=SAFFRON,alpha=min(fa,225))
    draw_mixed(draw,(CX,184),"నమస్కారం!",54,bold=True,fill=GOLD+(fa,),anchor="mm")

    # Host pill
    draw_card(draw,PAD,245,PAD+CARD_W,325,fill=(55,20,0),border=(160,80,0),alpha=min(fa,210))
    draw_mixed(draw,(CX,285),"నేను మీ పంచాంగం గురువు",36,bold=True,fill=CREAM+(fa,),anchor="mm")

    # City — large
    draw_mixed(draw,(CX,425),city,68,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    # Weekday + date
    draw_mixed(draw,(CX,514),weekday,42,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,570),date,34,fill=WHITE+(fa,),anchor="mm")

    draw.line([(PAD+20,610),(PAD+CARD_W-20,610)],fill=GOLD+(fa,),width=2)

    # Fix #10: tagline — use CX anchor="mm" 
    draw_mixed(draw,(CX,650),"నేటి పంచాంగం వివరాలు చూద్దాం!",
               36,fill=CREAM+(fa,),anchor="mm")
    return img


def scene_tithi(img, f, panchang):
    # Fix #1: This IS scene index 1 — tithi must show here
    tithi=fix_arrow(tf(panchang,"tithi")); paksha=tf(panchang,"paksha"); tz=panchang.get("tz_label","ET")
    fa=fade(f,10)
    img=add_glow(img,CX,H//2,radius=340,color=(255,150,0),alpha=20)
    img=add_scene_flash(img,f); draw=ImageDraw.Draw(img); draw_border(draw)

    # Fix #2: spread cards down the full screen
    draw_card(draw,PAD,105,PAD+CARD_W,198,fill=(65,25,0),border=SAFFRON,alpha=min(fa,228))
    draw_mixed(draw,(CX,151),"తిథి",58,bold=True,fill=SAFFRON+(fa,),anchor="mm")

    parts=tithi.split("->"); p1=parts[0].strip(); p2=("-> "+parts[1].strip()) if len(parts)>1 else ""
    draw_card(draw,PAD,215,PAD+CARD_W,430,fill=(42,14,0),border=GOLD,radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,305),p1,54,bold=True,fill=GOLD+(fa,),anchor="mm")
    if p2: draw_mixed(draw,(CX,388),p2,36,fill=CREAM+(fa,),anchor="mm")

    draw_card(draw,PAD+60,448,PAD+CARD_W-60,522,fill=(55,18,0),border=(175,135,0),radius=16,alpha=min(fa,215))
    draw_mixed(draw,(CX,485),paksha,34,fill=CREAM+(fa,),anchor="mm")

    draw_mixed(draw,(CX,540),tz,28,fill=DIM+(fa,),anchor="mm")

    # Extra card pushed down — tithi number context
    draw_card(draw,PAD,565,PAD+CARD_W,635,fill=(45,14,0),border=(140,110,0),radius=14,alpha=min(fa,200))
    draw_mixed(draw,(CX,600),"నేటి తిథి వివరాలు పైన చూడండి",28,fill=DIM+(fa,),anchor="mm")
    return img


def _info_scene(img, f, label, time_val, tz, subtext, accent, bg_dark, pulse=False):
    """Full-screen info scene — content distributed across full height"""
    fa=fade(f,10)
    if pulse:
        intensity=abs(math.sin(2*math.pi*2.5*(f/FPS)))
        img=add_warning_pulse(img,intensity*0.55)
        img=add_glow(img,CX,H//2,radius=320,color=(180,15,15),alpha=20)
    else:
        img=add_glow(img,CX,H//2,radius=320,color=accent,alpha=22)
    img=add_scene_flash(img,f); draw=ImageDraw.Draw(img); draw_border(draw)

    # Label — top
    draw_card(draw,PAD,105,PAD+CARD_W,200,fill=bg_dark,border=accent,alpha=min(fa,230))
    draw_mixed(draw,(CX,152),label,54,bold=True,fill=accent+(fa,),anchor="mm")

    # Time — large center
    clean=clean_time(time_val,tz)
    tsize=68; tw,_=measure_mixed(clean,tsize,bold=True)
    if tw>CARD_W-60: tsize=52
    draw_card(draw,PAD,220,PAD+CARD_W,420,
              fill=(bg_dark[0]//2,bg_dark[1]//2,bg_dark[2]//2),
              border=accent,radius=22,alpha=min(fa,245))
    draw_mixed(draw,(CX,320),clean,tsize,bold=True,fill=accent+(fa,),anchor="mm")

    # TZ — once
    draw_mixed(draw,(CX,438),tz,30,fill=DIM+(fa,),anchor="mm")

    # Subtext
    if subtext:
        draw_card(draw,PAD+20,462,PAD+CARD_W-20,546,
                  fill=(bg_dark[0]//3,bg_dark[1]//3,bg_dark[2]//3),
                  border=(accent[0]//2,accent[1]//2,accent[2]//2),
                  radius=14,alpha=min(fa,210))
        draw_mixed(draw,(CX,504),subtext,34,bold=True,fill=WHITE+(fa,),anchor="mm")

    # Fix #2: Extra card pushed further down to fill empty space
    draw_card(draw,PAD+40,568,PAD+CARD_W-40,638,
              fill=(bg_dark[0]//4,bg_dark[1]//4,bg_dark[2]//4),
              border=(accent[0]//3,accent[1]//3,accent[2]//3),
              radius=12,alpha=min(fa,180))
    if pulse:
        draw_mixed(draw,(CX,603),"జాగ్రత్త! సూచన గమనించండి",26,fill=CREAM+(fa,),anchor="mm")
    else:
        draw_mixed(draw,(CX,603),"శుభ కార్యాలకు ఉపయోగించండి",26,fill=CREAM+(fa,),anchor="mm")
    return img


def scene_rahu(img,f,p):
    return _info_scene(img,f,"రాహు కాలం",tf(p,"rahukaal"),p.get("tz_label","ET"),
                       "ఈ సమయంలో కొత్త పని వద్దు!",WARN_RED,DARK_RED,pulse=True)

def scene_durmuhurtam(img,f,p):
    return _info_scene(img,f,"దుర్ముహూర్తం",tf(p,"durmuhurtam"),p.get("tz_label","ET"),
                       "శుభ కార్యాలు ఈ వేళ వద్దు!",WARN_RED,DARK_RED,pulse=True)

def scene_brahma(img,f,p):
    # Fix #1: this is scene index 4
    return _info_scene(img,f,"బ్రహ్మ ముహూర్తం",tf(p,"brahma_muhurta"),p.get("tz_label","ET"),
                       "ప్రార్థన & ధ్యానానికి శ్రేష్ఠ సమయం",GOLD,(55,35,0),pulse=False)

def scene_abhijit(img,f,p):
    return _info_scene(img,f,"అభిజిత్ ముహూర్తం",tf(p,"abhijit"),p.get("tz_label","ET"),
                       "ముఖ్య పనులకు అత్యంత శుభ సమయం",GOLD,(55,35,0),pulse=False)


def scene_sun(img, f, panchang):
    sunrise=clean_time(tf(panchang,"sunrise"),panchang.get("tz_label","ET"))
    sunset=clean_time(tf(panchang,"sunset"),panchang.get("tz_label","ET"))
    tz=panchang.get("tz_label","ET"); fa=fade(f,10)
    img=add_glow(img,CX,H//2,radius=320,color=(255,130,0),alpha=22)
    img=add_scene_flash(img,f); draw=ImageDraw.Draw(img); draw_border(draw)
    draw_card(draw,PAD,105,PAD+CARD_W,198,fill=(58,22,0),border=SAFFRON,alpha=min(fa,228))
    draw_mixed(draw,(CX,151),"సూర్యోదయం & సూర్యాస్తమయం",42,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_card(draw,PAD,216,PAD+CARD_W,378,fill=(50,18,0),border=GOLD,radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,256),"సూర్యోదయం",38,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,332),sunrise,64,bold=True,fill=GOLD+(fa,),anchor="mm")
    draw_card(draw,PAD,396,PAD+CARD_W,558,fill=(48,15,0),border=SAFFRON,radius=20,alpha=min(fa,240))
    draw_mixed(draw,(CX,436),"సూర్యాస్తమయం",38,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,512),sunset,64,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_mixed(draw,(CX,575),tz,30,fill=DIM+(fa,),anchor="mm")
    return img


def scene_closing(img, f, panchang):
    fa=fade(f,10)
    img=add_glow(img,CX,H//2,radius=360,color=(255,170,0),alpha=26)
    img=add_scene_flash(img,f); draw=ImageDraw.Draw(img); draw_border(draw)
    draw_card(draw,PAD,105,PAD+CARD_W,288,fill=(65,28,0),border=GOLD,radius=20,alpha=min(fa,232))
    draw_mixed(draw,(CX,172),"మీకు శుభమైన రోజు కలగాలని",40,bold=True,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,245),"ఆశిస్తున్నాను!",50,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_card(draw,PAD,308,PAD+CARD_W,438,fill=(50,20,0),border=SAFFRON,radius=20,alpha=min(fa,225))
    draw_mixed(draw,(CX,354),"Daily Panchangam kosam",34,bold=True,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,410),"Follow చేయండి!",48,bold=True,fill=SAFFRON+(fa,),anchor="mm")
    draw_card(draw,PAD+20,458,PAD+CARD_W-20,534,fill=(38,14,0),border=(150,115,0),radius=14,alpha=min(fa,205))
    draw_mixed(draw,(CX,496),"Like | Share | Subscribe చేయండి",32,fill=CREAM+(fa,),anchor="mm")
    draw_mixed(draw,(CX,555),"@PanthuluPanchangam",28,fill=GOLD+(fa,),anchor="mm")
    draw_mixed(draw,(CX,608),"జయ శ్రీమన్నారాయణ!",42,bold=True,fill=GOLD+(fa,),anchor="mm")
    return img


# Fix #1: SCENE_RENDERERS list — verified order matches SCENE_WORD_COUNTS
SCENE_RENDERERS = [
    scene_intro,        # 0  — 11 words
    scene_tithi,        # 1  —  4 words
    scene_rahu,         # 2  —  7 words
    scene_durmuhurtam,  # 3  —  4 words
    scene_brahma,       # 4  —  5 words
    scene_abhijit,      # 5  —  6 words
    scene_sun,          # 6  —  0 words (2s visual)
    scene_closing,      # 7  — 11 words
]
assert len(SCENE_RENDERERS) == N_SCENES, "SCENE_RENDERERS length must equal N_SCENES"
assert len(SCENE_WORD_COUNTS) == N_SCENES, "SCENE_WORD_COUNTS length must equal N_SCENES"


# ── FRAME BUILDER ─────────────────────────────────────────────────────────────

def build_frame(frame_idx, panchang, scene_frames):
    scene=0; f_in=frame_idx; acc=0
    for i,nf in enumerate(scene_frames):
        if frame_idx < acc+nf: scene=i; f_in=frame_idx-acc; break
        acc+=nf
    img=make_bg(); img=draw_om_watermark(img,alpha=7)
    img=SCENE_RENDERERS[scene](img,f_in,panchang)
    img=paste_char(img,frame_idx,scene)
    draw=ImageDraw.Draw(img)
    # Fix #5: dots at H-20, radius=5
    n=N_SCENES; ds=26; sx=CX-(n*ds)//2; cy_dot=H-20
    for i in range(n):
        x=sx+i*ds
        if i==scene: draw.ellipse([x-7,cy_dot-7,x+7,cy_dot+7],fill=GOLD)
        else:        draw.ellipse([x-4,cy_dot-4,x+4,cy_dot+4],outline=(155,120,0),width=2)
    return img


# ── VIDEO ─────────────────────────────────────────────────────────────────────

def get_audio_duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","default=noprint_wrappers=1:nokey=1",path],capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except: return 33.0


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    city=panchang.get("city","?")
    has_audio=audio_path and os.path.exists(audio_path)
    audio_dur=get_audio_duration(audio_path) if has_audio else 33.0
    scene_frames=compute_scene_frames(audio_dur)
    total_frames=sum(scene_frames)
    print(f"   {city} — audio={audio_dur:.1f}s video={total_frames/FPS:.1f}s frames={total_frames}")
    print(f"   scenes={scene_frames}")
    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(total_frames):
            frame=build_frame(fi,panchang,scene_frames)
            frame.convert("RGB").save(str(Path(tmp)/f"frame_{fi:05d}.jpg"),"JPEG",quality=90)
            if fi%100==0:
                sc=0; acc=0
                for i,nf in enumerate(scene_frames):
                    if fi<acc+nf: sc=i; break
                    acc+=nf
                print(f"      frame {fi}/{total_frames} scene {sc+1}/{N_SCENES} ...")
        cmd=["ffmpeg","-y","-framerate",str(FPS),"-i",str(Path(tmp)/"frame_%05d.jpg")]
        if has_audio:
            cmd+=["-i",audio_path,"-c:a","aac","-b:a","128k"]
        cmd+=["-c:v","libx264","-preset","fast","-crf","20",
              "-pix_fmt","yuv420p","-movflags","+faststart",output_path]
        r=subprocess.run(cmd,capture_output=True,text=True)
        if r.returncode!=0: raise RuntimeError(f"FFmpeg: {r.stderr[-800:]}")
    print(f"  OK {output_path}"); return output_path


# ── THUMBNAIL ─────────────────────────────────────────────────────────────────

def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    img=make_bg(); img=draw_om_watermark(img,alpha=9)
    img=add_glow(img,CX,H//2,radius=440,color=(200,80,0),alpha=24)
    draw=ImageDraw.Draw(img); draw_border(draw)
    city=panchang.get("city","USA"); date=fmt_date(panchang.get("date",""))
    rahu=clean_time(tf(panchang,"rahukaal"),panchang.get("tz_label","ET"))
    tithi_val=tf(panchang,"tithi").split("->")[0].split("→")[0].strip()
    abhijit=clean_time(tf(panchang,"abhijit"),panchang.get("tz_label","ET"))
    tz=panchang.get("tz_label","ET")

    # Brand bar
    draw_card(draw,PAD,48,PAD+CARD_W,128,fill=(70,25,0),border=GOLD,alpha=230)
    draw_mixed(draw,(CX,88),"నేటి పంచాంగం | Panthulu",32,bold=True,fill=GOLD,anchor="mm")

    # Hook lines
    draw_mixed(draw,(CX,215),"ఈరోజు ఈ సమయం",76,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(CX,314),"తప్పించండి!",84,bold=True,fill=GOLD,anchor="mm")

    # City + date
    draw_mixed(draw,(CX,408),city,48,fill=CREAM,anchor="mm")
    draw_mixed(draw,(CX,466),date,32,fill=WHITE,anchor="mm")

    # Rahu card
    draw_card(draw,PAD,494,PAD+CARD_W,604,fill=(110,0,0),border=WARN_RED,radius=20,alpha=242)
    draw_mixed(draw,(CX,530),"రాహు కాలం",36,bold=True,fill=WARN_RED,anchor="mm")
    draw_mixed(draw,(CX,582),f"{rahu}  {tz}",40,bold=True,fill=CREAM,anchor="mm")

    # Fix #8: Extra info rows to fill empty space
    draw_card(draw,PAD,620,PAD+CARD_W,698,fill=(42,14,0),border=GOLD,radius=16,alpha=220)
    draw_mixed(draw,(CX,630),"తిథి",24,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(CX,666),tithi_val[:32],28,fill=GOLD,anchor="mm")

    draw_card(draw,PAD,714,PAD+CARD_W,792,fill=(38,22,0),border=(160,130,0),radius=16,alpha=210)
    draw_mixed(draw,(CX,724),"అభిజిత్ ముహూర్తం",24,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(CX,760),f"{abhijit}  {tz}",28,fill=GOLD,anchor="mm")

    # Character — bottom center
    char=_load_char()
    if char:
        ch=int(H*0.44); cw=int(char.size[0]*(ch/char.size[1]))
        img.paste(char.resize((cw,ch),Image.LANCZOS),(CX-cw//2,H-ch-50),
                  char.resize((cw,ch),Image.LANCZOS))
        draw=ImageDraw.Draw(img)

    # Follow CTA
    draw_card(draw,PAD,H-172,PAD+CARD_W,H-72,fill=(52,20,0),border=SAFFRON,radius=18,alpha=222)
    draw_mixed(draw,(CX,H-122),"Follow చేయండి @PanthuluPanchangam",
               28,bold=True,fill=GOLD,anchor="mm")

    img.convert("RGB").save(output_path,"JPEG",quality=95)
    print(f"  OK Thumbnail: {output_path}"); return output_path
