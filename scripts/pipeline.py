"""
pipeline.py — Runs full pipeline for all 5 Telugu-American cities.
"""
import os, sys, json, smtplib
from datetime import date
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scraper
from script_generator import generate_video_script
from voice_generator  import generate_voiceover
from video_creator    import create_panchang_video, create_thumbnail
from remotion_renderer import render_with_remotion

# ── Output dir: use env var if set (GitHub Actions), else go up one level from scripts/
_default_output = Path(__file__).parent.parent / "output"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(_default_output)))
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"
CITY_KEYS  = ["New_York", "Chicago", "Dallas", "California", "Michigan"]


def save_state(state):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"💾 State saved → {STATE_FILE}")


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def process_city(city_key, today, date_str, driver):
    print(f"\n  🏙️  Processing {scraper.CITIES[city_key]['display']}...")
    panchang = scraper.run(today, city_key, driver=driver)

    # Validate scraper returned real data (guards against CSS changes on drikpanchang)
    required = ["tithi", "nakshatra", "rahukaal"]
    empty = [f for f in required if not panchang.get(f) or panchang.get(f) == "N/A"]
    if empty:
        raise ValueError(f"Scraper returned empty/N/A for required fields: {empty}. "
                         "Drikpanchang HTML may have changed.")

    script = generate_video_script(panchang)
    print(f"     Title: {script.get('title','')[:60]}")

    audio_path = str(OUTPUT_DIR / f"voice_{city_key}_{date_str}.mp3")
    try:
        result = generate_voiceover(script, audio_path)
        if not result:
            print(f"     ⚠️  All TTS methods failed — no audio file generated")
            audio_path = ""
    except Exception as e:
        print(f"     ⚠️  Voice failed: {e}")
        audio_path = ""

    video_path     = str(OUTPUT_DIR / f"video_{city_key}_{date_str}.mp4")
    thumbnail_path = str(OUTPUT_DIR / f"thumb_{city_key}_{date_str}.jpg")
    try:
        render_with_remotion(panchang, script, audio_path, video_path)
    except Exception as e:
        print(f"     ⚠️  Remotion render failed: {e}")
        print(f"     ↩️  Falling back to Pillow renderer...")
        create_panchang_video(panchang, script, audio_path, video_path)
    create_thumbnail(panchang, thumbnail_path)

    return {
        "city_key": city_key, "city": panchang.get("city"),
        "panchang": panchang, "script": script,
        "video_path": video_path, "thumbnail_path": thumbnail_path,
        "audio_path": audio_path, "approval_status": "pending", "upload_result": {},
    }


def send_approval_email(all_cities, date_str):
    sender    = os.environ.get("APPROVAL_EMAIL_FROM", "")
    recipient = os.environ.get("APPROVAL_EMAIL_TO",   "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    if not all([sender, recipient, smtp_pass]):
        print("⚠️  Email secrets not set")
        return

    rows = ""
    for city_key, result in all_cities.items():
        if "error" in result:
            rows += f"<tr><td style='padding:10px;font-weight:bold;color:#8B0000;'>{result.get('city',city_key)}</td><td colspan='6' style='color:red;padding:10px;'>Error: {result['error'][:60]}</td></tr>"
            continue
        p = result.get("panchang", {})
        rows += f"""
        <tr style="border-bottom:1px solid #e0c89a;">
          <td style="padding:10px;font-weight:bold;color:#8B0000;">{p.get('city','')}</td>
          <td style="padding:10px;font-size:13px;">{p.get('tithi','N/A')}</td>
          <td style="padding:10px;font-size:13px;">{p.get('nakshatra','N/A')}</td>
          <td style="padding:10px;color:#c1121f;font-size:13px;">{p.get('rahukaal','N/A')}</td>
          <td style="padding:10px;color:#c1121f;font-size:13px;">{p.get('durmuhurtam','N/A')}</td>
          <td style="padding:10px;color:#2d6a4f;font-size:13px;">{p.get('abhijit','N/A')}</td>
          <td style="padding:10px;color:#2d6a4f;font-size:13px;">{p.get('amrit_kalam','N/A')}</td>
        </tr>"""

    html = f"""
<html><body style="font-family:Georgia,serif;background:#fdf6ec;padding:16px;">
<div style="max-width:900px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">
  <div style="background:#8B0000;color:gold;padding:20px;text-align:center;">
    <h1 style="margin:0;font-size:28px;">🕉 5 Panchangam Videos Ready</h1>
    <p style="color:#FFD700;margin:6px 0;">New York · Chicago · Dallas · Los Angeles · Detroit</p>
    <p style="color:#FFD700;margin:0;">{date_str}</p>
  </div>
  <div style="padding:20px;">
    <p style="color:#444;">All 5 city-specific videos generated with <strong>exact local timings</strong>.</p>
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr style="background:#8B0000;color:white;">
        <th style="padding:10px;text-align:left;">City</th>
        <th style="padding:10px;text-align:left;">Tithi</th>
        <th style="padding:10px;text-align:left;">Nakshatra</th>
        <th style="padding:10px;text-align:left;">⛔ Rahu Kalam</th>
        <th style="padding:10px;text-align:left;">⛔ Dur Muhurtam</th>
        <th style="padding:10px;text-align:left;">✅ Abhijit</th>
        <th style="padding:10px;text-align:left;">✅ Amrit Kalam</th>
      </tr>
      {rows}
    </table>
    </div>
    <div style="background:#e8f5e9;padding:16px;border-radius:8px;margin-top:20px;text-align:center;">
      <strong>👁️ Watch videos:</strong> GitHub repo → Actions → click today's run → Artifacts → download zip<br><br>
      <strong>✅ To publish all 5:</strong> Actions → Daily Panchangam Pipeline → Run workflow → <strong>upload_approved = true</strong>
    </div>
  </div>
</div></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🕉 5 Panchangam Videos Ready — {date_str}"
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(sender, smtp_pass)
            s.sendmail(sender, recipient, msg.as_string())
        print(f"✅ Approval email sent to {recipient}")
    except Exception as e:
        print(f"❌ Email error: {e}")


def run_pipeline(skip_approval=False, use_tomorrow=False):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import timedelta
    today    = date.today() + (timedelta(days=1) if use_tomorrow else timedelta(0))
    date_str = today.isoformat()

    print("\n" + "="*55)
    print("  🕉  DAILY PANCHANGAM PIPELINE — 5 CITIES")
    print(f"  📁  Output → {OUTPUT_DIR.resolve()}")
    print("="*55)

    driver     = scraper.get_driver()
    all_cities = {}
    try:
        for city_key in CITY_KEYS:
            try:
                result = process_city(city_key, today, date_str, driver)
                all_cities[city_key] = result
            except Exception as e:
                print(f"  ❌ {city_key} failed: {e}")
                import traceback; traceback.print_exc()
                all_cities[city_key] = {
                    "city_key": city_key,
                    "city": scraper.CITIES[city_key]["display"],
                    "error": str(e)
                }
            # Save after each city so a mid-run cancel doesn't lose completed work
            save_state({
                "date": date_str, "cities": all_cities,
                "approval_status": "approved" if skip_approval else "pending",
            })
    finally:
        driver.quit()

    state = {
        "date": date_str, "cities": all_cities,
        "approval_status": "approved" if skip_approval else "pending",
    }
    save_state(state)

    if skip_approval:
        print("\n⏭️  Auto-uploading...")
        _upload_all(state)
    else:
        print("\n📧 Sending approval email...")
        send_approval_email(all_cities, date_str)
        print("\n✅ Done! Check your email — 5 videos ready.")

    return state


def upload_approved():
    state = load_state()
    if not state:
        print("❌ No state found.")
        return
    state["approval_status"] = "approved"
    save_state(state)
    _upload_all(state)


def _upload_all(state):
    try:
        from uploader import upload_approved_video
        for city_key, result in state.get("cities", {}).items():
            if "error" in result:
                continue
            print(f"\n🚀 Uploading {result.get('city','?')}...")
            try:
                ur = upload_approved_video(
                    video_path=result["video_path"],
                    thumbnail_path=result["thumbnail_path"],
                    script=result["script"],
                    date_str=state["date"],
                )
                result["upload_result"] = ur
            except Exception as e:
                print(f"   ❌ {city_key}: {e}")
        save_state(state)
    except Exception as e:
        print(f"❌ Upload error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-approval",   action="store_true")
    parser.add_argument("--upload-approved", action="store_true")
    parser.add_argument("--tomorrow",        action="store_true",
                        help="Fetch and generate for tomorrow's date (run at 8 PM)")
    args = parser.parse_args()
    if args.upload_approved:
        upload_approved()
    else:
        run_pipeline(skip_approval=args.skip_approval, use_tomorrow=args.tomorrow)
