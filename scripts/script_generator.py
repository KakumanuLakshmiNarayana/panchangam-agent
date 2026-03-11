"""
script_generator.py — Uses Claude API to generate Telugu+English
bilingual narration script from Panchangam data.
"""

import json
import os
import sys
import anthropic
from datetime import date


def generate_script(panchang_data: dict) -> dict:
    """Generate Telugu+English video script from panchang JSON."""
    
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    
    d = panchang_data
    raw = d.get("raw", {})
    us = d.get("us_timings", {})
    target_date = d.get("date", date.today().isoformat())
    weekday = d.get("weekday", "")

    # Build timing summary for prompt
    timing_lines = []
    
    def fmt_range(key_start, key_end, label):
        s = us.get(key_start, {})
        e = us.get(key_end, {})
        if s and e:
            et_s = s.get("Eastern", "N/A")
            ct_s = s.get("Central", "N/A")
            pt_s = s.get("Pacific", "N/A")
            et_e = e.get("Eastern", "N/A")
            return f"{label}: ET {et_s}–{et_e} | CT {ct_s} | PT {pt_s}"
        return ""

    timing_lines.append(fmt_range("Sunrise", "Sunrise", "🌅 Sunrise"))
    timing_lines.append(fmt_range("Sunset", "Sunset", "🌇 Sunset"))
    timing_lines.append(fmt_range("Rahukalam_Start", "Rahukalam_End", "⚠️ Rahu Kalam (AVOID)"))
    timing_lines.append(fmt_range("Durmuhurtam_Start", "Durmuhurtam_End", "⚠️ Dur Muhurtam (AVOID)"))
    timing_lines.append(fmt_range("Yamagandam_Start", "Yamagandam_End", "⚠️ Yamagandam (AVOID)"))
    timing_lines.append(fmt_range("Gulikai_Start", "Gulikai_End", "⚠️ Gulikai Kalam (AVOID)"))
    timing_lines.append(fmt_range("Abhijit_Start", "Abhijit_End", "✅ Abhijit Muhurta (AUSPICIOUS)"))
    timing_lines.append(fmt_range("AmritKalam_Start", "AmritKalam_End", "✅ Amrit Kalam (AUSPICIOUS)"))
    timing_lines = [t for t in timing_lines if t]

    prompt = f"""You are creating a 60-second bilingual (Telugu + English) daily Panchangam video script for Hindu devotees living in the USA.

DATE: {weekday}, {target_date}

PANCHANGAM DATA:
- Tithi: {raw.get('tithi', 'N/A')}
- Nakshatra: {raw.get('nakshatra', 'N/A')}
- Yoga: {raw.get('yoga', 'N/A')}
- Karana: {raw.get('karana', 'N/A')}

TIMINGS (converted to US time zones):
{chr(10).join(timing_lines)}

INSTRUCTIONS:
1. Write a warm, devotional narration script mixing Telugu and English naturally (like a Telugu-American pandit would speak).
2. Start with a Sanskrit/Telugu greeting shloka (2 lines).
3. Announce the date and Panchangam details in Telugu first, then English.
4. Clearly state ALL inauspicious times (Rahu Kalam, Dur Muhurtam, Yamagandam, Gulikai) with a gentle warning.
5. Clearly state ALL auspicious times (Abhijit, Amrit Kalam) with encouragement.
6. Give timings for Eastern, Central, and Pacific time zones at minimum.
7. End with a Telugu blessing.
8. Total script: 60 seconds when read at natural pace (~130 words/minute = ~130 words max).
9. Format as JSON with these keys:
   - "opening_shloka": string (Sanskrit/Telugu greeting)
   - "main_narration": string (full bilingual script, ~120 words)  
   - "closing_blessing": string (Telugu/Sanskrit blessing, ~10 words)
   - "video_title": string (catchy English+Telugu title for YouTube/Instagram, max 60 chars)
   - "video_description": string (YouTube description, 150 words, with hashtags)
   - "text_overlays": array of objects with "timestamp_sec" and "text" for on-screen captions
   - "thumbnail_text": string (3-5 words for thumbnail)

Return ONLY valid JSON, no markdown fences."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    raw_text = message.content[0].text.strip()
    # Remove markdown fences if present
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    
    script = json.loads(raw_text)
    script["panchang_date"] = target_date
    script["weekday"] = weekday
    return script


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script_generator.py <panchang.json>")
        sys.exit(1)
    
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        panchang = json.load(f)
    
    script = generate_script(panchang)
    out_path = f"script_{panchang['date']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
    print(f"[script_gen] Saved to {out_path}")
    print(json.dumps(script, indent=2, ensure_ascii=False))
