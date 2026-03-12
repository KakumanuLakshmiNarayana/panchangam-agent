"""
scraper.py — Drikpanchang uses div-based layout, not tables.
Parse dpTableKey/dpTableValue div pairs.
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

    # Wait for dpTableValue class to appear — this is Drikpanchang's data div class
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CLASS_NAME, "dpTableValue"))
        )
        print(f"[scraper] dpTableValue divs found!")
    except Exception as e:
        print(f"[scraper] dpTableValue wait failed: {e}")
        time.sleep(8)

    # Scroll to load all lazy sections
    for scroll_y in [500, 1200, 2000, 2800]:
        driver.execute_script(f"window.scrollTo(0, {scroll_y});")
        time.sleep(0.8)

    time.sleep(2)
    html = driver.page_source

    # Debug — print structure of dpTableKey/dpTableValue elements
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    keys   = soup.find_all(class_=re.compile(r'dpTableKey',   re.I))
    values = soup.find_all(class_=re.compile(r'dpTableValue', re.I))
    print(f"[scraper] dpTableKey divs: {len(keys)}  dpTableValue divs: {len(values)}")

    # Print first 20 key-value pairs
    for k, v in zip(keys[:20], values[:20]):
        print(f"  KEY='{k.get_text(strip=True)[:40]}' => VALUE='{v.get_text(strip=True)[:60]}'")

    # Also print ALL class names present to understand the structure
    all_classes = set()
    for tag in soup.find_all(class_=True):
        for c in tag.get("class", []):
            if any(w in c.lower() for w in ['dp','panchang','muhurt','kalam','tithi','timing']):
                all_classes.add(c)
    print(f"[scraper] Relevant CSS classes: {sorted(all_classes)[:30]}")

    return html


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


def parse_dp_divs(soup, tz_label):
    """Parse Drikpanchang's dpTableKey + dpTableValue div pairs."""
    result = {}

    # Strategy 1: paired dpTableKey / dpTableValue siblings
    keys   = soup.find_all(class_=re.compile(r'dpTableKey',   re.I))
    values = soup.find_all(class_=re.compile(r'dpTableValue', re.I))
    for k, v in zip(keys, values):
        label = re.sub(r'[^\w\s]', '', k.get_text(strip=True).lower()).strip()
        value = v.get_text(separator=" ", strip=True)
        if label and len(label) < 80:
            times = extract_times(value)
            result[label] = fmt(times, tz_label) if times else value[:120]

    # Strategy 2: any element whose class contains timing-related words
    for cls_pattern in [r'rahu', r'kalam', r'muhurt', r'abhijit', r'amrit',
                        r'gulika', r'yama', r'sunrise', r'sunset', r'tithi',
                        r'nakshatra', r'yoga', r'varjyam']:
        for elem in soup.find_all(class_=re.compile(cls_pattern, re.I)):
            text = elem.get_text(separator=" ", strip=True)
            label = re.sub(r'[^\w\s]', '', cls_pattern).strip()
            times = extract_times(text)
            if times and label not in result:
                result[label] = fmt(times, tz_label)

    # Strategy 3: scan ALL divs/spans for label+time pairs in same container
    for container in soup.find_all(['div', 'li', 'section']):
        text = container.get_text(separator="|", strip=True)
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) >= 2:
            for i in range(len(parts) - 1):
                label_candidate = parts[i].lower()
                value_candidate = parts[i+1]
                times = extract_times(value_candidate)
                if times and any(w in label_candidate for w in
                    ['rahu', 'abhijit', 'gulika', 'yama', 'muhurt', 'amrit',
                     'varj', 'sunrise', 'sunset', 'tithi', 'nakshatra', 'yoga']):
                    key = re.sub(r'[^\w\s]', '', label_candidate).strip()[:60]
                    if key not in result:
                        result[key] = fmt(times, tz_label)

    return result


def lookup(table, *keys):
    for key in keys:
        k = re.sub(r'[^\w\s]', '', key.lower()).strip()
        if k in table:
            return table[k]
        for tk, tv in table.items():
            if k in tk:
                return tv
    return "N/A"


def find_text_field(soup, *labels):
    """Find text value from dpTableKey/dpTableValue pairs."""
    keys   = soup.find_all(class_=re.compile(r'dpTableKey',   re.I))
    values = soup.find_all(class_=re.compile(r'dpTableValue', re.I))
    for k, v in zip(keys, values):
        kt = k.get_text(strip=True)
        for label in labels:
            if label.lower() in kt.lower():
                return v.get_text(separator=" ", strip=True)
    return "N/A"


def first_part(val):
    if not val or val == "N/A":
        return "N/A"
    val = re.split(r'\s+upto\s+|\s+till\s+', val, flags=re.I)[0]
    return val.split(",")[0].strip()[:50]


def parse_panchang(html, ref_date, city_key):
    from bs4 import BeautifulSoup
    soup     = BeautifulSoup(html, "html.parser")
    city     = CITIES[city_key]
    tz_label = city["tz_label"]

    table = parse_dp_divs(soup, tz_label)
    print(f"     Found {len(table)} entries")
    for k, v in list(table.items())[:30]:
        print(f"     '{k}' => '{v[:60]}'")

    data = {
        "date": ref_date.isoformat(), "weekday": ref_date.strftime("%A"),
        "city_key": city_key, "city": city["display"],
        "timezone": city["timezone"], "tz_label": tz_label,
    }

    data["tithi"]           = first_part(find_text_field(soup, "Tithi"))
    data["nakshatra"]       = first_part(find_text_field(soup, "Nakshatra"))
    data["yoga"]            = first_part(find_text_field(soup, "Yoga"))
    data["karana"]          = first_part(find_text_field(soup, "Karana"))
    data["masa"]            = first_part(find_text_field(soup, "Masa", "Maasa"))
    data["paksha"]          = first_part(find_text_field(soup, "Paksha"))
    data["rahukaal"]        = lookup(table, "rahu kalam", "rahukalam", "rahu kaal", "rahu")
    data["durmuhurtam"]     = lookup(table, "dur muhurtam", "durmuhurtam")
    data["gulika"]          = lookup(table, "gulikai kalam", "gulika kalam", "gulika")
    data["yamagandam"]      = lookup(table, "yamaganda", "yamagandam")
    data["varjyam"]         = lookup(table, "varjyam", "varjam")
    data["brahma_muhurta"]  = lookup(table, "brahma muhurta")
    data["abhijit"]         = lookup(table, "abhijit muhurta", "abhijit")
    data["vijaya_muhurta"]  = lookup(table, "vijaya muhurta")
    data["godhuli_muhurta"] = lookup(table, "godhuli muhurta")
    data["amrit_kalam"]     = lookup(table, "amrit kalam", "amritkalam")
    data["sunrise"]         = lookup(table, "sunrise")
    data["sunset"]          = lookup(table, "sunset")
    data["moonrise"]        = lookup(table, "moonrise")
    data["moonset"]         = lookup(table, "moonset")

    print(f"     Tithi: {data['tithi']} | Rahukaal: {data['rahukaal']} | Abhijit: {data['abhijit']}")
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
