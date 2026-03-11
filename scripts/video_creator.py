"""
video_creator.py — FFmpeg video generator. Works with scraper.run() format.
"""
import subprocess, os, textwrap
from pathlib import Path
from typing import Optional

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
        a.append("box=1:boxcolor=0x00000088:boxborderw=8")
    if end:
        a.append(f"enable='between(t,{start},{end})'")
    return "drawtext=" + ":".join(a)


def get_et(panchang, field):
    us = panchang.get("us_timings", {})
    s_key, e_key = f"{field}_Start", f"{field}_End"
    if s_key in us and e_key in us:
        s = us[s_key].get("Eastern", "N/A")
        e = us[e_key].get("Eastern", "N/A")
        return f"{s} - {e}"
    if field in us:
        return us[field].get("Eastern", "N/A")
    return "N/A"


def build_filters(panchang, duration):
    raw = panchang.get("raw", {})
    H   = VIDEO_HEIGHT
    cx  = "(w-text_w)/2"
    filters = []

    # Card 1: Panchang details (0-15s)
    filters += [
        dt("🕉  Daily Panchangam",           cx, str(H//2-320), 66, GOLD,    0, 15),
        dt(f"{panchang.get('weekday','')} Panchangam", cx, str(H//2-220), 38, WHITE,   0, 15),
        dt(f"Tithi: {raw.get('tithi','N/A')}",         cx, str(H//2-140), 36, WHITE,   0, 15),
        dt(f"Nakshatra: {raw.get('nakshatra','N/A')}",  cx, str(H//2- 70), 36, WHITE,   0, 15),
        dt(f"Yoga: {raw.get('yoga','N/A')}",            cx, str(H//2),     36, WHITE,   0, 15),
        dt(f"Karana: {raw.get('karana','N/A')}",        cx, str(H//2+ 70), 36, SAFFRON, 0, 15),
    ]

    # Card 2: Avoid (15-35s)
    filters.append(dt("⛔  Times to AVOID",              cx, "240", 58, AVOID,   15, 35))
    for i, (label, field) in enumerate([
        ("Rahukaal",    "Rahukalam"),
        ("Durmuhurtam", "Durmuhurtam"),
        ("Gulika Kalam","Gulikai"),
        ("Yamagandam",  "Yamagandam"),
    ]):
        yb = 420 + i * 155
        filters.append(dt(f"{label} (ET):", cx, str(yb),    34, SAFFRON, 15, 35))
        filters.append(dt(get_et(panchang, field), cx, str(yb+48), 34, AVOID, 15, 35))

    # Card 3: Auspicious (35-52s)
    filters.append(dt("✅  Auspicious Times",            cx, "240", 58, AUSPIC, 35, 52))
    for i, (label, field) in enumerate([
        ("Abhijit Muhurta", "Abhijit"),
        ("Amrit Kalam",     "AmritKalam"),
    ]):
        yb = 420 + i * 180
        filters.append(dt(f"{label} (ET):", cx, str(yb),    34, SAFFRON, 35, 52))
        filters.append(dt(get_et(panchang, field), cx, str(yb+48), 34, AUSPIC, 35, 52))

    # Card 4: Sun/Moon + closing (52-end)
    filters += [
        dt("🌅  Sun & Moon",                            cx, "240",      56, GOLD,    52, duration),
        dt("Sunrise (ET): " + get_et(panchang,"Sunrise"), cx, "370",    34, WHITE,   52, duration),
        dt("Sunset  (ET): " + get_et(panchang,"Sunset"),  cx, "430",    34, WHITE,   52, duration),
        dt("🙏  Jay Srimannarayana!",                   cx, "620",      50, GOLD,    52, duration),
        dt("Like & Subscribe for Daily Updates",        cx, "700",      28, SAFFRON, 52, duration),
    ]

    # Watermark always
    filters += [
        dt("@DailyPanchangam",                cx, str(H-110), 32, SAFFRON),
        dt("All 6 US Timezones • Link in Bio", cx, str(H- 65), 24, WHITE),
    ]
    return filters


def create_panchang_video(panchang, script, audio_path, output_path="output/panchang_video.mp4"):
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

    print(f"🎬 Creating video...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg:\n{result.stderr[-2000:]}")
        raise RuntimeError("FFmpeg failed")
    print(f"✅ Video: {output_path}")
    return output_path


def create_thumbnail(panchang, output_path="output/thumbnail.jpg"):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    raw  = panchang.get("raw", {})
    day  = esc(panchang.get("weekday", "Today"))
    tithi = esc(raw.get("tithi", ""))
    naks  = esc(raw.get("nakshatra", ""))

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=0x1a0a00:s=1280x720:r=1:d=1",
        "-vf", ",".join([
            "drawtext=text='🕉 Daily Panchangam':x=(w-text_w)/2:y=80:fontsize=72:fontcolor=0xFFD700:box=1:boxcolor=0x00000088:boxborderw=12",
            f"drawtext=text='{day} Panchangam':x=(w-text_w)/2:y=220:fontsize=48:fontcolor=white",
            f"drawtext=text='Tithi\\: {tithi}':x=(w-text_w)/2:y=340:fontsize=42:fontcolor=0xFF6B00",
            f"drawtext=text='Nakshatra\\: {naks}':x=(w-text_w)/2:y=420:fontsize=42:fontcolor=0xFF6B00",
            "drawtext=text='All 6 US Time Zones':x=(w-text_w)/2:y=560:fontsize=36:fontcolor=0xFFD700",
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
