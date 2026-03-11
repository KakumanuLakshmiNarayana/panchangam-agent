"""
Voice Generator — Generates Telugu+English voiceover using ElevenLabs TTS
Falls back to Google Cloud TTS if ElevenLabs unavailable, then gTTS (free)
"""

import os
import requests
from pathlib import Path
from typing import Optional


ELEVENLABS_VOICES = {
    "telugu_female": "pNInz6obpgDQGcFmaJgB",
    "telugu_male":   "VR6AewLTigWG4xSOukaG",
    "default":       "21m00Tcm4TlvDq8ikWAM",
}


def generate_voice_elevenlabs(text: str, output_path: str, voice_id: Optional[str] = None) -> bool:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("⚠️  ELEVENLABS_API_KEY not set, trying gTTS fallback")
        return False

    if voice_id is None:
        voice_id = ELEVENLABS_VOICES["default"]

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": api_key}
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✅ ElevenLabs audio saved: {output_path}")
        return True
    else:
        print(f"❌ ElevenLabs error {response.status_code}: {response.text[:200]}")
        return False


def generate_voice_gtts(text: str, output_path: str, lang: str = "te") -> bool:
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output_path)
        print(f"✅ gTTS audio saved: {output_path}")
        return True
    except ImportError:
        print("❌ gTTS not installed. Run: pip install gtts")
        return False
    except Exception as e:
        print(f"❌ gTTS error: {e}")
        return False


def generate_voiceover(script: dict, output_path: str = "output/voiceover.mp3") -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    full_text = script.get("full_narration", "")
    if not full_text:
        segments = script.get("narration", [])
        full_text = " ".join(seg.get("text", "") for seg in segments)

    print(f"🎙️  Generating voiceover ({len(full_text)} chars)...")

    if generate_voice_elevenlabs(full_text, output_path):
        return output_path

    if generate_voice_gtts(full_text, output_path, lang="te"):
        return output_path

    raise RuntimeError("All TTS providers failed. Check API keys.")


def get_audio_duration(audio_path: str) -> float:
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 60.0
