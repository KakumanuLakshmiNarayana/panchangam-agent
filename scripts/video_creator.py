"""
video_creator.py v8 — Instagram Reel Format
- 10-12 second fast reels (vs old 60s)
- 7 scenes: Hook → Tithi → Rahu Kalam → Durmuhurtam → Best Muhurtham → Sunrise/Sunset → CTA
- Dual-font: NotoSansTelugu + NotoSans for Latin (fixes AM/PM boxes)
- Slide-in text animations per scene
- Zoom/scale animation on hook
- Glow effects for auspicious timings
- Warning pulse for Rahu Kalam
- Character (Panthulu) at bottom — never blocks text
- Brand consistent: saffron/gold/deep-red/cream
"""

import subprocess, os, tempfile, math, glob, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

W, H, FPS = 1080, 1920, 24

SCRIPTS_DIR    = os.path.dirname(os.path.abspath(__file__))
CHARACTER_PATH = os.path.join(SCRIPTS_DIR, "pandit_character.png")

TELUGU_RE = re.compile(r'[\u0C00-\u0C7F]')

GOLD       = (255, 215,   0)
SAFFRON    = (255, 107,   0)
DEEP_RED   = (180,  20,  20)
WARN_RED   = (255,  60,  60)
AUSPIC_G   = ( 80, 220, 120)
CREAM      = (255, 228, 181)
WHITE      = (255, 248, 240)
BG_TOP     = ( 12,   3,   0)
BG_MID     = ( 35,  10,   0)
BG_BTM     = ( 60,  20,   0)

CHAR_SCALE     = 0.48
CHAR_X         = W // 2
CHAR_Y_BOTTOM  = H - 20
CONTENT_Y_END  = int(H * 0.70)

SCENE_FRAMES = [48, 48, 48, 48, 48, 48, 48]
TOTAL_FRAMES = sum(SCENE_FRAMES)


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
    draw.rectangle([6,6,W-6,H-6], outline=GOLD, width=3)
    draw.rectangle([14,14,W-14,H-14], outline=(160,120,0), width=1)
    s=38
    for cx,cy in [(28,28),(W-28,28),(28,H-28),(W-28,H-28)]:
        draw.ellipse([cx-s//2,cy-s//2,cx+s//2,cy+s//2], outline=GOLD, width=2)
        draw.line([cx-s//2-4,cy,cx+s//2+4,cy], fill=GOLD, width=1)
        draw.line([cx,cy-s//2-4,cx,cy+s//2+4], fill=GOLD, width=1)


def draw_om_watermark(img, alpha=12):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    d.text((W//2,H//2-180),"ఓం",font=get_font(360,bold=True),fill=(255,200,0,alpha),anchor="mm")
    return Image.alpha_composite(img,ov)


def draw_card(draw,x1,y1,x2,y2,fill=(40,12,0),border=None,radius=20,alpha=220):
    fa=fill+(alpha,) if len(fill)==3 else fill; r=radius
    draw.rectangle([x1+r,y1,x2-r,y2],fill=fa); draw.rectangle([x1,y1+r,x2,y2-r],fill=fa)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r],fill=fa)
    if border:
        draw.rectangle([x1+r,y1,x2-r,y1+3],fill=border)
        draw.rectangle([x1+r,y2-3,x2-r,y2],fill=border)
        draw.rectangle([x1,y1+r,x1+3,y2-r],fill=border)
        draw.rectangle([x2-3,y1+r,x2,y2-r],fill=border)


def add_glow(img, cx, cy, radius=220, color=(255,200,0), alpha=35):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    for r in range(radius,0,-20):
        a=int(alpha*(1-r/radius)**1.5)
        d.ellipse([cx-r,cy-r,cx+r,cy+r],fill=color+(a,))
    ov=ov.filter(ImageFilter.GaussianBlur(30))
    return Image.alpha_composite(img,ov)


def add_sparkles(img, cx, cy, n=8, t=0.0):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    for i in range(n):
        angle=2*math.pi*i/n+t*3; dist=160+20*math.sin(t*4+i)
        sx,sy=int(cx+dist*math.cos(angle)),int(cy+dist*math.sin(angle))
        sz=int(8+4*math.sin(t*5+i*1.3))
        d.ellipse([sx-sz,sy-sz,sx+sz,sy+sz],fill=(255,220,50,200))
    return Image.alpha_composite(img,ov)


def add_warning_pulse(img, intensity):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    a=int(60*intensity)
    for margin in [0,15,30]:
        d.rectangle([margin,margin,W-margin,H-margin],outline=(220,40,40,a),width=8)
    return Image.alpha_composite(img,ov)


def slide_offset(frame_in_scene, total=12, direction="left"):
    progress=min(frame_in_scene/max(total,1),1.0); eased=1-(1-progress)**3
    if direction=="left":  return int((1-eased)*300),0
    if direction=="right": return int(-(1-eased)*300),0
    if direction=="up":    return 0,int((1-eased)*200)
    if direction=="down":  return 0,int(-(1-eased)*200)
    return 0,0


def zoom_scale(frame_in_scene, total=20, from_scale=1.3, to_scale=1.0):
    progress=min(frame_in_scene/max(total,1),1.0); eased=1-(1-progress)**3
    return from_scale+(to_scale-from_scale)*eased


_char_cache = None
def _load_char():
    global _char_cache
    if _char_cache is None and os.path.exists(CHARACTER_PATH):
        from scipy import ndimage
        orig=Image.open(CHARACTER_PATH).convert("RGBA"); arr=np.array(orig)
        r,g,b=arr[:,:,0].astype(int),arr[:,:,1].astype(int),arr[:,:,2].astype(int)
        sat=np.max([r,g,b],axis=0)-np.min([r,g,b],axis=0); brightness=(r+g+b)//3
        is_bg=(sat<30)&(brightness>130); labeled,_=ndimage.label(is_bg)
        border_labels=set()
        for la in [labeled[0,:],labeled[-1,:],labeled[:,0],labeled[:,-1]]:
            border_labels.update(la[la>0])
        bg_mask=np.zeros(is_bg.shape,dtype=bool)
        for lbl in border_labels: bg_mask|=(labeled==lbl)
        result=arr.copy(); result[bg_mask,3]=0
        _char_cache=Image.fromarray(result,"RGBA")
        print(f"  ✓ Panthulu loaded {_char_cache.size}")
    return _char_cache


def paste_char(base_img, frame_idx, scene, f_in_scene):
    char=_load_char()
    if char is None: return base_img
    t=frame_idx/FPS; bob=int(3*math.sin(2*math.pi*3.0*t))
    extra_bob=0; scale=CHAR_SCALE
    if scene==0:
        extra_bob=int(-12*abs(math.sin(2*math.pi*2.0*t)))
        scale=CHAR_SCALE+0.02*abs(math.sin(2*math.pi*1.5*t))
    elif scene==3: extra_bob=int(-6*abs(math.sin(2*math.pi*1.5*t)))
    elif scene==5: extra_bob=int(8*math.sin(2*math.pi*0.5*t))
    nw=int(char.size[0]*scale); nh=int(char.size[1]*scale)
    resized=char.resize((nw,nh),Image.LANCZOS)
    glow=Image.new("RGBA",base_img.size,(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse([CHAR_X-nw//2-25,CHAR_Y_BOTTOM-nh-5+bob+extra_bob,
                CHAR_X+nw//2+25,CHAR_Y_BOTTOM+20+bob+extra_bob],fill=(255,140,0,18))
    glow=glow.filter(ImageFilter.GaussianBlur(28))
    base_img=Image.alpha_composite(base_img,glow)
    shake_x=int(6*math.sin(2*math.pi*8*t)) if scene in (2,3) else 0
    px=max(0,min(CHAR_X-nw//2+shake_x,W-nw))
    py=max(CONTENT_Y_END-nh,CHAR_Y_BOTTOM-nh+bob+extra_bob)
    base_img.paste(resized,(px,py),resized)
    d=ImageDraw.Draw(base_img); bw,bh=240,40; bx=CHAR_X-bw//2; by=CHAR_Y_BOTTOM-42
    draw_card(d,bx,by,bx+bw,by+bh,fill=(80,40,0),border=GOLD,alpha=230)
    draw_mixed(d,(CHAR_X,by+bh//2),"పంతులు",24,bold=True,fill=GOLD,anchor="mm")
    return base_img


def tf(p,k):
    v=p.get(k,"N/A"); return v if v and v!="" else "N/A"


def scene_hook(base,draw,f,panchang):
    city=panchang.get("city","USA")
    sc=zoom_scale(f,total=18,from_scale=1.4,to_scale=1.0)
    base=add_glow(base,W//2,520,radius=320,color=(255,80,0),alpha=40)
    ox,oy=slide_offset(f,total=10,direction="up")
    s1,s2=int(90*sc),int(100*sc)
    draw_mixed(draw,(W//2+ox,300+oy),"ఈరోజు ఈ సమయం",s1,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(W//2+ox,420+oy),"తప్పించండి!",s2,bold=True,fill=GOLD,anchor="mm")
    sx,sy=slide_offset(f,total=16,direction="left")
    draw_mixed(draw,(W//2+sx,540+sy),city,42,fill=CREAM,anchor="mm")
    draw_mixed(draw,(W//2,598),panchang.get("date",""),34,fill=WHITE,anchor="mm")
    draw_card(draw,60,50,W-60,115,fill=(80,30,0),border=SAFFRON,alpha=200)
    draw_mixed(draw,(W//2,82),"నేటి పంచాంగం  |  Panthulu",30,bold=True,fill=GOLD,anchor="mm")
    return base


def scene_tithi(base,draw,f,panchang):
    tithi_val=tf(panchang,"tithi"); paksha=tf(panchang,"paksha")
    base=add_glow(base,W//2,600,radius=260,color=(255,160,0),alpha=25)
    sx,sy=slide_offset(f,total=10,direction="left")
    draw_card(draw,60+sx,180+sy,W-60+sx,260+sy,fill=(70,30,0),border=SAFFRON,alpha=220)
    draw_mixed(draw,(W//2+sx,220+sy),"ఈరోజు తిథి",44,bold=True,fill=SAFFRON,anchor="mm")
    vx,vy=slide_offset(max(f-6,0),total=12,direction="right")
    draw_card(draw,50+vx,290+vy,W-50+vx,450+vy,fill=(50,15,0),border=GOLD,radius=24,alpha=230)
    parts=tithi_val.split("→")
    if len(parts)==2:
        draw_mixed(draw,(W//2+vx,340+vy),parts[0].strip(),42,bold=True,fill=GOLD,anchor="mm")
        draw_mixed(draw,(W//2+vx,400+vy),"→ "+parts[1].strip(),36,fill=CREAM,anchor="mm")
    else:
        draw_mixed(draw,(W//2+vx,370+vy),tithi_val[:40],42,bold=True,fill=GOLD,anchor="mm")
    px2,py2=slide_offset(max(f-10,0),total=10,direction="up")
    draw_card(draw,200+px2,475+py2,W-200+px2,535+py2,fill=(60,20,0),border=(180,140,0),alpha=200)
    draw_mixed(draw,(W//2+px2,505+py2),paksha,30,fill=CREAM,anchor="mm")
    return base


def scene_rahu(base,draw,f,panchang):
    rahu=tf(panchang,"rahukaal"); tz=panchang.get("tz_label","ET")
    pulse=abs(math.sin(2*math.pi*2.5*(f/FPS)))
    base=add_warning_pulse(base,pulse*0.7)
    base=add_glow(base,W//2,550,radius=280,color=(220,30,30),alpha=30)
    sx,sy=slide_offset(f,total=10,direction="left")
    draw_card(draw,40+sx,170+sy,W-40+sx,270+sy,fill=(120,0,0),border=WARN_RED,alpha=230)
    draw.text((W//2+sx,220+sy),"⚠",font=get_latin_font(54,bold=True),fill=WARN_RED,anchor="mm")
    vx,vy=slide_offset(max(f-5,0),total=12,direction="right")
    draw_card(draw,50+vx,295+vy,W-50+vx,365+vy,fill=(90,0,0),border=WARN_RED,alpha=220)
    draw_mixed(draw,(W//2+vx,330+vy),"రాహు కాలం",46,bold=True,fill=WARN_RED,anchor="mm")
    tx,ty=slide_offset(max(f-8,0),total=12,direction="up")
    draw_card(draw,40+tx,390+ty,W-40+tx,510+ty,fill=(60,0,0),border=WARN_RED,radius=24,alpha=240)
    rahu_display=rahu.split("|")[0].strip()
    draw_mixed(draw,(W//2+tx,450+ty),rahu_display,52,bold=True,fill=WARN_RED,anchor="mm")
    draw_mixed(draw,(W//2+tx,500+ty),tz,28,fill=CREAM,anchor="mm")
    wx,wy=slide_offset(max(f-12,0),total=10,direction="up")
    draw_card(draw,60+wx,530+wy,W-60+wx,610+wy,fill=(80,10,10),border=(160,0,0),alpha=200)
    draw_mixed(draw,(W//2+wx,570+wy),"ఈ సమయంలో కొత్త పని వద్దు!",32,bold=True,fill=CREAM,anchor="mm")
    return base



def scene_durmuhurtam(base,draw,f,panchang):
    dur=tf(panchang,"durmuhurtam"); tz=panchang.get("tz_label","ET")
    pulse=abs(math.sin(2*math.pi*2.0*(f/FPS)))
    base=add_warning_pulse(base,pulse*0.5)
    base=add_glow(base,W//2,550,radius=260,color=(180,20,20),alpha=25)
    sx,sy=slide_offset(f,total=10,direction="right")
    draw_card(draw,40+sx,170+sy,W-40+sx,270+sy,fill=(110,0,0),border=WARN_RED,alpha=230)
    draw.text((W//2+sx,220+sy),"✗",font=get_latin_font(70,bold=True),fill=WARN_RED,anchor="mm")
    vx,vy=slide_offset(max(f-5,0),total=12,direction="left")
    draw_card(draw,50+vx,295+vy,W-50+vx,365+vy,fill=(85,0,0),border=WARN_RED,alpha=220)
    draw_mixed(draw,(W//2+vx,330+vy),"దుర్ముహూర్తం",46,bold=True,fill=WARN_RED,anchor="mm")
    tx,ty=slide_offset(max(f-8,0),total=12,direction="up")
    draw_card(draw,40+tx,390+ty,W-40+tx,510+ty,fill=(60,0,0),border=WARN_RED,radius=24,alpha=240)
    draw_mixed(draw,(W//2+tx,450+ty),dur,52,bold=True,fill=WARN_RED,anchor="mm")
    draw_mixed(draw,(W//2+tx,500+ty),tz,28,fill=CREAM,anchor="mm")
    wx,wy=slide_offset(max(f-12,0),total=10,direction="up")
    draw_card(draw,60+wx,530+wy,W-60+wx,610+wy,fill=(80,10,10),border=(160,0,0),alpha=200)
    draw_mixed(draw,(W//2+wx,570+wy),"శుభ కార్యాలు వద్దు!",32,bold=True,fill=CREAM,anchor="mm")
    return base

def scene_muhurtham(base,draw,f,panchang):
    abhijit=tf(panchang,"abhijit"); brahma=tf(panchang,"brahma_muhurta")
    base=add_glow(base,W//2,520,radius=300,color=(255,210,0),alpha=45)
    base=add_sparkles(base,W//2,480,n=10,t=f/FPS)
    sx,sy=slide_offset(f,total=10,direction="left")
    draw_card(draw,40+sx,165+sy,W-40+sx,255+sy,fill=(60,40,0),border=GOLD,alpha=230)
    draw.text((W//2+sx,210+sy),"✨",font=get_latin_font(50),fill=GOLD,anchor="mm")
    vx,vy=slide_offset(max(f-5,0),total=12,direction="right")
    draw_card(draw,50+vx,275+vy,W-50+vx,345+vy,fill=(50,35,0),border=GOLD,alpha=220)
    draw_mixed(draw,(W//2+vx,310+vy),"శుభ ముహూర్తం",46,bold=True,fill=GOLD,anchor="mm")
    tx,ty=slide_offset(max(f-8,0),total=12,direction="up")
    draw_card(draw,40+tx,365+ty,W-40+tx,490+ty,fill=(45,30,0),border=GOLD,radius=24,alpha=240)
    draw_mixed(draw,(W//2+tx,395+ty),"అభిజిత్ ముహూర్తం",34,bold=True,fill=CREAM,anchor="mm")
    draw_mixed(draw,(W//2+tx,448+ty),abhijit,46,bold=True,fill=GOLD,anchor="mm")
    bx,by=slide_offset(max(f-12,0),total=10,direction="up")
    draw_card(draw,60+bx,510+by,W-60+bx,590+by,fill=(40,25,0),border=(180,150,0),alpha=200)
    draw_mixed(draw,(W//2+bx,528+by),"బ్రహ్మ ముహూర్తం",26,fill=CREAM,anchor="mm")
    draw_mixed(draw,(W//2+bx,563+by),brahma.split("|")[0].strip(),30,bold=True,fill=(220,200,80),anchor="mm")
    return base


def scene_sunrise(base,draw,f,panchang):
    sunrise=tf(panchang,"sunrise"); sunset=tf(panchang,"sunset"); tz=panchang.get("tz_label","ET")
    base=add_glow(base,W//2,400,radius=250,color=(255,140,0),alpha=30)
    sx,sy=slide_offset(f,total=10,direction="up")
    draw_card(draw,60+sx,170+sy,W-60+sx,250+sy,fill=(60,30,0),border=SAFFRON,alpha=220)
    draw_mixed(draw,(W//2+sx,210+sy),"సూర్యుడు  ☀  చంద్రుడు",38,bold=True,fill=SAFFRON,anchor="mm")
    vx,vy=slide_offset(max(f-6,0),total=12,direction="left")
    draw_card(draw,40+vx,278+vy,W-40+vx,420+vy,fill=(55,22,0),border=GOLD,radius=22,alpha=235)
    draw_mixed(draw,(W//2+vx,315+vy),"🌅  సూర్యోదయం",36,bold=True,fill=CREAM,anchor="mm")
    draw_mixed(draw,(W//2+vx,375+vy),sunrise,58,bold=True,fill=GOLD,anchor="mm")
    tx,ty=slide_offset(max(f-10,0),total=12,direction="right")
    draw_card(draw,40+tx,445+ty,W-40+tx,580+ty,fill=(50,15,0),border=SAFFRON,radius=22,alpha=230)
    draw_mixed(draw,(W//2+tx,480+ty),"🌇  సూర్యాస్తమయం",36,bold=True,fill=CREAM,anchor="mm")
    draw_mixed(draw,(W//2+tx,543+ty),sunset,58,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(W//2,600),tz,28,fill=(180,160,100),anchor="mm")
    return base


def scene_cta(base,draw,f,panchang):
    base=add_glow(base,W//2,500,radius=350,color=(255,180,0),alpha=35)
    base=add_sparkles(base,W//2,480,n=12,t=f/FPS)
    sx,sy=slide_offset(f,total=12,direction="up")
    draw_card(draw,40+sx,160+sy,W-40+sx,320+sy,fill=(70,35,0),border=GOLD,radius=24,alpha=235)
    draw_mixed(draw,(W//2+sx,200+sy),"Daily Panchangam",40,bold=True,fill=GOLD,anchor="mm")
    draw_mixed(draw,(W//2+sx,255+sy),"కోసం Follow చేయండి!",46,bold=True,fill=SAFFRON,anchor="mm")
    vx,vy=slide_offset(max(f-8,0),total=12,direction="left")
    draw_card(draw,60+vx,345+vy,W-60+vx,425+vy,fill=(50,25,0),border=SAFFRON,alpha=210)
    draw_mixed(draw,(W//2+vx,385+vy),"Like ❤  Share 🔁  Comment 💬",32,bold=True,fill=CREAM,anchor="mm")
    nx,ny=slide_offset(max(f-12,0),total=10,direction="up")
    draw_mixed(draw,(W//2+nx,460+ny),"@PanthuluPanchangam",30,fill=GOLD,anchor="mm")
    bx,by=slide_offset(max(f-14,0),total=10,direction="up")
    draw_mixed(draw,(W//2+bx,530+by),"జయ శ్రీమన్నారాయణ! 🙏",38,bold=True,fill=GOLD,anchor="mm")
    return base


SCENE_RENDERERS=[scene_hook,scene_tithi,scene_rahu,scene_durmuhurtam,scene_muhurtham,scene_sunrise,scene_cta]


def build_frame(frame_idx, panchang):
    scene=0; f_in_scene=frame_idx; acc=0
    for i,nf in enumerate(SCENE_FRAMES):
        if frame_idx < acc+nf: scene=i; f_in_scene=frame_idx-acc; break
        acc+=nf
    img=make_bg(); img=draw_om_watermark(img,alpha=11)
    draw=ImageDraw.Draw(img); draw_border(draw)
    img=SCENE_RENDERERS[scene](img,draw,f_in_scene,panchang)
    img=paste_char(img,frame_idx,scene,f_in_scene)
    cy=H-28; spacing=24; sx=W//2-(7*spacing)//2; draw=ImageDraw.Draw(img)
    for i in range(7):
        x=sx+i*spacing
        if i==scene: draw.ellipse([x-9,cy-9,x+9,cy+9],fill=GOLD)
        else: draw.ellipse([x-5,cy-5,x+5,cy+5],outline=(160,130,0),width=2)
    return img


def get_audio_duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","default=noprint_wrappers=1:nokey=1",path],capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except: return 12.0


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    char_available=os.path.exists(CHARACTER_PATH)
    city=panchang.get("city","?")
    print(f"   {city} — {TOTAL_FRAMES} frames ({TOTAL_FRAMES/FPS:.1f}s) char={'✓' if char_available else '❌'}")
    with tempfile.TemporaryDirectory() as tmp:
        for fi in range(TOTAL_FRAMES):
            frame=build_frame(fi,panchang)
            frame.convert("RGB").save(str(Path(tmp)/f"frame_{fi:05d}.jpg"),"JPEG",quality=90)
            if fi%48==0: print(f"      Scene {fi//48+1}/7 rendered …")
        has_audio=audio_path and os.path.exists(audio_path)
        cmd=["ffmpeg","-y","-framerate",str(FPS),"-i",str(Path(tmp)/"frame_%05d.jpg")]
        if has_audio:
            cmd+=["-i",audio_path,"-c:a","aac","-b:a","192k",
                  "-t",str(TOTAL_FRAMES/FPS),"-shortest"]
        cmd+=["-c:v","libx264","-preset","fast","-crf","20",
              "-pix_fmt","yuv420p","-movflags","+faststart",output_path]
        r=subprocess.run(cmd,capture_output=True,text=True)
        if r.returncode!=0: raise RuntimeError(f"FFmpeg: {r.stderr[-1000:]}")
    print(f"  ✓ {output_path}"); return output_path


def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    TW,TH=1080,1920
    img=make_bg(); img=draw_om_watermark(img,alpha=10)
    draw=ImageDraw.Draw(img); draw_border(draw)
    city=panchang.get("city","USA"); date=panchang.get("date","")
    rahu=tf(panchang,"rahukaal").split("|")[0].strip(); tz=panchang.get("tz_label","ET")
    img=add_glow(img,TW//2,700,radius=350,color=(255,180,0),alpha=35); draw=ImageDraw.Draw(img)
    draw_card(draw,50,55,TW-50,135,fill=(80,30,0),border=GOLD,alpha=230)
    draw_mixed(draw,(TW//2,95),"నేటి పంచాంగం  ✦  Panthulu",32,bold=True,fill=GOLD,anchor="mm")
    draw_mixed(draw,(TW//2,230),"ఈరోజు ఈ సమయం",80,bold=True,fill=SAFFRON,anchor="mm")
    draw_mixed(draw,(TW//2,340),"తప్పించండి!",90,bold=True,fill=GOLD,anchor="mm")
    draw_mixed(draw,(TW//2,430),city,44,fill=CREAM,anchor="mm")
    draw_mixed(draw,(TW//2,484),date,36,fill=WHITE,anchor="mm")
    draw_card(draw,60,530,TW-60,640,fill=(100,0,0),border=WARN_RED,radius=22,alpha=235)
    draw_mixed(draw,(TW//2,562),"రాహు కాలం",36,bold=True,fill=WARN_RED,anchor="mm")
    draw_mixed(draw,(TW//2,612),f"{rahu}  {tz}",40,bold=True,fill=CREAM,anchor="mm")
    char=_load_char()
    if char:
        ch=int(TH*0.44); cw=int(char.size[0]*(ch/char.size[1]))
        img.paste(char.resize((cw,ch),Image.LANCZOS),(TW//2-cw//2,TH-ch-80),
                  char.resize((cw,ch),Image.LANCZOS))
    draw=ImageDraw.Draw(img)
    draw_card(draw,60,TH-180,TW-60,TH-80,fill=(60,30,0),border=SAFFRON,radius=20,alpha=220)
    draw_mixed(draw,(TW//2,TH-130),"Follow చేయండి  @PanthuluPanchangam",
               28,bold=True,fill=GOLD,anchor="mm")
    img.convert("RGB").save(output_path,"JPEG",quality=95)
    print(f"  ✓ Cover: {output_path}"); return output_path
