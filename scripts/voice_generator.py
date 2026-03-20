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
    """Clean romanized Telugu text for gTTS — keep Latin chars, strip digits and punctuation."""
    # Protect pause markers from being stripped
    text = text.replace("[SHORT_PAUSE]", "\x00SP\x00")
    text = text.replace("[PAUSE]",       "\x00P\x00")
    text = text.replace("[LONG_PAUSE]",  "\x00LP\x00")

    # Remove digits (times shown on screen, not spoken)
    text = re.sub(r'\d+', '', text)
    # Clean punctuation (keep letters, spaces, hyphens for compound words)
    text = re.sub(r'[\:\–,\.!?;]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Restore pause markers
    text = text.replace("\x00SP\x00", "[SHORT_PAUSE]")
    text = text.replace("\x00P\x00",  "[PAUSE]")
    text = text.replace("\x00LP\x00", "[LONG_PAUSE]")
    return text


def _clean_for_elevenlabs(text):
    """Prepare text for ElevenLabs: pause markers → SSML breaks.

    Text is now romanized Telugu (English letters) so no substitution needed.
    ElevenLabs accepts inline <break> tags without a <speak> wrapper.
    """
    # Convert pause markers to inline SSML break tags (no <speak> wrapper needed)
    text = text.replace("[LONG_PAUSE]",  '<break time="800ms"/> ')
    text = text.replace("[PAUSE]",       '<break time="500ms"/> ')
    text = text.replace("[SHORT_PAUSE]", '<break time="300ms"/> ')

    return text.strip()


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


def _ffprobe_duration(path):
    """Return audio duration in seconds via ffprobe."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _apply_voice_filter(src_mp3, dst_mp3):
    """Bass boost + compression only — no pitch shift so duration is preserved."""
    af = (
        "bass=g=5:f=150:w=0.6,"
        "acompressor=threshold=-20dB:ratio=3:attack=8:release=80:makeup=2dB,"
        "volume=1.3"
    )
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", src_mp3, "-af", af,
         "-ar", "44100", "-ab", "128k", "-codec:a", "libmp3lame", dst_mp3],
        capture_output=True, text=True)
    return r.returncode == 0


def _generate_gtts_scenes(scene_texts, output_path, lang="te"):
    """Generate one audio file from 4 scene texts, returning per-scene durations.

    Each scene is synthesised separately so we can measure its exact duration,
    enabling frame-accurate video/audio sync.  tld='co.in' uses Google India
    which has better Telugu pronunciation.
    Returns list of 4 float durations in seconds, or None on failure.
    """
    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available"); return None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw_files, scene_durations = [], []
            for i, text in enumerate(scene_texts):
                raw_mp3 = os.path.join(tmp, f"scene_{i}_raw.mp3")
                try:
                    tts = gTTS(text=text, lang=lang, slow=False, tld='co.in')
                    tts.save(raw_mp3)
                except Exception:
                    # tld kwarg not supported in older gtts — retry without it
                    tts = gTTS(text=text, lang=lang, slow=False)
                    tts.save(raw_mp3)

                # Measure raw duration (before filter — filter doesn't change duration)
                dur = _ffprobe_duration(raw_mp3)
                scene_durations.append(dur)
                raw_files.append(raw_mp3)
                print(f"  [VOICE] Scene {i} raw: {dur:.2f}s  text={text[:40]!r}...")

            # Concatenate all 4 scenes
            concat_mp3 = os.path.join(tmp, "concat.mp3")
            concat_txt = os.path.join(tmp, "concat.txt")
            with open(concat_txt, "w") as f:
                for rf in raw_files:
                    f.write(f"file '{rf}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_txt, "-c", "copy", concat_mp3],
                capture_output=True)

            # Apply voice enhancement (bass + compression, no duration change)
            final_mp3 = os.path.join(tmp, "final.mp3")
            ok = _apply_voice_filter(concat_mp3, final_mp3)
            shutil.copy(final_mp3 if ok else concat_mp3, output_path)

            total = _ffprobe_duration(output_path)
            print(f"  [VOICE] gTTS scenes: {scene_durations}  total={total:.2f}s")
            return scene_durations

    except Exception as e:
        print(f"  [VOICE] gTTS scene error: {e}")
        return None


def _generate_gtts_fallback(text, output_path, lang="te"):
    """Single-text gTTS fallback (used when scene texts unavailable)."""
    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available"); return False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw_mp3 = os.path.join(tmp, "raw.mp3")
            try:
                tts = gTTS(text=text, lang=lang, slow=False, tld='co.in')
                tts.save(raw_mp3)
            except Exception:
                tts = gTTS(text=text, lang=lang, slow=False)
                tts.save(raw_mp3)

            final_mp3 = os.path.join(tmp, "final.mp3")
            ok = _apply_voice_filter(raw_mp3, final_mp3)
            shutil.copy(final_mp3 if ok else raw_mp3, output_path)

            dur = _ffprobe_duration(output_path)
            print(f"  [VOICE] gTTS fallback: {dur:.2f}s  size={os.path.getsize(output_path)} bytes")
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

    # Fallback: gTTS with Telugu script — generate per-scene for accurate sync
    scene_texts = (script.get("gtts_scene_texts") if isinstance(script, dict) else None)
    if scene_texts and len(scene_texts) == 4:
        print(f"  [VOICE] gTTS per-scene mode (lang=te, tld=co.in)...")
        durations = _generate_gtts_scenes(scene_texts, output_path, lang="te")
        if durations:
            if isinstance(script, dict):
                script["scene_durations_sec"] = durations  # used by remotion_renderer
            return output_path

    # Last resort: single-text gTTS
    gtts_text = (script.get("gtts_narration", "") if isinstance(script, dict) else "") or clean_for_tts(text)
    gtts_lang = "te" if isinstance(script, dict) and script.get("gtts_narration") else "en"
    print(f"  [VOICE] gTTS single-text lang={gtts_lang} preview: {gtts_text[:80]}...")
    if _generate_gtts_fallback(gtts_text, output_path, lang=gtts_lang):
        return output_path

    print("  [VOICE] All TTS methods failed"); return None


generate_voiceover = generate_voice
generate_audio     = generate_voice
