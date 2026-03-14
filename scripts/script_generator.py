"""
script_generator.py v2
Generates SHORT 10-12 second narration scripts for Instagram Reels.
Target: ~25-35 words = ~12 seconds of speech at normal pace.
Structure matches the 7 video scenes.
"""

import os
import anthropic
import json


def generate_script(panchang: dict) -> dict:
    """Generate a short Reel-optimized narration + metadata for one city."""

    city     = panchang.get("city", "USA")
    date     = panchang.get("date", "")
    tithi    = panchang.get("tithi", "N/A")
    paksha   = panchang.get("paksha", "")
    rahu     = panchang.get("rahukaal", "N/A").split("|")[0].strip()
    dur      = panchang.get("durmuhurtam", "N/A")
    abhijit  = panchang.get("abhijit", "N/A")
    sunrise  = panchang.get("sunrise", "N/A")
    sunset   = panchang.get("sunset", "N/A")
    tz       = panchang.get("tz_label", "ET")
    weekday  = panchang.get("weekday", "")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""You are writing a SHORT voice narration for a 12-second Instagram Reel about Hindu Panchangam.

City: {city}
Date: {weekday}, {date}
Tithi: {tithi} ({paksha})
Rahu Kalam: {rahu} {tz}
Durmuhurtam: {dur} {tz}
Abhijit Muhurtham: {abhijit} {tz}
Sunrise: {sunrise} {tz} | Sunset: {sunset} {tz}

RULES:
- Maximum 35 words total. This is a HARD limit.
- Mix Telugu and English naturally (like how Telugu people speak in USA)
- Must cover: greeting, Rahu warning, best time, sign-off
- Warm devotional tone, like a friendly pandit
- End with "Follow cheyandi daily Panchangam kosam!"

Write ONLY the narration text, nothing else. No labels, no JSON."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}]
    )

    narration = message.content[0].text.strip()

    # Build on_screen_lines for caption/description use
    on_screen_lines = [
        f"Tithi: {tithi}",
        f"Rahu Kalam: {rahu} {tz}",
        f"Durmuhurtam: {dur} {tz}",
        f"Abhijit Muhurtham: {abhijit} {tz}",
        f"Sunrise: {sunrise} | Sunset: {sunset} {tz}",
    ]

    hashtags = [
        "DailyPanchangam", "TeluguPanchang", "HinduCalendar",
        "RahuKalam", "Panchangam", "Shorts", "Reels",
        "TeluguAmerica", "HinduAmerica", "PanthuluPanchangam"
    ]

    title = (f"Daily Panchangam {city} | {weekday} {date} | "
             f"Rahu Kalam {rahu} {tz}")

    description = (
        f"Today's Panchangam for {city}\n"
        f"Date: {weekday}, {date}\n\n"
        + "\n".join(on_screen_lines)
        + "\n\n#" + " #".join(hashtags)
    )

    return {
        "full_narration": narration,
        "on_screen_lines": on_screen_lines,
        "title": title,
        "description": description,
        "hashtags": hashtags,
    }


# Alias for backward compatibility
def generate_script_for_city(panchang: dict) -> dict:
    return generate_script(panchang)
