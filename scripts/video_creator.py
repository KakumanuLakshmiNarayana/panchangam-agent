"""
video_creator.py — Panchangam video with animated speaking character.
Character: pandit_character.png (transparent PNG, 912x1175)
Speaking animation: subtle body bob + scale pulse ONLY — character image untouched.
Name: నారాయణ
"""
import subprocess, os, tempfile, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 24

GOLD      = (255, 215, 0)
SAFFRON   = (255, 107, 0)
AVOID_RED = (220, 50, 50)
AUSPIC_G  = (46, 200, 80)
WHITE     = (255, 248, 240)
CREAM     = (255, 228, 181)
BG_TOP    = (18, 5, 0)
BG_MID    = (35, 10, 0)
BG_BTM    = (55, 18, 0)

SCRIPTS_DIR    = os.path.dirname(os.path.abspath(__file__))
CHARACTER_PATH = os.path.join(SCRIPTS_DIR, "pandit_character.png")

_char_cache = None
def _load_char():
    global _char_cache
    if _char_cache is None and os.path.exists(CHARACTER_PATH):
        _char_cache = Image.open(CHARACTER_PATH).convert("RGBA")
    return _char_cache


def get_font(size, bold=False):
    for p in [
        f"/usr/share/fonts/truetype/noto/NotoSans{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/noto/NotoSansTelugu-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: continue
    return ImageFont.load_default()


def draw_gradient_bg(img):
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        if t < 0.5:
            t2 = t*2
            r=int(BG_TOP[0]+(BG_MID[0]-BG_TOP[0])*t2)
            g=int(BG_TOP[1]+(BG_MID[1]-BG_TOP[1])*t2)
            b=int(BG_TOP[2]+(BG_MID[2]-BG_TOP[2])*t2)
        else:
            t2=(t-0.5)*2
            r=int(BG_MID[0]+(BG_BTM[0]-BG_MID[0])*t2)
            g=int(BG_MID[1]+(BG_BTM[1]-BG_MID[1])*t2)
            b=int(BG_MID[2]+(BG_BTM[2]-BG_MID[2])*t2)
        draw.line([(0,y),(W,y)],fill=(r,g,b))
    return img


def draw_border(draw):
    draw.rectangle([6,6,W-6,H-6],outline=GOLD,width=3)
    draw.rectangle([15,15,W-15,H-15],outline=(180,140,0),width=1)
    s=40
    for cx,cy in [(30,30),(W-30,30),(30,H-30),(W-30,H-30)]:
        draw.ellipse([cx-s//2,cy-s//2,cx+s//2,cy+s//2],outline=GOLD,width=2)
        draw.line([cx-s//2-5,cy,cx+s//2+5,cy],fill=GOLD,width=1)
        draw.line([cx,cy-s//2-5,cx,cy+s//2+5],fill=GOLD,width=1)


def draw_om_bg(img, alpha=14):
    ov=Image.new("RGBA",(W,H),(0,0,0,0))
    d=ImageDraw.Draw(ov)
    d.text((W//2,H//2-100),"ॐ",font=get_font(420,bold=True),fill=(255,200,0,alpha),anchor="mm")
    return Image.alpha_composite(img, ov)


def draw_card(draw,x1,y1,x2,y2,fill=(40,12,0,210),border=None,radius=18):
    r=radius
    draw.rectangle([x1+r,y1,x2-r,y2],fill=fill)
    draw.rectangle([x1,y1+r,x2,y2-r],fill=fill)
    for ex,ey in [(x1,y1),(x2-2*r,y1),(x1,y2-2*r),(x2-2*r,y2-2*r)]:
        draw.ellipse([ex,ey,ex+2*r,ey+2*r],fill=fill)
    if border:
        draw.rectangle([x1+r,y1,x2-r,y1+2],fill=border)
        draw.rectangle([x1+r,y2-2,x2-r,y2],fill=border)
        draw.rectangle([x1,y1+r,x1+2,y2-r],fill=border)
        draw.rectangle([x2-2,y1+r,x2,y2-r],fill=border)


def draw_section_header(draw,text,y,color=GOLD,size=46):
    font=get_font(size,bold=True)
    draw.line([(50,y-2),(W-50,y-2)],fill=color,width=1)
    draw.text((W//2,y+size//2),text,font=font,fill=color,anchor="mm")
    draw.line([(50,y+size+4),(W-50,y+size+4)],fill=color,width=1)


def draw_name_badge(draw,x_center,y,name="నారాయణ"):
    bw,bh=260,42
    x1=x_center-bw//2
    draw_card(draw,x1,y,x1+bw,y+bh,fill=(80,40,0,235),border=GOLD)
    draw.text((x_center,y+bh//2),name,font=get_font(26,bold=True),fill=GOLD,anchor="mm")


def draw_progress(draw,card_num,total=4):
    cy=H-55; spacing=28; sx=W//2-(total*spacing)//2
    for i in range(total):
        x=sx+i*spacing
        if i+1==card_num: draw.ellipse([x-10,cy-10,x+10,cy+10],fill=GOLD)
        else: draw.ellipse([x-6,cy-6,x+6,cy+6],outline=(180,140,0),width=2)


def tf(p,k):
    v=p.get(k,"N/A")
    return v if v and v!="" else "N/A"


# ── Speaking animation — body bob only, character image NEVER modified ────────

def paste_character_speaking(base_img, frame_idx, x_center, y_bottom, base_scale):
    """
    Paste character with subtle speaking animation.
    Uses only position bob + tiny scale pulse.
    The character PNG is NEVER modified — no black lines possible.
    """
    char = _load_char()
    if char is None:
        return base_img

    t = frame_idx / FPS
    # Natural speech rhythm: primary syllable rate ~3.5Hz + overtone
    bob_y   = int(4 * math.sin(2*math.pi*3.5*t))
    scale_d = 0.005 * math.sin(2*math.pi*3.5*t + 0.4)
    scale   = base_scale + scale_d

    nw = int(char.size[0] * scale)
    nh = int(char.size[1] * scale)
    resized = char.resize((nw, nh), Image.LANCZOS)

    # Warm glow behind character
    glow = Image.new("RGBA", base_img.size, (0,0,0,0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([x_center-nw//2-20, y_bottom-nh-15+bob_y,
                x_center+nw//2+20, y_bottom+20+bob_y],
               fill=(255,170,0,25))
    glow = glow.filter(ImageFilter.GaussianBlur(32))
    base_img = Image.alpha_composite(base_img, glow)

    px = x_center - nw//2
    py = y_bottom - nh + bob_y
    # Clamp to frame bounds
    px = max(0, min(px, W-nw))
    py = max(0, min(py, H-nh))
    base_img.paste(resized, (px, py), resized)
    return base_img


# ── Card builders ──────────────────────────────────────────────────────────────

def build_static_card(card_num, panchang):
    img = Image.new("RGBA",(W,H),(0,0,0,255))
    img = draw_gradient_bg(img)
    img = draw_om_bg(img,alpha=14)
    draw = ImageDraw.Draw(img)
    draw_border(draw)

    city=panchang.get("city","USA"); tz=panchang.get("tz_label","ET")

    if card_num==1:
        draw.text((W//2,70),"ॐ",font=get_font(60,bold=True),fill=GOLD,anchor="mm")
        draw.text((W//2,140),"నేటి పంచాంగం",font=get_font(58,bold=True),fill=GOLD,anchor="mm")
        draw.line([(50,178),(W-50,178)],fill=SAFFRON,width=2)
        draw.text((W//2,210),f"📍 {city}",font=get_font(38),fill=SAFFRON,anchor="mm")
        draw.text((W//2,258),f"{panchang.get('weekday','')}  •  {panchang.get('date','')}",
                  font=get_font(30),fill=CREAM,anchor="mm")
        rows=[("తిథి",tf(panchang,"tithi")),("నక్షత్రం",tf(panchang,"nakshatra")),
              ("యోగం",tf(panchang,"yoga")),("కరణం",tf(panchang,"karana")),
              ("పక్షం",tf(panchang,"paksha"))]
        y=308
        for label,val in rows:
            draw_card(draw,45,y,W-45,y+84,fill=(45,12,0,210),border=SAFFRON)
            draw.text((72,y+12),label,font=get_font(28,bold=True),fill=SAFFRON)
            v=val[:44]+"…" if len(val)>44 else val
            draw.text((72,y+46),v,font=get_font(28),fill=WHITE)
            y+=92
        draw_progress(draw,1)

    elif card_num==2:
        draw_section_header(draw,"⛔ నివారించవలసిన సమయాలు",52,color=AVOID_RED,size=44)
        draw.text((W//2,132),f"📍 {city} ({tz})",font=get_font(34),fill=SAFFRON,anchor="mm")
        draw.line([(50,165),(W-50,165)],fill=AVOID_RED,width=2)
        items=[("రాహు కాలం","rahukaal","🔴"),("దుర్ముహూర్తం","durmuhurtam","⛔"),
               ("గులిక కాలం","gulika","🟠"),("యమగండం","yamagandam","⚠️"),
               ("వర్జ్యం","varjyam","🚫")]
        y=192
        for label,key,icon in items:
            val=tf(panchang,key)
            draw_card(draw,45,y,W-45,y+90,fill=(65,0,0,215),border=AVOID_RED)
            draw.text((68,y+12),f"{icon} {label}",font=get_font(30,bold=True),fill=CREAM)
            draw.text((68,y+50),val,font=get_font(32,bold=True),fill=AVOID_RED)
            y+=98
        draw_progress(draw,2)

    elif card_num==3:
        draw_section_header(draw,"✅ శుభ ముహూర్తాలు",52,color=AUSPIC_G,size=44)
        draw.text((W//2,132),f"📍 {city} ({tz})",font=get_font(34),fill=SAFFRON,anchor="mm")
        draw.line([(50,165),(W-50,165)],fill=AUSPIC_G,width=2)
        items=[("బ్రహ్మ ముహూర్తం","brahma_muhurta","🌅"),
               ("అభిజిత్ ముహూర్తం","abhijit","⭐"),
               ("విజయ ముహూర్తం","vijaya_muhurta","🏆"),
               ("అమృత కాలం","amrit_kalam","🪷"),
               ("గోధూళి ముహూర్తం","godhuli_muhurta","🌇")]
        y=192
        for label,key,icon in items:
            val=tf(panchang,key)
            draw_card(draw,45,y,W-45,y+90,fill=(0,42,15,215),border=AUSPIC_G)
            draw.text((68,y+12),f"{icon} {label}",font=get_font(30,bold=True),fill=CREAM)
            draw.text((68,y+50),val,font=get_font(32,bold=True),fill=AUSPIC_G)
            y+=98
        draw_progress(draw,3)

    elif card_num==4:
        draw_section_header(draw,"🌅 సూర్య చంద్ర వివరాలు",52,color=GOLD,size=44)
        draw.text((W//2,132),f"📍 {city}",font=get_font(34),fill=SAFFRON,anchor="mm")
        draw.line([(50,165),(W-50,165)],fill=GOLD,width=2)
        items=[("🌅 సూర్యోదయం","sunrise"),("🌇 సూర్యాస్తమయం","sunset"),
               ("🌕 చంద్రోదయం","moonrise"),("🌑 చంద్రాస్తమయం","moonset")]
        y=198
        for label,key in items:
            val=tf(panchang,key)
            draw_card(draw,45,y,W-45,y+82,fill=(38,22,0,215),border=GOLD)
            draw.text((68,y+12),label,font=get_font(30,bold=True),fill=CREAM)
            draw.text((W-65,y+12),val,font=get_font(32,bold=True),fill=GOLD,anchor="ra")
            y+=90
        y+=22
        draw_card(draw,45,y,W-45,y+130,fill=(75,35,0,230),border=GOLD)
        draw.text((W//2,y+40),"🙏 జయ శ్రీమన్నారాయణ!",font=get_font(38,bold=True),fill=GOLD,anchor="mm")
        draw.text((W//2,y+90),"Like · Share · Subscribe చేయండి",font=get_font(28),fill=CREAM,anchor="mm")
        draw_progress(draw,4)

    return img


# x_center, y_bottom, scale per card
CHAR_POS = {
    1: (W-170, H-88, 0.37),
    2: (168,   H-88, 0.35),
    3: (W-170, H-88, 0.35),
    4: (W//2,  H-82, 0.39),
}


def get_audio_duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","default=noprint_wrappers=1:nokey=1",path],
                     capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except: return 60.0


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    has_audio = audio_path and os.path.exists(audio_path)
    duration  = get_audio_duration(audio_path) if has_audio else 60.0
    duration  = max(duration, 48.0)

    total_cards     = 4
    secs_per_card   = duration / total_cards
    frames_per_card = int(secs_per_card * FPS)
    char_available  = os.path.exists(CHARACTER_PATH)

    print(f"  🎬 {panchang.get('city','?')} — {duration:.0f}s, char={'✅' if char_available else '❌'}")

    with tempfile.TemporaryDirectory() as tmp:
        frame_idx = 0
        for card_num in range(1, total_cards+1):
            print(f"     📸 Card {card_num}/{total_cards}...")
            static = build_static_card(card_num, panchang)
            cx, cy_bot, scale = CHAR_POS[card_num]

            for f in range(frames_per_card):
                frame = static.copy()
                if char_available:
                    frame = paste_character_speaking(frame, frame_idx, cx, cy_bot, scale)
                    draw = ImageDraw.Draw(frame)
                    draw_name_badge(draw, cx, cy_bot - 40)

                fp = Path(tmp)/f"frame_{frame_idx:05d}.jpg"
                frame.convert("RGB").save(str(fp),"JPEG",quality=88)
                frame_idx += 1

        print(f"     🎞️  {frame_idx} frames — assembling MP4...")
        cmd = ["ffmpeg","-y","-framerate",str(FPS),
               "-i",str(Path(tmp)/"frame_%05d.jpg")]
        if has_audio:
            cmd += ["-i",audio_path,"-c:a","aac","-b:a","192k","-shortest"]
        cmd += ["-c:v","libx264","-preset","fast","-crf","22",
                "-pix_fmt","yuv420p","-movflags","+faststart",output_path]
        r = subprocess.run(cmd,capture_output=True,text=True)
        if r.returncode!=0:
            print(f"  ❌ FFmpeg:\n{r.stderr[-2000:]}")
            raise RuntimeError("FFmpeg failed")

    print(f"  ✅ {output_path}")
    return output_path


def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    TW,TH=1280,720
    img=Image.new("RGBA",(TW,TH),(0,0,0,255))
    draw=ImageDraw.Draw(img)
    for y in range(TH):
        t=y/TH; r=int(18+(55-18)*t); g=int(5+(18-5)*t)
        draw.line([(0,y),(TW,y)],fill=(r,g,0))
    ov=Image.new("RGBA",(TW,TH),(0,0,0,0))
    od=ImageDraw.Draw(ov)
    od.text((TW//2,TH//2),"ॐ",font=get_font(300,bold=True),fill=(255,200,0,18),anchor="mm")
    img=Image.alpha_composite(img,ov)
    draw=ImageDraw.Draw(img)
    draw.rectangle([6,6,TW-6,TH-6],outline=GOLD,width=3)

    city=panchang.get("city","USA"); weekday=panchang.get("weekday","")
    draw.text((TW//2,65),"🕉  నేటి పంచాంగం",font=get_font(64,bold=True),fill=GOLD,anchor="mm")
    draw.text((TW//2,148),f"📍 {city}",font=get_font(50),fill=SAFFRON,anchor="mm")
    draw.line([(50,182),(TW-50,182)],fill=SAFFRON,width=2)
    draw.text((TW//2,215),weekday,font=get_font(38),fill=WHITE,anchor="mm")
    draw.text((TW//2,270),f"తిథి: {tf(panchang,'tithi')[:38]}",font=get_font(36),fill=CREAM,anchor="mm")
    draw.text((TW//2,320),f"నక్షత్రం: {tf(panchang,'nakshatra')[:38]}",font=get_font(36),fill=CREAM,anchor="mm")
    draw_card(draw,60,362,TW-60,432,fill=(90,0,0,220),border=AVOID_RED)
    draw.text((TW//2,397),f"⛔ రాహు కాలం: {tf(panchang,'rahukaal')}",
              font=get_font(34,bold=True),fill=(255,100,100),anchor="mm")
    draw.text((TW//2,475),"అన్ని 5 అమెరికా నగరాలకు పంచాంగం",font=get_font(28),fill=GOLD,anchor="mm")
    draw.text((TW//2,520),"Subscribe • Like • Share చేయండి",font=get_font(26),fill=CREAM,anchor="mm")

    if os.path.exists(CHARACTER_PATH):
        char=Image.open(CHARACTER_PATH).convert("RGBA")
        ch=int(TH*0.88); cw=int(char.size[0]*(ch/char.size[1]))
        char=char.resize((cw,ch),Image.LANCZOS)
        img.paste(char,(TW-cw-10,TH-ch-5),char)

    img.convert("RGB").save(output_path,"JPEG",quality=93)
    print(f"  ✅ Thumbnail: {output_path}")
    return output_path
