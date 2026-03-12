"""
scraper.py — Selenium-based scraper with proper wait for full JS render.
"""

import json, re, sys, time, os
from datetime import datetime, date

CITIES = {
    "New_York":   {"display": "New York, NY",    "timezone": "America/New_York",    "tz_label": "ET", "geoname_id": "5128581"},
    "Chicago":    {"display": "Chicago, IL",     "timezone": "America/Chicago",     "tz_label": "CT", "geoname_id": "4887398"},
    "Dallas":     {"display": "Dallas, TX",      "timezone": "America/Chicago",     "tz_label": "CT", "geoname_id": "4684888"},
    "California": {"display": "Los Angeles, CA", "timezone": "America/Los_Angeles", "tz_label": "PT", "geoname_id": "5368361"},  # Los Angeles city
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
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--enable-javascript")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # Try system chromedriver paths
    for path in ["/usr/bin/chromedriver", "/usr/lib/chromium-browser/chromedriver",
                 "/usr/lib/chromium/chromedriver", "chromedriver"]:
        if os.path.exists(path) or path == "chromedriver":
            try:
                driver = webdriver.Chrome(service=Service(path), options=opts)
                print(f"[scraper] Using chromedriver: {path}")
                return driver
            except:
                continue
    from webdriver_manager.chrome import ChromeDriverManager
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def fetch_rendered_html(url, driver, city_display):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    print(f"[scraper] Loading: {url}")
    driver.get(url)

    # Wait for actual panchang table data — look for a time pattern like "06:23 AM"
    # This confirms the JS has fully rendered the data tables
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(@class,'dpTableValue') or contains(@class,'panchang')]")
            )
        )
        print(f"[scraper] dpTableValue found for {city_display}")
    except:
        pass

    # Scroll down to trigger any lazy-loaded sections
    driver.execute_script("window.scrollTo(0, 500);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 1200);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 2000);")
    time.sleep(2)

    # Wait for a time value to appear anywhere on page (strong signal data is loaded)
    try:
        WebDriverWait(driver, 15).until(
            lambda d: re.search(r'\d{1,2}:\d{2}\s*(?:AM|PM)', d.page_source)
        )
        print(f"[scraper] Time values detected on page for {city_display}")
    except:
        print(f"[scraper] No time values detected after waiting — proceeding anyway")

    time.sleep(2)
    html = driver.page_source

    # Debug: find and print lines containing "Rahu" or "Sunrise" or "Tithi"
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    print(f"[scraper] Total tags in page: {len(soup.find_all())}")
    print(f"[scraper] Total <tr> rows: {len(soup.find_all('tr'))}")
    print(f"[scraper] Total <td> cells: {len(soup.find_all('td'))}")

    # Print any text containing key panchang terms
    for term in ["Rahu", "Tithi", "Sunrise", "Nakshatra", "Abhijit"]:
        matches = soup.find_all(string=re.compile(term, re.I))
        if matches:
            print(f"[scraper] Found '{term}' in {len(matches)} elements: {[m.strip()[:40] for m in matches[:3]]}")
        else:
            print(f"[scraper] '{term}' NOT FOUND in page")

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


def parse_all_rows(soup, tz_label):
    result = {}
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        for i in range(0, len(cells) - 1, 2):
            if i + 1 >= len(cells):
                break
            label = cells[i].get_text(separator=" ", strip=True)
            value = cells[i+1].get_text(separator=" ", strip=True)
            if not label or len(label) > 80:
                continue
            key = re.sub(r'[^\w\s]', '', label.lower()).strip()
            times = extract_times(value)
            if times:
                result[key] = fmt(times, tz_label)
            elif value and len(value) < 150:
                result[key] = value.strip()

    # Also scan ALL elements with class containing "dpTable" or "panchang"
    from bs4 import BeautifulSoup
    for elem in soup.find_all(class_=re.compile(r'dpTable|panchang|muhurta|kalam', re.I)):
        text = elem.get_text(separator="|", strip=True)
        parts = [p.strip() for p in text.split("|") if p.strip()]
        for i in range(0, len(parts) - 1, 2):
            label = parts[i]
            value = parts[i+1] if i+1 < len(parts) else ""
            if label and len(label) < 80:
                key = re.sub(r'[^\w\s]', '', label.lower()).strip()
                times = extract_times(value)
                if times and key not in result:
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
    for label in labels:
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if txt.lower().strip() == label.lower().strip() or \
               (label.lower() in txt.lower() and len(txt) < 40):
                nxt = td.find_next_sibling("td")
                if nxt:
                    val = nxt.get_text(separator=" ", strip=True)
                    if val and len(val) < 200:
                        return val
        # Also try divs/spans with matching class
        for elem in soup.find_all(class_=re.compile(label.replace(" ",""), re.I)):
            val = elem.get_text(strip=True)
            if val and len(val) < 200:
                return val
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

    table = parse_all_rows(soup, tz_label)
    print(f"     Found {len(table)} table entries")
    for k, v in table.items():
        if any(w in k for w in ['rahu','muhurt','kalam','gulika','yama',
                                  'abhijit','amrit','varj','sunrise',
                                  'sunset','moon','tithi','nakshatra','yoga']):
            print(f"     KEY: '{k}' => '{v[:60]}'")

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
    data["rahukaal"]        = lookup(table, "rahu kalam", "rahukalam", "rahu kaal")
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
        html = fetch_rendered_html(url, driver, city["display"])
        return parse_panchang(html, target_date, city_key)
    finally:
        if own_driver:
            driver.quit()


def run_all_cities(target_date=None):
    if target_date is None:
        target_date = date.today()
    driver  = get_driver()
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
