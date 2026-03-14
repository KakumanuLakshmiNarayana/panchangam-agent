"""
voice_generator.py v4
Fixes:
11. Male-sounding voice — pitch lowered via ffmpeg asetrate
12. Voice/video sync — word count based, audio is source of truth
13. Better audio quality — 44100Hz, 128kbps
15. City names stripped from narration before TTS
"""
import os, re, tempfile, subprocess, shutil
from pathlib import Path

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# City name to Telugu translation for TTS
CITY_TELUGU = {
    "Los Angeles, CA": "లాస్ ఏంజెలెస్",
    "Chicago, IL":     "చికాగో",
    "Dallas, TX":      "డాలస్",
    "Detroit, MI":     "డెట్రాయిట్",
    "New York, NY":    "న్యూయార్క్",
}


def clean_for_tts(text, city=None):
    """
    Fix #15: Replace city name with Telugu version before cleaning.
    Fix #13: Remove digits and Latin so gTTS reads pure Telugu.
    """
    # Replace city name with Telugu
    if city and city in CITY_TELUGU:
        text = text.replace(city, CITY_TELUGU[city])

    # Also replace any remaining English city patterns
    for eng, tel in CITY_TELUGU.items():
        text = text.replace(eng, tel)

    # Remove digits (times should not be read)
    text = re.sub(r'\d+', '', text)
    # Remove remaining Latin characters
    text = re.sub(r'[a-zA-Z]+', '', text)
    # Clean punctuation artifacts
    text = re.sub(r'[\:\-–\.]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def generate_voice(script, output_path, city_key=None):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if isinstance(script, dict):
        text = script.get("full_narration", "") or script.get("narration", "")
        city = script.get("city", "")
    else:
        text = str(script)
        city = ""

    if not text:
        print("  [VOICE] No narration text"); return None

    cleaned = clean_for_tts(text, city)
    print(f"  [VOICE] {len(cleaned.split())} words: {cleaned[:60]}...")

    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available"); return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw_mp3    = os.path.join(tmp, "raw.mp3")
            final_mp3  = os.path.join(tmp, "final.mp3")

            # Generate TTS — normal speed, Telugu
            tts = gTTS(text=cleaned, lang='te', slow=False)
            tts.save(raw_mp3)

            # Fix #11: Lower pitch to sound more male
            # asetrate=44100*0.88 lowers pitch ~2 semitones
            # aresample=44100 resamples back to standard rate
            # Fix #13: Ensure 44100Hz 128kbps output
            cmd = [
                "ffmpeg", "-y", "-i", raw_mp3,
                "-af", "asetrate=44100*0.88,aresample=44100,volume=1.3",
                "-ar", "44100",
                "-ab", "128k",
                "-codec:a", "libmp3lame",
                final_mp3
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)

            if r.returncode == 0:
                shutil.copy(final_mp3, output_path)
                print(f"  [VOICE] OK (pitch-lowered) {os.path.getsize(output_path)} bytes")
            else:
                # Fallback to raw if ffmpeg fails
                shutil.copy(raw_mp3, output_path)
                print(f"  [VOICE] OK (raw fallback) {os.path.getsize(output_path)} bytes")

        return output_path

    except Exception as e:
        print(f"  [VOICE] Error: {e}"); return None


generate_voiceover = generate_voice
generate_audio     = generate_voice
