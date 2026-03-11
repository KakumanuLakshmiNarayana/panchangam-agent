"""
video_creator.py — City-specific Panchang video showing all timings from screenshot.
Auspicious Timings + Inauspicious Timings sections exactly matching Drikpanchang.
"""
import subprocess, os
from pathlib import Path

W, H, FPS = 1080, 1920, 30
DUR = 65

GOLD    = "0xFFD700"
SAFFRON = "0xFF6B00"
AVOID   = "0xFF5555"
AUSPIC  = "0x55FF88"
WHITE   = "0xFFF8F0"
CREAM   = "0xFFE4B5"
BG      = "0x1a0800"


def esc(t):
    return (str(t).replace("\\","\\\\").replace("'","\\'")
            .replace(":","\\:").replace("%","\\%")
            .replace("[","\\[").replace("]","\\]"))


def dt(text, x, y, size, color=WHITE, s=0, e=None, box=True, border=10):
    a = [f"text='{esc(str(text))}'",
         f"x={x}", f"y={y}",
         f"fontsize={size}", f"fontcolor={color}"]
    if box:
        a.append(f"box=1:boxcolor=0x00000099:boxborderw={border}")
    if e is not None:
        a.append(f"enable='between(t,{s},{e})'")
    return "drawtext=" + ":".join(a)


def tf(p, k, default="N/A"):
    v = p.get(k, default)
    return v if v and v != "" else default


def build_filters(p, duration):
    cx = "(w-text_w)/2"
    city     = p.get("city", "USA")
    tz       = p.get("tz_label", "")
    weekday  = p.get("weekday", "")
    filters  = []

    # ── CARD 1: Header + Basic Info (0–15s) ─────────────────────
    filters += [
        dt("🕉  Daily Panchangam",          cx,  130, 68, GOLD,    s=0,  e=15),
        dt(f"📍 {city}",                    cx,  230, 52, SAFFRON, s=0,  e=15),
        dt(weekday,                         cx,  310, 40, WHITE,   s=0,  e=15),
        dt(f"Tithi: {tf(p,'tithi')}",       cx,  390, 36, CREAM,   s=0,  e=15),
        dt(f"Nakshatra: {tf(p,'nakshatra')}",cx, 450, 36, CREAM,   s=0,  e=15),
        dt(f"Yoga: {tf(p,'yoga')}",         cx,  510, 34, WHITE,   s=0,  e=15),
        dt(f"Karana: {tf(p,'karana')}",     cx,  570, 34, WHITE,   s=0,  e=15),
        dt(f"Masa: {tf(p,'masa')} | {tf(p,'paksha')}", cx, 640, 30, SAFFRON, s=0, e=15),
    ]

    # ── CARD 2: Inauspicious Timings (15–35s) ───────────────────
    filters += [
        dt("⛔  Inauspicious Timings",       cx,  110, 56, AVOID,   s=15, e=35),
        dt(f"📍 {city} ({tz})",              cx,  190, 34, SAFFRON, s=15, e=35),
    ]
    avoid_rows = [
        ("Rahu Kalam",   "rahukaal"),
        ("Dur Muhurtam", "durmuhurtam"),
        ("Gulika Kalam", "gulika"),
        ("Yamaganda",    "yamagandam"),
        ("Varjyam",      "varjyam"),
    ]
    for i, (label, key) in enumerate(avoid_rows):
        yb = 290 + i * 130
        val = tf(p, key)
        filters.append(dt(f"{label}:",  cx, str(yb),    32, SAFFRON, s=15, e=35))
        filters.append(dt(val,          cx, str(yb+44), 32, AVOID,   s=15, e=35))

    # ── CARD 3: Auspicious Timings (35–55s) ─────────────────────
    filters += [
        dt("✅  Auspicious Timings",         cx,  110, 56, AUSPIC,  s=35, e=55),
        dt(f"📍 {city} ({tz})",              cx,  190, 34, SAFFRON, s=35, e=55),
    ]
    auspic_rows = [
        ("Brahma Muhurta",  "brahma_muhurta"),
        ("Abhijit",         "abhijit"),
        ("Vijaya Muhurta",  "vijaya_muhurta"),
        ("Godhuli Muhurta", "godhuli_muhurta"),
        ("Amrit Kalam",     "amrit_kalam"),
    ]
    for i, (label, key) in enumerate(auspic_rows):
        yb = 290 + i * 130
        val = tf(p, key)
        filters.append(dt(f"{label}:",  cx, str(yb),    32, SAFFRON, s=35, e=55))
        filters.append(dt(val,          cx, str(yb+44), 32, AUSPIC,  s=35, e=55))

    # ── CARD 4: Sun / Moon + Closing (55–end) ───────────────────
    filters += [
        dt(f"🌅 {city}",                     cx, 130, 50, GOLD,    s=55, e=duration),
        dt(f"Sunrise:  {tf(p,'sunrise')}",   cx, 220, 34, WHITE,   s=55, e=duration),
        dt(f"Sunset:   {tf(p,'sunset')}",    cx, 280, 34, WHITE,   s=55, e=duration),
        dt(f"Moonrise: {tf(p,'moonrise')}",  cx, 340, 32, CREAM,   s=55, e=duration),
        dt(f"Moonset:  {tf(p,'moonset')}",   cx, 395, 32, CREAM,   s=55, e=duration),
        dt("🙏  Jay Srimannarayana!",        cx, 530, 52, GOLD,    s=55, e=duration),
        dt("Like · Share · Subscribe",       cx, 620, 30, SAFFRON, s=55, e=duration),
        dt("Daily videos for all 5 US cities!", cx, 670, 26, WHITE, s=55, e=duration),
    ]

    # ── Watermark (always) ───────────────────────────────────────
    filters += [
        dt(f"@DailyPanchangam • {city}", cx, str(H - 110), 28, SAFFRON),
        dt("Subscribe for all 5 US cities",    cx, str(H -  65), 22, WHITE),
    ]
    return filters


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    dur = get_audio_duration(audio_path) if audio_path and os.path.exists(audio_path) else DUR

    flt = build_filters(panchang, dur)
    fstr = f"[0:v]{','.join(flt)}[vout]"

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={BG}:s={W}x{H}:r={FPS}:d={dur}",
    ]
    if audio_path and os.path.exists(audio_path):
        cmd += ["-i", audio_path]
    cmd += ["-filter_complex", fstr, "-map", "[vout]"]
    if audio_path and os.path.exists(audio_path):
        cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-t", str(dur), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", output_path]

    print(f"  🎬 {panchang.get('city','?')} video...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ❌ FFmpeg:\n{r.stderr[-1500:]}")
        raise RuntimeError("FFmpeg failed")
    print(f"  ✅ {output_path}")
    return output_path


def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    city    = esc(panchang.get("city", "USA"))
    weekday = esc(panchang.get("weekday", "Today"))
    tithi   = esc(panchang.get("tithi",  "")[:28])
    naks    = esc(panchang.get("nakshatra", "")[:28])
    rahu    = esc(panchang.get("rahukaal",  "N/A"))

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={BG}:s=1280x720:r=1:d=1",
        "-vf", ",".join([
            "drawtext=text='🕉 Daily Panchangam':x=(w-text_w)/2:y=55:fontsize=68:fontcolor=0xFFD700:box=1:boxcolor=0x00000088:boxborderw=12",
            f"drawtext=text='📍 {city}':x=(w-text_w)/2:y=165:fontsize=56:fontcolor=0xFF6B00:box=1:boxcolor=0x00000088:boxborderw=10",
            f"drawtext=text='{weekday}':x=(w-text_w)/2:y=260:fontsize=44:fontcolor=white",
            f"drawtext=text='Tithi\\: {tithi}':x=(w-text_w)/2:y=350:fontsize=38:fontcolor=0xFFE4B5",
            f"drawtext=text='Nakshatra\\: {naks}':x=(w-text_w)/2:y=420:fontsize=38:fontcolor=0xFFE4B5",
            f"drawtext=text='Rahu Kalam\\: {rahu}':x=(w-text_w)/2:y=510:fontsize=34:fontcolor=0xFF5555",
            "drawtext=text='Exact Local Timings':x=(w-text_w)/2:y=600:fontsize=32:fontcolor=0xFFD700",
        ]),
        "-frames:v", "1", output_path,
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"  ✅ Thumb: {output_path}")
    return output_path


def get_audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except:
        return DUR
