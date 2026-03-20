"""
remotion_renderer.py — Calls Remotion CLI to render PanchangamVideo with live panchang data.
"""
import json
import os
import subprocess
from datetime import date
from pathlib import Path

REMOTION_DIR = Path(__file__).parent.parent / "remotion"
FPS = 24


def _get_audio_duration(audio_path: str) -> float:
    """Return duration in seconds via ffprobe, falling back to 20 s."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            capture_output=True, text=True, check=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return 20.0


def _parse_field(raw: str):
    """Split 'Name upto HH:MM TZ' → (name, 'upto HH:MM TZ').  Returns (raw, '') if no separator found."""
    for sep in (" upto ", " → ", " -> "):
        if sep in raw:
            name, rest = raw.split(sep, 1)
            return name.strip(), f"upto {rest.strip()}"
    return raw.strip(), ""


def _fmt_date(iso_date: str) -> str:
    """'2026-03-19' → 'March 19, 2026'"""
    try:
        d = date.fromisoformat(iso_date)
        return d.strftime("%B %-d, %Y")
    except Exception:
        return iso_date


def build_props(panchang: dict, audio_path: str) -> dict:
    tithi_name, tithi_time = _parse_field(panchang.get("tithi", "N/A"))
    nak_name, nak_time = _parse_field(panchang.get("nakshatra", "N/A"))

    audio_exists = audio_path and Path(audio_path).exists()
    audio_dur = _get_audio_duration(audio_path) if audio_exists else 20.0
    audio_file = Path(audio_path).name if audio_exists else ""

    return {
        "city":            panchang.get("city", ""),
        "date":            _fmt_date(panchang.get("date", "")),
        "weekday":         panchang.get("weekday", ""),
        "tz":              panchang.get("tz_label", "ET"),
        "tithi":           tithi_name,
        "tithiTime":       tithi_time,
        "nakshatra":       nak_name,
        "nakshatraTime":   nak_time,
        "paksha":          panchang.get("paksha", ""),
        "rahukaal":        panchang.get("rahukaal", "N/A"),
        "durmuhurtam":     panchang.get("durmuhurtam", "N/A"),
        "brahma":          panchang.get("brahma_muhurta", "N/A"),
        "abhijit":         panchang.get("abhijit", "N/A"),
        "sunrise":         panchang.get("sunrise", "N/A"),
        "sunset":          panchang.get("sunset", "N/A"),
        "audioDurationSec": audio_dur,
        "audioFile":       audio_file,
    }


def _browser_args() -> list:
    """Return --browser-executable flag if a known headless Chrome is available locally."""
    candidates = [
        os.environ.get("REMOTION_BROWSER_EXECUTABLE", ""),
        os.path.expanduser(
            "~/.cache/ms-playwright/chromium_headless_shell-1194/chrome-linux/headless_shell"
        ),
        os.path.expanduser(
            "~/.cache/ms-playwright/chromium_headless_shell-1161/chrome-linux/headless_shell"
        ),
    ]
    for p in candidates:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return [f"--browser-executable={p}"]
    return []


def render_with_remotion(panchang: dict, script: dict, audio_path: str, output_path: str):
    """Render a Panchangam video using Remotion CLI."""
    import shutil

    props = build_props(panchang, audio_path)

    # Use Remotion's default public dir (remotion/public/).
    # staticFile('foo') → served at /public/foo from remotion/public/foo.
    # pandit_character.png is already committed there.
    # Copy the audio file in, render, then remove the audio copy.
    remotion_public = REMOTION_DIR / "public"
    remotion_public.mkdir(parents=True, exist_ok=True)

    # Ensure pandit_character.png is in remotion/public/ (copy from scripts/ if missing)
    pandit_dst = remotion_public / "pandit_character.png"
    if not pandit_dst.exists():
        pandit_src = Path(__file__).parent / "pandit_character.png"
        if pandit_src.exists():
            shutil.copy2(str(pandit_src), str(pandit_dst))
        else:
            print("  ⚠️  pandit_character.png not found — image will be missing in video")

    # Copy audio into remotion/public/ so staticFile(audioFile) resolves
    audio_copy = None
    if audio_path and Path(audio_path).exists():
        audio_copy = remotion_public / Path(audio_path).name
        shutil.copy2(audio_path, str(audio_copy))

    cmd = [
        "npx", "--yes", "remotion", "render",
        "src/index.ts", "PanchangamVideo",
        str(Path(output_path).resolve()),
        "--codec=h264",
        "--concurrency=2",
        f"--props={json.dumps(props)}",
    ] + _browser_args()

    print(f"  🎬 Remotion render → {Path(output_path).name}")
    print(f"     props: city={props['city']!r}, date={props['date']!r}, audio={props['audioFile']!r}")
    try:
        subprocess.run(cmd, cwd=str(REMOTION_DIR), check=True)
    finally:
        # Clean up the audio copy from remotion/public/
        if audio_copy and audio_copy.exists():
            audio_copy.unlink()
    print(f"  ✅ Video rendered: {output_path}")
