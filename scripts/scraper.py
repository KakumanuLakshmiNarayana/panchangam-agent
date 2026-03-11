"""
scraper.py — Fetches daily Panchangam data from drikpanchang.com
and converts all timings to all 6 US time zones.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import json
import re
import sys
from zoneinfo import ZoneInfo

US_ZONES = {
    "Eastern":  "America/New_York",
    "Central":  "America/Chicago",
    "Mountain": "America/Denver",
    "Pacific":  "America/Los_Angeles",
    "Alaska":   "America/Anchorage",
    "Hawaii":   "Pacific/Honolulu",
}

INDIA_ZONE = "Asia/Kolkata"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
}


def fetch_panchang_page(target_date):
    url = (
        f"https://www.drikpanchang.com/panchang/day-panchang.html"
        f"?date={target_date.strftime('%d/%m/%Y')}"
    )
    print(f"[scraper] Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def ist_to_us(time_str, ref_date):
    if not time_str or time_str.strip() in ("—", "-", "", "N/A"):
        return {z: "N/A" for z in US_ZONES}
    time_str = time_str.strip().replace("\xa0", " ")
    naive = None
    for fmt in ("%I:%M %p", "%H:%M", "%I:%M%p", "%I:%M %P"):
        try:
            naive = datetime.strptime(time_str, fmt)
            break
        except ValueError:
            pass
    if naive is None:
        return {z: time_str for z in US_ZONES}
    ist = ZoneInfo(INDIA_ZONE)
    aware_ist = datetime(
        ref_date.year, ref_date.month, ref_date.day,
        naive.hour, naive.minute, tzinfo=ist
    )
    result = {}
    for zone_name, zone_id in US_ZONES.items():
        us_tz = ZoneInfo(zone_id)
        us_time = aware_ist.astimezone(us_tz)
        result[zone_name] = us_time.strftime("%I:%M %p %Z")
    return result


def find_row_value(soup, label_text):
    for td in soup.find_all("td"):
        txt = td.get_text(strip=True)
        if label_text.lower() in txt.lower():
            sib = td.find_next_sibling("td")
            if sib:
                return sib.get_text(separator=" ", strip=True)
    # Also try divs/spans with dpTableValue class
    for span in soup.find_all(string=re.compile(label_text, re.I)):
        parent = span.parent
        if parent:
            nxt = parent.find_next_sibling()
            if nxt:
                return nxt.get_text(separator=" ", strip=True)
    return ""


def extract_first_time(s):
    m = re.search(r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)", s)
    return m.group(0).strip() if m else ""


def extract_time_range(s):
    times = re.findall(r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)", s)
    return times


def parse_panchang(soup, ref_date):
    data = {
        "date": ref_date.isoformat(),
        "weekday": ref_date.strftime("%A"),
        "raw": {},
        "us_timings": {}
    }

    fields = {
        "tithi":        ["Tithi"],
        "nakshatra":    ["Nakshatra"],
        "yoga":         ["Yoga"],
        "karana":       ["Karana"],
        "sunrise":      ["Sunrise"],
        "sunset":       ["Sunset"],
        "moonrise":     ["Moonrise"],
        "moonset":      ["Moonset"],
        "rahukalam":    ["Rahukalam", "Rahu Kalam"],
        "yamagandam":   ["Yamagandam", "Yama Gandam"],
        "gulikai":      ["Gulikai", "Gulikakalam"],
        "durmuhurtam":  ["Durmuhurtam", "Dur Muhurtam", "Durmuhurta"],
        "abhijit":      ["Abhijit Muhurta", "Abhijit"],
        "amrit_kalam":  ["Amrit Kalam", "Amritkalam"],
        "varjyam":      ["Varjyam", "Varjam"],
        "shaka_samvat": ["Shaka Samvat", "Vikram Samvat"],
    }

    for key, labels in fields.items():
        for label in labels:
            val = find_row_value(soup, label)
            if val:
                data["raw"][key] = val
                break
        if key not in data["raw"]:
            data["raw"][key] = "N/A"

    # Convert time-based fields to US timings
    time_fields = [
        ("sunrise",     "Sunrise"),
        ("sunset",      "Sunset"),
        ("moonrise",    "Moonrise"),
        ("moonset",     "Moonset"),
        ("rahukalam",   "Rahukalam"),
        ("yamagandam",  "Yamagandam"),
        ("gulikai",     "Gulikai"),
        ("durmuhurtam", "Durmuhurtam"),
        ("abhijit",     "Abhijit"),
        ("amrit_kalam", "AmritKalam"),
        ("varjyam",     "Varjyam"),
    ]

    for raw_key, us_key in time_fields:
        raw_val = data["raw"].get(raw_key, "")
        times = extract_time_range(raw_val)
        if len(times) >= 2:
            data["us_timings"][f"{us_key}_Start"] = ist_to_us(times[0], ref_date)
            data["us_timings"][f"{us_key}_End"]   = ist_to_us(times[1], ref_date)
        elif len(times) == 1:
            data["us_timings"][us_key] = ist_to_us(times[0], ref_date)
        else:
            first = extract_first_time(raw_val)
            if first:
                data["us_timings"][us_key] = ist_to_us(first, ref_date)

    return data


def run(target_date=None):
    if target_date is None:
        target_date = date.today()
    soup = fetch_panchang_page(target_date)
    panchang = parse_panchang(soup, target_date)
    return panchang


if __name__ == "__main__":
    d = date.today()
    if len(sys.argv) > 1:
        d = date.fromisoformat(sys.argv[1])
    result = run(d)
    out_path = f"panchang_{d.isoformat()}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[scraper] Saved to {out_path}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
