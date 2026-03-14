"""
voice_generator.py — FINAL
- Deep male voice: asetrate=44100*0.82 (-3.5 semitones from gTTS default)
- Confidence/presence: bass boost + light compression
- 44100Hz / 128kbps quality
- City names replaced with Telugu before TTS
- All digits and Latin stripped — pure Telugu audio
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
    "Los Angeles":     "లాస్ ఏంజెలెస్",
    "Chicago":         "చికాగో",
    "Dallas":          "డాలస్",
    "Detroit":         "డెట్రాయిట్",
    "New York":        "న్యూయార్క్",
}


def clean_for_tts(text):
    # Replace city names — longest first to prevent partial matches
    for eng in sorted(CITY_TELUGU.keys(), key=len, reverse=True):
        text = text.replace(eng, CITY_TELUGU[eng])

    # Remove all digits (times shown on screen, not spoken)
    text = re.sub(r'\d+', '', text)
    # Remove remaining Latin characters
    text = re.sub(r'[a-zA-Z]+', '', text)
    # Clean leftover punctuation artifacts
    text = re.sub(r'[\:\-–,\.]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def generate_voice(script, output_path, city_key=None):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if isinstance(script, dict):
        text = script.get("full_narration","") or script.get("narration","")
    else:
        text = str(script)

    if not text:
        print("  [VOICE] No narration text"); return None

    cleaned = clean_for_tts(text)
    word_count = len(cleaned.split())
    print(f"  [VOICE] {word_count} words after clean")
    print(f"  [VOICE] Preview: {cleaned[:80]}...")

    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available — install gtts"); return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw_mp3   = os.path.join(tmp, "raw.mp3")
            final_mp3 = os.path.join(tmp, "final.mp3")

            # Generate Telugu TTS at normal speed
            tts = gTTS(text=cleaned, lang='te', slow=False)
            tts.save(raw_mp3)

            raw_dur = subprocess.run(
                ["ffprobe","-v","error","-show_entries","format=duration",
                 "-of","default=noprint_wrappers=1:nokey=1", raw_mp3],
                capture_output=True, text=True)
            print(f"  [VOICE] Raw duration: {raw_dur.stdout.strip()}s")

            # DEEP MALE VOICE chain:
            # 1. asetrate=44100*0.82  — lower pitch 3.5 semitones (male depth)
            # 2. aresample=44100      — restore sample rate after pitch shift
            # 3. bass=g=6             — boost bass frequencies for warmth/confidence
            # 4. acompressor          — light compression for confident/punchy presence
            # 5. volume=1.4           — final volume boost for clarity
            af = (
                "asetrate=44100*0.82,"
                "aresample=44100,"
                "bass=g=6:f=150:w=0.6,"
                "acompressor=threshold=-20dB:ratio=3:attack=8:release=80:makeup=3dB,"
                "volume=1.4"
            )
            cmd = [
                "ffmpeg", "-y", "-i", raw_mp3,
                "-af", af,
                "-ar", "44100",
                "-ab", "128k",
                "-codec:a", "libmp3lame",
                final_mp3
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)

            if r.returncode == 0:
                shutil.copy(final_mp3, output_path)
                final_dur = subprocess.run(
                    ["ffprobe","-v","error","-show_entries","format=duration",
                     "-of","default=noprint_wrappers=1:nokey=1", output_path],
                    capture_output=True, text=True)
                print(f"  [VOICE] Final duration: {final_dur.stdout.strip()}s  size={os.path.getsize(output_path)} bytes")
            else:
                # ffmpeg filter failed — use raw as fallback
                shutil.copy(raw_mp3, output_path)
                print(f"  [VOICE] Used raw (ffmpeg failed): {r.stderr[-200:]}")

        return output_path

    except Exception as e:
        print(f"  [VOICE] Error: {e}"); return None


generate_voiceover = generate_voice
generate_audio     = generate_voice
