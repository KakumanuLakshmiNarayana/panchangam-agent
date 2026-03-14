"""
voice_generator.py v3
- Remove slow=True and atempo (was making audio 43s)
- Normal gTTS speed = ~1.6 words/sec for Telugu
- 48 words × 1.6 = ~30s — video will stretch to match exactly
- Clean narration before TTS (strip digits/Latin)
"""
import os, re, tempfile, subprocess, shutil
from pathlib import Path

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False


def clean_for_tts(text):
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'[a-zA-Z]+', '', text)
    text = re.sub(r'[\:\-–]+', ' ', text)
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

    if not GTTS_AVAILABLE:
        print("  [VOICE] gTTS not available"); return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw_mp3 = os.path.join(tmp, "raw.mp3")
            # Normal speed — no slow=True
            tts = gTTS(text=cleaned, lang='te', slow=False)
            tts.save(raw_mp3)
            shutil.copy(raw_mp3, output_path)
            print(f"  [VOICE] OK {os.path.getsize(output_path)} bytes")
        return output_path
    except Exception as e:
        print(f"  [VOICE] Error: {e}"); return None


generate_voiceover = generate_voice
generate_audio     = generate_voice
