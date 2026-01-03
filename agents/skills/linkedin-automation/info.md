---
name: linkedin-automation
description: "LinkedIn automation for Procaffe - connection requests, engagement, posting, lead scraping. Use when user mentions LinkedIn automation or B2B outreach."
deployment: local
license: Proprietary
allowed-tools: [Bash, Read]
---

# LinkedIn Automation

LinkedIn automation suite for Procaffe B2B outreach and lead generation. All scripts use Chrome DevTools Protocol (CDP) to connect to a persistent Chrome session, minimizing detection risk.

## Chrome CDP Architecture

**IMPORTANT:** All scripts use Chrome DevTools Protocol (CDP) to connect to a persistent Chrome instance - NOT Playwright browser automation. Playwright is only used for the CDP connection API.

**Port & Profile:**
- CDP Port: `9223`
- Chrome Profile: `~/chrome-linkedin-profile`
- Launcher: `~/.claude/skills/linkedin-automation/scripts/linkedin-chrome-launcher.sh`

**Why CDP over Playwright Browser:**
- Session persistence: Login once, reuse forever
- Detection resistant: Real browser, real user profile
- No browser management overhead
- Separate profile isolates LinkedIn session

**Process:**
1. Start Chrome launcher: `./scripts/linkedin-chrome-launcher.sh`
2. Browser opens with CDP enabled on port 9223
3. Log into LinkedIn (and Sales Navigator if needed)
4. Session saved to profile directory
5. Automation scripts connect via CDP
6. Browser stays open, reused for all runs

---

## Prerequisites

1. **Chrome Session**: Launch Chrome with CDP enabled
   ```bash
   ~/.claude/skills/linkedin-automation/scripts/linkedin-chrome-launcher.sh
   ```

2. **Manual Login**: Log into LinkedIn (and Sales Navigator if needed) in Chrome before running scripts

3. **Python Environment**: Uses `/opt/homebrew/bin/python3`

---

## Scripts Overview

### 1. Connection Requests (`linkedin-auto-connector.py`)
Send personalized connection requests to target prospects.

**Usage:**
```bash
# Regular LinkedIn search by job title
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-connector.py

# Dry run to preview
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-connector.py --dry-run

# Search specific job title
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-connector.py --title "Hotel Manager"

# Sales Navigator mode (requires subscription)
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-connector.py --sales-nav

# Use specific Sales Nav query by name
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-connector.py --sales-nav --query hotel_gm_vietnam

# Test with limited profiles
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-connector.py --test 3 --dry-run
```

**Options:**
- `--dry-run`: Show what would be sent without sending
- `--limit N`: Daily connection limit (default: 25)
- `--test N`: Test mode, only process first N profiles
- `--title "..."`: Search specific job title only
- `--sales-nav`: Use Sales Navigator search
- `--query NAME`: Use specific Sales Nav query by name (see config.py)

**Default Targets**: Hotel managers, restaurant owners, cafe owners, F&B directors in Vietnam

**Rate Limits**: 25/day, 2-5 min delays between requests

---

### 2. Content Engagement (`linkedin-auto-engager.py`)
Automatically like and comment on relevant posts to build presence.

**Usage:**
```bash
# Engage with posts from feed and keywords
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-engager.py

# Dry run
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-engager.py --dry-run

# Search specific keyword
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-engager.py --keyword "coffee machine"

# Likes only, no comments
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-engager.py --likes-only

# Test mode
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-auto-engager.py --test 5 --dry-run
```

**Options:**
- `--dry-run`: Show what would be engaged
- `--limit N`: Daily engagement limit (default: 80)
- `--test N`: Test mode, only process first N posts
- `--likes-only`: Skip comments, only like
- `--keyword "..."`: Search specific keyword only

**Default Keywords**: coffee machine, espresso vietnam, hotel vietnam, cafe business, hospitality vietnam

**Behavior**: Likes all posts, comments on ~7% (Vietnamese professional comments)

**Rate Limits**: 80/day, 1-3 min delays between engagements

---

### 3. Content Posting (`linkedin-content-poster.py`)
Fetch content from Facebook and post to LinkedIn with hashtags.

**Usage:**
```bash
# Fetch from Facebook and post to LinkedIn
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-content-poster.py

# Dry run
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-content-poster.py --dry-run

# Post multiple items
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-content-poster.py --limit 3
```

**Rate Limits**: 1-3 posts/day, 30-60 sec delays between posts

---

### 4. Lead Scraping (`linkedin-lead-scraper.py`)
Collect leads from connections, profile viewers, or import local data to Firestore.

**Usage:**
```bash
# Scrape existing connections
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-scraper.py connections --limit 100

# Scrape profile viewers (requires Premium)
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-scraper.py viewers --limit 50

# Sync local Sales Nav leads to Firestore
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-scraper.py sync-local
```

---

### 5. Lead Tracking (`linkedin-lead-tracker.py`)
CLI tool to manage and track leads through the sales funnel.

**Usage:**
```bash
# Show funnel status summary
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-tracker.py status

# List all leads
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-tracker.py list

# List by tier
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-tracker.py list tier1

# Update lead status
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-tracker.py update <URL> connected

# Add lead to InMail queue
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-lead-tracker.py queue-inmail <URL> --name "John Doe" --company "Hotel ABC"
```

**Lead Statuses**: cold, engaged, connect_sent, connected, inmail_sent, responded, meeting, qualified, disqualified

**Tiers**: tier1 (high priority), tier2 (medium), tier3 (low)

---

### 6. InMail Sending (`linkedin-inmail-sender.py`)
Send personalized InMails to Tier 1 prospects via Sales Navigator.

**Usage:**
```bash
# Send InMails from queue
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-inmail-sender.py

# Dry run
/opt/homebrew/bin/python3 ~/.claude/skills/linkedin-automation/scripts/linkedin-inmail-sender.py --dry-run
```

**Rate Limits**: 5/day, 15/week to preserve InMail credits

---

## Configuration (config.py)

```python
# Chrome DevTools Protocol
LINKEDIN_CDP_PORT = 9223
LINKEDIN_CHROME_PROFILE = ~/chrome-linkedin-profile

# Connector Settings
LINKEDIN_CONNECT_DELAY_MIN = 120   # 2 min between connections
LINKEDIN_CONNECT_DELAY_MAX = 300   # 5 min between connections
LINKEDIN_DAILY_CONNECT_MAX = 25

# Engager Settings
LINKEDIN_ENGAGE_DELAY_MIN = 60     # 1 min between engagements
LINKEDIN_ENGAGE_DELAY_MAX = 180    # 3 min between engagements
LINKEDIN_DAILY_ENGAGE_MAX = 80

# Time Windows
LINKEDIN_START_HOUR = 8            # 8 AM Vietnam time
LINKEDIN_END_HOUR = 11             # 11 AM Vietnam time

# Target Job Titles (Vietnam)
LINKEDIN_TARGET_TITLES = [
    "Hotel Owner", "Hotel Manager", "General Manager Hotel",
    "Restaurant Owner", "F&B Manager", "Food and Beverage Director",
    "Cafe Owner", "Coffee Shop Owner", "Barista Manager",
    "Office Manager", "Facilities Manager", "Procurement Manager"
]

# Vietnam GeoUrn (for search filter)
LINKEDIN_VIETNAM_GEO_URN = "104195383"
```

---

## Sales Navigator Queries (config.py)

Pre-configured Boolean queries with tiers and spotlight filters:

| Query Name | Target | Tier | Spotlight |
|------------|--------|------|-----------|
| `hotel_gm_vietnam` | "General Manager" Hotel Vietnam | tier1 | Posted 30d |
| `resort_owner` | Resort Owner/Manager Vietnam | tier1 | Changed job |
| `hotel_director` | "Hotel Director" / "Director of Operations" | tier1 | Posted 30d |
| `coffee_shop_owner` | "Coffee Shop" Owner Vietnam | tier2 | Posted 30d |
| `cafe_founder` | Cafe Founder / "Quán cà phê" Owner | tier2 | Changed job |
| `restaurant_owner_vietnam` | Restaurant Owner Vietnam / "Nhà hàng" | tier2 | Posted 30d |
| `fnb_director` | "F&B Director" / "Food and Beverage Director" | tier2 | Changed job |
| `office_manager_vietnam` | "Office Manager" Vietnam | tier3 | Changed job |
| `procurement_hospitality` | "Procurement Manager" Hospitality/Hotel | tier3 | Changed job |
| `boutique_hotel` | "Boutique Hotel" Owner/Manager Vietnam | tier1 | Changed job |

**Usage:** `--sales-nav --query hotel_gm_vietnam`

---

## Sales Navigator Rate Limits

```python
SALES_NAV_DAILY_SEARCH_MAX = 100      # max search result views/day
SALES_NAV_DAILY_PROFILE_VIEW_MAX = 50  # max profile views/day
SALES_NAV_DAILY_INMAIL_MAX = 5         # preserve InMail credits
SALES_NAV_WEEKLY_INMAIL_MAX = 15       # weekly InMail cap
```

---

## Connection Note Templates

**Value First (300 char max):**
```
Chào anh/chị {name}!

Thấy anh/chị có kinh nghiệm trong {industry}. ProCaffe đang hỗ trợ nhiều {segment} tại Vietnam với thiết bị cà phê chuyên nghiệp.

Rất mong được kết nối để chia sẻ thêm!
```

**Common Ground:**
```
Chào anh/chị {name}!

Rất ấn tượng với bài viết gần đây về {topic}. Tôi cũng đang trong ngành F&B/Hospitality.

Kết nối để trao đổi thêm nhé!
```

---

## Data Files

All data stored in `data/`:
- `linkedin-connections.json`: Sent/accepted connections
- `linkedin-leads.json`: Lead tracker database
- `linkedin-engaged.json`: Liked/commented posts
- `linkedin-posted.json`: Posted content hashes
- `linkedin-inmail-queue.json`: InMail queue
- `linkedin-inmail-sent.json`: Sent InMails

---

## Lead Scoring (config.py)

```python
ENGAGEMENT_WEIGHTS = {
    "follower": 5,       # They follow us
    "following": 2,      # We follow them
    "liker": 3,          # Liked our content
    "commenter": 8,      # Commented on our content
    "connection": 5,     # LinkedIn connection
    "profile_viewer": 4, # Viewed our profile
    "message_reply": 15, # Replied to message
}

# Tiers based on score
LEAD_TIER_1 = "tier1"  # High-value (score >= 30)
LEAD_TIER_2 = "tier2"  # Medium (score 10-29)
LEAD_TIER_3 = "tier3"  # Low (score < 10)
```

---

## Time Windows

All scripts run within 8 AM - 11 AM Vietnam time (configurable in `config.py`). Use `--test` flag to override.

---

## LaunchAgent Automation

LinkedIn automation can run via launchd:

**File:** `~/Library/LaunchAgents/com.procaffe.linkedin-*.plist`

```bash
# Check status
launchctl list | grep linkedin

# View logs
tail -f ~/logs/linkedin-auto/*.log
```

**IMPORTANT:** LaunchAgents should use local script paths (not OneDrive) to avoid permission issues with OneDrive sync.

---

## Workflow Example

1. **Discovery**: Use `linkedin-auto-connector.py --sales-nav` to find and connect with targets
2. **Engagement**: Run `linkedin-auto-engager.py` daily to maintain presence
3. **Content**: Post 1-2x/week with `linkedin-content-poster.py`
4. **Lead Management**: Use `linkedin-lead-tracker.py status` to monitor funnel
5. **Follow-up**: Queue tier1 leads and send InMails with `linkedin-inmail-sender.py`
6. **Reporting**: Generate weekly reports with `linkedin-lead-tracker.py report`

---

## Troubleshooting

**Chrome connection fails:**
```bash
# Restart Chrome with CDP
./scripts/linkedin-chrome-launcher.sh
# Check port
lsof -i :9223
```

**"Operation not permitted" (LaunchAgent):**
- **Root Cause:** OneDrive file permissions
- **Fix:** Use local script path in LaunchAgent plist, not OneDrive path
- Or: `chmod 755 scripts/*.py scripts/*.sh`

**LinkedIn logged out:**
- Manually log in to LinkedIn in the Chrome window
- Keep Chrome window open while scripts run

**Sales Navigator features not working:**
- Verify Sales Navigator subscription is active
- Log into Sales Nav manually in Chrome first

**Firestore errors:**
- Check Firebase credentials in `firebase_service_account.json`
- Verify Firestore permissions

---

## Safety Features

- **Dry-run mode**: All scripts support `--dry-run` for safe testing
- **Rate limits**: Prevent LinkedIn restrictions
- **Deduplication**: Avoid re-engaging same content/people
- **Time windows**: Run during business hours only
- **Human behavior**: Randomized delays and patterns
- **Chrome CDP**: Real browser with persistent session (less detectable)

---

## References

See `references/` directory for detailed implementation notes.
