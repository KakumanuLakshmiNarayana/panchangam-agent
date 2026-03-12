"""
scraper.py — Fixed: Durmuhurtam 2nd slot correctly assigned.
Key insight from debug logs:
  Raw pairs order around Durmuhurtam:
    KEY='Dur Muhurtam'   VAL='11:08 AM to 11:55 AM'
    KEY='Gulikai Kalam'  VAL='10:09 AM to 11:38 AM'
    KEY=''               VAL='03:51 PM to 04:38 PM'  ← actually Durmuhurtam slot 2

The website puts continuation rows AFTER the NEXT named key.
Fix: track a "pending continuation" queue per section index.
Each empty-key row belongs to the section that is (index - 1) positions back,
not the immediately previous named key.

Actual pattern (verified from logs):
  Tithi row, Nakshatra row, [Tithi cont], [Nakshatra cont]
  DurMuhurtam row, GulikaiKalam row, [DurMuhurtam cont], [GulikaiKalam cont]

So empty rows at position N belong to the named section that was N positions ago
in the sequence of named keys, counted from the last named key.
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
        slots.append(f"{clean_time(times[i])} – {clean_time(times[i+1])}")
    if len(times) % 2 == 1:
        slots.append(clean_time(times[-1]))
    return (" | ".join(slots) + f" {tz_label}") if slots else "N/A"


def parse_panchang(html, ref_date, city_key):
    from bs4 import BeautifulSoup
    soup     = BeautifulSoup(html, "html.parser")
    city     = CITIES[city_key]
    tz_label = city["tz_label"]

    def clean(el):
        return re.sub(r'\s*ⓘ\s*', '', el.get_text(separator=" ", strip=True)).strip()

    keys_els   = soup.find_all(class_=re.compile(r'\bdpTableKey\b',   re.I))
    values_els = soup.find_all(class_=re.compile(r'\bdpTableValue\b', re.I))
    raw = [(clean(k), clean(v)) for k, v in zip(keys_els, values_els)]

    print(f"[scraper] {city['display']}: {len(raw)} pairs found")

    # ── Two-pass parsing ──────────────────────────────────────────
    # Pass 1: identify named rows and empty rows, record their positions
    named_rows = []   # list of (position, key, val)
    empty_rows = []   # list of (position, val)

    for i, (kt, vt) in enumerate(raw):
        if kt:
            named_rows.append((i, kt, vt))
        else:
            if vt:
                empty_rows.append((i, vt))

    # Pass 2: for each empty row, find its true owner.
    # Pattern: empty rows appear AFTER the block they extend.
    # Specifically, each empty row at position P belongs to the named row
    # whose position is IMMEDIATELY before P, going backwards through ALL rows
    # (named + empty), but skipping other empty rows that came between.
    # 
    # BUT the tricky case: in the sequence
    #   pos=4  Tithi      val='Navami...'
    #   pos=5  Nakshatra  val='Mula...'
    #   pos=6  (empty)    val='Dashami'       ← belongs to Tithi (pos 4)
    #   pos=7  (empty)    val='Purva Ashadha' ← belongs to Nakshatra (pos 5)
    #
    # And similarly:
    #   pos=N   DurMuhurtam   val='11:08...'
    #   pos=N+1 GulikaiKalam  val='10:09...'
    #   pos=N+2 (empty)       val='03:51...'  ← belongs to DurMuhurtam (pos N)
    #   pos=N+3 (empty)       val='Gulika2nd' ← belongs to GulikaiKalam (pos N+1)
    #
    # The pattern: consecutive empty rows after a block of named rows
    # map 1-to-1 backwards to the named rows in REVERSE order.
    # i.e., the LAST empty row maps to the LAST named row before the block,
    # and the FIRST empty row maps to the FIRST named row before the block... 
    # Wait, let me re-examine:
    #   pos=4  Tithi      ← named[0] in block
    #   pos=5  Nakshatra  ← named[1] in block  
    #   pos=6  empty='Dashami'       ← should go to Tithi (named[0])
    #   pos=7  empty='Purva Ashadha' ← should go to Nakshatra (named[1])
    # So empty[0] → named[0], empty[1] → named[1]: SAME ORDER
    #
    # For the timing block:
    #   pos=N   DurMuhurtam  ← named[0]
    #   pos=N+1 Gulikai      ← named[1]
    #   pos=N+2 empty='03:51' ← DurMuhurtam (named[0])
    #   pos=N+3 empty='Gulika2' ← Gulikai (named[1])
    # Same order pattern: empty rows follow the same order as the named rows.
    #
    # Algorithm: scan through raw pairs. When we see a block of named rows
    # followed by empty rows, assign empty[i] → named[i % len(named_block)]

    sections = {}
    order    = []

    def add_to(key, val):
        if key not in sections:
            sections[key] = [val] if val else []
            order.append(key)
        elif val:
            sections[key].append(val)

    i = 0
    while i < len(raw):
        kt, vt = raw[i]
        if kt:
            # Start of a named block — collect consecutive named rows
            named_block = []
            while i < len(raw) and raw[i][0]:
                named_block.append((raw[i][0], raw[i][1]))
                add_to(raw[i][0], raw[i][1])
                i += 1
            # Now collect consecutive empty rows following this named block
            empty_block = []
            while i < len(raw) and not raw[i][0]:
                if raw[i][1]:
                    empty_block.append(raw[i][1])
                i += 1
            # Assign empty rows to named rows by index
            for j, ev in enumerate(empty_block):
                if named_block:
                    owner = named_block[j % len(named_block)][0]
                    if owner in sections:
                        sections[owner].append(ev)
        else:
            # Stray empty row (shouldn't happen after above logic, but handle gracefully)
            i += 1

    print(f"[scraper] {len(sections)} sections parsed:")
    for k in order[:35]:
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
        if not vals:
            return []
        t = []
        for v in vals:
            t.extend(extract_times(v))
        return t

    def fmt_timing(*labels):
        return fmt_all_slots(all_times(find_sec(*labels)), tz_label)

    def fmt_transition(*labels):
        vals = find_sec(*labels)
        if not vals:
            return "N/A"
        parts = []
        for v in vals:
            times = extract_times(v)
            if times:
                name = re.split(r'\bupto\b', v, flags=re.I)[0].strip()
                parts.append(f"{name} upto {clean_time(times[0])} {tz_label}")
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
        "tz_label": tz_label,
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
