---
name: fb-automation
description: "Facebook content scraping and repurposing for Procaffe. Use when user needs to scrape Facebook videos, reels, or import content to Firebase."
license: Proprietary
allowed-tools: [Bash, Read]
---

# Facebook Automation

Comprehensive Facebook content scraping and Firebase import automation for Procaffe social media workflows. Uses Chrome CDP for browser automation.

## Chrome CDP Architecture

**Port & Profile:**
- CDP Port: `9224`
- Chrome Profile: `~/chrome-fb-profile`
- Launcher: `~/.claude/skills/fb-automation/scripts/fb-chrome-launcher.sh`

**Why CDP:**
- Session persistence: Login once, reuse forever
- Detection resistant: Real browser, real user profile
- Separate from TikTok (9222) and LinkedIn (9223) profiles

---

## When to Use This Skill

Activate when user mentions:
- "scrape facebook", "fb scrape", "facebook content"
- "download facebook videos/reels"
- "import to firebase", "firebase sync"
- "procaffe facebook", "fb to firebase"
- "discover missing videos"

---

## Available Scripts

All scripts located at `~/.claude/skills/fb-automation/scripts/`

### 1. Content Scraping (`fb-scrape-content.py`)
Scrapes posts, images, videos from ProCaffeGroup page using Apify API.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/fb-automation/scripts/fb-scrape-content.py

# Options:
--max-posts 10      # Limit to 10 posts
--skip-media        # Metadata only (no downloads)
--no-comments       # Skip comments
--dry-run           # Show what would be done
--from-cache        # Use cached Apify data
```

**Requirements:**
- `APIFY_API_KEY` env var
- yt-dlp installed

**Output:**
- `data/fb-posts.json` - Parsed posts with media
- `data/apify-fb-raw.json` - Raw Apify output
- `exports/fb/videos/` - Downloaded videos
- `exports/fb/images/` - Downloaded images

---

### 2. Video Discovery (`fb-video-discovery.py`)
Discovers video URLs via Chrome DevTools Protocol, compares with downloaded videos.

**Usage:**
```bash
# First, launch Chrome with CDP:
./scripts/fb-chrome-launcher.sh

# Then run discovery:
/opt/homebrew/bin/python3 ~/.claude/skills/fb-automation/scripts/fb-video-discovery.py

# Options:
--download          # Download missing videos
--from-cache        # Use cached video list
```

**Requirements:**
- Chrome running with CDP (port 9224)
- Playwright async_api (for CDP connection only)

**Output:**
- `data/fb-video-ids.json` - Discovered video IDs
- `exports/fb/videos/` - Downloaded videos

---

### 3. Firebase Import (`fb-firebase-import.py`)
Uploads scraped media to Firebase Storage and indexes posts in Firestore.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/fb-automation/scripts/fb-firebase-import.py

# Options:
--limit 10          # Import first 10 posts
--skip-upload       # Skip media upload, only Firestore
--dry-run           # Show what would be done
--input <file>      # Custom input file
```

**Requirements:**
- `firebase_service_account.json` in project root
- `data/fb-posts.json` from scraper

**Output:**
- Firestore collection: `fb_posts`
- Firebase Storage: `fb/videos/`, `fb/images/`
- Comments subcollection per post

---

### 4. Reels Scraper (`fb-scrape-reels.py`)
Scrapes reel URLs from Facebook page using Playwright.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/fb-automation/scripts/fb-scrape-reels.py

# Options:
<page_url>          # Custom page URL
--login             # Login first
```

---

### 5. Playwright Downloader (`fb-download-playwright.py`)
Downloads videos from Facebook using Playwright and FFmpeg.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/fb-automation/scripts/fb-download-playwright.py <url>

# Options:
--login             # Login and save session
--batch urls.txt    # Batch download from file
```

**Output:**
- `exports/tiktok/raw/{date}-{title}/` - Downloaded videos with metadata

---

## Typical Workflows

### Full Content Scrape + Firebase Import
```bash
# 1. Scrape content
/opt/homebrew/bin/python3 scripts/fb-scrape-content.py --max-posts 100

# 2. Import to Firebase
/opt/homebrew/bin/python3 scripts/fb-firebase-import.py
```

### Discover and Download Missing Videos
```bash
# 1. Launch Chrome with CDP (port 9224)
./scripts/fb-chrome-launcher.sh

# 2. Discover missing videos
/opt/homebrew/bin/python3 scripts/fb-video-discovery.py --download
```

### Batch Reel Download
```bash
# 1. Login (first time only)
/opt/homebrew/bin/python3 scripts/fb-download-playwright.py --login

# 2. Download specific videos
/opt/homebrew/bin/python3 scripts/fb-download-playwright.py --batch video-urls.txt
```

---

## Configuration (config.py)

```python
# Chrome DevTools Protocol
FB_CDP_PORT = 9224  # Separate from TikTok (9222) and LinkedIn (9223)
FB_CHROME_PROFILE = ~/chrome-fb-profile

# Facebook Page
FB_PAGE_URL = "https://www.facebook.com/ProCaffeGroup"
FB_URL_PATTERN = r'https?://(www\.|m\.|web\.)?facebook\.com/.+'

# Paths
FB_EXPORTS_DIR = exports/fb/
FB_VIDEOS_DIR = exports/fb/videos/
FB_IMAGES_DIR = exports/fb/images/
FB_POSTS_FILE = data/fb-posts.json
FB_SCRAPE_PROGRESS_FILE = data/fb-scrape-progress.json
FB_IMPORT_PROGRESS_FILE = data/fb-import-progress.json
FB_APIFY_RAW_FILE = data/apify-fb-raw.json
FB_VIDEO_IDS_FILE = data/fb-video-ids.json

# Firebase
FIREBASE_PROJECT_ID = "procaffe-d3230"
FIREBASE_STORAGE_BUCKET = "procaffe-d3230.firebasestorage.app"

# Rate Limiting
RATE_LIMIT_DELAY = 1.5  # seconds between API requests
```

---

## Environment Variables

```bash
APIFY_API_KEY=your_apify_token
```

---

## File Outputs

```
data/
  fb-posts.json              # Parsed posts
  apify-fb-raw.json          # Raw Apify data
  fb-video-ids.json          # Discovered video IDs
  fb-scrape-progress.json    # Scrape progress
  fb-import-progress.json    # Import progress

exports/
  fb/
    videos/                  # Downloaded videos
    images/                  # Downloaded images
  tiktok/
    raw/                     # Videos for TikTok processing
    processed/               # Already processed videos
```

---

## Troubleshooting

**Apify API errors:**
- Check `APIFY_API_KEY` env var
- Verify account has credits

**CDP connection errors:**
- Ensure Chrome running: `./scripts/fb-chrome-launcher.sh`
- Check port 9224 is accessible: `lsof -i :9224`

**"Operation not permitted" (LaunchAgent):**
- **Root Cause:** OneDrive file permissions
- **Fix:** Use local script path in LaunchAgent plist, not OneDrive path
- Or: `chmod 755 scripts/*.py scripts/*.sh`

**Playwright login issues:**
- Run with `--login` to establish session
- Session saved at `/tmp/playwright-fb-profile`

**Firebase errors:**
- Verify `firebase_service_account.json` exists
- Check Firebase project permissions

---

## Rate Limiting

- Apify: Managed by Apify API
- Video downloads: 1.5s delay between requests
- Image downloads: 1s delay between requests

---

## References

See `references/` for detailed documentation.
