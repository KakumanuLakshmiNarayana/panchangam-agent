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
    "New York, NY":    "New York Telugu nesthalaku shubhodayam.",
    "Chicago, IL":     "Chicago Telugu nesthalaku shubhodayam.",
    "Dallas, TX":      "Dallas Telugu nesthalaku shubhodayam.",
    "Los Angeles, CA": "Los Angeles Telugu nesthalaku shubhodayam.",
    "Detroit, MI":     "Detroit Telugu nesthalaku shubhodayam.",
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
    """Extract just the tithi name in romanized Telugu pronunciation."""
    # Map common tithi names to romanized Telugu pronunciation
    roman_map = {
        "Ekadashi":   "Ekadashi",
        "Dwadashi":   "Dwadashi",
        "Trayodashi": "Trayodashi",
        "Chaturdashi":"Chaturdashi",
        "Purnima":    "Purnima",
        "Pratipada":  "Padyami",
        "Dwitiya":    "Vidiya",
        "Tritiya":    "Tadiya",
        "Chaturthi":  "Chaviti",
        "Panchami":   "Panchami",
        "Shashthi":   "Shashti",
        "Saptami":    "Saptami",
        "Ashtami":    "Ashtami",
        "Navami":     "Navami",
        "Dashami":    "Dashami",
        "Amavasya":   "Amavasya",
    }
    for eng, roman in roman_map.items():
        if eng.lower() in tithi_val.lower():
            return roman
    # fallback — return first word
    return tithi_val.split()[0] if tithi_val else "Tithi"


def get_paksha_telugu(paksha_val):
    if "Krishna" in paksha_val:
        return "Krishna Paksham"
    elif "Shukla" in paksha_val:
        return "Shukla Paksham"
    return paksha_val


def get_nakshatra_telugu(nakshatra_val):
    """Extract nakshatra name in romanized Telugu pronunciation."""
    roman_map = {
        "Ashwini": "Ashwini", "Bharani": "Bharani", "Krittika": "Krittika",
        "Rohini": "Rohini", "Mrigashira": "Mrigashira", "Ardra": "Ardra",
        "Punarvasu": "Punarvasu", "Pushya": "Pushyami", "Ashlesha": "Ashlesha",
        "Magha": "Magha", "Purva Phalguni": "Purva Phalguni",
        "Uttara Phalguni": "Uttara Phalguni", "Hasta": "Hasta",
        "Chitra": "Chitta", "Swati": "Swati", "Vishakha": "Vishakha",
        "Anuradha": "Anuradha", "Jyeshtha": "Jyeshtha", "Moola": "Moola",
        "Purva Ashadha": "Purva Ashadha", "Uttara Ashadha": "Uttara Ashadha",
        "Shravana": "Shravana", "Dhanishtha": "Dhanishtha",
        "Shatabhisha": "Shatabhisha", "Purva Bhadrapada": "Purva Bhadrapada",
        "Uttara Bhadrapada": "Uttara Bhadrapada", "Revati": "Revati",
    }
    for eng, roman in roman_map.items():
        if eng.lower() in nakshatra_val.lower():
            return roman
    return nakshatra_val.split()[0] if nakshatra_val else "Nakshatram"


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
        f"Namaskaram. [SHORT_PAUSE] {city_greeting} [LONG_PAUSE] "
        f"Eeroju {paksha}, {tithi_name} tithi. [SHORT_PAUSE] Nakshatram {nak_name}. [PAUSE] "
        f"Rahu kalam samayamlo kotta panulu modalupettakandi. [SHORT_PAUSE] Durmuhurtam samayamlo shubhakaryaalu nivarinchandi. [PAUSE] "
        f"Brahma muhurtam prarthana mariyu dhyananiki uttamam. [SHORT_PAUSE] Abhijit muhurtam mukhyamaina panulaku shubhapradam. [PAUSE] "
        f"Meeku ee roju shubhapradanga, anandanga gadavaalni manahpoorvanga aasisthunnanu. [PAUSE] Namaskaram. Like cheyandi, kutumba sabhyulato share cheyandi, PanthuluPanchangam subscribe chesukundi."
    )

    # Also use Claude API to generate a better version if available
    try:
        client = anthropic.Anthropic()

        prompt = f"""Write a Telugu voice narration for a 20-second Panchangam Instagram Reel.
The video has exactly 4 scenes. The narration must align word-count to each scene.

CRITICAL: Write the narration in ROMANIZED Telugu (Telugu words spelled in English letters).
This is for ElevenLabs TTS which pronounces romanized Telugu correctly.
Do NOT use Telugu script characters. Write everything phonetically in English letters.

STRICT RULES:
1. Write in ROMANIZED Telugu (English letters, Telugu pronunciation) — NO Telugu script characters
2. NO time values (screen shows them)
3. ~39 words total across 4 scenes, structure EXACTLY as below
4. Scene 0 (~12w): greeting + city greeting + today's paksha + tithi + nakshatra
5. Scene 1 (~9w):  rahu kalam warning + durmuhurtam warning
6. Scene 2 (~8w):  brahma muhurtam auspicious + abhijit auspicious
7. Scene 3 (~10w): blessing + CTA

VOCABULARY RULES (follow exactly for correct pronunciation):
- Start with "Namaskaram."
- City greeting format: "<CityName> Telugu nesthalaku shubhodayam."
- Use "Eeroju" NOT "naadu"
- Use "Rahu kalam samayamlo kotta panulu modalupettakandi"
- Use "Durmuhurtam samayamlo shubhakaryaalu nivarinchandi"
- Use "Brahma muhurtam prarthana mariyu dhyananiki uttamam"
- Use "Abhijit muhurtam mukhyamaina panulaku shubhapradam"
- Use "Meeku ee roju shubhapradanga, anandanga gadavaalni manahpoorvanga aasisthunnanu"
- End with: "Namaskaram. Like cheyandi, kutumba sabhyulato share cheyandi, PanthuluPanchangam subscribe chesukundi."

City: {city}
Tithi: {tithi_name}, Nakshatra: {nak_name}, Paksha: {paksha}

PAUSE MARKERS (use exactly as shown):
  [SHORT_PAUSE] = 300ms, [PAUSE] = 500ms, [LONG_PAUSE] = 800ms

EXAMPLE OUTPUT (follow this structure precisely):
Namaskaram. [SHORT_PAUSE] {city_greeting} [LONG_PAUSE] Eeroju {paksha}, {tithi_name} tithi. [SHORT_PAUSE] Nakshatram {nak_name}. [PAUSE] Rahu kalam samayamlo kotta panulu modalupettakandi. [SHORT_PAUSE] Durmuhurtam samayamlo shubhakaryaalu nivarinchandi. [PAUSE] Brahma muhurtam prarthana mariyu dhyananiki uttamam. [SHORT_PAUSE] Abhijit muhurtam mukhyamaina panulaku shubhapradam. [PAUSE] Meeku ee roju shubhapradanga, anandanga gadavaalni manahpoorvanga aasisthunnanu. [PAUSE] Namaskaram. Like cheyandi, kutumba sabhyulato share cheyandi, PanthuluPanchangam subscribe chesukundi.

Return ONLY valid JSON, no markdown:
{{
  "title": "Daily Panchangam {city} | {weekday} {date_str} | Rahu Kalam & All Timings",
  "description": "Today's complete Hindu Panchang for {city}. Rahu Kalam, Abhijit Muhurta, all auspicious and inauspicious timings.",
  "hashtags": ["DailyPanchangam","TeluguPanchang","HinduCalendar","RahuKalam","Panchang","Shorts","Reels","TeluguAmerica","HinduAmerica","DailyBlessing"],
  "full_narration": "Romanized Telugu narration with pause markers — NO times, end with 'Namaskaram. Like cheyandi, kutumba sabhyulato share cheyandi, PanthuluPanchangam subscribe chesukundi.'",
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
            model="claude-sonnet-4-6",
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

        # Validate: reject if narration contains unexpected digits (time values)
        # Romanized Telugu is expected — Latin chars are correct now
        import re as _re
        narr = result.get("full_narration", "")
        narr_check = _re.sub(r'\[(SHORT_PAUSE|PAUSE|LONG_PAUSE)\]', '', narr)
        has_digits = any(c.isdigit() for c in narr_check)
        word_count = len(narr.split())

        if has_digits or word_count > 80:
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
