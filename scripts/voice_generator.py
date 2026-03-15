"""
voice_generator.py
- Primary: ElevenLabs TTS (voice tK3s6QVNCS9FKJl6hetZ, eleven_multilingual_v2)
- Fallback: gTTS Telugu with deep-male FFmpeg processing
- City names replaced with Telugu before TTS
- All digits and Latin stripped — pure Telugu audio
"""
import os, re, tempfile, subprocess, shutil
from pathlib import Path

try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    try:
        from elevenlabs import ElevenLabs
        ELEVENLABS_AVAILABLE = True
    except ImportError:
        ELEVENLABS_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

ELEVENLABS_VOICE_ID = "tK3s6QVNCS9FKJl6hetZ"
ELEVENLABS_MODEL    = "eleven_multilingual_v2"

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


def _generate_elevenlabs(text, output_path):
    """Generate audio using ElevenLabs API. Returns True on success."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print("  [VOICE] ELEVENLABS_API_KEY not set — skipping ElevenLabs")
        return False

    try:
        client = ElevenLabs(api_key=api_key)

        audio_generator = client.text_to_speech.convert(
            voice_id=ELEVENLABS_VOICE_ID,
            text=text,
            model_id=ELEVENLABS_MODEL,
            output_format="mp3_44100_128",
        )

        # audio_generator may be a generator or bytes — handle both
        with open(output_path, "wb") as f:
            if hasattr(audio_generator, "__iter__") and not isinstance(audio_generator, (bytes, bytearray)):
                for chunk in audio_generator:
                    if chunk:
                        f.write(chunk)
            else:
                f.write(audio_generator)

        size = os.path.getsize(output_path)
        if size < 1000:
            print(f"  [VOICE] ElevenLabs returned suspiciously small file ({size} bytes)")
            return False

        dur = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", output_path],
            capture_output=True, text=True)
        print(f"  [VOICE] ElevenLabs OK — duration={dur.stdout.strip()}s  size={size} bytes")
        return True

    except Exception as e:
        print(f"  [VOICE] ElevenLabs error: {e}")
        return False


def _generate_gtts_fallback(text, output_path):
    """Generate audio using gTTS with deep-male FFmpeg processing."""
    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available"); return False

    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw_mp3   = os.path.join(tmp, "raw.mp3")
            final_mp3 = os.path.join(tmp, "final.mp3")

            tts = gTTS(text=text, lang='te', slow=False)
            tts.save(raw_mp3)

            raw_dur = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", raw_mp3],
                capture_output=True, text=True)
            print(f"  [VOICE] gTTS raw duration: {raw_dur.stdout.strip()}s")

            # Deep male voice: pitch down + bass boost + compression
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
                "-ar", "44100", "-ab", "128k",
                "-codec:a", "libmp3lame",
                final_mp3
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)

            src = final_mp3 if r.returncode == 0 else raw_mp3
            if r.returncode != 0:
                print(f"  [VOICE] FFmpeg failed, using raw: {r.stderr[-200:]}")
            shutil.copy(src, output_path)

            final_dur = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", output_path],
                capture_output=True, text=True)
            print(f"  [VOICE] gTTS final duration: {final_dur.stdout.strip()}s  size={os.path.getsize(output_path)} bytes")
        return True

    except Exception as e:
        print(f"  [VOICE] gTTS error: {e}"); return False


def generate_voice(script, output_path, city_key=None):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if isinstance(script, dict):
        text = script.get("full_narration", "") or script.get("narration", "")
    else:
        text = str(script)

    if not text:
        print("  [VOICE] No narration text"); return None

    cleaned = clean_for_tts(text)
    word_count = len(cleaned.split())
    print(f"  [VOICE] {word_count} words after clean")
    print(f"  [VOICE] Preview: {cleaned[:80]}...")

    # Try ElevenLabs first (voice tK3s6QVNCS9FKJl6hetZ)
    if ELEVENLABS_AVAILABLE:
        print(f"  [VOICE] Trying ElevenLabs voice {ELEVENLABS_VOICE_ID}...")
        if _generate_elevenlabs(cleaned, output_path):
            return output_path
        print("  [VOICE] Falling back to gTTS...")
    else:
        print("  [VOICE] ElevenLabs SDK not installed — using gTTS")

    # Fallback: gTTS
    if _generate_gtts_fallback(cleaned, output_path):
        return output_path

    print("  [VOICE] All TTS methods failed"); return None


generate_voiceover = generate_voice
generate_audio     = generate_voice
