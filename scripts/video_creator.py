"""
video_creator.py v6
- Flood fill background removal (preserves face perfectly)
- FreeSansBold/FreeSans for Telugu rendering
- Character at bottom, never overlaps content
"""
import subprocess, os, tempfile, math, glob
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

W, H, FPS = 1080, 1920, 24

# Startup font diagnostics
import glob as _g
_td = _g.glob("/usr/local/share/fonts/telugu/*.ttf") + _g.glob("/usr/share/fonts/**/*Telugu*", recursive=True)
print(f"[VIDEO_CREATOR] SCRIPTS_DIR = {os.path.dirname(os.path.abspath(__file__))}")
print(f"[VIDEO_CREATOR] Telugu fonts on system: {_td}")
print(f"[VIDEO_CREATOR] scripts/FreeSans.ttf exists: {os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'FreeSans.ttf'))}")
print(f"[VIDEO_CREATOR] scripts/FreeSansBold.ttf exists: {os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'FreeSansBold.ttf'))}")

GOLD      = (255, 215, 0)
SAFFRON   = (255, 107, 0)
AVOID_RED = (220, 50,  50)
AUSPIC_G  = (46,  200, 80)
WHITE     = (255, 248, 240)
CREAM     = (255, 228, 181)
BG_TOP    = (18,  5,   0)
BG_MID    = (35,  10,  0)
BG_BTM    = (55,  18,  0)

SCRIPTS_DIR    = os.path.dirname(os.path.abspath(__file__))
CHARACTER_PATH = os.path.join(SCRIPTS_DIR, "pandit_character.png")

CONTENT_Y_END = int(H * 0.72)
CHAR_Y_BOTTOM = H - 30
CHAR_X        = W // 2
CHAR_SCALE    = 0.52


def get_font(size, bold=False):
    # PRIORITY 1: Telugu font copied by workflow to writable path (Pillow-verified)
    candidates = [
        "/home/runner/fonts/telugu/NotoSansTelugu-Bold.ttf" if bold
        else "/home/runner/fonts/telugu/NotoSansTelugu-Regular.ttf",
        # fallback: old path
        "/usr/local/share/fonts/telugu/NotoSansTelugu-Bold.ttf" if bold
        else "/usr/local/share/fonts/telugu/NotoSansTelugu-Regular.ttf",
    ]
    # PRIORITY 2: System NotoSansTelugu from fonts-noto-extra package
    noto_bold_pats   = ["/usr/share/fonts/**/*NotoSansTelugu-Bold*", "/usr/share/fonts/**/*NotoSansTelugu-[A-Z][a-z]*Bold*"]
    noto_reg_pats    = ["/usr/share/fonts/**/*NotoSansTelugu-Regular*", "/usr/share/fonts/**/*NotoSansTelugu-[A-Z][a-z]*Regular*"]
    noto_any_pats    = ["/usr/share/fonts/**/*NotoSansTelugu*", "/usr/share/fonts/**/*NotoSerifTelugu*"]
    for pat in (noto_bold_pats if bold else noto_reg_pats) + noto_any_pats:
        candidates += sorted(glob.glob(pat, recursive=True))
    # PRIORITY 3: Any Telugu font anywhere on system
    for pat in ["/usr/share/fonts/**/*Telugu*", "/usr/local/share/fonts/**/*Telugu*"]:
        candidates += sorted(glob.glob(pat, recursive=True))
    # NOTE: FreeSans/DejaVu intentionally excluded — they have zero Telugu glyphs
    print(f"  [FONT] Looking for {'bold' if bold else 'regular'} font, size={size}")
    for p in candidates:
        exists = p and os.path.exists(p)
        print(f"  [FONT]   {'✅' if exists else '❌'} {p}")
        if exists:
            try:
                font = ImageFont.truetype(p, size)
                print(f"  [FONT] LOADED: {p}")
                return font
            except Exception as e:
                print(f"  [FONT]   load error: {e}")
    print(f"  [FONT] WARNING: falling back to default font (no Telugu support!)")
    return ImageFont.load_default()


_char_cache = None
def _load_char():
    global _char_cache
    if _char_cache is None and os.path.exists(CHARACTER_PATH):
        from scipy import ndimage
        orig = Image.open(CHARACTER_PATH).convert("RGBA")
        arr  = np.array(orig)
        r,g,b = arr[:,:,0].astype(int), arr[:,:,1].astype(int), arr[:,:,2].astype(int)
        sat   = np.max([r,g,b], axis=0) - np.min([r,g,b], axis=0)
        brightness = (r+g+b)//3
        is_bg_color = (sat < 30) & (brightness > 130)
        labeled, _ = ndimage.label(is_bg_color)
        border_labels = set()
        for la in [labeled[0,:], labeled[-1,:], labeled[:,0], labeled[:,-1]]:
            border_labels.update(la[la > 0])
        bg_mask = np.zeros(is_bg_color.shape, dtype=bool)
        for lbl in border_labels:
            bg_mask |= (labeled == lbl)
        result = arr.copy()
        result[bg_mask, 3] = 0
        _char_cache = Image.fromarray(result, 'RGBA')
        print(f"  ✅ Character loaded {_char_cache.size}, bg removed")
    return _char_cache


def draw_gradient_bg(img):
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
    draw.rectangle([15,15,W-15,H-15], outline=(180,140,0), width=1)
    s=40
    for cx,cy in [(30,30),(W-30,30),(30,H-30),(W-30,H-30)]:
        draw.ellipse([cx-s//2,cy-s//2,cx+s//2,cy+s//2], outline=GOLD, width=2)
        draw.line([cx-s//2-5,cy,cx+s//2+5,cy], fill=GOLD, width=1)
        draw.line([cx,cy-s//2-5,cx,cy+s//2+5], fill=GOLD, width=1)


def draw_om_bg(img, alpha=14):
    ov=Image.new("RGBA",(W,H),(0,0,0,0))
    d=ImageDraw.Draw(ov)
    d.text((W//2,H//2-200),"ॐ",font=get_font(380,bold=True),fill=(255,200,0,alpha),anchor="mm")
    return Image.alpha_composite(img,ov)


def draw_card(draw,x1,y1,x2,y2,fill=(40,12,0),border=None,radius=18,alpha=215):
    fa=fill+(alpha,) if len(fill)==3 else fill
    r=radius
    draw.rectangle([x1+r,y1,x2-r,y2],fill=fa); draw.rectangle([x1,y1+r,x2,y2-r],fill=fa)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r],fill=fa)
    if border:
        for pts in [[x1+r,y1,x2-r,y1+2],[x1+r,y2-2,x2-r,y2],[x1,y1+r,x1+2,y2-r],[x2-2,y1+r,x2,y2-r]]:
            draw.rectangle(pts,fill=border)


def draw_divider(draw,y,color=GOLD):
    draw.line([(50,y),(W-50,y)],fill=color,width=2)


def draw_section_header(draw,text,y,color=GOLD,size=44):
    draw_divider(draw,y-2,color)
    draw.text((W//2,y+size//2),text,font=get_font(size,bold=True),fill=color,anchor="mm")
    draw_divider(draw,y+size+4,color)


def draw_progress(draw,card_num,total=4):
    cy=H-40; spacing=28; sx=W//2-(total*spacing)//2
    for i in range(total):
        x=sx+i*spacing
        if i+1==card_num: draw.ellipse([x-10,cy-10,x+10,cy+10],fill=GOLD)
        else: draw.ellipse([x-6,cy-6,x+6,cy+6],outline=(180,140,0),width=2)


def draw_name_badge(draw,x_center,y,name="నారాయణ"):
    bw,bh=280,44; x1=x_center-bw//2
    draw_card(draw,x1,y,x1+bw,y+bh,fill=(80,40,0),border=GOLD,alpha=235)
    draw.text((x_center,y+bh//2),name,font=get_font(28,bold=True),fill=GOLD,anchor="mm")


def tf(p,k):
    v=p.get(k,"N/A"); return v if v and v!="" else "N/A"


def build_static_card(card_num, panchang):
    img=Image.new("RGBA",(W,H),(0,0,0,255))
    img=draw_gradient_bg(img); img=draw_om_bg(img,alpha=14)
    draw=ImageDraw.Draw(img); draw_border(draw)
    city=panchang.get("city","USA"); tz=panchang.get("tz_label","ET")

    if card_num==1:
        draw.text((W//2,65),"ॐ",font=get_font(58,bold=True),fill=GOLD,anchor="mm")
        draw.text((W//2,132),"నేటి పంచాంగం",font=get_font(56,bold=True),fill=GOLD,anchor="mm")
        draw_divider(draw,172,SAFFRON)
        draw.text((W//2,205),f"📍 {city}",font=get_font(38),fill=SAFFRON,anchor="mm")
        draw.text((W//2,252),f"{panchang.get('weekday','')}  •  {panchang.get('date','')}",
                  font=get_font(30),fill=CREAM,anchor="mm")
        rows=[("తిథి",tf(panchang,"tithi")),("నక్షత్రం",tf(panchang,"nakshatra")),
              ("యోగం",tf(panchang,"yoga")),("కరణం",tf(panchang,"karana")),("పక్షం",tf(panchang,"paksha"))]
        y=282
        for label,val in rows:
            draw_card(draw,40,y,W-40,y+86,fill=(45,12,0),border=SAFFRON)
            draw.text((68,y+10),label,font=get_font(26,bold=True),fill=SAFFRON)
            draw.text((68,y+44),val[:44],font=get_font(28),fill=WHITE)
            y+=94
        draw_progress(draw,1)

    elif card_num==2:
        draw_section_header(draw,"⛔ నివారించవలసిన సమయాలు",50,color=AVOID_RED,size=40)
        draw.text((W//2,126),f"📍 {city} ({tz})",font=get_font(34),fill=SAFFRON,anchor="mm")
        draw_divider(draw,162,AVOID_RED)
        items=[("రాహు కాలం","rahukaal","🔴"),("దుర్ముహూర్తం","durmuhurtam","⛔"),
               ("గులిక కాలం","gulika","🟠"),("యమగండం","yamagandam","⚠️"),("వర్జ్యం","varjyam","🚫")]
        y=175
        for label,key,icon in items:
            val=tf(panchang,key)
            if val=="N/A": continue
            draw_card(draw,40,y,W-40,y+92,fill=(65,0,0),border=AVOID_RED)
            draw.text((68,y+10),f"{icon} {label}",font=get_font(28,bold=True),fill=CREAM)
            draw.text((68,y+50),val,font=get_font(30,bold=True),fill=AVOID_RED)
            y+=100
        draw_progress(draw,2)

    elif card_num==3:
        draw_section_header(draw,"✅ శుభ ముహూర్తాలు",50,color=AUSPIC_G,size=40)
        draw.text((W//2,126),f"📍 {city} ({tz})",font=get_font(34),fill=SAFFRON,anchor="mm")
        draw_divider(draw,162,AUSPIC_G)
        items=[("బ్రహ్మ ముహూర్తం","brahma_muhurta","🌅"),("అభిజిత్ ముహూర్తం","abhijit","⭐"),
               ("విజయ ముహూర్తం","vijaya_muhurta","🏆"),("అమృత కాలం","amrit_kalam","🪷"),
               ("గోధూళి ముహూర్తం","godhuli_muhurta","🌇")]
        y=175
        for label,key,icon in items:
            val=tf(panchang,key)
            if val=="N/A": continue
            draw_card(draw,40,y,W-40,y+92,fill=(0,42,15),border=AUSPIC_G)
            draw.text((68,y+10),f"{icon} {label}",font=get_font(28,bold=True),fill=CREAM)
            draw.text((68,y+50),val,font=get_font(30,bold=True),fill=AUSPIC_G)
            y+=100
        draw_progress(draw,3)

    elif card_num==4:
        draw_section_header(draw,"🌅 సూర్య చంద్ర వివరాలు",50,color=GOLD,size=40)
        draw.text((W//2,126),f"📍 {city}",font=get_font(34),fill=SAFFRON,anchor="mm")
        draw_divider(draw,162,GOLD)
        items=[("🌅 సూర్యోదయం","sunrise"),("🌇 సూర్యాస్తమయం","sunset"),
               ("🌕 చంద్రోదయం","moonrise"),("🌑 చంద్రాస్తమయం","moonset")]
        y=180
        for label,key in items:
            val=tf(panchang,key)
            draw_card(draw,40,y,W-40,y+84,fill=(38,22,0),border=GOLD)
            draw.text((68,y+12),label,font=get_font(30,bold=True),fill=CREAM)
            draw.text((W-55,y+12),val,font=get_font(32,bold=True),fill=GOLD,anchor="ra")
            y+=92
        y+=16
        draw_card(draw,40,y,W-40,y+115,fill=(75,35,0),border=GOLD,alpha=230)
        draw.text((W//2,y+33),"🙏 జయ శ్రీమన్నారాయణ!",font=get_font(36,bold=True),fill=GOLD,anchor="mm")
        draw.text((W//2,y+80),"Like · Share · Subscribe చేయండి",font=get_font(26),fill=CREAM,anchor="mm")
        draw_progress(draw,4)

    return img


def paste_character_speaking(base_img, frame_idx, x_center, y_bottom, base_scale):
    char=_load_char()
    if char is None: return base_img
    t=frame_idx/FPS
    bob_y=int(4*math.sin(2*math.pi*3.5*t))
    scale=base_scale+0.005*math.sin(2*math.pi*3.5*t+0.4)
    nw=int(char.size[0]*scale); nh=int(char.size[1]*scale)
    resized=char.resize((nw,nh),Image.LANCZOS)
    glow=Image.new("RGBA",base_img.size,(0,0,0,0))
    gd=ImageDraw.Draw(glow)
    gd.ellipse([x_center-nw//2-20,y_bottom-nh-10+bob_y,
                x_center+nw//2+20,y_bottom+15+bob_y],fill=(255,160,0,20))
    glow=glow.filter(ImageFilter.GaussianBlur(30))
    base_img=Image.alpha_composite(base_img,glow)
    px=max(0,min(x_center-nw//2,W-nw)); py=max(CONTENT_Y_END-nh, y_bottom-nh+bob_y)
    base_img.paste(resized,(px,py),resized)
    return base_img


def get_audio_duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","default=noprint_wrappers=1:nokey=1",path],capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except: return 60.0


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    has_audio=audio_path and os.path.exists(audio_path)
    duration=max(get_audio_duration(audio_path) if has_audio else 60.0, 48.0)
    frames_per_card=int((duration/4)*FPS)
    char_available=os.path.exists(CHARACTER_PATH)
    print(f"  🎬 {panchang.get('city','?')} — {duration:.0f}s char={'✅' if char_available else '❌'}")
    with tempfile.TemporaryDirectory() as tmp:
        frame_idx=0
        for card_num in range(1,5):
            print(f"     📸 Card {card_num}/4 …")
            static=build_static_card(card_num,panchang)
            for f in range(frames_per_card):
                frame=static.copy()
                if char_available:
                    frame=paste_character_speaking(frame,frame_idx,CHAR_X,CHAR_Y_BOTTOM,CHAR_SCALE)
                    d=ImageDraw.Draw(frame); draw_name_badge(d,CHAR_X,CHAR_Y_BOTTOM-48)
                frame.convert("RGB").save(str(Path(tmp)/f"frame_{frame_idx:05d}.jpg"),"JPEG",quality=88)
                frame_idx+=1
        cmd=["ffmpeg","-y","-framerate",str(FPS),"-i",str(Path(tmp)/"frame_%05d.jpg")]
        if has_audio:
            cmd+=["-i",audio_path,"-c:a","aac","-b:a","192k","-shortest"]
        cmd+=["-c:v","libx264","-preset","fast","-crf","22","-pix_fmt","yuv420p","-movflags","+faststart",output_path]
        r=subprocess.run(cmd,capture_output=True,text=True)
        if r.returncode!=0: raise RuntimeError(f"FFmpeg: {r.stderr[-1000:]}")
    print(f"  ✅ {output_path}"); return output_path


def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    TW,TH=1280,720
    img=Image.new("RGBA",(TW,TH),(0,0,0,255)); draw=ImageDraw.Draw(img)
    for y in range(TH):
        t=y/TH; draw.line([(0,y),(TW,y)],fill=(int(18+(55-18)*t),int(5+(18-5)*t),0))
    ov=Image.new("RGBA",(TW,TH),(0,0,0,0)); od=ImageDraw.Draw(ov)
    od.text((TW//2,TH//2),"ॐ",font=get_font(280,bold=True),fill=(255,200,0,18),anchor="mm")
    img=Image.alpha_composite(img,ov); draw=ImageDraw.Draw(img)
    draw.rectangle([6,6,TW-6,TH-6],outline=GOLD,width=3)
    TX=TW*68//100
    draw.text((TX//2,65),"🕉  నేటి పంచాంగం",font=get_font(58,bold=True),fill=GOLD,anchor="mm")
    draw.text((TX//2,142),f"📍 {panchang.get('city','USA')}",font=get_font(44),fill=SAFFRON,anchor="mm")
    draw.line([(40,178),(TX-10,178)],fill=SAFFRON,width=2)
    draw.text((TX//2,208),panchang.get("weekday",""),font=get_font(34),fill=WHITE,anchor="mm")
    draw.text((TX//2,256),f"తిథి: {tf(panchang,'tithi')[:32]}",font=get_font(30),fill=CREAM,anchor="mm")
    draw.text((TX//2,298),f"నక్షత్రం: {tf(panchang,'nakshatra')[:30]}",font=get_font(30),fill=CREAM,anchor="mm")
    draw_card(draw,40,334,TX-10,400,fill=(90,0,0),border=AVOID_RED,alpha=220)
    draw.text((TX//2,366),f"⛔ రాహు కాలం: {tf(panchang,'rahukaal')}",
              font=get_font(28,bold=True),fill=(255,100,100),anchor="mm")
    draw.text((TX//2,453),"అన్ని 5 అమెరికా నగరాలకు పంచాంగం",font=get_font(25),fill=GOLD,anchor="mm")
    draw.text((TX//2,493),"Subscribe • Like • Share చేయండి",font=get_font(23),fill=CREAM,anchor="mm")
    char=_load_char()
    if char:
        ch=int(TH*0.97); cw=int(char.size[0]*(ch/char.size[1]))
        img.paste(char.resize((cw,ch),Image.LANCZOS),(TW-cw-4,TH-ch),char.resize((cw,ch),Image.LANCZOS))
    img.convert("RGB").save(output_path,"JPEG",quality=93)
    print(f"  ✅ Thumbnail: {output_path}"); return output_path
