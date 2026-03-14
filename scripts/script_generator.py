"""
script_generator.py — City-specific Telugu+English script covering all timing fields.
Updated for 12-second Instagram Reels format (~30 words narration).
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

    prompt = f"""You are creating a 12-second Instagram Reel voice narration for 
daily Hindu Panchang for Telugu-speaking Hindus in {city}.

Today's Panchang for {city} ({tz_label}):
Date: {weekday}, {date_str}

KEY TIMINGS:
- Tithi: {tf(panchang,'tithi')}
- Paksha: {tf(panchang,'paksha')}
- Rahu Kalam: {tf(panchang,'rahukaal')}
- Dur Muhurtam: {tf(panchang,'durmuhurtam')}
- Abhijit Muhurta: {tf(panchang,'abhijit')}
- Brahma Muhurta: {tf(panchang,'brahma_muhurta')}
- Sunrise: {tf(panchang,'sunrise')}
- Sunset: {tf(panchang,'sunset')}

STRICT RULES:
1. MAXIMUM 30 words total — this is a HARD limit, reel is only 12 seconds
2. Natural Telugu+English mix (how Telugu-Americans actually speak)
3. Say "{city}" specifically
4. Mention Rahu Kalam time as the main warning
5. Mention Abhijit Muhurta as the best time
6. End with "Follow cheyandi daily Panchangam kosam!"
7. Start with "Namaskaram!" 

Return ONLY valid JSON with no markdown or backticks:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Rahu Kalam & All Timings",
  "description": "Today's complete Hindu Panchang for {city}. Rahu Kalam, Abhijit Muhurta, all auspicious and inauspicious timings in Telugu and English.",
  "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","RahuKalam","Panchang","Shorts","Reels","TeluguAmerica","HinduAmerica","DailyBlessing"],
  "full_narration": "30-word max Telugu+English narration here",
  "on_screen_lines": [
    "📍 {city}",
    "⛔ Rahu Kalam: exact time",
    "⛔ Dur Muhurtam: exact time",
    "✅ Brahma Muhurta: exact time",
    "✅ Abhijit: exact time"
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
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except:
        return {
            "title": f"Daily Panchangam {city} | {weekday} {date_str}",
            "description": f"Complete Hindu Panchang for {city}. All timings in Telugu & English.",
            "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","Shorts"],
            "full_narration": (
                f"Namaskaram! {city} Panchangam. "
                f"Rahu Kalam {tf(panchang,'rahukaal')} avoid cheyandi. "
                f"Abhijit Muhurta {tf(panchang,'abhijit')} best time. "
                f"Follow cheyandi daily Panchangam kosam!"
            ),
            "on_screen_lines": [
                f"📍 {city}",
                f"⛔ Rahu Kalam: {tf(panchang,'rahukaal')}",
                f"⛔ Dur Muhurtam: {tf(panchang,'durmuhurtam')}",
                f"✅ Brahma Muhurta: {tf(panchang,'brahma_muhurta')}",
                f"✅ Abhijit: {tf(panchang,'abhijit')}",
            ]
        }
