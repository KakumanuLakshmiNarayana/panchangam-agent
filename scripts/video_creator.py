"""
video_creator.py — Creates city-specific Panchang video with exact local timings.
"""
import subprocess, os
from pathlib import Path

VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS = 1080, 1920, 30
VIDEO_DURATION = 62

GOLD    = "0xFFD700"
SAFFRON = "0xFF6B00"
AVOID   = "0xFF4444"
AUSPIC  = "0x44FF88"
WHITE   = "0xFFF8F0"


def esc(t):
    return (str(t).replace("'","\\'").replace(":","\\:")
            .replace("%","\\%").replace("[","\\[").replace("]","\\]"))


def dt(text, x, y, size, color=WHITE, start=0, end=None, box=True):
    a = [f"text='{esc(text)}'", f"x={x}", f"y={y}",
         f"fontsize={size}", f"fontcolor={color}"]
    if box:
        a.append("box=1:boxcolor=0x00000099:boxborderw=10")
    if end:
        a.append(f"enable='between(t,{start},{end})'")
    return "drawtext=" + ":".join(a)


def tf(panchang, field):
    return panchang.get(field, "N/A")


def build_filters(panchang, duration):
    H   = VIDEO_HEIGHT
    cx  = "(w-text_w)/2"
    city     = panchang.get("city", "USA")
    tz_label = panchang.get("tz_label", "ET")
    weekday  = panchang.get("weekday", "")
    filters  = []

    # ── Card 1: Header (0–14s) ──────────────────────────────────
    filters += [
        dt("🕉  Daily Panchangam",                cx, "180",      70, GOLD,    0, 14),
        dt(f"📍 {city}",                          cx, "290",      52, SAFFRON, 0, 14),
        dt(weekday,                               cx, "380",      42, WHITE,   0, 14),
        dt(f"Tithi: {tf(panchang,'tithi')[:35]}", cx, "470",      38, WHITE,   0, 14),
        dt(f"Nakshatra: {tf(panchang,'nakshatra')[:30]}", cx, "540", 36, WHITE, 0, 14),
        dt(f"Yoga: {tf(panchang,'yoga')[:30]}",   cx, "610",      34, SAFFRON, 0, 14),
        dt(f"Masa: {tf(panchang,'masa')[:25]} | {tf(panchang,'paksha')[:20]}", cx, "680", 30, SAFFRON, 0, 14),
    ]

    # ── Card 2: Avoid (14–34s) ──────────────────────────────────
    filters += [
        dt(f"⛔  Avoid These Times",              cx, "160", 58, AVOID,   14, 34),
        dt(f"📍 {city} ({tz_label})",             cx, "250", 36, SAFFRON, 14, 34),
    ]
    avoid_items = [
        ("Rahukaal",     "rahukaal"),
        ("Durmuhurtam",  "durmuhurtam"),
        ("Gulika Kalam", "gulika"),
        ("Yamagandam",   "yamagandam"),
    ]
    for i, (label, key) in enumerate(avoid_items):
        yb = 360 + i * 155
        filters.append(dt(f"{label}:", cx, str(yb),    34, SAFFRON, 14, 34))
        filters.append(dt(tf(panchang, key), cx, str(yb+48), 34, AVOID, 14, 34))

    # ── Card 3: Auspicious (34–52s) ─────────────────────────────
    filters += [
        dt(f"✅  Auspicious Times",               cx, "160", 58, AUSPIC,  34, 52),
        dt(f"📍 {city} ({tz_label})",             cx, "250", 36, SAFFRON, 34, 52),
    ]
    auspic_items = [
        ("Abhijit Muhurta", "abhijit"),
        ("Amrit Kalam",     "amrit_kalam"),
        ("Shubh Muhurat",   "shubh_muhurat"),
    ]
    for i, (label, key) in enumerate(auspic_items):
        yb = 360 + i * 165
        filters.append(dt(f"{label}:", cx, str(yb),    34, SAFFRON, 34, 52))
        filters.append(dt(tf(panchang, key), cx, str(yb+48), 36, AUSPIC, 34, 52))

    # ── Card 4: Sun + Closing (52–end) ──────────────────────────
    filters += [
        dt(f"🌅 {city} — Sun & Moon",            cx, "200", 48, GOLD,    52, duration),
        dt(f"Sunrise: {tf(panchang,'sunrise')}",  cx, "310", 36, WHITE,   52, duration),
        dt(f"Sunset:  {tf(panchang,'sunset')}",   cx, "380", 36, WHITE,   52, duration),
        dt(f"Moonrise: {tf(panchang,'moonrise')}", cx,"450", 34, SAFFRON, 52, duration),
        dt("🙏  Jay Srimannarayana!",             cx, "600", 52, GOLD,    52, duration),
        dt("Like & Subscribe for Daily Updates",  cx, "690", 28, SAFFRON, 52, duration),
        dt("One video per city, every day!",      cx, "740", 26, WHITE,   52, duration),
    ]

    # ── Watermark always ────────────────────────────────────────
    filters += [
        dt(f"@DailyPanchangam • {city}",         cx, str(H-110), 30, SAFFRON),
        dt("Subscribe for all 5 US cities",       cx, str(H- 65), 24, WHITE),
    ]
    return filters


def create_panchang_video(panchang, script, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    duration = VIDEO_DURATION
    if audio_path and os.path.exists(audio_path):
        duration = get_audio_duration(audio_path)

    filters    = build_filters(panchang, duration)
    filter_str = f"[0:v]{','.join(filters)}[vout]"

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=0x1a0a00:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r={VIDEO_FPS}:d={duration}",
    ]
    if audio_path and os.path.exists(audio_path):
        cmd += ["-i", audio_path]

    cmd += ["-filter_complex", filter_str, "-map", "[vout]"]
    if audio_path and os.path.exists(audio_path):
        cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]

    cmd += ["-c:v","libx264","-preset","medium","-crf","23",
            "-t", str(duration), "-pix_fmt","yuv420p",
            "-movflags","+faststart", output_path]

    print(f"🎬 Creating video for {panchang.get('city','?')}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg error:\n{result.stderr[-1500:]}")
        raise RuntimeError("FFmpeg failed")
    print(f"✅ Video: {output_path}")
    return output_path


def create_thumbnail(panchang, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    city    = esc(panchang.get("city", "USA"))
    weekday = esc(panchang.get("weekday", "Today"))
    tithi   = esc(panchang.get("tithi", "")[:30])
    naks    = esc(panchang.get("nakshatra", "")[:30])

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=0x1a0a00:s=1280x720:r=1:d=1",
        "-vf", ",".join([
            "drawtext=text='🕉 Daily Panchangam':x=(w-text_w)/2:y=60:fontsize=68:fontcolor=0xFFD700:box=1:boxcolor=0x00000088:boxborderw=12",
            f"drawtext=text='📍 {city}':x=(w-text_w)/2:y=180:fontsize=54:fontcolor=0xFF6B00:box=1:boxcolor=0x00000088:boxborderw=10",
            f"drawtext=text='{weekday}':x=(w-text_w)/2:y=280:fontsize=44:fontcolor=white",
            f"drawtext=text='Tithi\\: {tithi}':x=(w-text_w)/2:y=370:fontsize=38:fontcolor=0xFF6B00",
            f"drawtext=text='Nakshatra\\: {naks}':x=(w-text_w)/2:y=440:fontsize=38:fontcolor=0xFF6B00",
            "drawtext=text='Exact Local Timings':x=(w-text_w)/2:y=560:fontsize=34:fontcolor=0xFFD700",
        ]),
        "-frames:v", "1", output_path,
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✅ Thumbnail: {output_path}")
    return output_path


def get_audio_duration(path):
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return VIDEO_DURATION
