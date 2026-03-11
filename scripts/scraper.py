"""
scraper.py — Fetches Panchang for 5 Telugu-American cities from Drikpanchang
Each city gets its own URL with lat/long so timings are location-accurate.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import json, re, sys
from zoneinfo import ZoneInfo

# ── 5 Telugu-American cities with their Drikpanchang location params ──────────
CITIES = {
    "New_York": {
        "display":  "New York, NY",
        "timezone": "America/New_York",
        "tz_label": "ET",
        "lat": "40.71",
        "lon": "-74.00",
        "place": "New+York",
    },
    "Chicago": {
        "display":  "Chicago, IL",
        "timezone": "America/Chicago",
        "tz_label": "CT",
        "lat": "41.85",
        "lon": "-87.65",
        "place": "Chicago",
    },
    "Dallas": {
        "display":  "Dallas, TX",
        "timezone": "America/Chicago",
        "tz_label": "CT",
        "lat": "32.78",
        "lon": "-96.80",
        "place": "Dallas",
    },
    "California": {
        "display":  "Los Angeles, CA",
        "timezone": "America/Los_Angeles",
        "tz_label": "PT",
        "lat": "34.05",
        "lon": "-118.24",
        "place": "Los+Angeles",
    },
    "Michigan": {
        "display":  "Detroit, MI",
        "timezone": "America/Detroit",
        "tz_label": "ET",
        "lat": "42.33",
        "lon": "-83.05",
        "place": "Detroit",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
}

INDIA_ZONE = "Asia/Kolkata"


def fetch_panchang_page(target_date, city_key="New_York"):
    """Fetch Drikpanchang page for a specific city and date."""
    city = CITIES[city_key]
    url = (
        f"https://www.drikpanchang.com/panchang/day-panchang.html"
        f"?date={target_date.strftime('%d/%m/%Y')}"
        f"&place={city['place']}"
        f"&lang=en"
    )
    print(f"[scraper] Fetching {city['display']}: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def find_value(soup, *labels):
    """Find a table value by searching for label text."""
    for label in labels:
        # Try td siblings
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if label.lower() in txt.lower() and len(txt) < 60:
                sib = td.find_next_sibling("td")
                if sib:
                    val = sib.get_text(separator=" ", strip=True)
                    if val and len(val) < 200:
                        return val
        # Try div/span with text
        for tag in soup.find_all(string=re.compile(re.escape(label), re.I)):
            parent = tag.parent
            if parent:
                nxt = parent.find_next_sibling()
                if nxt:
                    val = nxt.get_text(separator=" ", strip=True)
                    if val and len(val) < 200:
                        return val
    return "N/A"


def extract_times(s):
    """Extract all HH:MM AM/PM patterns from a string."""
    return re.findall(r"\d{1,2}:\d{2}\s*(?:AM|PM)", s, re.I)


def parse_time_to_local(time_str, ref_date, city_key):
    """Parse a time string (already in local city time from Drikpanchang) and format it."""
    if not time_str or time_str.strip() in ("N/A", "—", ""):
        return "N/A"
    time_str = time_str.strip()
    for fmt in ("%I:%M %p", "%I:%M%p"):
        try:
            t = datetime.strptime(time_str.upper(), fmt)
            return t.strftime("%I:%M %p")
        except ValueError:
            pass
    return time_str


def format_range(times, ref_date, city_key):
    """Format a start-end time pair."""
    tz_label = CITIES[city_key]["tz_label"]
    if len(times) >= 2:
        s = parse_time_to_local(times[0], ref_date, city_key)
        e = parse_time_to_local(times[1], ref_date, city_key)
        return f"{s} – {e} {tz_label}"
    elif len(times) == 1:
        s = parse_time_to_local(times[0], ref_date, city_key)
        return f"{s} {tz_label}"
    return "N/A"


def parse_panchang(soup, ref_date, city_key):
    """Parse all Panchang fields from the page."""
    city = CITIES[city_key]
    data = {
        "date":     ref_date.isoformat(),
        "weekday":  ref_date.strftime("%A"),
        "city_key": city_key,
        "city":     city["display"],
        "timezone": city["timezone"],
        "tz_label": city["tz_label"],
    }

    # ── Non-time fields ─────────────────────────────────────────
    data["tithi"]    = find_value(soup, "Tithi")
    data["nakshatra"]= find_value(soup, "Nakshatra")
    data["yoga"]     = find_value(soup, "Yoga")
    data["karana"]   = find_value(soup, "Karana")
    data["masa"]     = find_value(soup, "Masa", "Month")
    data["paksha"]   = find_value(soup, "Paksha")
    data["samvat"]   = find_value(soup, "Samvat", "Vikram")

    # Clean up tithi — remove long descriptions, keep just the name
    if data["tithi"] and len(data["tithi"]) > 60:
        # Take just the first meaningful part
        parts = re.split(r'[,.]', data["tithi"])
        data["tithi"] = parts[0].strip()

    # ── Time fields (Drikpanchang shows local city time when location given) ──
    time_fields = [
        ("sunrise",      ["Sunrise"]),
        ("sunset",       ["Sunset"]),
        ("moonrise",     ["Moonrise"]),
        ("moonset",      ["Moonset"]),
        ("rahukaal",     ["Rahu Kalam", "Rahukalam", "Rahu Kaal"]),
        ("yamagandam",   ["Yamagandam", "Yama Gandam"]),
        ("gulika",       ["Gulika", "Gulikai", "Gulika Kalam"]),
        ("durmuhurtam",  ["Durmuhurtam", "Dur Muhurtam"]),
        ("abhijit",      ["Abhijit Muhurta", "Abhijit"]),
        ("amrit_kalam",  ["Amrit Kalam", "Amritkalam"]),
        ("varjyam",      ["Varjyam", "Varjam"]),
        ("shubh_muhurat",["Shubh Muhurat", "Shubha Muhurta"]),
    ]

    for key, labels in time_fields:
        raw_val = find_value(soup, *labels)
        times   = extract_times(raw_val)
        data[key] = format_range(times, ref_date, city_key)
        data[f"{key}_raw"] = raw_val

    return data


def run(target_date=None, city_key="New_York"):
    """Fetch panchang for one city."""
    if target_date is None:
        target_date = date.today()
    soup    = fetch_panchang_page(target_date, city_key)
    panchang = parse_panchang(soup, target_date, city_key)
    return panchang


def run_all_cities(target_date=None):
    """Fetch panchang for all 5 cities. Returns dict keyed by city."""
    if target_date is None:
        target_date = date.today()
    results = {}
    for city_key in CITIES:
        try:
            results[city_key] = run(target_date, city_key)
            print(f"  ✅ {CITIES[city_key]['display']} done")
        except Exception as e:
            print(f"  ❌ {CITIES[city_key]['display']} failed: {e}")
            results[city_key] = {"city": CITIES[city_key]["display"], "error": str(e)}
    return results


if __name__ == "__main__":
    d = date.today()
    if len(sys.argv) > 1:
        d = date.fromisoformat(sys.argv[1])
    results = run_all_cities(d)
    print(json.dumps(results, indent=2, ensure_ascii=False))
