"""
voice_generator.py — Male confident Telugu voice
Primary: ElevenLabs multilingual_v2 with optimized settings
Fallback: gTTS Telugu with speed/pitch adjustment via ffmpeg
"""
import os, requests, json, subprocess
from pathlib import Path

ELEVENLABS_VOICE_PRIORITY = [
    ("Rahul",   "TX3LPaxmHKxFdv7VOQHJ"),  # Deep Indian male - best for Telugu
    ("Chetan",  "onwK4e9ZLuTAKqWW03F9"),  # Indian male, warm
    ("Rishi",   "giB4zAYcqQUkFiIVHagE"),  # Indian male narrator
    ("Suresh",  "N2lVS1w4EtoT3dr4eOWO"),  # Deep male
    ("Adam",    "pNInz6obpgDQGcFmaJgB"),  # Neutral deep male fallback
]

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")


def get_best_voice_id():
    if not ELEVENLABS_API_KEY:
        return None, None
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=10
        )
        if resp.status_code != 200:
            return ELEVENLABS_VOICE_PRIORITY[0]
        available = {v["voice_id"]: v["name"] for v in resp.json().get("voices", [])}
        for name, vid in ELEVENLABS_VOICE_PRIORITY:
            if vid in available:
                print(f"     🎤 ElevenLabs voice: {name}")
                return name, vid
        for vid, name in available.items():
            if any(k in name.lower() for k in ["rahul","rishi","arjun","suresh","chetan","kumar"]):
                print(f"     🎤 Found Indian voice: {name}")
                return name, vid
        return ELEVENLABS_VOICE_PRIORITY[0]
    except Exception as e:
        print(f"     ⚠️  Voice lookup: {e}")
        return ELEVENLABS_VOICE_PRIORITY[0]


def generate_with_elevenlabs(text: str, output_path: str) -> bool:
    if not ELEVENLABS_API_KEY:
        return False
    voice_name, voice_id = get_best_voice_id()
    if not voice_id:
        return False
    try:
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.60,          # Confident, less wavering
                "similarity_boost": 0.85,   # Stay true to voice character
                "style": 0.35,              # Slight style for warmth
                "use_speaker_boost": True,  # Clearer, more present sound
            }
        }
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            json=payload,
            timeout=60
        )
        if resp.status_code == 200:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(resp.content)
            size = os.path.getsize(output_path)
            print(f"     ✅ ElevenLabs audio: {size//1024}KB")
            return True
        else:
            print(f"     ❌ ElevenLabs {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"     ❌ ElevenLabs error: {e}")
        return False


def generate_with_gtts(text: str, output_path: str) -> bool:
    """gTTS Telugu fallback — post-process with ffmpeg for deeper male voice."""
    try:
        from gtts import gTTS
        import tempfile

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Save raw gTTS output to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name

        tts = gTTS(text=text, lang='te', slow=False)
        tts.save(tmp_path)

        # Post-process with ffmpeg:
        # - pitch down by 15% (deeper male voice)
        # - speed up slightly (more confident, less slow)
        # - normalize volume
        cmd = [
            "ffmpeg", "-y", "-i", tmp_path,
            "-af", (
                "asetrate=44100*0.88,"      # pitch down ~15% (deeper)
                "aresample=44100,"           # resample back to 44100
                "atempo=1.08,"               # slight speed up (more confident)
                "loudnorm=I=-16:TP=-1.5:LRA=11"  # normalize volume
            ),
            "-codec:a", "libmp3lame",
            "-q:a", "2",
            output_path
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)

        # Cleanup temp
        try: os.unlink(tmp_path)
        except: pass

        if r.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"     ✅ gTTS (Telugu, male-processed): {size//1024}KB")
            return True
        else:
            # Fallback: save raw gTTS without processing
            tts = gTTS(text=text, lang='te', slow=False)
            tts.save(output_path)
            print(f"     ⚠️  gTTS raw (ffmpeg processing failed)")
            return True
    except Exception as e:
        print(f"     ❌ gTTS error: {e}")
        return False


def generate_voice(script: str, output_path: str) -> str:
    """
    Generate voice audio. Returns path to audio file or None.
    Priority: ElevenLabs → gTTS Telugu
    """
    print(f"  🎙️  Generating voice ({len(script)} chars)...")

    # Try ElevenLabs first
    if ELEVENLABS_API_KEY:
        if generate_with_elevenlabs(script, output_path):
            return output_path
        print("     ↩️  ElevenLabs failed, falling back to gTTS")

    # Fallback: gTTS Telugu
    if generate_with_gtts(script, output_path):
        return output_path

    print("  ❌ All voice generation failed")
    return None

# Alias for pipeline.py compatibility
generate_voiceover = generate_voice
