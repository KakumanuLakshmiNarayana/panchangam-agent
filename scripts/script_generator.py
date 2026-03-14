"""
script_generator.py v3
9-scene sync: intro → tithi → rahu → durmuhurtam → brahma → abhijit → sunrise → sunset → closing
Start: "నమస్కారం నేను మీ పంచాంగం గురువు"
End: positive Telugu blessing + like/share/subscribe
~13-14 seconds total, ~40-50 words
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

    tithi    = tf(panchang, "tithi").split("→")[0].strip()
    rahu     = tf(panchang, "rahukaal").split("|")[0].strip().replace(f" {tz_label}","").strip()
    dur      = tf(panchang, "durmuhurtam").replace(f" {tz_label}","").strip()
    brahma   = tf(panchang, "brahma_muhurta").split("|")[0].strip().replace(f" {tz_label}","").strip()
    abhijit  = tf(panchang, "abhijit").replace(f" {tz_label}","").strip()
    sunrise  = tf(panchang, "sunrise").replace(f" {tz_label}","").strip()
    sunset   = tf(panchang, "sunset").replace(f" {tz_label}","").strip()

    prompt = f"""Write a SHORT voice narration for a 13-second Instagram Reel Panchangam video.

City: {city} | Date: {weekday} {date_str} | Timezone: {tz_label}

DATA TO COVER (in this order):
1. Tithi: {tithi}
2. Rahu Kalam: {rahu}
3. Durmuhurtam: {dur}
4. Brahma Muhurtam: {brahma}
5. Abhijit: {abhijit}
6. Sunrise: {sunrise} | Sunset: {sunset}

STRICT RULES:
- Start EXACTLY with: "నమస్కారం! nenu meepanchangamguyusa."
- Say city name: {city}
- Cover all 6 data points above with exact times
- End with a positive Telugu blessing like "మీకు శుభమైన రోజు కలగాలని ఆశిస్తున్నాను"
- Then say "Like, Share, Subscribe చేయండి!"
- Natural Telugu+English mix (like Telugu-Americans speak)
- MAXIMUM 55 words total — HARD LIMIT
- Do NOT say "follow" — say "Subscribe చేయండి"

Return ONLY valid JSON, no markdown:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Rahu Kalam & All Timings",
  "description": "Today's complete Hindu Panchang for {city}. Rahu Kalam, Abhijit Muhurta, all auspicious and inauspicious timings in Telugu and English.",
  "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","RahuKalam","Panchang","Shorts","Reels","TeluguAmerica","HinduAmerica","DailyBlessing"],
  "full_narration": "55-word max narration here",
  "on_screen_lines": [
    "Tithi: {tithi}",
    "Rahu Kalam: {rahu} {tz_label}",
    "Durmuhurtam: {dur} {tz_label}",
    "Brahma Muhurtam: {brahma} {tz_label}",
    "Abhijit: {abhijit} {tz_label}",
    "Sunrise: {sunrise} {tz_label} | Sunset: {sunset} {tz_label}"
  ]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
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
        return {
            "title": f"Daily Panchangam {city} | {weekday} {date_str}",
            "description": f"Complete Hindu Panchang for {city}. All timings in Telugu & English.",
            "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","Shorts"],
            "full_narration": (
                f"నమస్కారం! nenu meepanchangamguyusa. "
                f"{city} lo {weekday} Panchangam. "
                f"Tithi {tithi}. "
                f"Rahu Kalam {rahu} {tz_label} avoid cheyandi. "
                f"Durmuhurtam {dur}. "
                f"Brahma Muhurtam {brahma} prayers ki best. "
                f"Abhijit {abhijit} important work ki. "
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
