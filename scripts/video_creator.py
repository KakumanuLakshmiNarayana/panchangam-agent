"""
Video Creator — Generates a 60-second Panchang short video using FFmpeg
"""

import subprocess
import os
import textwrap
from pathlib import Path
from typing import Optional

VIDEO_WIDTH   = 1080
VIDEO_HEIGHT  = 1920
VIDEO_FPS     = 30
VIDEO_DURATION = 62

COLORS = {
    "saffron":    "0xFF6B00",
    "gold":       "0xFFD700",
    "avoid":      "0xFF4444",
    "auspicious": "0x44FF88",
    "white":      "0xFFF8F0",
}


def esc(text: str) -> str:
    """Escape text for FFmpeg drawtext."""
    return (str(text)
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("%", "\\%")
            .replace("[", "\\[")
            .replace("]", "\\]"))


def drawtext(text, x, y, size, color="white", start=0, end=None, box=True):
    args = [
        f"text='{esc(text)}'",
        f"x={x}", f"y={y}",
        f"fontsize={size}",
        f"fontcolor={color}",
    ]
    if box:
        args.append("box=1:boxcolor=0x00000088:boxborderw=8")
    if end:
        args.append(f"enable='between(t,{start},{end})'")
    return "drawtext=" + ":".join(args)


def get_et(panchang, field):
    val = panchang.get(field, {})
    if isinstance(val, dict):
        return val.get("us", {}).get("Eastern", "N/A")
    return "N/A"


def build_filters(panchang, duration):
    p = panchang
    filters = []
    H = VIDEO_HEIGHT

    # Card 1: Title (0–15s)
    for text, y, size, color in [
        ("🕉  Daily Panchangam",          H//2-300, 68, COLORS["gold"]),
        (p.get("date","")[:28],           H//2-190, 38, "white"),
        (f"{p.get('masa','')} • {p.get('paksha','')}", H//2-120, 32, COLORS["saffron"]),
        (f"Tithi: {p.get('tithi','')}",   H//2- 40, 36, "white"),
        (f"Nakshatra: {p.get('nakshatra','')}", H//2+30, 36, "white"),
        (f"Yoga: {p.get('yoga','')}",     H//2+100, 36, "white"),
        (f"Vara: {p.get('vara','')}",     H//2+170, 36, "white"),
    ]:
        filters.append(drawtext(text, "(w-text_w)/2", str(y), size, color, 0, 15))

    # Card 2: Avoid (15–35s)
    filters.append(drawtext("⛔  Times to AVOID", "(w-text_w)/2", "250", 56, COLORS["avoid"], 15, 35))
    for i, (label, key) in enumerate([
        ("Rahukaal",    "rahukaal"),
        ("Durmuhurtam", "durmuhurtam"),
        ("Gulika Kalam","gulika"),
        ("Yamagandam",  "yamagandam"),
    ]):
        y_base = 420 + i * 150
        val = get_et(p, key)
        filters.append(drawtext(label + " (ET):", "(w-text_w)/2", str(y_base),    34, COLORS["saffron"], 15, 35))
        filters.append(drawtext(val,              "(w-text_w)/2", str(y_base+48), 36, COLORS["avoid"],   15, 35))

    # Card 3: Auspicious (35–52s)
    filters.append(drawtext("✅  Auspicious Times", "(w-text_w)/2", "250", 56, COLORS["auspicious"], 35, 52))
    for i, (label, key) in enumerate([
        ("Abhijit Muhurta", "abhijit"),
        ("Amrit Kalam",     "amrit_kalam"),
        ("Shubh Muhurat",   "shubh_muhurat"),
    ]):
        y_base = 420 + i * 160
        val = get_et(p, key)
        filters.append(drawtext(label + " (ET):",  "(w-text_w)/2", str(y_base),    34, COLORS["saffron"],    35, 52))
        filters.append(drawtext(val,               "(w-text_w)/2", str(y_base+48), 36, COLORS["auspicious"], 35, 52))

    # Card 4: Closing (52–end)
    for text, y, size, color in [
        ("🌅  Sun & Moon",              250, 56, COLORS["gold"]),
        ("Sunrise (ET): " + get_et(p,"sunrise"), 380, 34, "white"),
        ("Sunset  (ET): " + get_et(p,"sunset"),  450, 34, "white"),
        ("🙏  Jay Srimannarayana!",     620, 52, COLORS["gold"]),
        ("Like & Subscribe",            720, 30, COLORS["saffron"]),
        ("for Daily Panchang Updates",  770, 30, COLORS["saffron"]),
    ]:
        filters.append(drawtext(text, "(w-text_w)/2", str(y), size, color, 52, duration))

    # Watermark always
    filters.append(drawtext("@DailyPanchangam", "(w-text_w)/2", str(H-110), 32, COLORS["saffron"]))
    filters.append(drawtext("All 6 US Timezones • Link in Bio", "(w-text_w)/2", str(H-65), 24, "white"))

    return filters


def create_panchang_video(panchang, script, audio_path, output_path="output/panchang_video.mp4"):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    duration = VIDEO_DURATION
    if audio_path and os.path.exists(audio_path):
        duration = get_audio_duration(audio_path)

    filters = build_filters(panchang, duration)
    filter_str = f"[0:v]{','.join(filters)}[vout]"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x1a0a00:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r={VIDEO_FPS}:d={duration}",
    ]

    if audio_path and os.path.exists(audio_path):
        cmd += ["-i", audio_path]

    cmd += [
        "-filter_complex", filter_str,
        "-map", "[vout]",
    ]

    if audio_path and os.path.exists(audio_path):
        cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]

    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-t", str(duration), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", output_path
    ]

    print(f"🎬 Creating video: {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg error:\n{result.stderr[-2000:]}")
        raise RuntimeError("FFmpeg failed")
    print(f"✅ Video created: {output_path}")
    return output_path


def create_thumbnail(panchang, output_path="output/thumbnail.jpg"):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    date_str  = panchang.get("date", "Today")[:22].replace("'", "")
    tithi     = panchang.get("tithi", "").replace("'", "")
    nakshatra = panchang.get("nakshatra", "").replace("'", "")

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=0x1a0a00:s=1280x720:r=1:d=1",
        "-vf", ",".join([
            "drawtext=text='🕉 Daily Panchangam':x=(w-text_w)/2:y=80:fontsize=72:fontcolor=0xFFD700:box=1:boxcolor=0x00000088:boxborderw=12",
            f"drawtext=text='{esc(date_str)}':x=(w-text_w)/2:y=220:fontsize=48:fontcolor=white:box=1:boxcolor=0x00000088:boxborderw=10",
            f"drawtext=text='Tithi\\: {esc(tithi)}':x=(w-text_w)/2:y=340:fontsize=42:fontcolor=0xFF6B00",
            f"drawtext=text='Nakshatra\\: {esc(nakshatra)}':x=(w-text_w)/2:y=420:fontsize=42:fontcolor=0xFF6B00",
            "drawtext=text='All 6 US Time Zones':x=(w-text_w)/2:y=560:fontsize=36:fontcolor=0xFFD700",
        ]),
        "-frames:v", "1", output_path,
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✅ Thumbnail: {output_path}")
    return output_path


def get_audio_duration(audio_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return VIDEO_DURATION
