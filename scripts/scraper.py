"""
scraper.py — Card-based parsing using dpCard/dpCardRow/dpTitle/dpKey structure.

From the HTML screenshot, Dur Muhurtam card looks like:
  <div class="dpCard dpFullCard dpFlexEqual">
    <div class="dpCardRow"><span class="dpTitle">Dur Muhurtam</span></div>
    <div class="dpCardRow"><span class="dpKey">11:08 AM to 11:55 AM</span></div>
    <div class="dpCardRow"><span class="dpKey">03:51 PM to 04:38 PM</span></div>
  </div>

So each card has:
  - One dpTitle = the section name
  - One or more dpKey = the values

This is the correct structure to parse!
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
            except:
                continue
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
            EC.presence_of_element_located((By.CLASS_NAME, "dpCardRow"))
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


def fmt_all_slots(times, tz_label):
    slots = []
    for i in range(0, len(times) - 1, 2):
        slots.append(f"{clean_time(times[i])} – {clean_time(times[i+1])}")
    if len(times) % 2 == 1:
        slots.append(clean_time(times[-1]))
    return (" | ".join(slots) + f" {tz_label}") if slots else "N/A"


def clean_text(el):
    return re.sub(r'\s*ⓘ\s*', '', el.get_text(separator=" ", strip=True)).strip()


def parse_panchang(html, ref_date, city_key):
    from bs4 import BeautifulSoup
    soup  = BeautifulSoup(html, "html.parser")
    city  = CITIES[city_key]
    tz    = city["tz_label"]

    # ── Parse by dpCard ───────────────────────────────────────────
    # Each card has a dpTitle (section name) and one+ dpKey (values)
    sections = {}
    order    = []

    cards = soup.find_all(class_=re.compile(r'\bdpCard\b'))
    print(f"[scraper] {city['display']}: {len(cards)} cards found")

    for card in cards:
        title_el = card.find(class_=re.compile(r'\bdpTitle\b'))
        if not title_el:
            continue
        title = clean_text(title_el)
        if not title:
            continue

        # Get all dpKey elements within this card
        key_els = card.find_all(class_=re.compile(r'\bdpKey\b'))
        vals = [clean_text(k) for k in key_els if clean_text(k)]

        if title not in sections:
            sections[title] = vals
            order.append(title)
        else:
            sections[title].extend(vals)

    print(f"[scraper] {len(sections)} sections from cards:")
    for k in order:
        if any(x in k.lower() for x in ['tithi','nakshatra','rahu','dur ','gulika','amrit','abhijit','varjy','sunrise','sunset','brahma','yoga','karana']):
            print(f"  [{k}] => {sections[k]}")

    # ── Helpers ───────────────────────────────────────────────────
    def find_sec(*labels):
        for label in labels:
            ll = label.lower()
            for k in order:
                if ll in k.lower():
                    return sections[k]
        return None

    def all_times(vals):
        if not vals: return []
        t = []
        for v in vals: t.extend(extract_times(v))
        return t

    def fmt_timing(*labels):
        return fmt_all_slots(all_times(find_sec(*labels)), tz)

    def fmt_transition(*labels):
        vals = find_sec(*labels)
        if not vals: return "N/A"
        parts = []
        for v in vals:
            times = extract_times(v)
            if times:
                name = re.split(r'\bupto\b', v, flags=re.I)[0].strip()
                parts.append(f"{name} upto {clean_time(times[0])} {tz}")
            elif v.strip():
                parts.append(v.strip())
        return " → ".join(parts) if parts else "N/A"

    def fmt_simple(*labels):
        vals = find_sec(*labels)
        return vals[0] if vals else "N/A"

    # ── Build output ──────────────────────────────────────────────
    data = {
        "date":     ref_date.isoformat(),
        "weekday":  ref_date.strftime("%A"),
        "city_key": city_key,
        "city":     city["display"],
        "timezone": city["timezone"],
        "tz_label": tz,
    }

    data["tithi"]           = fmt_transition("Tithi")
    data["nakshatra"]       = fmt_transition("Nakshatra")
    data["yoga"]            = fmt_transition("Yoga")
    data["karana"]          = fmt_transition("Karana")
    data["paksha"]          = fmt_simple("Paksha")
    data["rahukaal"]        = fmt_timing("Rahu Kalam")
    data["gulika"]          = fmt_timing("Gulikai Kalam", "Gulika Kalam")
    data["yamagandam"]      = fmt_timing("Yamaganda")
    data["durmuhurtam"]     = fmt_timing("Dur Muhurtam")
    data["varjyam"]         = fmt_timing("Varjyam")
    data["abhijit"]         = fmt_timing("Abhijit")
    data["amrit_kalam"]     = fmt_timing("Amrit Kalam")
    data["brahma_muhurta"]  = fmt_timing("Brahma Muhurta")
    data["vijaya_muhurta"]  = fmt_timing("Vijaya Muhurta")
    data["godhuli_muhurta"] = fmt_timing("Godhuli Muhurta")
    data["pratah_sandhya"]  = fmt_timing("Pratah Sandhya")
    data["sayahna_sandhya"] = fmt_timing("Sayahna Sandhya")
    data["nishita_muhurta"] = fmt_timing("Nishita Muhurta")
    data["sunrise"]         = fmt_timing("Sunrise")
    data["sunset"]          = fmt_timing("Sunset")
    data["moonrise"]        = fmt_timing("Moonrise")
    data["moonset"]         = fmt_timing("Moonset")

    print(f"     Tithi:       {data['tithi']}")
    print(f"     Nakshatra:   {data['nakshatra']}")
    print(f"     Rahukaal:    {data['rahukaal']}")
    print(f"     Durmuhurtam: {data['durmuhurtam']}")
    print(f"     Gulika:      {data['gulika']}")
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
