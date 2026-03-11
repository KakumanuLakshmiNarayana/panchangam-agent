"""
pipeline.py — Master orchestrator. Runs the full pipeline:
1. Scrape Panchangam
2. Generate script
3. Generate voiceover
4. Create video
5. Upload to GitHub Pages (for approval dashboard)
6. Send approval notification email
"""

import os
import sys
import json
import shutil
import smtplib
import subprocess
from datetime import date
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(__file__))
import scraper
import script_generator
import voiceover
import video_generator


WORK_DIR    = Path(os.environ.get("WORK_DIR", "/tmp/panchangam"))
ASSETS_DIR  = Path(os.environ.get("ASSETS_DIR", "assets"))
APPROVE_URL = os.environ.get("APPROVAL_DASHBOARD_URL", "")


def send_approval_email(video_path: str, script_data: dict, approval_url: str):
    """Send email with preview link asking for approval."""
    smtp_host  = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port  = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user  = os.environ.get("SMTP_USER", "")
    smtp_pass  = os.environ.get("SMTP_PASS", "")
    to_email   = os.environ.get("APPROVAL_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print("[pipeline] Email credentials not set, skipping email")
        return

    date_str  = script_data.get("panchang_date", "today")
    weekday   = script_data.get("weekday", "")
    title     = script_data.get("video_title", "Daily Panchangam")
    narration = script_data.get("main_narration", "")

    subject = f"✅ Approve Panchangam Video — {weekday}, {date_str}"

    approve_link = f"{approval_url}?date={date_str}&action=approve"
    reject_link  = f"{approval_url}?date={date_str}&action=reject"

    html_body = f"""
<html><body style="font-family:Georgia,serif;max-width:600px;margin:auto;background:#fdf6ec;padding:24px;border-radius:12px;">
  <div style="text-align:center;background:#8B0000;color:gold;padding:16px;border-radius:8px 8px 0 0;">
    <h1 style="margin:0;font-size:28px;">🪔 Daily Panchangam Video</h1>
    <p style="margin:4px 0;color:#FFD700;">{weekday}, {date_str}</p>
  </div>
  <div style="background:white;padding:20px;border:1px solid #ddd;">
    <h2 style="color:#8B0000;">Video Title: {title}</h2>
    <h3>Script Preview:</h3>
    <blockquote style="background:#fef9f0;padding:12px;border-left:4px solid #FFD700;font-style:italic;">
      {narration[:500]}...
    </blockquote>
    <h3>Opening Shloka:</h3>
    <p style="color:#8B0000;font-size:18px;">{script_data.get("opening_shloka","")}</p>
    
    <div style="text-align:center;margin-top:24px;">
      <a href="{approval_url}" style="background:#1a1a2e;color:white;padding:12px 24px;
         border-radius:6px;text-decoration:none;font-size:16px;margin:8px;">
        👁️ Preview Video Dashboard
      </a>
    </div>
    <div style="text-align:center;margin-top:16px;">
      <a href="{approve_link}" style="background:#2d6a4f;color:white;padding:14px 32px;
         border-radius:6px;text-decoration:none;font-size:18px;font-weight:bold;margin:8px;display:inline-block;">
        ✅ APPROVE & UPLOAD
      </a>
      &nbsp;&nbsp;
      <a href="{reject_link}" style="background:#c1121f;color:white;padding:14px 32px;
         border-radius:6px;text-decoration:none;font-size:18px;font-weight:bold;margin:8px;display:inline-block;">
        ❌ REJECT
      </a>
    </div>
  </div>
  <p style="text-align:center;color:#888;font-size:12px;margin-top:12px;">
    This video will auto-upload to YouTube Shorts & Instagram Reels after approval.
  </p>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    
    print(f"[pipeline] Approval email sent to {to_email}")


def run_pipeline(target_date: date = None):
    if target_date is None:
        target_date = date.today()
    
    date_str = target_date.isoformat()
    work_dir = WORK_DIR / date_str
    work_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"  PANCHANGAM PIPELINE — {date_str}")
    print(f"{'='*60}\n")

    # ── Step 1: Scrape ─────────────────────────────────────────
    print("[1/5] Scraping Panchangam data...")
    panchang_data = scraper.run(target_date)
    panchang_path = work_dir / f"panchang_{date_str}.json"
    with open(panchang_path, "w", encoding="utf-8") as f:
        json.dump(panchang_data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Panchang data saved: {panchang_path}")

    # ── Step 2: Generate Script ────────────────────────────────
    print("[2/5] Generating Telugu+English script via Claude AI...")
    script_data = script_generator.generate_script(panchang_data)
    script_path = work_dir / f"script_{date_str}.json"
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Script saved: {script_path}")

    # ── Step 3: Generate Voiceover ─────────────────────────────
    print("[3/5] Generating Telugu+English voiceover...")
    audio_path = voiceover.generate_voiceover(script_data, str(work_dir))
    print(f"  ✓ Audio saved: {audio_path}")

    # ── Step 4: Generate Video ─────────────────────────────────
    print("[4/5] Creating video with FFmpeg...")
    video_path = video_generator.generate_video(
        script_data, audio_path, str(work_dir), str(ASSETS_DIR)
    )
    print(f"  ✓ Video saved: {video_path}")

    # ── Step 5: Stage for Approval Dashboard ──────────────────
    print("[5/5] Staging files for approval dashboard...")
    
    # Save metadata for dashboard
    metadata = {
        "date": date_str,
        "status": "pending",
        "video_file": os.path.basename(video_path),
        "script": script_data,
        "panchang": panchang_data,
    }
    meta_path = work_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Copy to dashboard/pending
    dashboard_dir = Path("dashboard") / "pending" / date_str
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video_path, dashboard_dir / os.path.basename(video_path))
    shutil.copy2(meta_path,  dashboard_dir / "metadata.json")
    
    print(f"  ✓ Files staged at: {dashboard_dir}")

    # ── Send approval email ────────────────────────────────────
    if APPROVE_URL:
        send_approval_email(str(video_path), script_data, APPROVE_URL)
    else:
        print("[pipeline] APPROVAL_DASHBOARD_URL not set — skipping email")
        print(f"[pipeline] Open dashboard manually to review and approve.")

    print(f"\n{'='*60}")
    print(f"  ✅ PIPELINE COMPLETE — Awaiting approval")
    print(f"{'='*60}\n")
    
    return {
        "video_path": str(video_path),
        "script_path": str(script_path),
        "metadata_path": str(meta_path),
    }


if __name__ == "__main__":
    d = date.today()
    if len(sys.argv) > 1:
        d = date.fromisoformat(sys.argv[1])
    result = run_pipeline(d)
    print(json.dumps(result, indent=2))
