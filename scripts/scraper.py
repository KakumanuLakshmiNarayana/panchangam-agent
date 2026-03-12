"""
scraper.py — dpTableKey/dpTableValue parsing. FINAL CORRECT VERSION.

Continuation assignment:
  NAME continuations (Tithi→Dashami, Nakshatra→Purva Ashadha):
    FIFO queue of pending name keys. First in = first served.
    
  TIMING continuations (Dur Muhurtam 2nd slot = 03:51 PM):
    From the HTML screenshot: Dur Muhurtam card has 2 rows.
    In raw pairs: Dur Muhurtam, Gulikai appear consecutively, then empty='03:51 PM'
    The extra slot belongs to the FIRST timing key in the run (Dur Muhurtam).
    
  Multi-slot (Varjyam): same first timing key gets all timing empties in a run.
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

TIMING_KEYS = {
    "rahu kalam", "dur muhurtam", "gulikai kalam", "gulika kalam",
    "yamaganda", "varjyam", "amrit kalam", "abhijit", "brahma muhurta",
    "vijaya muhurta", "godhuli muhurta", "pratah sandhya", "sayahna sandhya",
    "nishita muhurta", "ganda moola", "aadal yoga", "bhadra",
    "sunrise", "sunset", "moonrise", "moonset",
}
NAME_KEYS = {"tithi", "nakshatra", "yoga", "karana", "weekday", "paksha",
             "raja", "surya nakshatra", "surya pada", "nakshatra pada"}


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


def fmt_all_slots(times, tz_label):
    slots = []
    for i in range(0, len(times) - 1, 2):
        slots.append(f"{clean_time(times[i])} \u2013 {clean_time(times[i+1])}")
    if len(times) % 2 == 1:
        slots.append(clean_time(times[-1]))
    return (" | ".join(slots) + f" {tz_label}") if slots else "N/A"


def parse_panchang(html, ref_date, city_key):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    city = CITIES[city_key]
    tz   = city["tz_label"]

    def clean(el):
        return re.sub(r'\s*\u24d8\s*', '', el.get_text(separator=" ", strip=True)).strip()

    keys_els   = soup.find_all(class_=re.compile(r'\bdpTableKey\b',   re.I))
    values_els = soup.find_all(class_=re.compile(r'\bdpTableValue\b', re.I))
    raw = [(clean(k), clean(v)) for k, v in zip(keys_els, values_els)]

    print(f"[scraper] {city['display']}: {len(raw)} pairs found")

    sections = {}
    order    = []

    def add(key, val):
        if not val:
            return
        if key not in sections:
            sections[key] = [val]
            order.append(key)
        else:
            sections[key].append(val)

    # State for continuation assignment
    pending_name_keys = []   # FIFO: first pending name key gets next name continuation
    first_timing_key  = None # first timing key in current named run gets timing continuations
    in_named_run      = False

    for key, val in raw:
        if key:
            # Named row
            add(key, val)
            kl = key.lower()
            if not in_named_run:
                # Starting a fresh named run — reset first_timing_key tracker
                first_timing_key = None
                in_named_run = True
            if kl in NAME_KEYS:
                pending_name_keys.append(key)
            if kl in TIMING_KEYS:
                if first_timing_key is None:
                    first_timing_key = key
        else:
            # Empty (continuation) row
            in_named_run = False
            if not val:
                continue
            has_time = bool(extract_times(val))
            if has_time:
                # Timing continuation → first timing key in the run
                if first_timing_key:
                    add(first_timing_key, val)
            else:
                # Name continuation → oldest pending name key (FIFO)
                if pending_name_keys:
                    owner = pending_name_keys.pop(0)
                    add(owner, val)

    print(f"[scraper] {len(sections)} sections parsed:")
    DEBUG = {'tithi','nakshatra','rahu kalam','dur muhurtam','gulikai kalam',
             'amrit kalam','abhijit','varjyam','sunrise','sunset','brahma muhurta'}
    for k in order:
        if k.lower() in DEBUG:
            print(f"  [{k}] => {sections[k]}")

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
        return " \u2192 ".join(parts) if parts else "N/A"

    def fmt_simple(*labels):
        vals = find_sec(*labels)
        return vals[0] if vals else "N/A"

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
                print(f"  \u2705 {results[city_key]['city']} done")
            except Exception as e:
                print(f"  \u274c {CITIES[city_key]['display']}: {e}")
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
