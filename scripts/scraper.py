"""
scraper.py — Fetches Panchang for 5 Telugu-American cities using exact geoname-id URLs.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import json, re, sys
from zoneinfo import ZoneInfo

CITIES = {
    "New_York": {
        "display":   "New York, NY",
        "timezone":  "America/New_York",
        "tz_label":  "ET",
        "geoname_id": "5128581",
    },
    "Chicago": {
        "display":   "Chicago, IL",
        "timezone":  "America/Chicago",
        "tz_label":  "CT",
        "geoname_id": "4887398",
    },
    "Dallas": {
        "display":   "Dallas, TX",
        "timezone":  "America/Chicago",
        "tz_label":  "CT",
        "geoname_id": "4684888",
    },
    "California": {
        "display":   "Los Angeles, CA",
        "timezone":  "America/Los_Angeles",
        "tz_label":  "PT",
        "geoname_id": "4350049",
    },
    "Michigan": {
        "display":   "Detroit, MI",
        "timezone":  "America/Detroit",
        "tz_label":  "ET",
        "geoname_id": "4990729",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_page(target_date, city_key):
    city     = CITIES[city_key]
    date_str = target_date.strftime("%d/%m/%Y")
    url = (
        f"https://www.drikpanchang.com/panchang/day-panchang.html"
        f"?geoname-id={city['geoname_id']}&date={date_str}"
    )
    print(f"[scraper] {city['display']}: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def extract_times(text):
    return re.findall(r"\d{1,2}:\d{2}\s*(?:AM|PM)", text, re.I)


def clean_time(t):
    t = t.strip().upper().replace(" ", "")
    for fmt in ("%I:%M%p", "%H:%M"):
        try:
            return datetime.strptime(t, fmt).strftime("%I:%M %p")
        except:
            pass
    return t.strip()


def fmt(times, tz_label):
    if len(times) >= 2:
        return f"{clean_time(times[0])} – {clean_time(times[1])} {tz_label}"
    elif len(times) == 1:
        return f"{clean_time(times[0])} {tz_label}"
    return "N/A"


def parse_all_rows(soup, tz_label):
    """
    Scan every <tr> on the page.
    Each row has pairs of cells: label | value | label | value
    Build a flat dict of {label_lower: formatted_value}
    """
    result = {}
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        # Process in pairs
        for i in range(0, len(cells) - 1, 2):
            if i + 1 >= len(cells):
                break
            label = cells[i].get_text(separator=" ", strip=True)
            value = cells[i+1].get_text(separator=" ", strip=True)

            if not label or len(label) > 80:
                continue

            key = label.lower().strip()
            # Remove any Ω or special symbols from label
            key = re.sub(r'[^\w\s]', '', key).strip()

            times = extract_times(value)
            if times:
                result[key] = fmt(times, tz_label)
            elif value and len(value) < 150:
                result[key] = value.strip()

    return result


def lookup(table, *keys):
    """Try multiple key variants to find a value."""
    for key in keys:
        k = key.lower().strip()
        # Exact match
        if k in table:
            return table[k]
        # Partial match — key is contained in a table key
        for tk, tv in table.items():
            if k in tk and "raw" not in tk:
                return tv
    return "N/A"


def find_text_field(soup, *labels):
    """Find plain text value (Tithi name, Nakshatra etc.) from table rows."""
    for label in labels:
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            # Match label exactly or as start of cell
            if txt.lower().strip() == label.lower().strip():
                nxt = td.find_next_sibling("td")
                if nxt:
                    val = nxt.get_text(separator=" ", strip=True)
                    if val and len(val) < 200:
                        return val
            # Also try: label is contained in short cell text
            if label.lower() in txt.lower() and len(txt) < 40:
                nxt = td.find_next_sibling("td")
                if nxt:
                    val = nxt.get_text(separator=" ", strip=True)
                    if val and len(val) < 200:
                        return val
    return "N/A"


def first_part(val):
    """Keep only the first part before 'upto', 'till', comma etc."""
    if not val or val == "N/A":
        return "N/A"
    val = re.split(r'\s+upto\s+|\s+till\s+', val, flags=re.I)[0]
    val = val.split(",")[0].strip()
    return val[:50] if val else "N/A"


def parse_panchang(soup, ref_date, city_key):
    city     = CITIES[city_key]
    tz_label = city["tz_label"]

    # Build complete row lookup
    table = parse_all_rows(soup, tz_label)

    # Debug — print all keys found
    print(f"     Found {len(table)} table entries")
    # Print keys that look like timing-related ones
    timing_keys = [k for k in table.keys() if any(w in k for w in
        ['rahu','muhurt','kalam','gulika','yama','abhijit','amrit',
         'varj','sunrise','sunset','moon','tithi','nakshatra','yoga'])]
    for k in timing_keys[:20]:
        print(f"     KEY: '{k}' => '{table[k][:50]}'")

    data = {
        "date":     ref_date.isoformat(),
        "weekday":  ref_date.strftime("%A"),
        "city_key": city_key,
        "city":     city["display"],
        "timezone": city["timezone"],
        "tz_label": tz_label,
    }

    # ── Basic Panchang fields ────────────────────────────────────
    data["tithi"]     = first_part(find_text_field(soup, "Tithi"))
    data["nakshatra"] = first_part(find_text_field(soup, "Nakshatra"))
    data["yoga"]      = first_part(find_text_field(soup, "Yoga"))
    data["karana"]    = first_part(find_text_field(soup, "Karana"))
    data["masa"]      = first_part(find_text_field(soup, "Masa", "Maasa"))
    data["paksha"]    = first_part(find_text_field(soup, "Paksha"))
    data["samvat"]    = first_part(find_text_field(soup, "Samvat", "Vikram Samvat"))

    # ── Inauspicious Timings ─────────────────────────────────────
    data["rahukaal"]    = lookup(table, "rahu kalam", "rahukalam", "rahu kaal")
    data["durmuhurtam"] = lookup(table, "dur muhurtam", "durmuhurtam", "durmuhurta")
    data["gulika"]      = lookup(table, "gulikai kalam", "gulika kalam", "gulikai", "gulika")
    data["yamagandam"]  = lookup(table, "yamaganda", "yamagandam", "yama gandam")
    data["varjyam"]     = lookup(table, "varjyam", "varjam")

    # ── Auspicious Timings ───────────────────────────────────────
    data["brahma_muhurta"]  = lookup(table, "brahma muhurta", "brahma muhurtam")
    data["abhijit"]         = lookup(table, "abhijit muhurta", "abhijit")
    data["vijaya_muhurta"]  = lookup(table, "vijaya muhurta")
    data["godhuli_muhurta"] = lookup(table, "godhuli muhurta")
    data["amrit_kalam"]     = lookup(table, "amrit kalam", "amritkalam")
    data["pratah_sandhya"]  = lookup(table, "pratah sandhya")
    data["sayahna_sandhya"] = lookup(table, "sayahna sandhya")
    data["nishita_muhurta"] = lookup(table, "nishita muhurta")

    # ── Sun / Moon ───────────────────────────────────────────────
    data["sunrise"]  = lookup(table, "sunrise")
    data["sunset"]   = lookup(table, "sunset")
    data["moonrise"] = lookup(table, "moonrise")
    data["moonset"]  = lookup(table, "moonset")

    print(f"     Tithi:     {data['tithi']}")
    print(f"     Nakshatra: {data['nakshatra']}")
    print(f"     Rahukaal:  {data['rahukaal']}")
    print(f"     Abhijit:   {data['abhijit']}")
    print(f"     Sunrise:   {data['sunrise']}")

    return data


def run(target_date=None, city_key="New_York"):
    if target_date is None:
        target_date = date.today()
    soup = fetch_page(target_date, city_key)
    return parse_panchang(soup, target_date, city_key)


def run_all_cities(target_date=None):
    if target_date is None:
        target_date = date.today()
    results = {}
    for city_key in CITIES:
        try:
            results[city_key] = run(target_date, city_key)
            print(f"  ✅ {results[city_key]['city']} done")
        except Exception as e:
            print(f"  ❌ {CITIES[city_key]['display']}: {e}")
            results[city_key] = {
                "city": CITIES[city_key]["display"],
                "city_key": city_key,
                "error": str(e)
            }
    return results


if __name__ == "__main__":
    d = date.today()
    if len(sys.argv) > 1:
        d = date.fromisoformat(sys.argv[1])
    results = run_all_cities(d)
    print(json.dumps(results, indent=2, ensure_ascii=False))
