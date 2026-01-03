---
name: fb-to-tiktok
description: Repurpose Facebook videos for TikTok. Download FB reels via yt-dlp, convert to 9:16 vertical format with blur background, upload via Publer API. Runs daily at 9 AM via launchd. Use when user mentions "repurpose facebook", "fb to tiktok", "download fb videos", or "upload to tiktok".
deployment: local
license: Proprietary
allowed-tools: [Bash, Read]
---

# FB-to-TikTok Video Repurposing

Download Facebook videos, convert to TikTok 9:16 format, generate captions, and upload via Publer API.

## Key Architecture

**Pipeline Type:** Pure bash + FFmpeg (no Playwright browser automation)

**Process Flow:**
1. Find videos in `exports/fb/videos/`
2. Skip already-processed (tracked in `data/fb-to-tiktok-processed.txt`)
3. Create directory structure in `exports/tiktok/raw/`
4. FFmpeg conversion to 9:16 vertical format with blur background
5. Generate thumbnail
6. Generate caption using AI (`caption-generator.py`)
7. Mark as processed

**Dependencies:**
- FFmpeg (not Playwright)
- yt-dlp for downloads
- Bash utilities
- Python for caption generation

---

## Automation

**Daily execution**: 9 AM via launchd (`com.procaffe.fb-to-tiktok`)

| Action | Command |
|--------|---------|
| Check status | `launchctl list \| grep procaffe` |
| Manual run | `./scripts/fb-to-tiktok-process.sh` |
| View logs | `tail -f logs/launchd.log` |
| Load | `launchctl load ~/Library/LaunchAgents/com.procaffe.fb-to-tiktok.plist` |
| Unload | `launchctl unload ~/Library/LaunchAgents/com.procaffe.fb-to-tiktok.plist` |

**IMPORTANT:** LaunchAgents should use local script paths (not OneDrive) to avoid permission issues with OneDrive sync.

---

## Available Scripts

### 1. Video Processing (`fb-to-tiktok-process.sh`)

Converts horizontal FB videos to 9:16 vertical format with blur background.

**Path:** `/Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/fb-to-tiktok-process.sh`

**Usage:**
```bash
# Process all new FB videos
./scripts/fb-to-tiktok-process.sh

# With verbose output
./scripts/fb-to-tiktok-process.sh -v
```

**Input:** `exports/fb/videos/`
**Output:** `exports/tiktok/raw/{date}-{video_id}/`

**FFmpeg Conversion:**
- Adds blur background for pillarboxing
- Scales to 9:16 aspect ratio (1080x1920)
- Preserves audio quality
- Generates thumbnail

---

### 2. Caption Generator (`caption-generator.py`)

Generates AI-powered captions for processed videos using Gemini.

**Path:** `/Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/caption-generator.py`

**Usage:**
```bash
# Generate captions for all unprocessed videos
/opt/homebrew/bin/python3 scripts/caption-generator.py

# Generate for specific video
/opt/homebrew/bin/python3 scripts/caption-generator.py --video-id abc123

# Dry run
/opt/homebrew/bin/python3 scripts/caption-generator.py --dry-run

# Limit to N videos
/opt/homebrew/bin/python3 scripts/caption-generator.py --limit 5
```

**Features:**
- Analyzes video content using Gemini vision
- Generates Vietnamese captions with relevant hashtags
- Saves to `caption.txt` in each video folder

---

### 3. Publer Upload (`publer-upload.py`)

Uploads processed videos to TikTok via Publer API.

**Path:** `/Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/publer-upload.py`

**Usage:**
```bash
# Upload 5 videos as drafts
/opt/homebrew/bin/python3 scripts/publer-upload.py --limit 5

# Auto-schedule (90 min intervals)
/opt/homebrew/bin/python3 scripts/publer-upload.py --limit 10 --auto-schedule

# Dry run
/opt/homebrew/bin/python3 scripts/publer-upload.py --dry-run
```

See **publer-automation** skill for full documentation.

---

### 4. Batch Download (`fb-batch-download.sh`)

Downloads multiple FB videos from a list of URLs.

**Path:** `/Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/fb-batch-download.sh`

**Usage:**
```bash
# Download from URL list
./scripts/fb-batch-download.sh urls.txt

# Download single URL
./scripts/fb-batch-download.sh "https://facebook.com/reel/..."
```

---

## Quick Start

### Full Pipeline (Manual)
```bash
# 1. Download FB videos (if not already done)
./scripts/fb-batch-download.sh urls.txt

# 2. Process to TikTok format
./scripts/fb-to-tiktok-process.sh

# 3. Generate captions
/opt/homebrew/bin/python3 scripts/caption-generator.py

# 4. Upload to Publer as drafts
/opt/homebrew/bin/python3 scripts/publer-upload.py --limit 10
```

### Full Pipeline (Automated)
```bash
# Run full pipeline orchestrator
./scripts/apify-orchestrator.sh
```

---

## Directory Structure

```
exports/
  fb/
    videos/              # Downloaded FB videos (input)
  tiktok/
    raw/                 # Converted videos ready for upload
      {date}-{video_id}/
        video.mp4        # 9:16 converted video
        thumbnail.jpg    # Auto-generated thumbnail
        caption.txt      # AI-generated caption
        metadata.json    # Source metadata
    processed/           # Already uploaded videos
    ai-generated/        # Veo-generated videos

data/
  fb-to-tiktok-processed.txt  # Tracking file
  uploaded-videos.txt         # Already uploaded to Publer
```

---

## Configuration (config.py)

```python
# Exports Directory
EXPORTS_DIR = exports/tiktok/
AI_GENERATED_DIR = exports/tiktok/ai-generated/

# Veo Video Generation (Gemini API)
VEO_MODEL_ID = "veo-3.1-fast-generate-preview"  # Fast tier: $0.15/sec
VEO_COST_PER_SECOND = 0.15
VEO_DAILY_BUDGET = 50.0     # USD
VEO_CLIP_DURATION = 8       # seconds per generation
VEO_POLL_INTERVAL = 10      # seconds between status checks
VEO_POLL_TIMEOUT = 300      # max wait for generation (5 min)
```

---

## Troubleshooting

**FFmpeg errors:**
- Ensure FFmpeg installed: `brew install ffmpeg`
- Check input video is valid

**"Operation not permitted" (LaunchAgent):**
- **Root Cause:** OneDrive file permissions
- **Fix:** Use local script path in LaunchAgent plist, not OneDrive path
- Or: `chmod 755 scripts/*.sh scripts/*.py`

**Caption generation fails:**
- Check `GEMINI_API_KEY` env var
- Verify video file exists and is readable

**Publer upload fails:**
- See **publer-automation** skill for troubleshooting
- Check `PUBLER_API_KEY` env var

---

## References

See `references/` folder for detailed documentation:
- `processing.md` - FFmpeg conversion details
- `captions.md` - Caption generation prompts
- `upload.md` - Publer upload workflow
