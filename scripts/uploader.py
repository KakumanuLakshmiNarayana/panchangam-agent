"""
uploader.py — Uploads approved video to YouTube Shorts and Instagram Reels.
"""

import os
import sys
import json
import time
from pathlib import Path


# ── YouTube Upload ─────────────────────────────────────────────
def upload_youtube(video_path: str, script_data: dict) -> str:
    """Upload to YouTube Shorts using YouTube Data API v3."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials

    creds_json = os.environ.get("YOUTUBE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise ValueError("YOUTUBE_CREDENTIALS_JSON secret not set")
    
    creds_data = json.loads(creds_json)
    creds = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    youtube = build("youtube", "v3", credentials=creds)

    title       = script_data.get("video_title", "Daily Panchangam")[:100]
    description = script_data.get("video_description", "Daily Panchangam timings")
    date_str    = script_data.get("panchang_date", "")

    # Append #Shorts for YouTube Shorts detection
    if "#Shorts" not in description:
        description += "\n\n#Shorts #Panchangam #HinduCalendar"

    body = {
        "snippet": {
            "title": f"{title} | {date_str} #Shorts",
            "description": description,
            "tags": [
                "Panchangam", "Telugu Panchangam", "Daily Panchangam",
                "Hindu Calendar", "Rahu Kalam", "Panchang USA",
                "Telugu", "Shorts", "PanchangamUSA"
            ],
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "te",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    print("[uploader] Uploading to YouTube...")
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  YouTube upload {int(status.progress() * 100)}%")
    
    video_id = response["id"]
    url = f"https://www.youtube.com/shorts/{video_id}"
    print(f"[uploader] YouTube upload complete: {url}")
    return url


# ── Instagram Upload ───────────────────────────────────────────
def upload_instagram(video_path: str, script_data: dict) -> str:
    """Upload Instagram Reel via Meta Graph API."""
    import requests

    access_token  = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    ig_account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
    video_public_url = os.environ.get("VIDEO_PUBLIC_URL", "")

    if not access_token or not ig_account_id:
        raise ValueError("INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID must be set")

    caption = script_data.get("video_description", "Daily Panchangam")
    caption = caption[:2200]  # Instagram caption limit

    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_public_url,
        "caption": caption,
        "access_token": access_token,
        "share_to_feed": "true",
    }
    resp = requests.post(container_url, data=params, timeout=60)
    resp.raise_for_status()
    container_id = resp.json()["id"]
    print(f"[uploader] Instagram container created: {container_id}")

    # Step 2: Wait for processing
    for attempt in range(20):
        time.sleep(10)
        status_resp = requests.get(
            f"https://graph.facebook.com/v19.0/{container_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=30,
        )
        status = status_resp.json().get("status_code", "")
        print(f"  Instagram status: {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram media processing failed: {status_resp.json()}")

    # Step 3: Publish
    publish_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media_publish"
    pub_resp = requests.post(
        publish_url,
        data={"creation_id": container_id, "access_token": access_token},
        timeout=60,
    )
    pub_resp.raise_for_status()
    media_id = pub_resp.json()["id"]
    url = f"https://www.instagram.com/p/{media_id}/"
    print(f"[uploader] Instagram Reel published: {url}")
    return url


def upload_all(video_path: str, script_data: dict, platforms: list = None) -> dict:
    """Upload to all specified platforms. Returns dict of URLs."""
    if platforms is None:
        platforms = ["youtube", "instagram"]
    
    results = {}
    
    if "youtube" in platforms:
        try:
            results["youtube"] = upload_youtube(video_path, script_data)
        except Exception as e:
            print(f"[uploader] YouTube upload failed: {e}")
            results["youtube_error"] = str(e)
    
    if "instagram" in platforms:
        try:
            results["instagram"] = upload_instagram(video_path, script_data)
        except Exception as e:
            print(f"[uploader] Instagram upload failed: {e}")
            results["instagram_error"] = str(e)
    
    return results


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python uploader.py <video.mp4> <script.json>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    with open(sys.argv[2], "r") as f:
        script_data = json.load(f)
    
    results = upload_all(video_path, script_data)
    print(json.dumps(results, indent=2))
