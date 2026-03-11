"""
scraper.py — Fetches Panchang for 5 Telugu-American cities.
Targets the exact "Auspicious Timings" and "Inauspicious Timings" 
table sections visible on Drikpanchang.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import json, re, sys
from zoneinfo import ZoneInfo

CITIES = {
    "New_York": {
        "display":  "New York, NY",
        "timezone": "America/New_York",
        "tz_label": "ET",
        "geo":      "geo=40.7128,-74.0059",
    },
    "Chicago": {
        "display":  "Chicago, IL",
        "timezone": "America/Chicago",
        "tz_label": "CT",
        "geo":      "geo=41.8781,-87.6298",
    },
    "Dallas": {
        "display":  "Dallas, TX",
        "timezone": "America/Chicago",
        "tz_label": "CT",
        "geo":      "geo=32.7767,-96.7970",
    },
    "California": {
        "display":  "Los Angeles, CA",
        "timezone": "America/Los_Angeles",
        "tz_label": "PT",
        "geo":      "geo=34.0522,-118.2437",
    },
    "Michigan": {
        "display":  "Detroit, MI",
        "timezone": "America/Detroit",
        "tz_label": "ET",
        "geo":      "geo=42.3314,-83.0458",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page(target_date, city_key):
    city     = CITIES[city_key]
    date_str = target_date.strftime("%d/%m/%Y")
    url = (
        f"https://www.drikpanchang.com/panchang/day-panchang.html"
        f"?date={date_str}&{city['geo']}&lang=en"
    )
    print(f"[scraper] {city['display']}: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def extract_times(text):
    """Extract all HH:MM AM/PM patterns."""
    return re.findall(r"\d{1,2}:\d{2}\s*(?:AM|PM)", text, re.I)


def clean_time(t):
    t = t.strip().upper().replace(" ", "")
    for fmt in ("%I:%M%p", "%H:%M%p"):
        try:
            return datetime.strptime(t, fmt).strftime("%I:%M %p")
        except:
            pass
    return t.strip()


def fmt(times, tz_label):
    """Format 1 or 2 times with timezone label."""
    if len(times) >= 2:
        return f"{clean_time(times[0])} – {clean_time(times[1])} {tz_label}"
    elif len(times) == 1:
        return f"{clean_time(times[0])} {tz_label}"
    return "N/A"


def parse_table_section(soup, section_heading):
    """
    Find a section by its heading text (e.g. "Auspicious Timings")
    then parse all label→value pairs from its table rows.
    Returns dict of {label_lower: raw_text}
    """
    result = {}

    # Find the heading element
    heading_tag = None
    for tag in soup.find_all(string=re.compile(section_heading, re.I)):
        heading_tag = tag
        break

    if not heading_tag:
        return result

    # Walk up to find the containing table or div
    container = heading_tag.parent
    for _ in range(5):
        if container is None:
            break
        if container.name in ("table", "div", "section"):
            break
        container = container.parent

    if not container:
        return result

    # Find the next table after this heading
    # Look for the table that follows this heading
    search_root = container.parent if container.parent else soup

    found_heading = False
    for elem in search_root.find_all(["table", "tr", "div"]):
        text = elem.get_text(strip=True)
        if section_heading.lower() in text.lower() and len(text) < 100:
            found_heading = True
            continue
        if found_heading:
            # Parse this table
            rows = elem.find_all("tr") if elem.name == "table" else elem.find_all("tr")
            if not rows and elem.name == "tr":
                rows = [elem]
            for row in rows:
                cells = row.find_all(["td", "th"])
                # Each row has pairs: label, value, label, value
                for i in range(0, len(cells) - 1, 2):
                    label = cells[i].get_text(strip=True)
                    value = cells[i+1].get_text(separator=" ", strip=True) if i+1 < len(cells) else ""
                    if label and len(label) < 50:
                        result[label.lower()] = value
            if rows:
                break

    return result


def parse_all_table_rows(soup, tz_label):
    """
    Scan ALL table rows on the page for label-value pairs.
    This catches Rahu Kalam, Abhijit, etc. regardless of section.
    Returns flat dict of {normalized_label: formatted_time_string}
    """
    result = {}

    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        # Process pairs of cells: (label, value, label, value ...)
        for i in range(0, len(cells) - 1, 2):
            if i + 1 >= len(cells):
                break
            label_text = cells[i].get_text(strip=True)
            value_text = cells[i+1].get_text(separator=" ", strip=True)

            if not label_text or len(label_text) > 60:
                continue

            label_lower = label_text.lower().strip()
            times = extract_times(value_text)

            if times:
                result[label_lower] = fmt(times, tz_label)
                result[f"{label_lower}_raw"] = value_text
            elif value_text and len(value_text) < 120:
                result[label_lower] = value_text

    return result


def lookup(table, *keys):
    """Look up a value from parsed table using multiple possible key names."""
    for key in keys:
        # Exact match
        if key.lower() in table:
            return table[key.lower()]
        # Partial match
        for k, v in table.items():
            if key.lower() in k and "_raw" not in k:
                return v
    return "N/A"


def find_simple_value(soup, *labels):
    """Find a plain text value (non-time) like Tithi name."""
    for label in labels:
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if txt.lower().strip() == label.lower().strip() or \
               (label.lower() in txt.lower() and len(txt) < 50):
                nxt = td.find_next_sibling("td")
                if nxt:
                    val = nxt.get_text(separator=" ", strip=True)
                    if val and len(val) < 200:
                        return val
    return "N/A"


def clean_short(val):
    """Keep only the first meaningful part before upto/till/comma."""
    if not val or val == "N/A":
        return "N/A"
    cleaned = re.split(r'\s+upto\s+|\s+till\s+', val, maxsplit=1, flags=re.I)[0]
    cleaned = cleaned.split(",")[0].strip()
    return cleaned[:50] if cleaned else val[:50]


def parse_panchang(soup, ref_date, city_key):
    city     = CITIES[city_key]
    tz_label = city["tz_label"]

    data = {
        "date":     ref_date.isoformat(),
        "weekday":  ref_date.strftime("%A"),
        "city_key": city_key,
        "city":     city["display"],
        "timezone": city["timezone"],
        "tz_label": tz_label,
    }

    # ── Parse ALL table rows into one flat lookup dict ───────────
    table = parse_all_table_rows(soup, tz_label)

    # ── Non-time Panchang fields ─────────────────────────────────
    data["tithi"]     = clean_short(find_simple_value(soup, "Tithi"))
    data["nakshatra"] = clean_short(find_simple_value(soup, "Nakshatra"))
    data["yoga"]      = clean_short(find_simple_value(soup, "Yoga"))
    data["karana"]    = clean_short(find_simple_value(soup, "Karana"))
    data["masa"]      = clean_short(find_simple_value(soup, "Masa", "Maasa"))
    data["paksha"]    = clean_short(find_simple_value(soup, "Paksha"))
    data["samvat"]    = clean_short(find_simple_value(soup, "Samvat", "Vikram Samvat"))

    # ── Inauspicious Timings ─────────────────────────────────────
    data["rahukaal"]    = lookup(table,
        "rahu kalam", "rahukalam", "rahu kaal", "rahu")
    data["yamagandam"]  = lookup(table,
        "yamaganda", "yamagandam", "yama gandam", "yamakantam")
    data["gulika"]      = lookup(table,
        "gulikai kalam", "gulika kalam", "gulikakalam", "gulikai", "gulika")
    data["durmuhurtam"] = lookup(table,
        "dur muhurtam", "durmuhurtam", "durmuhurta")
    data["varjyam"]     = lookup(table,
        "varjyam", "varjam")
    data["aadal_yoga"]  = lookup(table,
        "aadal yoga", "vinchudo")

    # ── Auspicious Timings ───────────────────────────────────────
    data["abhijit"]      = lookup(table,
        "abhijit", "abhijit muhurta")
    data["amrit_kalam"]  = lookup(table,
        "amrit kalam", "amritkalam", "amrita kalam")
    data["brahma_muhurta"] = lookup(table,
        "brahma muhurta", "brahma muhurtam")
    data["vijaya_muhurta"] = lookup(table,
        "vijaya muhurta")
    data["godhuli_muhurta"] = lookup(table,
        "godhuli muhurta")
    data["nishita_muhurta"] = lookup(table,
        "nishita muhurta")
    data["pratah_sandhya"]  = lookup(table,
        "pratah sandhya")
    data["sayahna_sandhya"] = lookup(table,
        "sayahna sandhya")

    # ── Sun / Moon ───────────────────────────────────────────────
    data["sunrise"]  = lookup(table, "sunrise")
    data["sunset"]   = lookup(table, "sunset")
    data["moonrise"] = lookup(table, "moonrise")
    data["moonset"]  = lookup(table, "moonset")

    # Debug — print what we found
    print(f"     Tithi:      {data['tithi']}")
    print(f"     Nakshatra:  {data['nakshatra']}")
    print(f"     Rahukaal:   {data['rahukaal']}")
    print(f"     Abhijit:    {data['abhijit']}")
    print(f"     Durmuhurt:  {data['durmuhurtam']}")
    print(f"     Sunrise:    {data['sunrise']}")

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
