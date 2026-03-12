"""
scraper.py — Fixed to capture both Tithi/Nakshatra values + all timing fields.
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


def fmt(times, tz_label):
    if len(times) >= 2:
        return f"{clean_time(times[0])} – {clean_time(times[1])} {tz_label}"
    elif len(times) == 1:
        return f"{clean_time(times[0])} {tz_label}"
    return "N/A"


def fmt_multi(times, tz_label):
    """Format multiple time ranges (e.g. Durmuhurtam has 2 slots)."""
    slots = []
    for i in range(0, len(times) - 1, 2):
        s = clean_time(times[i])
        e = clean_time(times[i+1])
        slots.append(f"{s} – {e}")
    if len(times) % 2 == 1:
        slots.append(clean_time(times[-1]))
    return (" | ".join(slots) + f" {tz_label}") if slots else "N/A"


def parse_panchang(html, ref_date, city_key):
    from bs4 import BeautifulSoup
    soup     = BeautifulSoup(html, "html.parser")
    city     = CITIES[city_key]
    tz_label = city["tz_label"]

    # Get ALL dpTableKey/dpTableValue pairs
    keys   = soup.find_all(class_=re.compile(r'dpTableKey',   re.I))
    values = soup.find_all(class_=re.compile(r'dpTableValue', re.I))

    # Build list of (key_text, value_text) pairs preserving order
    pairs = []
    for k, v in zip(keys, values):
        kt = k.get_text(strip=True)
        vt = v.get_text(separator=" ", strip=True)
        # Clean ⓘ and extra whitespace
        vt = re.sub(r'\s*ⓘ\s*', '', vt).strip()
        pairs.append((kt, vt))

    print(f"[scraper] {city['display']}: {len(pairs)} pairs found")

    # ── Helper: find ALL values for a given key label ────────────
    def find_all_vals(label):
        """Return list of all values matching this label (including empty-key continuations)."""
        results = []
        capturing = False
        for kt, vt in pairs:
            if kt.lower().strip() == label.lower().strip():
                capturing = True
                if vt:
                    results.append(vt)
            elif capturing and kt == "":
                # Empty key = continuation of previous section
                if vt:
                    results.append(vt)
            elif capturing and kt != "":
                break  # New section started
        return results

    def find_val(label):
        for kt, vt in pairs:
            if label.lower() in kt.lower() and kt.strip():
                return vt
        return "N/A"

    def find_timing(label):
        """Find timing value — search by label in key."""
        for kt, vt in pairs:
            if label.lower() in kt.lower():
                times = extract_times(vt)
                if times:
                    return fmt(times, tz_label)
        return "N/A"

    def find_timing_multi(label):
        """Find timing that may span multiple slots (like Durmuhurtam)."""
        all_times = []
        capturing = False
        for kt, vt in pairs:
            if label.lower() in kt.lower() and kt.strip():
                capturing = True
                all_times.extend(extract_times(vt))
            elif capturing and kt == "":
                # Continuation — additional time slot
                t = extract_times(vt)
                if t:
                    all_times.extend(t)
                elif vt and not extract_times(vt):
                    break  # non-time continuation = different field
            elif capturing and kt.strip():
                break
        if all_times:
            return fmt_multi(all_times, tz_label)
        return "N/A"

    # ── Tithi: "Navami upto 08:58 PM → Dashami" ─────────────────
    def build_tithi():
        vals = find_all_vals("Tithi")
        if not vals:
            return "N/A"
        parts = []
        for v in vals:
            times = extract_times(v)
            clean_v = re.sub(r'upto\s*', 'upto ', v).strip()
            if times:
                name = re.split(r'upto', v, flags=re.I)[0].strip()
                t    = clean_time(times[0])
                parts.append(f"{name} upto {t} {tz_label}")
            else:
                parts.append(v.strip())
        return " → ".join(parts)

    def build_nakshatra():
        vals = find_all_vals("Nakshatra")
        if not vals:
            return "N/A"
        parts = []
        for v in vals:
            times = extract_times(v)
            if times:
                name = re.split(r'upto', v, flags=re.I)[0].strip()
                t    = clean_time(times[0])
                parts.append(f"{name} upto {t} {tz_label}")
            else:
                parts.append(v.strip())
        return " → ".join(parts)

    # ── Build data dict ──────────────────────────────────────────
    data = {
        "date":     ref_date.isoformat(),
        "weekday":  ref_date.strftime("%A"),
        "city_key": city_key,
        "city":     city["display"],
        "timezone": city["timezone"],
        "tz_label": tz_label,
    }

    data["tithi"]     = build_tithi()
    data["nakshatra"] = build_nakshatra()
    data["yoga"]      = find_val("Yoga")
    data["karana"]    = find_val("Karana")
    data["paksha"]    = find_val("Paksha")

    # Inauspicious
    data["rahukaal"]    = find_timing("Rahu Kalam")
    data["gulika"]      = find_timing("Gulikai Kalam")
    data["yamagandam"]  = find_timing("Yamaganda")
    data["durmuhurtam"] = find_timing_multi("Dur Muhurtam")  # has 2 slots
    data["varjyam"]     = find_timing_multi("Varjyam")       # may have 2 slots

    # Auspicious
    data["abhijit"]         = find_timing("Abhijit")
    data["amrit_kalam"]     = find_timing("Amrit Kalam")
    data["brahma_muhurta"]  = find_timing("Brahma Muhurta")
    data["vijaya_muhurta"]  = find_timing("Vijaya Muhurta")
    data["godhuli_muhurta"] = find_timing("Godhuli Muhurta")
    data["pratah_sandhya"]  = find_timing("Pratah Sandhya")
    data["sayahna_sandhya"] = find_timing("Sayahna Sandhya")
    data["nishita_muhurta"] = find_timing("Nishita Muhurta")

    # Sun/Moon
    data["sunrise"]  = find_timing("Sunrise")
    data["sunset"]   = find_timing("Sunset")
    data["moonrise"] = find_timing("Moonrise")
    data["moonset"]  = find_timing("Moonset")

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
