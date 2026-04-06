"""
pipeline.py — Runs full pipeline for all 5 Telugu-American cities.

Two-phase design:
  Phase 1 (--data-only):   Scrape + script only. No audio/video. Saves state for dashboard review.
  Phase 2 (--render-approved): Load approved state, render voice+video, upload.

Legacy single-shot mode (--skip-approval) still works for testing.
"""
import os, sys, json, smtplib
from datetime import date
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scraper
from script_generator import generate_video_script

# ── Output dir: use env var if set (GitHub Actions), else go up one level from scripts/
_default_output = Path(__file__).parent.parent / "output"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(_default_output)))
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"
CITY_KEYS  = ["New_York", "Chicago", "Dallas", "California", "Michigan"]

# Pre-recorded intro audio files stored in scripts/
SCRIPTS_DIR = Path(__file__).parent
CITY_AUDIO = {
    "New_York":   SCRIPTS_DIR / "Newyork Audio.mp3",
    "Chicago":    SCRIPTS_DIR / "Chicago Audio.mp3",
    "Dallas":     SCRIPTS_DIR / "Dallas Audio.mp3",
    "California": SCRIPTS_DIR / "California Audio.mp3",
    "Michigan":   SCRIPTS_DIR / "Michigan Audio.mp3",
}


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


# ── Phase 1: scrape data + generate script (no audio/video) ──────────────────

def scrape_city(city_key, today, date_str, driver, overrides=None):
    """Scrape panchangam data and generate script. No audio or video rendering."""
    print(f"\n  🏙️  Scraping {scraper.CITIES[city_key]['display']}...")
    panchang = scraper.run(today, city_key, driver=driver)

    required = ["tithi", "nakshatra", "rahukaal"]
    empty = [f for f in required if not panchang.get(f) or panchang.get(f) == "N/A"]
    if empty:
        raise ValueError(f"Scraper returned empty/N/A for required fields: {empty}. "
                         "Drikpanchang HTML may have changed.")

    if overrides:
        panchang.update(overrides)
        print(f"     ✏️  Applied {len(overrides)} override(s)")

    script = generate_video_script(panchang)
    print(f"     Title: {script.get('title','')[:60]}")

    return {
        "city_key": city_key,
        "city": panchang.get("city"),
        "panchang": panchang,
        "script": script,
        "approval_status": "pending",
        "upload_result": {},
    }


def run_data_pipeline(use_tomorrow=False, city_key=None, overrides=None):
    """
    Phase 1: scrape data for all (or one) city, save state, send approval email.
    No audio or video is generated.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import timedelta
    today    = date.today() + (timedelta(days=1) if use_tomorrow else timedelta(0))
    date_str = today.isoformat()

    print("\n" + "="*55)
    print("  🕉  PANCHANGAM DATA PIPELINE — 5 CITIES (data only)")
    print(f"  📁  Output → {OUTPUT_DIR.resolve()}")
    print("="*55)

    # If regenerating a single city, load existing state first
    if city_key:
        state = load_state()
        all_cities = state.get("cities", {})
        cities_to_process = [city_key]
        city_overrides = (overrides or {}).get(city_key, {})
    else:
        all_cities = {}
        cities_to_process = CITY_KEYS
        city_overrides = None

    driver = scraper.get_driver()
    try:
        for ck in cities_to_process:
            ov = (overrides or {}).get(ck) if not city_key else city_overrides
            try:
                result = scrape_city(ck, today, date_str, driver, overrides=ov or None)
                all_cities[ck] = result
            except Exception as e:
                print(f"  ❌ {ck} failed: {e}")
                import traceback; traceback.print_exc()
                all_cities[ck] = {
                    "city_key": ck,
                    "city": scraper.CITIES[ck]["display"],
                    "error": str(e),
                }
            save_state({"date": date_str, "cities": all_cities, "approval_status": "pending"})
    finally:
        driver.quit()

    state = {"date": date_str, "cities": all_cities, "approval_status": "pending"}
    save_state(state)

    if not city_key:
        print("\n📧 Sending approval email...")
        send_approval_email(all_cities, date_str)
        print("\n✅ Data ready! Review in the dashboard, then approve to generate & upload videos.")

    return state


# ── Phase 2: render voice+video for approved state, then upload ───────────────

def render_city(city_key, city_data, date_str):
    """Generate voice + render video + create thumbnail for one city."""
    from voice_generator  import generate_voiceover
    from video_creator    import create_panchang_video, create_thumbnail
    from remotion_renderer import render_with_remotion
    import shutil

    panchang = city_data["panchang"]
    script   = city_data["script"]

    audio_path = str(OUTPUT_DIR / f"voice_{city_key}_{date_str}.mp3")

    # Use pre-recorded city audio if available, otherwise generate via TTS
    prerecorded = CITY_AUDIO.get(city_key)
    if prerecorded and prerecorded.exists():
        print(f"     🎙️  Using pre-recorded audio: {prerecorded.name}")
        shutil.copy(str(prerecorded), audio_path)
    else:
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

    city_data.update({
        "video_path": video_path,
        "thumbnail_path": thumbnail_path,
        "audio_path": audio_path,
    })
    return city_data


def run_render_and_upload():
    """
    Phase 2: load approved state from dashboard/pipeline_state.json (has any dashboard edits),
    render video for each non-rejected city, then upload.
    """
    # Prefer dashboard state (contains dashboard edits) over output state
    dashboard_state = Path(__file__).parent.parent / "dashboard" / "pipeline_state.json"
    if dashboard_state.exists():
        with open(dashboard_state, encoding="utf-8") as f:
            state = json.load(f)
        print(f"📂 Loaded state from dashboard/pipeline_state.json")
    else:
        state = load_state()
        print(f"📂 Loaded state from output/pipeline_state.json")

    if not state:
        print("❌ No state found. Run the data pipeline first.")
        return

    date_str = state.get("date", date.today().isoformat())
    all_cities = state.get("cities", {})

    print("\n" + "="*55)
    print("  🎬  PANCHANGAM RENDER + UPLOAD PIPELINE")
    print(f"  📅  Date: {date_str}")
    print("="*55)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for city_key, city_data in all_cities.items():
        if "error" in city_data:
            print(f"\n  ⏭️  Skipping {city_key} (has error)")
            continue
        city_status = city_data.get("approval_status", "pending")
        if city_status == "rejected":
            print(f"\n  ⏭️  Skipping {city_key} (rejected)")
            continue

        print(f"\n  🎬  Rendering {city_data.get('city', city_key)}...")
        try:
            city_data = render_city(city_key, city_data, date_str)
            all_cities[city_key] = city_data
        except Exception as e:
            print(f"  ❌ Render failed for {city_key}: {e}")
            import traceback; traceback.print_exc()

    state["cities"] = all_cities
    state["approval_status"] = "approved"
    save_state(state)

    print("\n🚀 Uploading...")
    _upload_all(state)
    return state


# ── Phase 2a: render only (no upload) ────────────────────────────────────────

def run_render_only():
    """Phase 2a: render voice+video for all non-rejected cities. No upload."""
    dashboard_state = Path(__file__).parent.parent / "dashboard" / "pipeline_state.json"
    if dashboard_state.exists():
        with open(dashboard_state, encoding="utf-8") as f:
            state = json.load(f)
        print(f"📂 Loaded state from dashboard/pipeline_state.json")
    else:
        state = load_state()
        print(f"📂 Loaded state from output/pipeline_state.json")

    if not state:
        print("❌ No state found. Run --data-only first.")
        return

    date_str   = state.get("date", date.today().isoformat())
    all_cities = state.get("cities", {})

    print("\n" + "="*55)
    print("  🎬  PANCHANGAM RENDER PIPELINE")
    print(f"  📅  Date: {date_str}")
    print("="*55)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for city_key, city_data in all_cities.items():
        if "error" in city_data:
            print(f"\n  ⏭️  Skipping {city_key} (has error)")
            continue
        if city_data.get("approval_status") == "rejected":
            print(f"\n  ⏭️  Skipping {city_key} (rejected)")
            continue
        print(f"\n  🎬  Rendering {city_data.get('city', city_key)}...")
        try:
            # Always regenerate script from panchang so dashboard edits
            # (saved back into panchang via saveStateToRepo) are reflected
            # in both on-screen text AND the voice narration
            try:
                city_data["script"] = generate_video_script(city_data["panchang"])
                print(f"     ✅ Script regenerated from latest panchang data")
            except Exception as e:
                print(f"     ⚠️  Script regen failed ({e}) — using cached script")

            city_data = render_city(city_key, city_data, date_str)
            city_data["approval_status"] = "rendered"
            all_cities[city_key] = city_data
        except Exception as e:
            print(f"  ❌ Render failed for {city_key}: {e}")
            import traceback; traceback.print_exc()

    state["cities"]          = all_cities
    state["approval_status"] = "rendered"
    state["render_run_id"]   = os.environ.get("GITHUB_RUN_ID", "")
    save_state(state)
    print("\n✅ Videos rendered! Review thumbnails in the dashboard, then approve to upload.")
    return state


# ── Phase 2b: upload only (expects rendered artifacts in output/) ─────────────

def run_upload_only():
    """Phase 2b: upload already-rendered videos. Normalises paths to OUTPUT_DIR."""
    dashboard_state = Path(__file__).parent.parent / "dashboard" / "pipeline_state.json"
    if dashboard_state.exists():
        with open(dashboard_state, encoding="utf-8") as f:
            state = json.load(f)
        print(f"📂 Loaded state from dashboard/pipeline_state.json")
    else:
        state = load_state()
        print(f"📂 Loaded state from output/pipeline_state.json")

    if not state:
        print("❌ No state found.")
        return

    date_str   = state.get("date", date.today().isoformat())
    all_cities = state.get("cities", {})

    print("\n" + "="*55)
    print("  🚀  PANCHANGAM UPLOAD PIPELINE")
    print(f"  📅  Date: {date_str}")
    print("="*55)

    # Normalise absolute render-runner paths → current OUTPUT_DIR
    for city_data in all_cities.values():
        for key in ("video_path", "thumbnail_path", "audio_path"):
            val = city_data.get(key)
            if val:
                city_data[key] = str(OUTPUT_DIR / os.path.basename(val))

    # Validate at least one city has a rendered video to upload
    uploadable = [
        ck for ck, cd in all_cities.items()
        if cd.get("video_path") and Path(cd["video_path"]).exists()
        and cd.get("approval_status") not in ("rejected",)
        and "error" not in cd
    ]
    if not uploadable:
        print("❌ No rendered video files found in output/. "
              "Run --render-only first and ensure artifacts were downloaded.")
        return

    print(f"  📦  Cities to upload: {', '.join(uploadable)}")
    state["cities"] = all_cities
    _upload_all(state)

    # Only mark as "uploaded" if at least one platform actually succeeded
    any_success = any(
        result.get("upload_result", {}).get("youtube") or
        result.get("upload_result", {}).get("instagram")
        for result in state.get("cities", {}).values()
        if "error" not in result
    )
    if any_success:
        state["approval_status"] = "uploaded"
        print("\n✅ Upload complete.")
    else:
        print("\n❌ All uploads failed — approval_status remains 'rendered'. "
              "Check the error messages above and retry.")
    save_state(state)
    return state


# ── Legacy single-shot pipeline (--skip-approval) ────────────────────────────

def process_city(city_key, today, date_str, driver):
    """Single-shot: scrape + script + audio + video in one go."""
    import shutil
    from voice_generator  import generate_voiceover
    from video_creator    import create_panchang_video, create_thumbnail
    from remotion_renderer import render_with_remotion

    print(f"\n  🏙️  Processing {scraper.CITIES[city_key]['display']}...")
    panchang = scraper.run(today, city_key, driver=driver)

    required = ["tithi", "nakshatra", "rahukaal"]
    empty = [f for f in required if not panchang.get(f) or panchang.get(f) == "N/A"]
    if empty:
        raise ValueError(f"Scraper returned empty/N/A for required fields: {empty}. "
                         "Drikpanchang HTML may have changed.")

    script = generate_video_script(panchang)
    print(f"     Title: {script.get('title','')[:60]}")

    audio_path = str(OUTPUT_DIR / f"voice_{city_key}_{date_str}.mp3")

    # Use pre-recorded city audio if available, otherwise generate via TTS
    prerecorded = CITY_AUDIO.get(city_key)
    if prerecorded and prerecorded.exists():
        print(f"     🎙️  Using pre-recorded audio: {prerecorded.name}")
        shutil.copy(str(prerecorded), audio_path)
    else:
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


def run_pipeline(skip_approval=False, use_tomorrow=False):
    """Legacy single-shot pipeline. Use --skip-approval to auto-upload without review."""
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
    """Legacy upload from saved state (no re-render)."""
    state = load_state()
    if not state:
        print("❌ No state found.")
        return
    state["approval_status"] = "approved"
    save_state(state)
    _upload_all(state)


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
    <h1 style="margin:0;font-size:28px;">🕉 5 Panchangam Data Ready for Review</h1>
    <p style="color:#FFD700;margin:6px 0;">New York · Chicago · Dallas · Los Angeles · Detroit</p>
    <p style="color:#FFD700;margin:0;">{date_str}</p>
  </div>
  <div style="padding:20px;">
    <p style="color:#444;">Panchangam data scraped for all 5 cities. <strong>Review and approve in the dashboard</strong> — videos will be generated only after you approve.</p>
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
      <strong>👁️ Review data:</strong> Open the dashboard → Panchangam tab → edit any values if needed<br><br>
      <strong>✅ To generate &amp; publish all 5 videos:</strong> Dashboard → Approve All
    </div>
  </div>
</div></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🕉 5 Panchangam Data Ready for Review — {date_str}"
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


def _upload_all(state):
    try:
        from uploader import upload_approved_video
        for city_key, result in state.get("cities", {}).items():
            if "error" in result:
                print(f"\n  ⏭️  Skipping {city_key} (has error)")
                continue
            if result.get("approval_status") == "rejected":
                print(f"\n  ⏭️  Skipping {city_key} (rejected)")
                continue
            video_path = result.get("video_path")
            if not video_path or not Path(video_path).exists():
                print(f"\n  ⏭️  Skipping {city_key} (video file missing: {video_path})")
                continue
            print(f"\n🚀 Uploading {result.get('city','?')}...")
            try:
                ur = upload_approved_video(
                    video_path=video_path,
                    thumbnail_path=result.get("thumbnail_path", ""),
                    script=result["script"],
                    date_str=state["date"],
                )
                result["upload_result"] = ur
                if ur.get("youtube") or ur.get("instagram"):
                    result["approval_status"] = "uploaded"
                else:
                    print(f"   ⚠️  {city_key}: no successful platform upload "
                          f"(errors: {[v for k,v in ur.items() if 'error' in k]})")
            except Exception as e:
                print(f"   ❌ {city_key}: {e}")
        save_state(state)
    except Exception as e:
        print(f"❌ Upload error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-only",       action="store_true",
                        help="Phase 1: scrape data + script only, no video render")
    parser.add_argument("--render-only",     action="store_true",
                        help="Phase 2a: render videos only, no upload")
    parser.add_argument("--upload-only",     action="store_true",
                        help="Phase 2b: upload already-rendered videos")
    parser.add_argument("--render-approved", action="store_true",
                        help="Legacy: render + upload in one shot from approved state")
    parser.add_argument("--skip-approval",   action="store_true",
                        help="Legacy: single-shot scrape+render+upload without review")
    parser.add_argument("--upload-approved", action="store_true",
                        help="Legacy: upload from existing rendered artifact")
    parser.add_argument("--tomorrow",        action="store_true",
                        help="Fetch and generate for tomorrow's date (run at 8 PM)")
    parser.add_argument("--city",            default=None,
                        help="Regenerate data for a single city key (use with --data-only)")
    parser.add_argument("--overrides",       default=None,
                        help="JSON string of field overrides keyed by city_key")
    args = parser.parse_args()

    overrides = json.loads(args.overrides) if args.overrides else None

    if args.render_only:
        run_render_only()
    elif args.upload_only:
        run_upload_only()
    elif args.render_approved:
        run_render_and_upload()
    elif args.data_only:
        run_data_pipeline(use_tomorrow=args.tomorrow, city_key=args.city, overrides=overrides)
    elif args.upload_approved:
        upload_approved()
    else:
        run_pipeline(skip_approval=args.skip_approval, use_tomorrow=args.tomorrow)
