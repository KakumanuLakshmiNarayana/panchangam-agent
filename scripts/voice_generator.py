"""
voice_generator.py
- Primary: ElevenLabs TTS (voice tK3s6QVNCS9FKJl6hetZ, eleven_multilingual_v2)
  - Pause markers converted to SSML <break> tags
  - Voice settings tuned for confident middle-aged male
- Fallback: gTTS Telugu with deep-male FFmpeg processing
  - Pause markers produce actual silence segments
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
    from elevenlabs import VoiceSettings
    VOICE_SETTINGS_AVAILABLE = True
except ImportError:
    VOICE_SETTINGS_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

ELEVENLABS_VOICE_ID = "tK3s6QVNCS9FKJl6hetZ"
ELEVENLABS_MODEL    = "eleven_multilingual_v2"

# Pause marker → silence duration (seconds) for gTTS fallback
PAUSE_DURATIONS = {
    "[SHORT_PAUSE]": "0.3",
    "[PAUSE]":       "0.5",
    "[LONG_PAUSE]":  "0.8",
}

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
    """Clean text for gTTS — pure Telugu + pause markers, strip everything else."""
    # Replace city names — longest first to prevent partial matches
    for eng in sorted(CITY_TELUGU.keys(), key=len, reverse=True):
        text = text.replace(eng, CITY_TELUGU[eng])

    # Protect pause markers from being stripped
    text = text.replace("[SHORT_PAUSE]", "\x00SP\x00")
    text = text.replace("[PAUSE]",       "\x00P\x00")
    text = text.replace("[LONG_PAUSE]",  "\x00LP\x00")

    # Remove digits (times shown on screen, not spoken)
    text = re.sub(r'\d+', '', text)
    # Remove Latin characters (gTTS Telugu only)
    text = re.sub(r'[a-zA-Z]+', '', text)
    # Clean punctuation
    text = re.sub(r'[\:\-–,\.!?;]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Restore pause markers
    text = text.replace("\x00SP\x00", "[SHORT_PAUSE]")
    text = text.replace("\x00P\x00",  "[PAUSE]")
    text = text.replace("\x00LP\x00", "[LONG_PAUSE]")
    return text


def _clean_for_elevenlabs(text):
    """Prepare text for ElevenLabs: city names → Telugu, pause markers → SSML breaks."""
    for eng in sorted(CITY_TELUGU.keys(), key=len, reverse=True):
        text = text.replace(eng, CITY_TELUGU[eng])

    # Convert pause markers to SSML break tags
    text = text.replace("[LONG_PAUSE]",  '<break time="800ms"/>')
    text = text.replace("[PAUSE]",       '<break time="500ms"/>')
    text = text.replace("[SHORT_PAUSE]", '<break time="300ms"/>')

    return f"<speak>{text.strip()}</speak>"


def _generate_elevenlabs(text, output_path):
    """Generate audio using ElevenLabs API with confident male voice settings."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print("  [VOICE] ELEVENLABS_API_KEY not set — skipping ElevenLabs")
        return False

    try:
        client = ElevenLabs(api_key=api_key)

        # Confident, stable middle-aged male — low style prevents anime/exaggerated tone
        kwargs = dict(
            voice_id=ELEVENLABS_VOICE_ID,
            text=text,
            model_id=ELEVENLABS_MODEL,
            output_format="mp3_44100_128",
        )
        if VOICE_SETTINGS_AVAILABLE:
            kwargs["voice_settings"] = VoiceSettings(
                stability=0.75,         # consistent, authoritative
                similarity_boost=0.85,  # close to original voice character
                style=0.15,             # low = natural; high = anime/exaggerated
                use_speaker_boost=True,
            )

        audio_generator = client.text_to_speech.convert(**kwargs)

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
    """Generate audio using gTTS with typed pause support and deep-male FFmpeg processing.

    Splits text on [SHORT_PAUSE] / [PAUSE] / [LONG_PAUSE] markers,
    generates each text chunk via gTTS, inserts the matching silence duration,
    then concatenates and applies deep-male voice processing.
    """
    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available"); return False

    try:
        with tempfile.TemporaryDirectory() as tmp:
            # Split on any pause marker, preserving the delimiters
            marker_pattern = r'(\[SHORT_PAUSE\]|\[PAUSE\]|\[LONG_PAUSE\])'
            parts = re.split(marker_pattern, text)

            segment_files = []
            for idx, part in enumerate(parts):
                part = part.strip()
                if not part:
                    continue

                if part in PAUSE_DURATIONS:
                    silence_mp3 = os.path.join(tmp, f"silence_{idx}.mp3")
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "lavfi",
                        "-i", "anullsrc=r=44100:cl=mono",
                        "-t", PAUSE_DURATIONS[part],
                        "-ar", "44100", "-ab", "128k",
                        silence_mp3
                    ], capture_output=True)
                    segment_files.append(silence_mp3)
                else:
                    chunk_mp3 = os.path.join(tmp, f"chunk_{idx}.mp3")
                    tts = gTTS(text=part, lang='te', slow=False)
                    tts.save(chunk_mp3)
                    segment_files.append(chunk_mp3)

            if not segment_files:
                return False

            print(f"  [VOICE] gTTS: {len(segment_files)} segment(s)")

            # Concatenate all segments
            raw_mp3 = os.path.join(tmp, "raw.mp3")
            if len(segment_files) > 1:
                concat_txt = os.path.join(tmp, "concat.txt")
                with open(concat_txt, "w") as f:
                    for sf in segment_files:
                        f.write(f"file '{sf}'\n")
                subprocess.run([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_txt, "-c", "copy", raw_mp3
                ], capture_output=True)
            else:
                shutil.copy(segment_files[0], raw_mp3)

            raw_dur = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", raw_mp3],
                capture_output=True, text=True)
            print(f"  [VOICE] gTTS raw duration: {raw_dur.stdout.strip()}s")

            # Deep male voice: pitch down + bass boost + compression
            final_mp3 = os.path.join(tmp, "final.mp3")
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

    # Try ElevenLabs first — converts pause markers to SSML, keeps Telugu+English
    if ELEVENLABS_AVAILABLE:
        el_text = _clean_for_elevenlabs(text)
        print(f"  [VOICE] ElevenLabs SSML preview: {el_text[:120]}...")
        print(f"  [VOICE] Trying ElevenLabs voice {ELEVENLABS_VOICE_ID} (stable=0.75, style=0.15)...")
        if _generate_elevenlabs(el_text, output_path):
            return output_path
        print("  [VOICE] Falling back to gTTS...")
    else:
        print("  [VOICE] ElevenLabs SDK not installed — using gTTS")

    # Fallback: gTTS — strip to pure Telugu, keep pause markers as silence
    gtts_text = clean_for_tts(text)
    print(f"  [VOICE] gTTS preview: {gtts_text[:80]}...")
    if _generate_gtts_fallback(gtts_text, output_path):
        return output_path

    print("  [VOICE] All TTS methods failed"); return None


generate_voiceover = generate_voice
generate_audio     = generate_voice
