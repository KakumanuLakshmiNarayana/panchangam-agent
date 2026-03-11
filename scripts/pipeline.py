"""
pipeline.py — Master orchestrator for Daily Panchangam Video Agent
Steps: Scrape → Script → Voice → Video → Email Approval
"""

import os
import sys
import json
import smtplib
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Make sure imports find sibling scripts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper          import get_daily_panchang
from script_generator import generate_video_script
from voice_generator  import generate_voiceover
from video_creator    import create_panchang_video, create_thumbnail

OUTPUT_DIR = Path("output")
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"


def save_state(state: dict):
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"💾 State saved: {STATE_FILE}")


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def send_approval_email(state: dict):
    sender    = os.environ.get("APPROVAL_EMAIL_FROM", "")
    recipient = os.environ.get("APPROVAL_EMAIL_TO", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", sender)
    smtp_pass = os.environ.get("SMTP_PASS", "")

    if not all([sender, recipient, smtp_pass]):
        print("⚠️  Email credentials not set — skipping approval email.")
        return

    panchang = state.get("panchang", {})
    script   = state.get("script",   {})
    date_str = state.get("date", datetime.now().strftime("%Y-%m-%d"))

    def get_et(field):
        val = panchang.get(field, {})
        if isinstance(val, dict):
            return val.get("us", {}).get("Eastern", "N/A")
        return str(val)

    narration_preview = script.get("full_narration", "")[:400]
    title             = script.get("title", f"Daily Panchangam {date_str}")

    html_body = f"""
<html><body style="font-family:Georgia,serif;background:#fdf6ec;padding:20px;">
<div style="max-width:600px;margin:auto;background:white;border-radius:12px;overflow:hidden;">
  <div style="background:#8B0000;color:gold;padding:20px;text-align:center;">
    <h1 style="margin:0;">🕉 Daily Panchangam Video Ready</h1>
    <p style="color:#FFD700;">{panchang.get('date', date_str)}</p>
  </div>
  <div style="padding:24px;">
    <h2 style="color:#8B0000;">{title[:80]}</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
      <tr><td style="padding:6px;color:#8B0000;font-weight:bold;">Tithi</td><td>{panchang.get('tithi','N/A')}</td></tr>
      <tr style="background:#fef9f0;"><td style="padding:6px;color:#8B0000;font-weight:bold;">Nakshatra</td><td>{panchang.get('nakshatra','N/A')}</td></tr>
      <tr><td style="padding:6px;color:#8B0000;font-weight:bold;">Yoga</td><td>{panchang.get('yoga','N/A')}</td></tr>
      <tr style="background:#fef9f0;"><td style="padding:6px;color:#8B0000;font-weight:bold;">Rahukaal (ET)</td><td style="color:#c1121f;">{get_et('rahukaal')}</td></tr>
      <tr><td style="padding:6px;color:#8B0000;font-weight:bold;">Abhijit (ET)</td><td style="color:#2d6a4f;">{get_et('abhijit')}</td></tr>
      <tr style="background:#fef9f0;"><td style="padding:6px;color:#8B0000;font-weight:bold;">Sunrise (ET)</td><td>{get_et('sunrise')}</td></tr>
    </table>
    <div style="background:#fef9f0;border-left:4px solid #FFD700;padding:12px;margin-bottom:20px;">
      <strong style="color:#8B0000;">🎙️ Script Preview:</strong><br>
      <em style="color:#444;">{narration_preview}...</em>
    </div>
    <div style="background:#e8f5e9;padding:16px;border-radius:8px;text-align:center;">
      <p style="margin:0 0 8px;font-weight:bold;color:#2d6a4f;">To approve and publish this video:</p>
      <p style="margin:0;color:#444;font-size:14px;">
        GitHub repo → <strong>Actions</strong> → <strong>Daily Panchangam Pipeline</strong><br>
        → <strong>Run workflow</strong> → set <strong>upload_approved = true</strong> → Run
      </p>
    </div>
  </div>
</div>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🕉 Panchangam Video Ready — {panchang.get('date', date_str)}"
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"✅ Approval email sent to: {recipient}")
    except Exception as e:
        print(f"❌ Email failed: {e}")


def run_pipeline(skip_approval: bool = False):
    OUTPUT_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")

    print("\n" + "="*55)
    print("  🕉  DAILY PANCHANGAM VIDEO PIPELINE")
    print("="*55)

    # Step 1: Scrape
    print("\n[1/5] 📅 Scraping Drikpanchang...")
    panchang = get_daily_panchang()
    print(f"      Tithi: {panchang.get('tithi')} | Nakshatra: {panchang.get('nakshatra')}")

    # Step 2: Script
    print("\n[2/5] ✍️  Generating Telugu+English script...")
    script = generate_video_script(panchang)
    print(f"      Title: {script.get('title','')[:60]}")

    # Step 3: Voice
    print("\n[3/5] 🎙️  Generating voiceover...")
    audio_path = str(OUTPUT_DIR / f"voiceover_{date_str}.mp3")
    try:
        generate_voiceover(script, audio_path)
    except Exception as e:
        print(f"      ⚠️  Voice failed: {e} — using silent video")
        audio_path = ""

    # Step 4: Video
    print("\n[4/5] 🎬 Creating video...")
    video_path     = str(OUTPUT_DIR / f"panchang_{date_str}.mp4")
    thumbnail_path = str(OUTPUT_DIR / f"thumbnail_{date_str}.jpg")
    create_panchang_video(panchang, script, audio_path, video_path)
    create_thumbnail(panchang, thumbnail_path)

    # Step 5: Save + notify
    state = {
        "date":            date_str,
        "panchang":        panchang,
        "script":          script,
        "video_path":      video_path,
        "thumbnail_path":  thumbnail_path,
        "audio_path":      audio_path,
        "approval_status": "approved" if skip_approval else "pending",
        "upload_results":  {},
    }
    save_state(state)

    if skip_approval:
        print("\n[5/5] ⏭️  Auto-uploading...")
        _upload(state)
    else:
        print("\n[5/5] 📧 Sending approval email...")
        send_approval_email(state)
        print("\n✅ Done! Check your email to approve the video.")

    return state


def upload_approved():
    state = load_state()
    if not state:
        print("❌ No state found. Run full pipeline first.")
        return
    state["approval_status"] = "approved"
    save_state(state)
    _upload(state)


def _upload(state: dict):
    try:
        from uploader import upload_approved_video
        results = upload_approved_video(
            video_path=state["video_path"],
            thumbnail_path=state["thumbnail_path"],
            script=state["script"],
            date_str=state["date"],
        )
        state["upload_results"] = results
        save_state(state)
        print("\n🚀 Upload complete!")
        for platform, result in results.items():
            print(f"   {platform.upper()}: {result.get('status')} — {result.get('url','N/A')}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")


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
