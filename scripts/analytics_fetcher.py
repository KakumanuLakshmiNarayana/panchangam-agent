"""
analytics_fetcher.py — Fetches Instagram Reels + YouTube Shorts analytics.

Outputs dashboard/analytics.json with:
  - Instagram: account stats, per-reel metrics (reach, plays, likes, comments, shares, saved)
  - YouTube: channel stats, per-short metrics (views, likes, comments, watchTime)
  - Top hashtags performance
  - Historical snapshots (appended, last 90 entries kept)
"""
import os, json, re, sys
from datetime import datetime, timedelta, date
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent.parent / "dashboard" / "analytics.json"
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

TODAY = date.today().isoformat()


# ── helpers ─────────────────────────────────────────────────────────────────

def _load_existing():
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text())
        except Exception:
            pass
    return {"instagram": {}, "youtube": {}, "snapshots": [], "last_updated": ""}


def _save(data):
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    OUTPUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"✅ Analytics saved → {OUTPUT_FILE}")


# ── Instagram Graph API ──────────────────────────────────────────────────────

def fetch_instagram():
    import requests

    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    ig_id = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
    if not token or not ig_id:
        print("⚠️  Instagram credentials not set — skipping")
        return None

    base = "https://graph.facebook.com/v19.0"

    # Account stats
    acc = requests.get(f"{base}/{ig_id}", params={
        "fields": "followers_count,follows_count,media_count,name,biography",
        "access_token": token
    }, timeout=20).json()

    print(f"  Instagram account: {acc.get('name')} — {acc.get('followers_count')} followers")

    # Fetch recent reels (last 50)
    media_resp = requests.get(f"{base}/{ig_id}/media", params={
        "fields": "id,caption,media_type,timestamp,permalink,thumbnail_url,like_count,comments_count",
        "limit": 50,
        "access_token": token
    }, timeout=30).json()

    reels = [m for m in media_resp.get("data", []) if m.get("media_type") == "REELS"]
    print(f"  Found {len(reels)} reels")

    reel_details = []
    for reel in reels:
        rid = reel["id"]
        # Per-reel insights
        try:
            ins = requests.get(f"{base}/{rid}/insights", params={
                "metric": "reach,impressions,likes,comments,shares,saved,plays,ig_reels_avg_watch_time,ig_reels_video_view_total_time",
                "access_token": token
            }, timeout=20).json()

            metrics = {i["name"]: i["values"][0]["value"] if i.get("values") else i.get("value", 0)
                       for i in ins.get("data", [])}
        except Exception as e:
            print(f"    Reel {rid} insights error: {e}")
            metrics = {}

        # Extract city + date from caption
        caption = reel.get("caption", "")
        city_match = re.search(r'(New York|Chicago|Dallas|Los Angeles|Detroit)', caption)
        city = city_match.group(1) if city_match else "Unknown"

        # Extract hashtags from caption
        hashtags = re.findall(r'#\w+', caption)

        reel_details.append({
            "id":           rid,
            "city":         city,
            "timestamp":    reel.get("timestamp", ""),
            "permalink":    reel.get("permalink", ""),
            "thumbnail":    reel.get("thumbnail_url", ""),
            "caption_short": caption[:120],
            "hashtags":     hashtags,
            "likes":        reel.get("like_count", 0),
            "comments":     reel.get("comments_count", 0),
            **metrics,
        })

    # Hashtag performance: aggregate reach by hashtag
    hashtag_stats = {}
    for r in reel_details:
        reach = r.get("reach", 0) or 0
        plays = r.get("plays", 0) or 0
        for tag in r.get("hashtags", []):
            t = tag.lower()
            if t not in hashtag_stats:
                hashtag_stats[t] = {"count": 0, "total_reach": 0, "total_plays": 0}
            hashtag_stats[t]["count"] += 1
            hashtag_stats[t]["total_reach"] += reach
            hashtag_stats[t]["total_plays"] += plays

    # Sort by total reach
    top_hashtags = sorted(hashtag_stats.items(),
                          key=lambda x: x[1]["total_reach"], reverse=True)[:20]

    return {
        "account": {
            "followers":    acc.get("followers_count", 0),
            "following":    acc.get("follows_count", 0),
            "media_count":  acc.get("media_count", 0),
            "name":         acc.get("name", ""),
        },
        "reels": reel_details,
        "top_hashtags": [{"tag": k, **v} for k, v in top_hashtags],
        "fetched_at": TODAY,
    }


# ── YouTube Data API ─────────────────────────────────────────────────────────

def fetch_youtube():
    import requests

    creds_json = os.environ.get("YOUTUBE_CREDENTIALS_JSON", "")
    if not creds_json:
        print("⚠️  YouTube credentials not set — skipping")
        return None

    # Refresh access token
    creds = json.loads(creds_json)
    token_resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type":    "refresh_token",
    }, timeout=20).json()
    access_token = token_resp.get("access_token", "")
    if not access_token:
        print(f"  YouTube token refresh failed: {token_resp}")
        return None

    headers = {"Authorization": f"Bearer {access_token}"}
    base = "https://www.googleapis.com/youtube/v3"
    yt_analytics = "https://youtubeanalytics.googleapis.com/v2"

    # Channel stats
    ch = requests.get(f"{base}/channels", params={
        "part": "snippet,statistics",
        "mine": "true"
    }, headers=headers, timeout=20).json()

    channel = ch.get("items", [{}])[0]
    stats   = channel.get("statistics", {})
    print(f"  YouTube channel: {channel.get('snippet', {}).get('title')} — {stats.get('subscriberCount')} subs")

    # List recent uploaded videos
    uploads_playlist = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
    videos = []
    if uploads_playlist:
        pl_resp = requests.get(f"{base}/playlistItems", params={
            "part": "snippet,contentDetails",
            "playlistId": uploads_playlist,
            "maxResults": 50
        }, headers=headers, timeout=30).json()
        video_ids = [i["contentDetails"]["videoId"] for i in pl_resp.get("items", [])]

        if video_ids:
            v_resp = requests.get(f"{base}/videos", params={
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids[:50])
            }, headers=headers, timeout=30).json()

            for v in v_resp.get("items", []):
                s = v.get("statistics", {})
                caption = v.get("snippet", {}).get("title", "")
                city_match = re.search(r'(New York|Chicago|Dallas|Los Angeles|Detroit)', caption)
                city = city_match.group(1) if city_match else "Unknown"
                videos.append({
                    "id":          v["id"],
                    "city":        city,
                    "title":       caption,
                    "published":   v["snippet"].get("publishedAt", ""),
                    "url":         f"https://www.youtube.com/shorts/{v['id']}",
                    "thumbnail":   v["snippet"].get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "views":       int(s.get("viewCount", 0)),
                    "likes":       int(s.get("likeCount", 0)),
                    "comments":    int(s.get("commentCount", 0)),
                    "duration":    v["contentDetails"].get("duration", ""),
                })

    # Analytics: per-video watch time (last 90 days)
    start = (date.today() - timedelta(days=90)).isoformat()
    end   = date.today().isoformat()
    try:
        analytics_resp = requests.get(f"{yt_analytics}/reports", params={
            "ids":         "channel==MINE",
            "startDate":   start,
            "endDate":     end,
            "metrics":     "views,estimatedMinutesWatched,averageViewDuration,likes,subscribersGained,subscribersLost",
            "dimensions":  "video",
            "sort":        "-views",
            "maxResults":  50
        }, headers=headers, timeout=30).json()

        # Map video_id → analytics
        col_headers = [c["name"] for c in analytics_resp.get("columnHeaders", [])]
        for row in analytics_resp.get("rows", []):
            row_dict = dict(zip(col_headers, row))
            vid_id = row_dict.get("video", "")
            for v in videos:
                if v["id"] == vid_id:
                    v["watch_minutes"]    = row_dict.get("estimatedMinutesWatched", 0)
                    v["avg_view_sec"]     = row_dict.get("averageViewDuration", 0)
                    v["subs_gained"]      = row_dict.get("subscribersGained", 0)
    except Exception as e:
        print(f"  YouTube analytics error (non-fatal): {e}")

    return {
        "channel": {
            "subscribers":   int(stats.get("subscriberCount", 0)),
            "total_views":   int(stats.get("viewCount", 0)),
            "video_count":   int(stats.get("videoCount", 0)),
            "title":         channel.get("snippet", {}).get("title", ""),
        },
        "videos": videos,
        "fetched_at": TODAY,
    }


# ── Snapshot (follower/subscriber history) ──────────────────────────────────

def _update_snapshot(data, ig, yt):
    snapshots = data.get("snapshots", [])
    entry = {"date": TODAY}
    if ig:
        entry["ig_followers"] = ig["account"]["followers"]
    if yt:
        entry["yt_subscribers"] = yt["channel"]["subscribers"]
    # Avoid duplicate for same date
    if snapshots and snapshots[-1].get("date") == TODAY:
        snapshots[-1] = entry
    else:
        snapshots.append(entry)
    # Keep last 90 days
    data["snapshots"] = snapshots[-90:]


# ── Main ─────────────────────────────────────────────────────────────────────

def fetch_all():
    data = _load_existing()

    print("\n📊 Fetching Instagram analytics...")
    ig = fetch_instagram()
    if ig:
        data["instagram"] = ig

    print("\n📊 Fetching YouTube analytics...")
    yt = fetch_youtube()
    if yt:
        data["youtube"] = yt

    _update_snapshot(data, ig, yt)
    _save(data)
    return data


if __name__ == "__main__":
    fetch_all()
