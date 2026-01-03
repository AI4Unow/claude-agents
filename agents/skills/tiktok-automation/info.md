---
name: tiktok-automation
description: "TikTok automation for Procaffe - auto-liking, following, scraping profiles, processing videos. Use when user mentions TikTok automation, engagement, or content scraping."
deployment: local
license: Proprietary
allowed-tools: [Bash, Read]
---

# TikTok Automation Skill

Automates TikTok engagement and content management for Procaffe using Chrome CDP (DevTools Protocol).

## When to Use

- User asks to **like TikTok videos** from followed accounts
- User wants to **follow competitors** automatically
- User needs to **scrape videos** from TikTok profiles
- User wants to **track competitors** on TikTok
- User mentions **TikTok automation**, engagement, or content discovery

## Chrome CDP Architecture

**IMPORTANT:** All scripts use Chrome DevTools Protocol (CDP) to connect to a persistent Chrome instance - NOT Playwright browser automation. Playwright is only used for the CDP connection API.

**Port & Profile:**
- CDP Port: `9222`
- Chrome Profile: `~/chrome-tiktok-profile`
- Launcher: `~/.claude/skills/tiktok-automation/scripts/tiktok-chrome-launcher.sh`

**Why CDP over Playwright Browser:**
- Session persistence: Login once, reuse forever
- Detection resistant: Real browser, real user profile
- No browser management overhead
- Separate profile isolates TikTok session

**Process:**
1. Start Chrome launcher script
2. Browser opens with CDP enabled on port 9222
3. User logs in manually (first time only)
4. Session saved to profile directory
5. Automation scripts connect via CDP
6. Browser stays open, reused for all runs

---

## Available Scripts

All scripts located at `~/.claude/skills/tiktok-automation/scripts/`. Use `/opt/homebrew/bin/python3` and require Chrome running with CDP.

### 1. Auto-Liker (`tiktok-auto-liker.py`)

Automatically like latest videos from accounts you follow. **Currently runs 6x daily (6 AM - 11 PM Vietnam time).**

**Path:** `~/.claude/skills/tiktok-automation/scripts/tiktok-auto-liker.py`

**Usage:**
```bash
cd ~/.claude/skills/tiktok-automation/scripts

# Standard run (50 likes/session, 6x daily = ~300 total)
/opt/homebrew/bin/python3 tiktok-auto-liker.py

# Dry run (preview without liking)
/opt/homebrew/bin/python3 tiktok-auto-liker.py --dry-run

# Test mode (process only 5 accounts)
/opt/homebrew/bin/python3 tiktok-auto-liker.py --test 5

# Custom daily limit (50 likes/session)
/opt/homebrew/bin/python3 tiktok-auto-liker.py --limit 50

# Skip accounts already liked today
/opt/homebrew/bin/python3 tiktok-auto-liker.py --skip-liked-today

# Only like accounts never liked before
/opt/homebrew/bin/python3 tiktok-auto-liker.py --new-only

# Use different TikTok username
/opt/homebrew/bin/python3 tiktok-auto-liker.py --username procaffe26
```

**Options:**
- `--dry-run` - Show what would be liked without actually liking
- `--limit N` - Override session like limit (default: 50)
- `--test N` - Test mode: only process first N accounts
- `--username U` - TikTok username to get following list from (default: procaffe26)
- `--skip-liked-today` - Skip accounts already liked today
- `--new-only` - Only like accounts never liked before

**Prerequisites:**
1. Start Chrome with CDP: `./scripts/tiktok-chrome-launcher.sh`
2. Log in to TikTok manually in the Chrome instance
3. Keep Chrome open while running script

**How It Works:**
1. Connects to Chrome via CDP (port 9222)
2. Scrapes Following list from @procaffe26 profile
3. Visits each account's profile
4. Opens latest video and clicks like button
5. Random delays (30-90s) between actions for human-like behavior
6. Tracks liked accounts in Firebase

**Logs:** `~/logs/tiktok-auto-liker/YYYY-MM-DD.log`

---

### 2. Auto-Follower (`tiktok-auto-follower.py`)

Follow accounts from queue with human-like behavior.

**Path:** `~/.claude/skills/tiktok-automation/scripts/tiktok-auto-follower.py`

**Usage:**
```bash
cd ~/.claude/skills/tiktok-automation/scripts

# Standard run (10 follows/hour, 9 AM - 11 PM Vietnam time)
/opt/homebrew/bin/python3 tiktok-auto-follower.py

# Dry run (preview without following)
/opt/homebrew/bin/python3 tiktok-auto-follower.py --dry-run

# Custom batch size (20 accounts/batch)
/opt/homebrew/bin/python3 tiktok-auto-follower.py --batch 20

# Test mode (process only 3 accounts)
/opt/homebrew/bin/python3 tiktok-auto-follower.py --test 3
```

**Options:**
- `--dry-run` - Show what would be followed without actually following
- `--batch N` - Accounts per batch (default: 10)
- `--test N` - Test mode: only process first N accounts

**Prerequisites:**
1. Build follow queue first: `tiktok-account-discoverer.py`
2. Start Chrome with CDP: `./scripts/tiktok-chrome-launcher.sh`
3. Keep Chrome open while running

**How It Works:**
1. Connects to Chrome via CDP (port 9222)
2. Loads follow queue from `data/follow-queue.json`
3. Filters out already-followed accounts
4. Visits each profile and clicks Follow button
5. Random delays (30-120s) between follows
6. Saves followed accounts to `data/followed-accounts.json`

**Logs:** `~/logs/tiktok-auto-follower/YYYY-MM-DD.log`

---

### 3. Profile Scraper (`tiktok-scrape-profile.py`)

Download all videos from a TikTok profile using yt-dlp.

**Path:** `~/.claude/skills/tiktok-automation/scripts/tiktok-scrape-profile.py`

**Usage:**
```bash
# Scrape all videos from profile
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/tiktok-scrape-profile.py @cubesasia

# Limit to 20 most recent videos
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/tiktok-scrape-profile.py @cubesasia --limit 20

# Dry run (show command without running)
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/tiktok-scrape-profile.py @cubesasia --dry-run
```

**Arguments:**
- `username` (required) - TikTok username (e.g., @procaffe or procaffe)
- `--limit N` - Max videos to download (0 = all, default: 0)
- `--dry-run` - Show command without running

**Output Structure:**
```
~/exports/raw/{username}/
├── YYYYMMDD_{video_id}/
│   ├── video.mp4
│   └── {video_id}.info.json
```

**Dependencies:**
- yt-dlp with curl_cffi support
- Chrome cookies (exported or auto-extracted)

---

### 4. Video Processor (`tiktok-process-videos.py`)

Move raw videos to processed folder structure.

**Path:** `~/.claude/skills/tiktok-automation/scripts/tiktok-process-videos.py`

**Usage:**
```bash
# Process all new videos
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/tiktok-process-videos.py

# Dry run (preview without processing)
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/tiktok-process-videos.py --dry-run
```

---

### 5. Competitor Tracker (`tiktok-competitor-tracker.py`)

Track competitor TikTok profiles using Apify API.

**Path:** `~/.claude/skills/tiktok-automation/scripts/tiktok-competitor-tracker.py`

**Usage:**
```bash
# Track all competitors (from config.py TIKTOK_COMPETITORS list)
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/tiktok-competitor-tracker.py

# Track single profile
/opt/homebrew/bin/python3 /Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/scripts/tiktok-competitor-tracker.py --profile @cubesasia
```

**Default Competitors (config.py):**
- `cubesasia`
- `copen_coffee`
- `thegioimaypha`

---

## Configuration (config.py)

```python
# Chrome DevTools Protocol
TIKTOK_CDP_PORT = 9222
TIKTOK_CHROME_PROFILE = ~/chrome-tiktok-profile

# Auto-Liker Settings (runs 6x daily)
TIKTOK_DAILY_LIKE_MAX = 50        # per-session limit
TIKTOK_LIKE_DELAY_MIN = 30        # seconds
TIKTOK_LIKE_DELAY_MAX = 90        # seconds
TIKTOK_START_HOUR = 6             # 6 AM Vietnam
TIKTOK_END_HOUR = 23              # 11 PM Vietnam

# Auto-Follower Settings
TIKTOK_HOURLY_FOLLOW_MAX = 10
TIKTOK_FOLLOW_DELAY_MIN = 30      # seconds
TIKTOK_FOLLOW_DELAY_MAX = 120     # seconds
TIKTOK_FOLLOW_START_HOUR = 9      # 9 AM Vietnam
TIKTOK_FOLLOW_END_HOUR = 23       # 11 PM Vietnam

# Discovery Keywords
TIKTOK_SEARCH_KEYWORDS = [
    "khách sạn vietnam", "hotel vietnam",
    "quán cà phê", "coffee shop vietnam",
    "nhà hàng vietnam", "restaurant vietnam"
]

# Competitors to Track
TIKTOK_COMPETITORS = ["cubesasia", "copen_coffee", "thegioimaypha"]

# Paths
TIKTOK_AUTO_LIKER_LOG_DIR = ~/logs/tiktok-auto-liker
TIKTOK_AUTO_FOLLOWER_LOG_DIR = ~/logs/tiktok-auto-follower
TIKTOK_FOLLOW_QUEUE_FILE = data/follow-queue.json
TIKTOK_FOLLOWED_FILE = data/followed-accounts.json
```

---

## LaunchAgent Automation

Auto-liker runs 6x daily via launchd (6 AM, 9 AM, 12 PM, 3 PM, 6 PM, 9 PM):

**File:** `~/Library/LaunchAgents/com.procaffe.tiktok-auto-liker.plist`

```bash
# Load launchd job
launchctl load ~/Library/LaunchAgents/com.procaffe.tiktok-auto-liker.plist

# Unload launchd job
launchctl unload ~/Library/LaunchAgents/com.procaffe.tiktok-auto-liker.plist

# Check status
launchctl list | grep procaffe

# View logs
tail -f ~/logs/tiktok-auto-liker/launchd.log
```

**IMPORTANT:** LaunchAgents should use local script paths (not OneDrive) to avoid permission issues with OneDrive sync.

---

## Common Workflows

### Daily Engagement Automation
1. Keep Chrome open with TikTok logged in
2. Auto-liker runs 6x daily via launchd
3. Likes ~50 videos per session (~300 total/day)

### Competitor Content Discovery
1. Track competitors: `tiktok-competitor-tracker.py`
2. Review top-performing content in report
3. Scrape videos from best performers: `tiktok-scrape-profile.py @competitor`
4. Process videos: `tiktok-process-videos.py`

### Follow Competitor Followers
1. Discover accounts: `tiktok-account-discoverer.py` (builds queue)
2. Follow accounts: `tiktok-auto-follower.py` (10/hour, runs hourly)
3. Auto-liker engages with newly followed accounts

---

## Troubleshooting

### "Failed to connect to Chrome"
- Ensure Chrome is running: `ps aux | grep chrome`
- Start Chrome launcher: `./scripts/tiktok-chrome-launcher.sh`
- Check CDP port: `lsof -i :9222`

### "Not logged in to TikTok"
- Open Chrome at `http://localhost:9222`
- Manually log in to TikTok
- Keep session active

### "Operation not permitted" (LaunchAgent)
- **Root Cause:** OneDrive file permissions
- **Fix:** Use local script path in LaunchAgent plist, not OneDrive path
- Or: `chmod 755 scripts/*.py scripts/*.sh`

### yt-dlp Download Failures
- Update yt-dlp: `brew upgrade yt-dlp`
- Export fresh cookies from Chrome
- Check TikTok hasn't changed HTML structure

---

## Firebase Integration

Auto-liker tracks liked accounts in Firebase (`tiktok_accounts` collection):

**Document Structure:**
```json
{
  "username": "cubesasia",
  "sources": ["auto-liker"],
  "liked": true,
  "liked_at": "2024-12-28T07:44:00Z",
  "like_count": 5,
  "created_at": "2024-12-20T10:00:00Z",
  "updated_at": "2024-12-28T07:44:00Z"
}
```

**Fallback:** If Firebase unavailable, tracks in daily log files.

---

## Security Considerations

- **Human-like behavior:** Random delays (30-90s), time windows prevent detection
- **Rate limits:** Session caps (50 likes) distributed across 6 daily runs
- **Chrome CDP:** Uses real Chrome with persistent session (less detectable than Playwright)
- **No headless mode:** Visible browser reduces ban risk
- **Session persistence:** Real user profile with cookies

---

## Related Tools

- `tiktok-chrome-launcher.sh` - Start Chrome with CDP enabled on port 9222
- `tiktok-account-discoverer.py` - Build follow queue from competitors
- `tiktok-upload-playwright.py` - Upload processed videos to TikTok
- `tiktok-firebase-sync.py` - Sync account data to Firebase

---

## References

See `references/` directory for detailed implementation notes.
