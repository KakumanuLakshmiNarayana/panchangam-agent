"""
pipeline.py — Runs full pipeline for all 5 Telugu-American cities.
Produces 5 videos per day, sends one approval email with all 5 previews.
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

OUTPUT_DIR = Path("output")
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"

CITY_KEYS = ["New_York", "Chicago", "Dallas", "California", "Michigan"]


def save_state(state):
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"💾 State saved")


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def process_city(city_key, today, date_str):
    """Run full pipeline for one city. Returns city result dict."""
    print(f"\n  🏙️  Processing {scraper.CITIES[city_key]['display']}...")

    # Scrape
    panchang = scraper.run(today, city_key)
    print(f"     Tithi: {panchang.get('tithi','?')[:40]}")

    # Script
    script = generate_video_script(panchang)
    print(f"     Title: {script.get('title','')[:55]}")

    # Voice
    audio_path = str(OUTPUT_DIR / f"voice_{city_key}_{date_str}.mp3")
    try:
        generate_voiceover(script, audio_path)
    except Exception as e:
        print(f"     ⚠️  Voice failed: {e}")
        audio_path = ""

    # Video
    video_path     = str(OUTPUT_DIR / f"video_{city_key}_{date_str}.mp4")
    thumbnail_path = str(OUTPUT_DIR / f"thumb_{city_key}_{date_str}.jpg")
    create_panchang_video(panchang, script, audio_path, video_path)
    create_thumbnail(panchang, thumbnail_path)

    return {
        "city_key":      city_key,
        "city":          panchang.get("city"),
        "panchang":      panchang,
        "script":        script,
        "video_path":    video_path,
        "thumbnail_path":thumbnail_path,
        "audio_path":    audio_path,
        "approval_status": "pending",
        "upload_result": {},
    }


def send_approval_email(all_cities, date_str):
    sender    = os.environ.get("APPROVAL_EMAIL_FROM", "")
    recipient = os.environ.get("APPROVAL_EMAIL_TO",   "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not all([sender, recipient, smtp_pass]):
        print("⚠️  Email secrets not set — skipping email.")
        return

    rows = ""
    for city_key, result in all_cities.items():
        p = result.get("panchang", {})
        s = result.get("script",   {})
        city = p.get("city", city_key)
        rows += f"""
        <tr style="border-bottom:1px solid #ddd;">
          <td style="padding:10px;font-weight:bold;color:#8B0000;">{city}</td>
          <td style="padding:10px;">{p.get('tithi','N/A')[:35]}</td>
          <td style="padding:10px;">{p.get('nakshatra','N/A')[:25]}</td>
          <td style="padding:10px;color:#c1121f;">{p.get('rahukaal','N/A')}</td>
          <td style="padding:10px;color:#2d6a4f;">{p.get('abhijit','N/A')}</td>
        </tr>"""

    html = f"""
<html><body style="font-family:Georgia,serif;background:#fdf6ec;padding:20px;">
<div style="max-width:750px;margin:auto;background:white;border-radius:12px;overflow:hidden;">
  <div style="background:#8B0000;color:gold;padding:20px;text-align:center;">
    <h1 style="margin:0;">🕉 5 Panchangam Videos Ready</h1>
    <p style="color:#FFD700;margin:6px 0;">New York · Chicago · Dallas · Los Angeles · Detroit</p>
    <p style="color:#FFD700;margin:0;">{date_str}</p>
  </div>
  <div style="padding:24px;">
    <p style="color:#444;">All 5 city-specific videos have been generated with <strong>exact local timings</strong>. 
    Review below and approve to publish all to YouTube Shorts + Instagram Reels.</p>

    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr style="background:#8B0000;color:white;">
        <th style="padding:10px;text-align:left;">City</th>
        <th style="padding:10px;text-align:left;">Tithi</th>
        <th style="padding:10px;text-align:left;">Nakshatra</th>
        <th style="padding:10px;text-align:left;">⛔ Rahukaal</th>
        <th style="padding:10px;text-align:left;">✅ Abhijit</th>
      </tr>
      {rows}
    </table>

    <div style="background:#e8f5e9;padding:16px;border-radius:8px;margin-top:20px;text-align:center;">
      <strong style="color:#2d6a4f;">To approve all 5 videos and publish:</strong><br><br>
      GitHub repo → <strong>Actions</strong> → <strong>Daily Panchangam Pipeline</strong><br>
      → <strong>Run workflow</strong> → set <strong>upload_approved = true</strong> → Run
    </div>

    <p style="color:#888;font-size:13px;margin-top:16px;text-align:center;">
      5 videos · 5 cities · Exact local timings · Telugu+English voiceover
    </p>
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


def run_pipeline(skip_approval=False):
    OUTPUT_DIR.mkdir(exist_ok=True)
    today    = date.today()
    date_str = today.isoformat()

    print("\n" + "="*55)
    print("  🕉  DAILY PANCHANGAM PIPELINE — 5 CITIES")
    print("="*55)

    all_cities = {}
    for city_key in CITY_KEYS:
        try:
            result = process_city(city_key, today, date_str)
            all_cities[city_key] = result
        except Exception as e:
            print(f"  ❌ {city_key} failed: {e}")
            all_cities[city_key] = {"city_key": city_key, "error": str(e)}

    state = {
        "date":        date_str,
        "cities":      all_cities,
        "approval_status": "approved" if skip_approval else "pending",
    }
    save_state(state)

    if skip_approval:
        print("\n⏭️  Auto-uploading all 5 cities...")
        _upload_all(state)
    else:
        print("\n📧 Sending approval email...")
        send_approval_email(all_cities, date_str)
        print("\n✅ Done! Check your email — 5 videos ready for review.")
        print("   Approve via GitHub Actions → Run workflow → upload_approved=true")

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
        cities = state.get("cities", {})
        for city_key, result in cities.items():
            if "error" in result:
                print(f"⏭️  Skipping {city_key} (had error)")
                continue
            print(f"\n🚀 Uploading {result.get('city','?')}...")
            try:
                upload_result = upload_approved_video(
                    video_path=result["video_path"],
                    thumbnail_path=result["thumbnail_path"],
                    script=result["script"],
                    date_str=state["date"],
                )
                result["upload_result"] = upload_result
                print(f"   ✅ {result.get('city')} uploaded!")
            except Exception as e:
                print(f"   ❌ {city_key} upload failed: {e}")
        save_state(state)
    except Exception as e:
        print(f"❌ Upload module error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-approval",   action="store_true")
    parser.add_argument("--upload-approved", action="store_true")
    args = parser.parse_args()
    if args.upload_approved:
        upload_approved()
    else:
        run_pipeline(skip_approval=args.skip_approval)
