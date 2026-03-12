"""
scraper.py — Card-based parsing matching the actual Drikpanchang DOM structure.

Each panchang item is a dpCardRow containing:
  - dpElementInfoPopupWrapper  → contains the timing text (e.g. "Navami upto 08:58 PM")
  - dpKey span(s)              → contains next value (e.g. "Dashami", "Purva Ashadha")
  - dpFlexWrap                 → contains secondary time slots (e.g. 2nd Durmuhurtam slot)

Section headings come from dpSectionTitle or dpCardTitle divs.
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


def fetch_html(url, driver):
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


def fmt_slots(times, tz_label):
    """Pairs of times → 'HH:MM AM – HH:MM PM | HH:MM PM – HH:MM PM TZ'"""
    slots = []
    for i in range(0, len(times) - 1, 2):
        slots.append(f"{clean_time(times[i])} – {clean_time(times[i+1])}")
    if len(times) % 2 == 1:
        slots.append(clean_time(times[-1]))
    return (" | ".join(slots) + f" {tz_label}") if slots else "N/A"


def t(el):
    return el.get_text(" ", strip=True)


def parse_panchang(html, ref_date, city_key):
    from bs4 import BeautifulSoup
    soup     = BeautifulSoup(html, "html.parser")
    city     = CITIES[city_key]
    tz_label = city["tz_label"]

    # ── Strategy: find each dpCardRow, extract label + all values ──
    # Each dpCardRow typically has:
    #   dpTableKey  = label  (e.g. "Tithi", "Rahu Kalam")
    #   dpTableValue = primary value (e.g. "Navami upto 08:58 PM")
    #   dpKey span  = next value / overflow (e.g. "Dashami", "Purva Ashadha")
    #   dpFlexWrap  = second time rows for multi-slot items

    card_rows = soup.find_all(class_=re.compile(r'\bdpCardRow\b'))
    print(f"[scraper] {city['display']}: {len(card_rows)} dpCardRow elements")

    sections = {}  # label_lower -> {"label": str, "primary": str, "extra_names": [str], "extra_times": [str]}

    for row in card_rows:
        # Key
        key_el = row.find(class_=re.compile(r'\bdpTableKey\b'))
        val_el = row.find(class_=re.compile(r'\bdpTableValue\b'))
        if not key_el or not val_el:
            continue

        label     = key_el.get_text(strip=True).strip()
        label_key = label.lower()
        if not label_key:
            continue

        primary   = val_el.get_text(" ", strip=True)

        # Extra names from dpKey spans (e.g. "Dashami", "Purva Ashadha")
        extra_names = []
        for dpkey in row.find_all(class_=re.compile(r'\bdpKey\b')):
            txt = dpkey.get_text(" ", strip=True)
            if txt:
                extra_names.append(txt)

        # Extra time rows from dpFlexWrap (2nd/3rd time slots for Durmuhurtam, Varjyam etc.)
        extra_times_raw = []
        for fw in row.find_all(class_=re.compile(r'\bdpFlexWrap\b')):
            txt = fw.get_text(" ", strip=True)
            if txt:
                extra_times_raw.append(txt)

        sections[label_key] = {
            "label":       label,
            "primary":     primary,
            "extra_names": extra_names,
            "extra_times": extra_times_raw,
        }

    # Print all sections for debug
    print(f"[scraper] {len(sections)} sections parsed:")
    for k, v in sections.items():
        print(f"  [{v['label']}] primary='{v['primary']}' | names={v['extra_names']} | extra_times={v['extra_times']}")

    # ── Lookup helpers ──────────────────────────────────────────
    def find(*labels):
        for lbl in labels:
            for k, v in sections.items():
                if lbl.lower() in k:
                    return v
        return None

    def fmt_transition(*labels):
        """Name upto TIME TZ → NextName"""
        sec = find(*labels)
        if not sec:
            return "N/A"
        parts = []
        primary = sec["primary"]
        times = extract_times(primary)
        if times:
            name = re.split(r'\bupto\b', primary, flags=re.I)[0].strip()
            parts.append(f"{name} upto {clean_time(times[0])} {tz_label}")
        elif primary.strip():
            parts.append(primary.strip())
        for name in sec["extra_names"]:
            if name.strip():
                parts.append(name.strip())
        return " → ".join(parts) if parts else "N/A"

    def fmt_timing(*labels):
        """Collect ALL times from primary + extra_times rows → slot format"""
        sec = find(*labels)
        if not sec:
            return "N/A"
        all_times = []
        # Primary row times
        all_times.extend(extract_times(sec["primary"]))
        # Extra time rows (2nd slot, 3rd slot, etc.)
        for row_txt in sec["extra_times"]:
            all_times.extend(extract_times(row_txt))
        return fmt_slots(all_times, tz_label) if all_times else "N/A"

    def fmt_simple(*labels):
        sec = find(*labels)
        if not sec:
            return "N/A"
        return sec["primary"].strip() or "N/A"

    # ── Build output ────────────────────────────────────────────
    data = {
        "date":     ref_date.isoformat(),
        "weekday":  ref_date.strftime("%A"),
        "city_key": city_key,
        "city":     city["display"],
        "timezone": city["timezone"],
        "tz_label": tz_label,
    }

    data["tithi"]           = fmt_transition("tithi")
    data["nakshatra"]       = fmt_transition("nakshatra")
    data["yoga"]            = fmt_transition("yoga")
    data["karana"]          = fmt_transition("karana")
    data["paksha"]          = fmt_simple("paksha")

    data["rahukaal"]        = fmt_timing("rahu kalam", "rahukaal")
    data["gulika"]          = fmt_timing("gulikai", "gulika")
    data["yamagandam"]      = fmt_timing("yamaganda")
    data["durmuhurtam"]     = fmt_timing("dur muhurtam", "durmuhurtam")
    data["varjyam"]         = fmt_timing("varjyam")

    data["abhijit"]         = fmt_timing("abhijit")
    data["amrit_kalam"]     = fmt_timing("amrit kalam")
    data["brahma_muhurta"]  = fmt_timing("brahma muhurta")
    data["vijaya_muhurta"]  = fmt_timing("vijaya muhurta")
    data["godhuli_muhurta"] = fmt_timing("godhuli")
    data["pratah_sandhya"]  = fmt_timing("pratah sandhya")
    data["sayahna_sandhya"] = fmt_timing("sayahna sandhya")
    data["nishita_muhurta"] = fmt_timing("nishita muhurta")

    data["sunrise"]         = fmt_timing("sunrise")
    data["sunset"]          = fmt_timing("sunset")
    data["moonrise"]        = fmt_timing("moonrise")
    data["moonset"]         = fmt_timing("moonset")

    print(f"     Tithi:       {data['tithi']}")
    print(f"     Nakshatra:   {data['nakshatra']}")
    print(f"     Yoga:        {data['yoga']}")
    print(f"     Karana:      {data['karana']}")
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
        html = fetch_html(url, driver)
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
