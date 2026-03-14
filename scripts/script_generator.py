"""
script_generator.py v5

VOICE STRATEGY COMPLETE RETHINK:
- Problem: gTTS reads "10:04 AM" as "ten colon zero four A M" — robotic
- Problem: Mixed Telugu+English confuses gTTS pronunciation
- Problem: 56 words = 28s but video is 14s

NEW APPROACH:
- Voice NEVER reads times — screen shows times
- Voice only says section name + one feeling word
- Everything in pure Telugu script — no English/Latin in narration
- ~22 words = ~14s at gTTS Telugu pace (1.6 words/sec for pure Telugu)

VOICE STRUCTURE (matches 8 video scenes):
0. నమస్కారం — greeting + city
1. తిథి పేరు చెప్పు (no time reading)
2. రాహు కాలం — warning (no time reading)  
3. దుర్ముహూర్తం — warning (no time reading)
4. బ్రహ్మ ముహూర్తం — auspicious (no time reading)
5. అభిజిత్ — auspicious (no time reading)
6. సూర్యోదయం సూర్యాస్తమయం (no time reading)
7. శుభాకాంక్షలు + subscribe

gTTS Telugu reads pure Telugu at ~1.6 words/sec
22 Telugu words = ~14 seconds — perfect sync
"""

import os, json
import anthropic


def tf(p, k):
    v = p.get(k, "N/A")
    return v if v and v != "" else "N/A"


def get_tithi_name(tithi_val):
    """Extract just the tithi name in Telugu — no English, no times."""
    # Map common tithi names to Telugu
    telugu_map = {
        "Ekadashi":  "ఏకాదశి",
        "Dwadashi":  "ద్వాదశి",
        "Trayodashi":"త్రయోదశి",
        "Chaturdashi":"చతుర్దశి",
        "Purnima":   "పూర్ణిమ",
        "Pratipada": "పాడ్యమి",
        "Dwitiya":   "విదియ",
        "Tritiya":   "తదియ",
        "Chaturthi": "చవితి",
        "Panchami":  "పంచమి",
        "Shashthi":  "షష్ఠి",
        "Saptami":   "సప్తమి",
        "Ashtami":   "అష్టమి",
        "Navami":    "నవమి",
        "Dashami":   "దశమి",
        "Amavasya":  "అమావాస్య",
    }
    for eng, tel in telugu_map.items():
        if eng.lower() in tithi_val.lower():
            return tel
    # fallback — return first word
    return tithi_val.split()[0] if tithi_val else "తిథి"


def get_paksha_telugu(paksha_val):
    if "Krishna" in paksha_val:
        return "కృష్ణ పక్షం"
    elif "Shukla" in paksha_val:
        return "శుక్ల పక్షం"
    return paksha_val


def generate_video_script(panchang):
    city     = panchang.get("city",     "USA")
    tz_label = panchang.get("tz_label", "ET")
    weekday  = panchang.get("weekday",  "")
    date_str = panchang.get("date",     "")
    paksha   = get_paksha_telugu(tf(panchang, "paksha"))
    tithi_name = get_tithi_name(tf(panchang, "tithi"))

    # Build the narration locally — no API needed for this structure
    # Pure Telugu, no time reading, ~22 words
    narration = (
        f"నమస్కారం! నేను మీ పంచాంగం గురువు. "
        f"{city} వారికి నేటి పంచాంగం. "
        f"నేడు {paksha} {tithi_name}. "
        f"రాహు కాలం సమయంలో కొత్త పని మొదలు పెట్టకండి. "
        f"దుర్ముహూర్తంలో శుభ కార్యాలు వద్దు. "
        f"బ్రహ్మ ముహూర్తం ప్రార్థనకు శ్రేష్ఠమైన సమయం. "
        f"అభిజిత్ ముహూర్తం ముఖ్యమైన పనులకు అనువైన సమయం. "
        f"మీకు శుభమైన రోజు కలగాలని ఆశిస్తున్నాను! "
        f"లైక్ చేయండి, షేర్ చేయండి, సబ్స్క్రైబ్ చేయండి!"
    )

    # Also use Claude API to generate a better version if available
    try:
        client = anthropic.Anthropic()

        prompt = f"""Write a Telugu voice narration for a 14-second Panchangam Instagram Reel.

STRICT RULES — READ CAREFULLY:
1. Write ONLY in Telugu script (తెలుగు లిపి) — NO English, NO numbers, NO time values
2. DO NOT read any times — the screen shows times, voice only says section names
3. Maximum 22 words total — HARD LIMIT (gTTS Telugu = 1.6 words/sec)
4. Structure: greeting → tithi name → rahu warning → durmuhurtam warning → brahma auspicious → abhijit auspicious → sunrise/sunset mention → blessing
5. Use natural conversational Telugu — not Sanskrit-heavy
6. Start with: నమస్కారం! నేను మీ పంచాంగం గురువు.

City: {city}
Tithi name in Telugu: {tithi_name}
Paksha: {paksha}

EXAMPLE of correct style (22 words):
నమస్కారం! నేను మీ పంచాంగం గురువు. {city} వారికి నేటి పంచాంగం. నేడు {paksha} {tithi_name}. రాహు కాలంలో జాగ్రత్త. బ్రహ్మ ముహూర్తం ప్రార్థనకు శ్రేష్ఠం. అభిజిత్ ముహూర్తం శుభం. మీకు మంచి రోజు కలగాలి! లైక్ చేయండి!

Return ONLY valid JSON, no markdown:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Rahu Kalam & All Timings",
  "description": "Today's complete Hindu Panchang for {city}. Rahu Kalam, Abhijit Muhurta, all auspicious and inauspicious timings.",
  "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","RahuKalam","Panchang","Shorts","Reels","TeluguAmerica","HinduAmerica","DailyBlessing"],
  "full_narration": "22-word pure Telugu narration here — NO English, NO times",
  "on_screen_lines": [
    "తిథి: {tithi_name} ({paksha})",
    "రాహు కాలం: {tf(panchang, 'rahukaal').split('|')[0].strip()} {tz_label}",
    "దుర్ముహూర్తం: {tf(panchang, 'durmuhurtam')} {tz_label}",
    "బ్రహ్మ ముహూర్తం: {tf(panchang, 'brahma_muhurta').split('|')[0].strip()} {tz_label}",
    "అభిజిత్: {tf(panchang, 'abhijit')} {tz_label}",
    "సూర్యోదయం: {tf(panchang, 'sunrise')} | సూర్యాస్తమయం: {tf(panchang, 'sunset')} {tz_label}"
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
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        result = json.loads(raw)

        # Validate: reject if narration contains digits or Latin chars
        narr = result.get("full_narration", "")
        has_digits = any(c.isdigit() for c in narr)
        has_latin  = any(c.isascii() and c.isalpha() for c in narr)
        word_count = len(narr.split())

        if has_digits or has_latin or word_count > 28:
            # API gave bad result — use local fallback
            result["full_narration"] = narration
        return result

    except Exception:
        pass

    # Full fallback
    return {
        "title":       f"Daily Panchangam {city} | {weekday} {date_str}",
        "description": f"Complete Hindu Panchang for {city}.",
        "hashtags":    ["DailyPanchangam", "TeluguPanchang", "HinduCalendar", "Shorts"],
        "full_narration": narration,
        "on_screen_lines": [
            f"తిథి: {tithi_name} ({paksha})",
            f"రాహు కాలం: {tf(panchang,'rahukaal').split('|')[0].strip()} {tz_label}",
            f"దుర్ముహూర్తం: {tf(panchang,'durmuhurtam')} {tz_label}",
            f"బ్రహ్మ ముహూర్తం: {tf(panchang,'brahma_muhurta').split('|')[0].strip()} {tz_label}",
            f"అభిజిత్: {tf(panchang,'abhijit')} {tz_label}",
            f"సూర్యోదయం: {tf(panchang,'sunrise')} | సూర్యాస్తమయం: {tf(panchang,'sunset')} {tz_label}",
        ]
    }
