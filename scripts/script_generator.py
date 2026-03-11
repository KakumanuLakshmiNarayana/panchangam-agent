"""
script_generator.py — Generates Telugu+English script for one city's panchang.
"""
import os, json
import anthropic


def generate_video_script(panchang):
    """Generate a 60-sec Telugu+English script for a specific city."""
    client = anthropic.Anthropic()

    city     = panchang.get("city", "USA")
    tz_label = panchang.get("tz_label", "ET")
    weekday  = panchang.get("weekday", "")
    date_str = panchang.get("date", "")

    def t(field):
        return panchang.get(field, "N/A")

    summary = f"""
City: {city} ({tz_label})
Date: {weekday}, {date_str}
Tithi: {t('tithi')}
Nakshatra: {t('nakshatra')}
Yoga: {t('yoga')}
Karana: {t('karana')}
Masa: {t('masa')} | Paksha: {t('paksha')}

LOCAL TIMINGS for {city}:
Sunrise:      {t('sunrise')}
Sunset:       {t('sunset')}
Rahukaal:     {t('rahukaal')}   ← AVOID
Durmuhurtam:  {t('durmuhurtam')} ← AVOID
Gulika Kalam: {t('gulika')}     ← AVOID
Yamagandam:   {t('yamagandam')} ← AVOID
Abhijit Muhurta: {t('abhijit')} ← AUSPICIOUS
Amrit Kalam:  {t('amrit_kalam')} ← AUSPICIOUS
Varjyam:      {t('varjyam')}
"""

    prompt = f"""You are creating a 60-second Instagram Reel / YouTube Shorts script for 
daily Hindu Panchang specifically for Telugu-speaking Hindus living in {city}.

Panchang data:
{summary}

Rules:
- Mix Telugu and English naturally (like a Telugu-American speaks)
- Mention {city} specifically so viewers know it's for their city
- Give EXACT local timings — do NOT say "location based" or "check your area"
- Clearly say which times to AVOID (Rahukaal, Durmuhurtam) and which are AUSPICIOUS (Abhijit)
- Total script: 130-150 words (reads in ~60 seconds)
- Start with Telugu blessing, end with Telugu blessing

Return ONLY valid JSON, no markdown, no backticks:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Exact Local Timings",
  "description": "50-word English YouTube description mentioning {city}",
  "hashtags": ["DailyPanchangam","{city.replace(' ','')}","Telugu","HinduCalendar","Panchang","Shorts","Reels","TeluguAmerica"],
  "full_narration": "Complete Telugu+English script with exact {city} timings",
  "on_screen_lines": [
    "📍 {city}",
    "Tithi: ...",
    "⛔ Rahukaal: ...",
    "✅ Abhijit: ..."
  ]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = message.content[0].text.strip()
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Safe fallback
        return {
            "title": f"Daily Panchangam {city} | {weekday} {date_str}",
            "description": f"Daily Hindu Panchang for {city}. Exact local timings in Telugu & English.",
            "hashtags": ["DailyPanchangam", "Telugu", "HinduCalendar", "Shorts"],
            "full_narration": (
                f"నమస్కారం! {city} లో ఉన్న మన అందరికీ శుభోదయం! "
                f"Today is {weekday}, {t('tithi')} Tithi. Nakshatra: {t('nakshatra')}. "
                f"Rahukaal {city}: {t('rahukaal')} — please avoid important work. "
                f"Abhijit Muhurta {city}: {t('abhijit')} — very auspicious for new beginnings. "
                f"మీకు శుభమగుగాక! Jay Srimannarayana!"
            ),
            "on_screen_lines": [
                f"📍 {city}",
                f"Tithi: {t('tithi')}",
                f"⛔ Rahukaal: {t('rahukaal')}",
                f"✅ Abhijit: {t('abhijit')}",
            ]
        }


def t(panchang, field):
    return panchang.get(field, "N/A")
