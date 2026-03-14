"""
voice_generator.py v5
Fix #8/#12: City names properly replaced before TTS
Fix: pass panchang city through pipeline correctly
"""
import os, re, tempfile, subprocess, shutil
from pathlib import Path

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

CITY_TELUGU = {
    "Los Angeles, CA": "లాస్ ఏంజెలెస్",
    "Chicago, IL":     "చికాగో",
    "Dallas, TX":      "డాలస్",
    "Detroit, MI":     "డెట్రాయిట్",
    "New York, NY":    "న్యూయార్క్",
    # Also handle state abbreviations alone
    "Los Angeles":     "లాస్ ఏంజెలెస్",
    "Chicago":         "చికాగో",
    "Dallas":          "డాలస్",
    "Detroit":         "డెట్రాయిట్",
    "New York":        "న్యూయార్క్",
}


def clean_for_tts(text):
    """
    Fix #8/#12: Replace all city names FIRST (longest match first),
    then strip remaining digits and Latin.
    """
    # Replace city names — longest first to avoid partial replacements
    for eng in sorted(CITY_TELUGU.keys(), key=len, reverse=True):
        if eng in text:
            text = text.replace(eng, CITY_TELUGU[eng])

    # Remove digits (times not spoken — shown on screen)
    text = re.sub(r'\d+', '', text)
    # Remove remaining Latin characters
    text = re.sub(r'[a-zA-Z]+', '', text)
    # Clean leftover punctuation
    text = re.sub(r'[\:\-–,\.]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def generate_voice(script, output_path, city_key=None):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if isinstance(script, dict):
        text = script.get("full_narration", "") or script.get("narration", "")
    else:
        text = str(script)

    if not text:
        print("  [VOICE] No narration text"); return None

    cleaned = clean_for_tts(text)
    print(f"  [VOICE] {len(cleaned.split())} words after clean")
    print(f"  [VOICE] Preview: {cleaned[:80]}...")

    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available"); return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw_mp3   = os.path.join(tmp, "raw.mp3")
            final_mp3 = os.path.join(tmp, "final.mp3")

            tts = gTTS(text=cleaned, lang='te', slow=False)
            tts.save(raw_mp3)

            # Lower pitch for male voice, ensure 44100Hz/128kbps quality
            cmd = [
                "ffmpeg", "-y", "-i", raw_mp3,
                "-af", "asetrate=44100*0.88,aresample=44100,volume=1.3",
                "-ar", "44100", "-ab", "128k",
                "-codec:a", "libmp3lame",
                final_mp3
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            src = final_mp3 if r.returncode == 0 else raw_mp3
            shutil.copy(src, output_path)
            print(f"  [VOICE] OK {os.path.getsize(output_path)} bytes")
        return output_path
    except Exception as e:
        print(f"  [VOICE] Error: {e}"); return None


generate_voiceover = generate_voice
generate_audio     = generate_voice
