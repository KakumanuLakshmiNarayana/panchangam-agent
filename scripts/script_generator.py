"""
script_generator.py — City-specific Telugu+English script covering all timing fields.
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

    prompt = f"""You are creating a 60-second Instagram Reel / YouTube Shorts script for 
daily Hindu Panchang for Telugu-speaking Hindus in {city}.

Today's complete Panchang for {city} ({tz_label}):
Date: {weekday}, {date_str}

BASIC INFO:
- Tithi: {tf(panchang,'tithi')}
- Nakshatra: {tf(panchang,'nakshatra')}
- Yoga: {tf(panchang,'yoga')}
- Karana: {tf(panchang,'karana')}
- Masa: {tf(panchang,'masa')} | Paksha: {tf(panchang,'paksha')}

INAUSPICIOUS TIMINGS for {city}:
- Rahu Kalam: {tf(panchang,'rahukaal')}
- Dur Muhurtam: {tf(panchang,'durmuhurtam')}
- Gulika Kalam: {tf(panchang,'gulika')}
- Yamaganda: {tf(panchang,'yamagandam')}
- Varjyam: {tf(panchang,'varjyam')}

AUSPICIOUS TIMINGS for {city}:
- Brahma Muhurta: {tf(panchang,'brahma_muhurta')}
- Abhijit: {tf(panchang,'abhijit')}
- Vijaya Muhurta: {tf(panchang,'vijaya_muhurta')}
- Amrit Kalam: {tf(panchang,'amrit_kalam')}
- Godhuli Muhurta: {tf(panchang,'godhuli_muhurta')}

SUN & MOON:
- Sunrise: {tf(panchang,'sunrise')}
- Sunset: {tf(panchang,'sunset')}

STRICT RULES:
1. Natural Telugu+English mix (how Telugu-Americans actually speak)
2. Say "{city}" specifically — viewers need to know it's for their city
3. Give EXACT timings — never say "check your area" or "location based"
4. Highlight what to AVOID and what is AUSPICIOUS with clear language
5. 130-150 words total (reads in ~60 seconds)
6. Start with a Telugu blessing, end with a Telugu blessing

Return ONLY valid JSON with no markdown or backticks:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Rahu Kalam & All Timings",
  "description": "Today's complete Hindu Panchang for {city}. Rahu Kalam, Abhijit Muhurta, all auspicious and inauspicious timings in Telugu and English.",
  "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","RahuKalam","Panchang","Shorts","Reels","TeluguAmerica","HinduAmerica","DailyBlessing"],
  "full_narration": "Complete Telugu+English 60-second script here with exact {city} timings",
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
        max_tokens=1500,
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
                f"నమస్కారం! {city} లో ఉన్న మన అందరికీ శుభోదయం! "
                f"Today is {weekday}. Tithi {tf(panchang,'tithi')}, "
                f"Nakshatra {tf(panchang,'nakshatra')}. "
                f"Rahu Kalam {city}: {tf(panchang,'rahukaal')} — avoid important work. "
                f"Dur Muhurtam: {tf(panchang,'durmuhurtam')} — also avoid. "
                f"Brahma Muhurta: {tf(panchang,'brahma_muhurta')} — excellent for prayers. "
                f"Abhijit Muhurta: {tf(panchang,'abhijit')} — very auspicious. "
                f"Sunrise: {tf(panchang,'sunrise')}. "
                f"మీకు శుభమగుగాక! Jay Srimannarayana!"
            ),
            "on_screen_lines": [
                f"📍 {city}",
                f"⛔ Rahu Kalam: {tf(panchang,'rahukaal')}",
                f"✅ Brahma Muhurta: {tf(panchang,'brahma_muhurta')}",
                f"✅ Abhijit: {tf(panchang,'abhijit')}",
            ]
        }
