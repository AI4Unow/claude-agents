---
name: publer-automation
description: "Publer social media management for Procaffe. Use when user needs to upload, schedule, or manage social media posts via Publer."
license: Proprietary
allowed-tools: [Bash, Read]
---

# Publer Automation

Social media management automation for Procaffe via Publer API. Manages video uploads, scheduling, caption updates, and analytics for TikTok.

## When to Use

- User asks to upload videos to TikTok
- User wants to schedule social media posts
- User needs to update captions on existing posts
- User wants to check scheduled posts or duplicates
- User requests trends/analytics reports

---

## Key Learning: Scheduling Methods

**IMPORTANT:** Publer has TWO scheduling methods:

### Method 1: Timestamp-Based (Current Implementation)
```json
{
  "bulk": {
    "state": "scheduled",
    "posts": [{
      "scheduled_at": "2025-12-28T10:30:00Z",
      "networks": {...}
    }]
  }
}
```

**Behavior:** Posts may be created as drafts if:
- Timestamp in past
- No posting schedule configured in Publer UI
- Account lacks scheduling permissions

### Method 2: Slot-Based Auto-Scheduling (Recommended)
```json
{
  "bulk": {
    "state": "scheduled",
    "posts": [{
      "auto": true,
      "range": {
        "start_date": "2025-12-28",
        "end_date": "2025-12-31"
      },
      "networks": {...}
    }]
  }
}
```

**Requirements:**
1. Configure posting schedule in Publer UI for TikTok account first
2. Use `auto: true` in payload (mutually exclusive with `scheduled_at`)
3. Optional date range to constrain slot selection

**NOTE:** Current `--auto-schedule` flag generates timestamps, NOT Publer's slot-based `auto: true` parameter.

---

## Core Capabilities

### 1. Video Upload (`publer-upload.py`)

Upload processed videos to TikTok via Publer with automated scheduling.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/publer-automation/scripts/publer-upload.py [OPTIONS]
```

**Options:**
- `--limit N` - Max videos to upload (default: 5)
- `--state {draft|scheduled}` - Post state (default: draft)
- `--publish` - Publish immediately instead of draft
- `--auto-schedule` - Auto-schedule posts (90 min intervals, starting 1 hour from now)
- `--schedule-interval N` - Hours between scheduled posts (0=no scheduling)
- `--start-hour N` - Hour of day to start scheduling (0-23, default: 8)
- `--dry-run` - List videos without uploading

**Examples:**
```bash
# Upload 5 videos as drafts (default)
/opt/homebrew/bin/python3 scripts/publer-upload.py

# Publish 3 videos immediately
/opt/homebrew/bin/python3 scripts/publer-upload.py --limit 3 --publish

# Auto-schedule 10 videos (90 min intervals)
/opt/homebrew/bin/python3 scripts/publer-upload.py --limit 10 --auto-schedule

# Schedule every 6 hours starting at 9 AM
/opt/homebrew/bin/python3 scripts/publer-upload.py --schedule-interval 6 --start-hour 9

# Preview what would be uploaded
/opt/homebrew/bin/python3 scripts/publer-upload.py --dry-run
```

**Features:**
- Automatic media validation (file size, TikTok compatibility)
- Smart caption loading from `caption.txt` files
- Job status polling until complete
- Tracking to prevent duplicate uploads
- Rate limiting (1.5s between API calls)
- ISO timestamp scheduling in UTC

**Known Issue:** Posts created as drafts when no posting schedule configured in Publer UI.

---

### 2. Clear Schedule (`publer-clear-schedule.py`)

Remove all scheduled posts from Publer.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/publer-automation/scripts/publer-clear-schedule.py [OPTIONS]
```

**Options:**
- `--execute` - Actually delete (default: dry-run)

**Examples:**
```bash
# Preview scheduled posts
/opt/homebrew/bin/python3 scripts/publer-clear-schedule.py

# Delete all scheduled posts
/opt/homebrew/bin/python3 scripts/publer-clear-schedule.py --execute
```

**Features:**
- Pagination support (fetches all pages)
- Batch deletion (20 posts per request)
- Dry-run mode by default
- Shows post preview before deletion

---

### 3. Update Captions (`publer-update-captions.py`)

Update draft posts with new captions from local `caption.txt` files.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/publer-automation/scripts/publer-update-captions.py [OPTIONS]
```

**Options:**
- `--dry-run` - List drafts without updating
- `--limit N` - Limit posts to update (0=all)
- `--force` - Update even if caption seems same

**Examples:**
```bash
# Preview caption updates
/opt/homebrew/bin/python3 scripts/publer-update-captions.py --dry-run

# Update all draft captions
/opt/homebrew/bin/python3 scripts/publer-update-captions.py

# Update first 5 drafts only
/opt/homebrew/bin/python3 scripts/publer-update-captions.py --limit 5
```

---

### 4. Check Posts (`check-publer-posts.py`)

Analyze scheduled posts for duplicates and display schedule overview.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/publer-automation/scripts/check-publer-posts.py
```

**Features:**
- Duplicate media detection
- Duplicate content analysis
- Schedule overview (sorted by time)
- TikTok account filtering

**Output:**
- Total scheduled posts count
- Duplicate media warnings
- Next 10 scheduled posts preview

---

### 5. Trends Report (`publer-trends.py`)

Generate analytics report with hashtag performance, best posting times, and competitor insights.

**Usage:**
```bash
/opt/homebrew/bin/python3 ~/.claude/skills/publer-automation/scripts/publer-trends.py [OPTIONS]
```

**Options:**
- `--days N` - Days of data to analyze (default: 30)
- `--output PATH` - Custom output path

**Examples:**
```bash
# Generate 30-day report
/opt/homebrew/bin/python3 scripts/publer-trends.py

# Generate 7-day report
/opt/homebrew/bin/python3 scripts/publer-trends.py --days 7
```

**Report Sections:**
- 📊 Top Performing Hashtags (posts, engagement, score)
- ⏰ Best Posting Times (by day, top 3 hours)
- 🎯 Competitor Insights (followers, engagement, posts)
- 💡 Recommendations

**Output:** `plans/reports/trends-{date}.md`

---

## Configuration (config.py)

```python
# Publer API
PUBLER_API_BASE = "https://app.publer.com/api/v1"

# File Size Limits
MAX_FILE_SIZE_MB = 100        # 100MB Publer limit
MIN_VIDEO_SIZE = 10000        # 10KB minimum valid video

# Timeouts
UPLOAD_TIMEOUT = 300          # 5 min for large file uploads
JOB_POLL_TIMEOUT = 30         # Job status poll
DEFAULT_TIMEOUT = 60          # General API calls

# Rate Limiting
RATE_LIMIT_DELAY = 1.5        # seconds between API requests

# TikTok Limits
TIKTOK_MAX_DURATION = 600     # 10 min max

# Timezone
LOCAL_TIMEZONE_OFFSET = 7     # GMT+7 for Vietnam
```

---

## Environment Variables

Required for all scripts:
```bash
PUBLER_API_KEY=your_api_key
PUBLER_WORKSPACE_ID=your_workspace_id
PUBLER_TIKTOK_ACCOUNT_ID=your_tiktok_account_id
```

Set in `/Users/nad/Library/CloudStorage/OneDrive-Personal/Procaffe/.env`

---

## Data Paths

- Processed videos: `exports/processed/{date}-{video_id}/`
- Caption files: `exports/processed/{date}-{video_id}/caption.txt`
- Tracking file: `data/uploaded-videos.txt`
- Reports: `plans/reports/trends-{date}.md`

---

## Workflow

Typical content publishing workflow:

1. **Process videos** (via fb-to-tiktok pipeline)
2. **Generate captions** (`caption-generator.py`)
3. **Upload to Publer** (`publer-upload.py --auto-schedule`)
4. **Check schedule** (`check-publer-posts.py`)
5. **Update captions** if needed (`publer-update-captions.py`)
6. **Analyze trends** weekly (`publer-trends.py`)

---

## Troubleshooting

**Posts created as drafts instead of scheduled:**
- **Root Cause:** No posting schedule configured in Publer UI
- **Fix:** Configure posting schedule in Publer → TikTok account → Settings
- Or: Use timestamps in future + ensure schedule exists

**API Key errors:**
- Check `PUBLER_API_KEY` env var
- Verify API key is valid in Publer settings

**File size errors:**
- Max file size: 100MB (Publer limit)
- Check video file size before upload

**Rate limiting:**
- Default delay: 1.5s between API calls
- Increase if hitting rate limits

---

## API Endpoints

**Schedule Management:**
- `GET /accounts/{id}/schedule` - Retrieve posting schedule
- `POST /posts/schedule` - Create scheduled post
- `GET /accounts/{id}/insights/best-times` - Get optimal posting times

**Current Script Usage:**
- `POST /media` - Upload video (working ✓)
- `POST /posts/schedule` - Create post
- `GET /job_status/{job_id}` - Poll completion (working ✓)

---

## Limitations

- Max file size: 100MB (Publer limit)
- Batch delete: 20 posts per request
- Scheduling: must use UTC timestamps
- Rate limit: ~1.5s between API calls recommended

---

## References

See `references/` folder for detailed documentation.
