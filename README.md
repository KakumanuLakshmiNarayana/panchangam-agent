# 🕉 Daily Panchangam Video Agent

Automated daily pipeline — scrapes Drikpanchang, generates Telugu+English video,
sends for approval, then uploads to YouTube Shorts and Instagram Reels.

## Setup
See SETUP.md for full step-by-step instructions.

## Files
- scripts/scraper.py         — Fetches Drikpanchang + converts to all 6 US timezones
- scripts/script_generator.py — Claude AI writes Telugu+English narration
- scripts/voice_generator.py  — ElevenLabs / gTTS voiceover
- scripts/video_creator.py    — FFmpeg 1080x1920 video with overlays
- scripts/uploader.py         — YouTube + Instagram upload
- scripts/pipeline.py         — Main orchestrator
- dashboard/index.html        — Approval dashboard (GitHub Pages)
- .github/workflows/daily-pipeline.yml — Runs 8:30 Pm CST
