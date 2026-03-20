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

    # staticFile() in Remotion 4 generates URLs like /public/<file> relative to
    # --public-dir, so both pandit.png and the audio file must live in a
    # public/ sub-directory inside the public-dir root.
    output_dir = Path(output_path).parent.resolve()
    public_subdir = output_dir / "public"
    public_subdir.mkdir(parents=True, exist_ok=True)

    # Copy pandit.png from remotion/public/ into public_subdir
    pandit_src = REMOTION_DIR / "public" / "pandit.png"
    if pandit_src.exists():
        shutil.copy2(str(pandit_src), str(public_subdir / "pandit.png"))

    # Copy the audio file into public_subdir so staticFile(audioFile) resolves
    if audio_path and Path(audio_path).exists():
        audio_dest = public_subdir / Path(audio_path).name
        if not audio_dest.exists() or audio_dest.resolve() != Path(audio_path).resolve():
            shutil.copy2(audio_path, str(audio_dest))

    cmd = [
        "npx", "--yes", "remotion", "render",
        "src/index.ts", "PanchangamVideo",
        str(Path(output_path).resolve()),
        "--codec=h264",
        "--concurrency=2",
        f"--props={json.dumps(props)}",
        f"--public-dir={output_dir}",
    ] + _browser_args()

    print(f"  🎬 Remotion render → {Path(output_path).name}")
    print(f"     props: city={props['city']!r}, date={props['date']!r}, audio={props['audioFile']!r}")
    subprocess.run(cmd, cwd=str(REMOTION_DIR), check=True)
    print(f"  ✅ Video rendered: {output_path}")
