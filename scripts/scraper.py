"""
scraper.py — Fixed parsing: Tithi gets both values, Nakshatra gets both values,
Durmuhurtam gets both time slots. Empty-key rows belong to the PREVIOUS named key.
"""

import json, re, sys, time, os
from datetime import datetime, date

CITIES = {
    "New_York":   {"display": "New York, NY",    "timezone": "America/New_York",    "tz_label": "ET", "geoname_id": "5128581"},
    "Chicago":    {"display": "Chicago, IL",     "timezone": "America/Chicago",     "tz_label": "CT", "geoname_id": "4887398"},
    "Dallas":     {"display": "Dallas, TX",      "timezone": "America/Chicago",     "tz_label": "CT", "geoname_id": "4684888"},
    "California": {"display": "Los Angeles, CA", "timezone": "America/Los_Angeles", "tz_label": "PT", "geoname_id": "5368361"},
    "Michigan":   {"display": "Detroit, MI",     "timezone": "America/Detroit",     "tz_label": "ET", "geoname_id": "4990729"},
}


def get_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    for path in ["/usr/bin/chromedriver", "/usr/lib/chromium-browser/chromedriver", "chromedriver"]:
        if os.path.exists(path) or path == "chromedriver":
            try:
                driver = webdriver.Chrome(service=Service(path), options=opts)
                print(f"[scraper] chromedriver: {path}")
                return driver
            except: continue
    from webdriver_manager.chrome import ChromeDriverManager
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def fetch_html(url, driver, city_display):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    print(f"[scraper] Loading: {url}")
    driver.get(url)
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CLASS_NAME, "dpTableValue"))
        )
    except:
        time.sleep(8)
    for y in [500, 1200, 2000, 2800]:
        driver.execute_script(f"window.scrollTo(0, {y});")
        time.sleep(0.8)
    time.sleep(2)
    return driver.page_source


def extract_times(text):
    return re.findall(r"\d{1,2}:\d{2}\s*(?:AM|PM)", text, re.I)


def clean_time(t):
    t = t.strip().upper().replace(" ", "")
    try:
        return datetime.strptime(t, "%I:%M%p").strftime("%I:%M %p")
    except:
        return t.strip()


def fmt_range(times, tz_label):
    """Format one time range: start – end TZ"""
    if len(times) >= 2:
        return f"{clean_time(times[0])} – {clean_time(times[1])} {tz_label}"
    elif len(times) == 1:
        return f"{clean_time(times[0])} {tz_label}"
    return "N/A"


def fmt_all_slots(all_times, tz_label):
    """Format multiple time ranges (pairs of times) joined by ' | '"""
    slots = []
    for i in range(0, len(all_times) - 1, 2):
        s = clean_time(all_times[i])
        e = clean_time(all_times[i + 1])
        slots.append(f"{s} – {e}")
    if not slots:
        return "N/A"
    return " | ".join(slots) + f" {tz_label}"


def clean_val(v):
    """Remove ⓘ and trailing junk."""
    return re.sub(r'\s*ⓘ\s*', '', v).strip()


def build_sections(pairs):
    """
    Convert flat (key, value) pairs into sections.
    Each section = {label: str, rows: [str]}
    Empty-key rows belong to the most recent non-empty key.

    Example raw pairs for Tithi:
      ('Tithi', 'Navami upto 08:58 PM')
      ('',      'Dashami')             ← continuation of Tithi
      ('Nakshatra', 'Mula upto 03:13 PM')
      ('',      'Purva Ashadha')       ← continuation of Nakshatra
    """
    sections = []
    current  = None
    for key, val in pairs:
        key_c = clean_val(key)
        val_c = clean_val(val)
        if key_c:
            # New named section
            current = {"label": key_c, "rows": [val_c] if val_c else []}
            sections.append(current)
        else:
            # Empty key = continuation of previous section
            if current is not None and val_c:
                current["rows"].append(val_c)
    return sections


def find_section(sections, *labels):
    """Find the first section whose label matches any of the given labels."""
    for label in labels:
        ll = label.lower()
        for sec in sections:
            if ll in sec["label"].lower():
                return sec
    return None


def fmt_tithi_like(sec, tz_label):
    """
    Format Tithi or Nakshatra which have rows like:
      row 0: "Navami upto 08:58 PM"
      row 1: "Dashami"            ← next tithi, no time
    Output: "Navami upto 08:58 PM ET → Dashami"
    """
    if not sec or not sec["rows"]:
        return "N/A"
    parts = []
    for row in sec["rows"]:
        times = extract_times(row)
        if times:
            name = re.split(r'upto', row, flags=re.I)[0].strip()
            t    = clean_time(times[0])
            parts.append(f"{name} upto {t} {tz_label}")
        elif row.strip():
            parts.append(row.strip())
    return " → ".join(parts) if parts else "N/A"


def fmt_timing(sec, tz_label):
    """
    Format a timing section — collect ALL times across ALL rows.
    E.g. Durmuhurtam:
      row 0: "11:08 AM to 11:55 AM"
      row 1: "03:51 PM to 04:38 PM"   ← second slot
    Output: "11:08 AM – 11:55 AM | 03:51 PM – 04:38 PM ET"
    """
    if not sec:
        return "N/A"
    all_times = []
    for row in sec["rows"]:
        all_times.extend(extract_times(row))
    return fmt_all_slots(all_times, tz_label) if all_times else "N/A"


def fmt_simple(sec):
    """Return first non-empty row as plain text."""
    if not sec or not sec["rows"]:
        return "N/A"
    return sec["rows"][0].strip() or "N/A"


def parse_panchang(html, ref_date, city_key):
    from bs4 import BeautifulSoup
    soup     = BeautifulSoup(html, "html.parser")
    city     = CITIES[city_key]
    tz_label = city["tz_label"]

    # Build raw pairs list
    keys_els   = soup.find_all(class_=re.compile(r'dpTableKey',   re.I))
    values_els = soup.find_all(class_=re.compile(r'dpTableValue', re.I))
    pairs = [(k.get_text(strip=True), v.get_text(separator=" ", strip=True))
             for k, v in zip(keys_els, values_els)]

    # Build structured sections
    sections = build_sections(pairs)
    print(f"[scraper] {city['display']}: {len(pairs)} pairs, {len(sections)} sections")

    # Debug first 30 sections
    for sec in sections[:30]:
        print(f"  SEC '{sec['label']}' => {sec['rows'][:3]}")

    data = {
        "date":     ref_date.isoformat(),
        "weekday":  ref_date.strftime("%A"),
        "city_key": city_key,
        "city":     city["display"],
        "timezone": city["timezone"],
        "tz_label": tz_label,
    }

    # ── Panchang basics ──────────────────────────────────────────
    data["tithi"]     = fmt_tithi_like(find_section(sections, "Tithi"),     tz_label)
    data["nakshatra"] = fmt_tithi_like(find_section(sections, "Nakshatra"), tz_label)
    data["yoga"]      = fmt_tithi_like(find_section(sections, "Yoga"),      tz_label)
    data["karana"]    = fmt_tithi_like(find_section(sections, "Karana"),    tz_label)
    data["paksha"]    = fmt_simple(find_section(sections, "Paksha"))

    # ── Inauspicious timings ─────────────────────────────────────
    data["rahukaal"]    = fmt_timing(find_section(sections, "Rahu Kalam"),    tz_label)
    data["gulika"]      = fmt_timing(find_section(sections, "Gulikai Kalam"), tz_label)
    data["yamagandam"]  = fmt_timing(find_section(sections, "Yamaganda"),     tz_label)
    data["durmuhurtam"] = fmt_timing(find_section(sections, "Dur Muhurtam"),  tz_label)  # 2 slots
    data["varjyam"]     = fmt_timing(find_section(sections, "Varjyam"),       tz_label)  # 2 slots

    # ── Auspicious timings ───────────────────────────────────────
    data["abhijit"]         = fmt_timing(find_section(sections, "Abhijit"),         tz_label)
    data["amrit_kalam"]     = fmt_timing(find_section(sections, "Amrit Kalam"),     tz_label)
    data["brahma_muhurta"]  = fmt_timing(find_section(sections, "Brahma Muhurta"),  tz_label)
    data["vijaya_muhurta"]  = fmt_timing(find_section(sections, "Vijaya Muhurta"),  tz_label)
    data["godhuli_muhurta"] = fmt_timing(find_section(sections, "Godhuli Muhurta"), tz_label)
    data["pratah_sandhya"]  = fmt_timing(find_section(sections, "Pratah Sandhya"),  tz_label)
    data["sayahna_sandhya"] = fmt_timing(find_section(sections, "Sayahna Sandhya"), tz_label)
    data["nishita_muhurta"] = fmt_timing(find_section(sections, "Nishita Muhurta"), tz_label)

    # ── Sun / Moon ───────────────────────────────────────────────
    data["sunrise"]  = fmt_timing(find_section(sections, "Sunrise"),  tz_label)
    data["sunset"]   = fmt_timing(find_section(sections, "Sunset"),   tz_label)
    data["moonrise"] = fmt_timing(find_section(sections, "Moonrise"), tz_label)
    data["moonset"]  = fmt_timing(find_section(sections, "Moonset"),  tz_label)

    print(f"     Tithi:       {data['tithi']}")
    print(f"     Nakshatra:   {data['nakshatra']}")
    print(f"     Rahukaal:    {data['rahukaal']}")
    print(f"     Durmuhurtam: {data['durmuhurtam']}")
    print(f"     Amrit Kalam: {data['amrit_kalam']}")
    print(f"     Abhijit:     {data['abhijit']}")
    print(f"     Sunrise:     {data['sunrise']}")

    return data


def run(target_date=None, city_key="New_York", driver=None):
    if target_date is None:
        target_date = date.today()
    city     = CITIES[city_key]
    date_str = target_date.strftime("%d/%m/%Y")
    url      = f"https://www.drikpanchang.com/panchang/day-panchang.html?geoname-id={city['geoname_id']}&date={date_str}"
    own_driver = driver is None
    if own_driver:
        driver = get_driver()
    try:
        html = fetch_html(url, driver, city["display"])
        return parse_panchang(html, target_date, city_key)
    finally:
        if own_driver:
            driver.quit()


def run_all_cities(target_date=None):
    if target_date is None:
        target_date = date.today()
    driver = get_driver()
    results = {}
    try:
        for city_key in CITIES:
            try:
                results[city_key] = run(target_date, city_key, driver=driver)
                print(f"  ✅ {results[city_key]['city']} done")
            except Exception as e:
                print(f"  ❌ {CITIES[city_key]['display']}: {e}")
                import traceback; traceback.print_exc()
                results[city_key] = {"city": CITIES[city_key]["display"], "city_key": city_key, "error": str(e)}
    finally:
        driver.quit()
    return results


if __name__ == "__main__":
    d = date.today()
    if len(sys.argv) > 1:
        d = date.fromisoformat(sys.argv[1])
    results = run_all_cities(d)
    print(json.dumps(results, indent=2, ensure_ascii=False))
