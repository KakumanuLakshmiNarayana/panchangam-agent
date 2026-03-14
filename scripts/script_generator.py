"""
script_generator.py v4
8-scene sync: intro → tithi → rahu → durmuhurtam → brahma → abhijit → sun → closing
Max 30 words for ~13-14s audio at gTTS pace (~2.2 words/sec)
Start: "నమస్కారం! nenu meepanchangamguyusa."
End: positive Telugu blessing + Like Share Subscribe
"""
import os, json
import anthropic


def tf(p, k):
    v = p.get(k, "N/A")
    return v if v and v != "" else "N/A"


def generate_video_script(panchang):
    client   = anthropic.Anthropic()
    city     = panchang.get("city",     "USA")
    tz_label = panchang.get("tz_label", "ET")
    weekday  = panchang.get("weekday",  "")
    date_str = panchang.get("date",     "")

    # Pre-clean all values — strip TZ and take first slot only
    def clean(key):
        v = tf(panchang, key).split("|")[0].strip()
        return v.replace(f" {tz_label}","").strip()

    tithi   = clean("tithi").split("→")[0].split("->")[0].strip()
    rahu    = clean("rahukaal")
    dur     = clean("durmuhurtam")
    brahma  = clean("brahma_muhurta")
    abhijit = clean("abhijit")
    sunrise = clean("sunrise")
    sunset  = clean("sunset")

    prompt = f"""Write a voice narration for a 14-second Instagram Reel Panchangam video.

City: {city} | {weekday} | Timezone: {tz_label}

DATA (in order):
1. Tithi: {tithi}
2. Rahu Kalam: {rahu}
3. Durmuhurtam: {dur}
4. Brahma Muhurtam: {brahma}
5. Abhijit: {abhijit}
6. Sunrise: {sunrise} | Sunset: {sunset}

STRICT RULES:
- Start EXACTLY with: "నమస్కారం! nenu meepanchangamguyusa."
- Say city: {city}
- Mention each of the 6 data points with times
- End EXACTLY with: "మీకు శుభమైన రోజు కలగాలని ఆశిస్తున్నాను! Like, Share, Subscribe చేయండి!"
- Natural Telugu+English mix
- MAXIMUM 45 words total — HARD LIMIT (gTTS reads ~3 words/sec)
- Keep each data point to 4-5 words max

Return ONLY valid JSON, no markdown:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Rahu Kalam & All Timings",
  "description": "Today's complete Hindu Panchang for {city}. Rahu Kalam, Abhijit Muhurta, all auspicious and inauspicious timings in Telugu and English.",
  "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","RahuKalam","Panchang","Shorts","Reels","TeluguAmerica","HinduAmerica","DailyBlessing"],
  "full_narration": "45-word max narration here",
  "on_screen_lines": [
    "Tithi: {tithi}",
    "Rahu Kalam: {rahu} {tz_label}",
    "Durmuhurtam: {dur} {tz_label}",
    "Brahma Muhurtam: {brahma} {tz_label}",
    "Abhijit: {abhijit} {tz_label}",
    "Sunrise: {sunrise} | Sunset: {sunset} {tz_label}"
  ]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except:
        # Fallback — hardcoded short narration
        return {
            "title": f"Daily Panchangam {city} | {weekday} {date_str}",
            "description": f"Complete Hindu Panchang for {city}.",
            "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","Shorts"],
            "full_narration": (
                f"నమస్కారం! nenu meepanchangamguyusa. "
                f"{city} Panchangam. "
                f"Tithi {tithi}. "
                f"Rahu Kalam {rahu} avoid. "
                f"Durmuhurtam {dur}. "
                f"Brahma Muhurtam {brahma}. "
                f"Abhijit {abhijit} best time. "
                f"Sunrise {sunrise}, Sunset {sunset}. "
                f"మీకు శుభమైన రోజు కలగాలని ఆశిస్తున్నాను! "
                f"Like, Share, Subscribe చేయండి!"
            ),
            "on_screen_lines": [
                f"Tithi: {tithi}",
                f"Rahu Kalam: {rahu} {tz_label}",
                f"Durmuhurtam: {dur} {tz_label}",
                f"Brahma Muhurtam: {brahma} {tz_label}",
                f"Abhijit: {abhijit} {tz_label}",
                f"Sunrise: {sunrise} | Sunset: {sunset} {tz_label}",
            ]
        }
