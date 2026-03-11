"""
script_generator.py — Uses Claude API to write Telugu+English narration
Works with the scraper.run() output format.
"""
import os, json
import anthropic


def get_et_range(panchang, field):
    """Extract Eastern time range string from panchang us_timings."""
    us = panchang.get("us_timings", {})
    s_key, e_key = f"{field}_Start", f"{field}_End"
    if s_key in us and e_key in us:
        s = us[s_key].get("Eastern", "N/A")
        e = us[e_key].get("Eastern", "N/A")
        return f"{s} to {e}"
    if field in us:
        return us[field].get("Eastern", "N/A")
    return panchang.get("raw", {}).get(field.lower(), "N/A")


def format_for_prompt(panchang):
    raw = panchang.get("raw", {})
    lines = [
        f"Date: {panchang.get('weekday','')} {panchang.get('date','')}",
        f"Tithi: {raw.get('tithi','N/A')}",
        f"Nakshatra: {raw.get('nakshatra','N/A')}",
        f"Yoga: {raw.get('yoga','N/A')}",
        f"Karana: {raw.get('karana','N/A')}",
        "",
        "=== US TIMINGS (Eastern Time) ===",
        f"Rahukaal:    {get_et_range(panchang, 'Rahukalam')}",
        f"Durmuhurtam: {get_et_range(panchang, 'Durmuhurtam')}",
        f"Gulika:      {get_et_range(panchang, 'Gulikai')}",
        f"Yamagandam:  {get_et_range(panchang, 'Yamagandam')}",
        f"Abhijit:     {get_et_range(panchang, 'Abhijit')}",
        f"Amrit Kalam: {get_et_range(panchang, 'AmritKalam')}",
        f"Sunrise:     {get_et_range(panchang, 'Sunrise')}",
        f"Sunset:      {get_et_range(panchang, 'Sunset')}",
    ]
    return "\n".join(lines)


def generate_video_script(panchang):
    client = anthropic.Anthropic()
    summary = format_for_prompt(panchang)
    raw = panchang.get("raw", {})

    prompt = f"""You are creating a 60-second short-form video script for daily Hindu Panchang 
targeted at Telugu-speaking Hindu Americans. Mix Telugu and English naturally.

Today's Panchang:
{summary}

Return ONLY valid JSON (no markdown, no backticks):
{{
  "title": "YouTube/Instagram title with date in English (max 80 chars)",
  "description": "50-word English description for YouTube",
  "hashtags": ["DailyPanchangam","HinduCalendar","Telugu","Panchang","Shorts"],
  "full_narration": "Complete 60-second Telugu+English script (130-150 words). Start with a Telugu blessing, cover Rahukaal to avoid, Abhijit muhurta to use, Tithi and Nakshatra, end with Telugu blessing.",
  "on_screen_lines": [
    "Line 1 shown on screen",
    "Line 2 shown on screen",
    "Line 3 shown on screen",
    "Line 4 shown on screen"
  ]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = message.content[0].text.strip()
    # Strip markdown fences if present
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Fallback script if JSON parse fails
        return {
            "title": f"Daily Panchangam {panchang.get('date','')} | {raw.get('tithi','')} Tithi",
            "description": "Daily Hindu Panchang timings for all US time zones. Telugu & English.",
            "hashtags": ["DailyPanchangam","HinduCalendar","Telugu","Panchang","Shorts","Reels"],
            "full_narration": (
                f"నమస్కారం! Today is {panchang.get('weekday','')}. "
                f"Tithi: {raw.get('tithi','')}. Nakshatra: {raw.get('nakshatra','')}. "
                f"Rahukaal Eastern Time: {get_et_range(panchang,'Rahukalam')} — please avoid important work. "
                f"Abhijit Muhurta: {get_et_range(panchang,'Abhijit')} — very auspicious time. "
                f"మీకు శుభమగుగాక! Jay Srimannarayana!"
            ),
            "on_screen_lines": [
                f"Tithi: {raw.get('tithi','')}",
                f"Nakshatra: {raw.get('nakshatra','')}",
                f"Rahukaal (ET): {get_et_range(panchang,'Rahukalam')}",
                f"Abhijit (ET): {get_et_range(panchang,'Abhijit')}",
            ]
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            panchang = json.load(f)
    else:
        from scraper import run
        from datetime import date
        panchang = run(date.today())
    result = generate_video_script(panchang)
    print(json.dumps(result, indent=2, ensure_ascii=False))
