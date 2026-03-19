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


CITY_GREETINGS = {
    "New York, NY":    "న్యూయార్క్ తెలుగు వారికి శుభోదయం.",
    "Chicago, IL":     "చికాగో తెలుగు వారికి శుభోదయం.",
    "Dallas, TX":      "డాలస్ తెలుగు వారికి శుభోదయం.",
    "Los Angeles, CA": "కాలిఫోర్నియా తెలుగు వారికి శుభోదయం.",
    "Detroit, MI":     "మిషిగన్ తెలుగు వారికి శుభోదయం.",
}

# Pause marker reference:
#   [SHORT_PAUSE]  = 300ms  — brief breath between short phrases
#   [PAUSE]        = 500ms  — natural sentence break
#   [LONG_PAUSE]   = 800ms  — paragraph-level pause (after greeting)


def tf(p, k):
    v = p.get(k, "N/A")
    return v if v and v != "" else "N/A"


def strip_tz(val, tz):
    """Remove embedded timezone label and take only the first slot."""
    val = val.split("|")[0].strip()
    return val.replace(f" {tz}", "").strip()


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


def get_nakshatra_telugu(nakshatra_val):
    """Extract nakshatra name in Telugu."""
    telugu_map = {
        "Ashwini": "అశ్విని", "Bharani": "భరణి", "Krittika": "కృత్తిక",
        "Rohini": "రోహిణి", "Mrigashira": "మృగశిర", "Ardra": "ఆర్ద్ర",
        "Punarvasu": "పునర్వసు", "Pushya": "పుష్యమి", "Ashlesha": "ఆశ్లేష",
        "Magha": "మఘ", "Purva Phalguni": "పూర్వ ఫల్గుణి",
        "Uttara Phalguni": "ఉత్తర ఫల్గుణి", "Hasta": "హస్త",
        "Chitra": "చిత్త", "Swati": "స్వాతి", "Vishakha": "విశాఖ",
        "Anuradha": "అనూరాధ", "Jyeshtha": "జ్యేష్ఠ", "Moola": "మూల",
        "Purva Ashadha": "పూర్వాషాఢ", "Uttara Ashadha": "ఉత్తరాషాఢ",
        "Shravana": "శ్రవణం", "Dhanishtha": "ధనిష్ఠ",
        "Shatabhisha": "శతభిష", "Purva Bhadrapada": "పూర్వ భాద్రపద",
        "Uttara Bhadrapada": "ఉత్తర భాద్రపద", "Revati": "రేవతి",
    }
    for eng, tel in telugu_map.items():
        if eng.lower() in nakshatra_val.lower():
            return tel
    return nakshatra_val.split()[0] if nakshatra_val else "నక్షత్రం"


def generate_video_script(panchang):
    city       = panchang.get("city",     "USA")
    tz_label   = panchang.get("tz_label", "ET")
    weekday    = panchang.get("weekday",  "")
    date_str   = panchang.get("date",     "")
    paksha     = get_paksha_telugu(tf(panchang, "paksha"))
    tithi_name = get_tithi_name(tf(panchang, "tithi"))
    nak_name   = get_nakshatra_telugu(tf(panchang, "nakshatra"))

    city_greeting = CITY_GREETINGS.get(city, f"{city} తెలుగు వారికి శుభోదయం!")

    # 4-scene narration — word counts must match video_creator.SCENE_WORD_COUNTS = [12, 9, 8, 10]
    # Scene 0 (~12w): greeting + city + tithi + nakshatra
    # Scene 1 (~9w):  rahu warning + durmuhurtam warning
    # Scene 2 (~8w):  brahma auspicious + abhijit auspicious
    # Scene 3 (~10w): blessing + save/share
    narration = (
        f"నమస్కారం! [SHORT_PAUSE] {city_greeting} [LONG_PAUSE] "
        f"నేడు {paksha} {tithi_name}. [SHORT_PAUSE] నక్షత్రం: {nak_name}. [PAUSE] "
        f"రాహుకాలంలో కొత్త పనులు వద్దు. [SHORT_PAUSE] దుర్ముహూర్తంలో శుభ కార్యాలు వద్దు. [PAUSE] "
        f"బ్రహ్మ ముహూర్తం ప్రార్థనకు ఉత్తమం. [SHORT_PAUSE] అభిజిత్ ముహూర్తం శుభం. [PAUSE] "
        f"మీకు శుభమైన రోజు కలగాలని ఆశిస్తున్నాను. [PAUSE] ధన్యవాదాలు. please like share and subscribe."
    )

    # Also use Claude API to generate a better version if available
    try:
        client = anthropic.Anthropic()

        prompt = f"""Write a Telugu voice narration for a 20-second Panchangam Instagram Reel.
The video has exactly 4 scenes. The narration must align word-count to each scene.

STRICT RULES:
1. Write ONLY in Telugu script — NO English letters, NO numbers, NO time values
2. DO NOT read any times — screen shows them
3. ~39 words total across 4 scenes, structure EXACTLY as below
4. Scene 0 (~12w): greeting + city greeting + today's tithi + nakshatra
5. Scene 1 (~9w):  rahu kalam warning + durmuhurtam warning
6. Scene 2 (~8w):  brahma muhurtam auspicious + abhijit auspicious
7. Scene 3 (~10w): blessing + save/share CTA

City: {city}
Tithi: {tithi_name}, Nakshatra: {nak_name}, Paksha: {paksha}

PAUSE MARKERS (use exactly as shown):
  [SHORT_PAUSE] = 300ms, [PAUSE] = 500ms, [LONG_PAUSE] = 800ms

EXAMPLE:
నమస్కారం! [SHORT_PAUSE] {city_greeting} [LONG_PAUSE] నేడు {paksha} {tithi_name}. [SHORT_PAUSE] నక్షత్రం: {nak_name}. [PAUSE] రాహుకాలంలో కొత్త పనులు వద్దు. [SHORT_PAUSE] దుర్ముహూర్తంలో శుభ కార్యాలు వద్దు. [PAUSE] బ్రహ్మ ముహూర్తం ప్రార్థనకు ఉత్తమం. [SHORT_PAUSE] అభిజిత్ ముహూర్తం శుభం. [PAUSE] మీకు శుభమైన రోజు కలగాలని ఆశిస్తున్నాను. [PAUSE] ధన్యవాదాలు. please like share and subscribe.

Return ONLY valid JSON, no markdown:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Rahu Kalam & All Timings",
  "description": "Today's complete Hindu Panchang for {city}. Rahu Kalam, Abhijit Muhurta, all auspicious and inauspicious timings.",
  "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","RahuKalam","Panchang","Shorts","Reels","TeluguAmerica","HinduAmerica","DailyBlessing"],
  "full_narration": "Telugu narration with [SHORT_PAUSE]/[PAUSE]/[LONG_PAUSE] markers — NO times, end with 'ధన్యవాదాలు. please like share and subscribe.'",
  "on_screen_lines": [
    "తిథి: {tithi_name} ({paksha})",
    "నక్షత్రం: nakshatra_name",
    "రాహు కాలం: stripped_rahu {tz_label}",
    "దుర్ముహూర్తం: stripped_dur {tz_label}",
    "బ్రహ్మ ముహూర్తం: stripped_brahma {tz_label}",
    "అభిజిత్: stripped_abhijit {tz_label}",
    "సూర్యోదయం: stripped_sunrise | సూర్యాస్తమయం: stripped_sunset {tz_label}"
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

        # Validate: reject if narration contains digits or unexpected Latin chars
        # Strip allowed markers/English CTA before checking
        import re as _re
        narr = result.get("full_narration", "")
        narr_check = _re.sub(r'\[(SHORT_PAUSE|PAUSE|LONG_PAUSE)\]', '', narr)
        narr_check = narr_check.replace("please like share and subscribe", "")
        narr_check = narr_check.replace("ధన్యవాదాలు.", "")
        has_digits = any(c.isdigit() for c in narr_check)
        has_latin  = any(c.isascii() and c.isalpha() for c in narr_check)
        word_count = len(narr.split())

        if has_digits or has_latin or word_count > 60:
            # API gave bad result — use local fallback
            result["full_narration"] = narration

        nakshatra_raw = tf(panchang, "nakshatra").split()[0] if tf(panchang, "nakshatra") != "N/A" else "N/A"
        # Always override on_screen_lines with correctly formatted (no double tz) values
        result["on_screen_lines"] = [
            f"తిథి: {tithi_name} ({paksha})",
            f"నక్షత్రం: {nakshatra_raw}",
            f"రాహు కాలం: {strip_tz(tf(panchang,'rahukaal'), tz_label)} {tz_label}",
            f"దుర్ముహూర్తం: {strip_tz(tf(panchang,'durmuhurtam'), tz_label)} {tz_label}",
            f"బ్రహ్మ ముహూర్తం: {strip_tz(tf(panchang,'brahma_muhurta'), tz_label)} {tz_label}",
            f"అభిజిత్: {strip_tz(tf(panchang,'abhijit'), tz_label)} {tz_label}",
            f"సూర్యోదయం: {strip_tz(tf(panchang,'sunrise'), tz_label)} | సూర్యాస్తమయం: {strip_tz(tf(panchang,'sunset'), tz_label)} {tz_label}",
        ]
        return result

    except Exception:
        pass

    nakshatra_raw = tf(panchang, "nakshatra").split()[0] if tf(panchang, "nakshatra") != "N/A" else "N/A"

    # Full fallback
    return {
        "title":       f"Daily Panchangam {city} | {weekday} {date_str}",
        "description": f"Complete Hindu Panchang for {city}.",
        "hashtags":    ["DailyPanchangam", "TeluguPanchang", "HinduCalendar", "Shorts"],
        "full_narration": narration,
        "on_screen_lines": [
            f"తిథి: {tithi_name} ({paksha})",
            f"నక్షత్రం: {nakshatra_raw}",
            f"రాహు కాలం: {strip_tz(tf(panchang,'rahukaal'), tz_label)} {tz_label}",
            f"దుర్ముహూర్తం: {strip_tz(tf(panchang,'durmuhurtam'), tz_label)} {tz_label}",
            f"బ్రహ్మ ముహూర్తం: {strip_tz(tf(panchang,'brahma_muhurta'), tz_label)} {tz_label}",
            f"అభిజిత్: {strip_tz(tf(panchang,'abhijit'), tz_label)} {tz_label}",
            f"సూర్యోదయం: {strip_tz(tf(panchang,'sunrise'), tz_label)} | సూర్యాస్తమయం: {strip_tz(tf(panchang,'sunset'), tz_label)} {tz_label}",
        ]
    }
