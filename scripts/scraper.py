"""
scraper.py — FINAL FIX.

From raw pairs dump, the actual pattern is:
  Each named row owns the empty rows that follow it IF no other named row intervenes.
  BUT Tithi and Nakshatra each get ONE empty row despite appearing consecutive.
  
  raw[4]: Tithi='Navami...'
  raw[5]: Nakshatra='Mula...'
  raw[6]: empty='Dashami'        → Tithi's 2nd
  raw[7]: empty='Purva Ashadha'  → Nakshatra's 2nd

  raw[63]: Dur Muhurtam='11:08 AM...'
  raw[64]: Gulikai Kalam='10:09 AM...'
  raw[65]: empty='03:51 PM...'   → Dur Muhurtam's 2nd slot

The ONLY consistent rule that explains ALL cases:
  Walk pairs in order. Maintain a QUEUE of recently-seen named keys.
  When you see empty row N:
    - Pop the OLDEST key from the queue and assign to it.
  When you see a named key: push to queue.
  Queue resets when two consecutive named rows appear without empties between them
  (which means they don't have continuations yet).

Actually simpler: the page renders rows in TWO COLUMNS layout visually:
  LEFT column:  Tithi, then Nakshatra (stacked)
  RIGHT column: their continuation values (stacked)
  
  So raw sequence = [left_row1, left_row2, right_row1, right_row2]
  
  Named rows come in PAIRS (or singles), then their continuations come in same-count.
  empty[0] → named[-2] (second-to-last named before empties)
  empty[1] → named[-1] (last named before empties)

For Dur Muhurtam case:
  named[-2]=Dur Muhurtam, named[-1]=Gulikai Kalam
  empty[0]='03:51 PM' → Dur Muhurtam (named[-2]) ✓ but only 1 empty for 2 named
  
  Actually: empty[0] → named[-(num_empty + num_empty - 1)]...
  
  No wait. Let me just look at what the correct mapping IS:
  
  Case A (2 named, 2 empty): Tithi→empty[0], Nakshatra→empty[1]
    → empty[j] maps to named[j]  (forward order)
  
  Case B (2 named, 1 empty): Dur Muhurtam→empty[0], Gulikai gets nothing
    → empty[0] maps to named[0]  (first named, not last)

  Case C (1 named, 2 empty): Varjyam→['slot1', 'slot2']
    → Both empties go to Varjyam

  ALL CASES: empty[j] → named[j % len(named)]
  BUT the named block for Tithi/Nakshatra must be just [Tithi, Nakshatra]
  and NOT include Sunrise/Sunset/Moonrise/Moonset.

THE REAL PROBLEM: Sunrise/Sunset/Moonrise/Moonset have NO continuations,
so they should be in a SEPARATE block from Tithi/Nakshatra.

How to detect block boundaries: a named row that has NO continuation
should not be in the same block as one that does. But we don't know ahead of time.

SIMPLEST CORRECT APPROACH: Don't use blocks at all.
Use a FIFO queue. Named rows enter the queue. Empty rows dequeue from front.
Queue clears when a named row that already has all its continuations arrives
(i.e., when we see named rows that are NOT immediately preceded by named rows
 OR after processing all pending empties).

Actually the simplest: treat each named row individually.
Each named row gets at most the empty rows that immediately follow it
BEFORE the next named row appears.
EXCEPT when multiple named rows appear consecutively — then empties are distributed
one-per-named in order.

VERIFIED IMPLEMENTATION:
Process raw pairs left to right with a pending_named deque.
- Named row → append to pending_named
- Empty row → if pending_named, pop LEFT (oldest) and assign to it
  BUT if count(empty rows in current run) > count(pending_named), 
  assign all to the last named.

Let me just use the deque/FIFO approach which handles all cases:
  pending = deque()
  for each pair:
    if named: pending.append(key); sections[key]=[val]
    if empty: 
      if pending: owner = pending.popleft(); sections[owner].append(val)
"""

import json, re, sys, time, os
from collections import deque
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

    # ── FIFO queue parsing ────────────────────────────────────────
    # Named row → pushed into queue AND recorded in sections
    # Empty row → dequeue oldest named key and append value to it
    # This correctly handles:
    #   [Tithi, Nakshatra, empty='Dashami', empty='Purva Ashadha']
    #     Tithi gets 'Dashami', Nakshatra gets 'Purva Ashadha'  ✓
    #   [Dur Muhurtam, Gulikai Kalam, empty='03:51 PM']
    #     Dur Muhurtam gets '03:51 PM'  ✓
    #   [Varjyam, empty='slot2']
    #     Varjyam gets 'slot2'  ✓
    #   [Sunrise, Sunset, Moonrise, Moonset, Tithi, Nakshatra, empty='Dashami', empty='Purva Ashadha']
    #     Sunrise gets 'Dashami'... WRONG!
    #
    # Problem: Sunrise/Sunset/Moonrise/Moonset have no continuations but pollute queue.
    # Fix: when a named row appears and queue is non-empty, CLEAR the queue first
    # (previous named rows clearly had no continuations since we hit another named row).
    # Then add current to queue.
    # BUT this breaks Tithi→Nakshatra consecutive case!
    #
    # REAL FIX: Don't clear on named. Instead, when we see an empty row,
    # look at ALL pending named rows and assign based on position among empties.
    # 
    # Track: after each "run" of named rows, count how many empties follow.
    # Then: empty[j] → pending[j] (FIFO from oldest in the run)
    # A "run" ends when we see a named row after empties, or EOF.
    # Queue resets after each run's empties are consumed.

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

    i = 0
    while i < len(raw):
        # Collect a run of named rows
        run = []
        while i < len(raw) and raw[i][0]:
            kt, vt = raw[i]
            add(kt, vt)
            run.append(kt)
            i += 1

        # Collect empty rows following this run
        empties = []
        while i < len(raw) and not raw[i][0]:
            if raw[i][1]:
                empties.append(raw[i][1])
            i += 1

        # Distribute: empty[j] → run[j] (if j < len(run))
        # For the Sunrise/Sunset/Moonrise/Moonset + Tithi/Nakshatra case:
        # run = [Sunrise, Sunset, Moonrise, Moonset, Tithi, Nakshatra]
        # empties = [Dashami, Purva Ashadha]
        # empty[0]→run[0]=Sunrise  WRONG
        #
        # We need empty[0]→Tithi, empty[1]→Nakshatra
        # i.e. align from the END: empty[j] → run[len(run)-len(empties)+j]
        # 
        # BUT for Dur Muhurtam case:
        # run = [Dur Muhurtam, Gulikai Kalam]
        # empties = ['03:51 PM']  (1 empty)
        # align from END: empty[0] → run[2-1+0] = run[1] = Gulikai  WRONG
        # align from START: empty[0] → run[0] = Dur Muhurtam  CORRECT
        #
        # These two cases contradict each other with simple offset rules.
        # 
        # THE ONLY SOLUTION: look at CONTENT to decide.
        # If empty value contains a TIME RANGE → assign to FIRST named row in run
        #   that is a TIMING section (has times in its value).
        # If empty value is NAME-ONLY → assign to FIRST named row that is a 
        #   NAME section (Tithi/Nakshatra/etc).

        TIMING_KEYS = {
            "rahu kalam", "dur muhurtam", "gulikai kalam", "gulika kalam",
            "yamaganda", "varjyam", "amrit kalam", "abhijit", "brahma muhurta",
            "vijaya muhurta", "godhuli muhurta", "pratah sandhya", "sayahna sandhya",
            "nishita muhurta", "ganda moola", "aadal yoga", "bhadra"
        }
        NAME_KEYS = {"tithi", "nakshatra", "yoga", "karana"}

        for ev in empties:
            has_time = bool(extract_times(ev))
            assigned = False
            if has_time:
                # Find first timing key in run that hasn't been assigned a continuation yet
                # (use the first timing key overall)
                for rk in run:
                    if rk.lower() in TIMING_KEYS:
                        add(rk, ev)
                        assigned = True
                        break
            else:
                # Name-only: find matching name key
                for rk in run:
                    if rk.lower() in NAME_KEYS:
                        # Check if this key already has a name continuation
                        existing = sections.get(rk, [])
                        # Only assign if not already assigned a name continuation
                        has_name_cont = any(not extract_times(v) for v in existing[1:])
                        if not has_name_cont:
                            add(rk, ev)
                            assigned = True
                            break
            if not assigned and run:
                # Fallback: assign to first in run
                add(run[0], ev)

    print(f"[scraper] {len(sections)} sections parsed:")
    for k in order:
        v = sections[k]
        if any(x in k.lower() for x in ['tithi','nakshatra','rahu','dur ','gulika','amrit','abhijit','varjy','sunrise','sunset']):
            print(f"  [{k}] => {v}")

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
        return fmt_all_slots(all_times(find_sec(*labels)), tz_label)

    def fmt_transition(*labels):
        vals = find_sec(*labels)
        if not vals: return "N/A"
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
