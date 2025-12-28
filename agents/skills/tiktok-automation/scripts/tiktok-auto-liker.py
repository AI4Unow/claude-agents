#!/usr/bin/env python3
"""
TikTok Auto-Liker: Automatically like latest videos from accounts you follow.

Uses Chrome DevTools Protocol (CDP) to control a real Chrome browser with
persistent session, minimizing detection risk.

Approach: Scrapes Following list from profile, visits each account, likes latest video.

Usage:
    1. First run: ./tiktok-chrome-launcher.sh and log in to TikTok manually
    2. Keep Chrome open, then run: python3 tiktok-auto-liker.py

Options:
    --dry-run       Show what would be liked without actually liking
    --limit N       Override daily like limit (default: 80)
    --test N        Test mode: only process first N accounts
    --username U    TikTok username to get following list from (default: procaffe26)
"""

import argparse
import asyncio
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page

from config import (
    TIKTOK_CDP_PORT,
    TIKTOK_LIKE_DELAY_MIN,
    TIKTOK_LIKE_DELAY_MAX,
    TIKTOK_DAILY_LIKE_MAX,
    TIKTOK_START_HOUR,
    TIKTOK_END_HOUR,
    TIKTOK_AUTO_LIKER_LOG_DIR,
)

# Default TikTok username
DEFAULT_USERNAME = "procaffe26"


def setup_logging() -> logging.Logger:
    """Configure logging to file and console."""
    TIKTOK_AUTO_LIKER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = TIKTOK_AUTO_LIKER_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("tiktok-auto-liker")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)

    return logger


def is_within_time_window() -> bool:
    """Check if current time is within allowed window (9 AM - 9 PM Vietnam)."""
    now = datetime.now()
    return TIKTOK_START_HOUR <= now.hour < TIKTOK_END_HOUR


def random_delay() -> float:
    """Generate human-like random delay with gaussian distribution."""
    mean = (TIKTOK_LIKE_DELAY_MIN + TIKTOK_LIKE_DELAY_MAX) / 2
    std = (TIKTOK_LIKE_DELAY_MAX - TIKTOK_LIKE_DELAY_MIN) / 4
    delay = random.gauss(mean, std)
    return max(TIKTOK_LIKE_DELAY_MIN, min(TIKTOK_LIKE_DELAY_MAX, delay))


async def connect_to_chrome(logger: logging.Logger):
    """Connect to existing Chrome instance via CDP."""
    cdp_url = f"http://127.0.0.1:{TIKTOK_CDP_PORT}"
    logger.info(f"Connecting to Chrome via CDP at {cdp_url}")

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
        logger.info("Connected to Chrome successfully")
        return playwright, browser
    except Exception as e:
        logger.error(f"Failed to connect to Chrome: {e}")
        logger.error("Make sure Chrome is running with: ./tiktok-chrome-launcher.sh")
        await playwright.stop()
        raise


async def get_following_list(page: Page, username: str, logger: logging.Logger, limit: int = 1000) -> list:
    """
    Get list of accounts the user follows by scraping profile's Following modal.
    Returns list of usernames.
    """
    logger.info(f"Getting following list for @{username}...")

    # Navigate to profile
    await page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(4)  # Wait for page to fully render

    # Close any modal overlays that might be present
    await page.keyboard.press("Escape")
    await asyncio.sleep(1)

    # Check for login wall
    if "login" in page.url.lower():
        logger.error("Not logged in to TikTok. Please log in manually first.")
        return []

    # Click on Following count to open modal using parent element approach
    clicked = await page.evaluate('''
        () => {
            const el = document.querySelector('[data-e2e="following-count"]');
            if (el) {
                const link = el.closest('a') || el.parentElement;
                if (link) {
                    link.click();
                    return true;
                }
            }
            return false;
        }
    ''')

    if not clicked:
        logger.error("Could not find Following link on profile")
        return []

    await asyncio.sleep(3)  # Wait for modal to open and populate

    # Scroll the modal to load all accounts
    usernames = set()
    prev_count = 0
    stale_scrolls = 0

    for scroll in range(500):  # Max 500 scroll attempts for large following lists
        # Find all user links in modal
        links = await page.query_selector_all('a[href*="/@"]')

        for link in links:
            try:
                href = await link.get_attribute("href")
                if href and "/@" in href:
                    u = href.split("/@")[-1].split("/")[0].split("?")[0]
                    if u and u != username:
                        usernames.add(u)
            except Exception:
                continue

        # Check if we've collected enough
        if len(usernames) >= limit:
            break

        # Check for stale scrolling (no new users found)
        if len(usernames) == prev_count:
            stale_scrolls += 1
            if stale_scrolls >= 50:  # Very patient - TikTok loads slowly
                logger.info(f"Stopped scrolling at {scroll} due to stale ({stale_scrolls} scrolls)")
                break
        else:
            stale_scrolls = 0
        prev_count = len(usernames)

        # Scroll the modal container - use specific selector
        await page.evaluate('''
            const modal = document.querySelector('[class*="DivUserListContainer"]')
                || document.querySelector('[class*="FollowingList"]')
                || document.querySelector('[role="dialog"]');
            if (modal) modal.scrollBy(0, 500);
        ''')
        await asyncio.sleep(0.8)  # Balance between speed and loading

        if scroll % 20 == 0:
            logger.info(f"Scroll {scroll}: found {len(usernames)} accounts")

    # Close modal by pressing Escape
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.5)

    logger.info(f"Collected {len(usernames)} accounts from following list")
    return list(usernames)


async def like_latest_video(page: Page, username: str, logger: logging.Logger, dry_run: bool = False) -> bool:
    """
    Navigate to user's profile and like their latest video.
    Returns True if liked successfully, False otherwise.
    """
    try:
        logger.info(f"Processing @{username}")

        if dry_run:
            logger.info(f"[DRY RUN] Would like video from @{username}")
            return True

        # Navigate to user's profile
        await page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Quick check for "no videos" indicators before searching for videos
        no_video_indicators = [
            '[data-e2e="no-video"]',
            'text="No content"',
            'text="This account is private"',
            'text="Couldn\'t find this account"',
        ]
        for indicator in no_video_indicators:
            try:
                elem = await page.query_selector(indicator)
                if elem:
                    logger.warning(f"@{username} has no accessible videos (indicator found)")
                    return False
            except Exception:
                pass

        # Find first video on profile with short timeout
        video_link = await page.query_selector('[data-e2e="user-post-item"] a')
        if not video_link:
            video_link = await page.query_selector('[class*="DivVideoCard"] a')
        if not video_link:
            video_link = await page.query_selector('a[href*="/video/"]')

        if not video_link:
            logger.warning(f"No videos found on @{username}'s profile")
            return False

        # Check if video link is visible before clicking (avoid 30s timeout)
        is_visible = await video_link.is_visible()
        if not is_visible:
            logger.warning(f"Video link not visible on @{username}'s profile")
            return False

        # Click to open video with reduced timeout
        await video_link.click(timeout=5000)
        await asyncio.sleep(random.uniform(2, 3))  # Watch briefly

        # Find like button
        like_button = await page.query_selector('[data-e2e="like-icon"]')
        if not like_button:
            like_button = await page.query_selector('[data-e2e="browse-like-icon"]')

        if not like_button:
            logger.warning(f"Could not find like button for @{username}")
            await page.keyboard.press("Escape")  # Close video modal
            return False

        # Check if already liked
        try:
            parent = await like_button.evaluate_handle("el => el.closest('button') || el.parentElement")
            aria_label = await parent.evaluate("el => el.getAttribute('aria-label') || ''")

            if "unlike" in aria_label.lower():
                logger.info(f"Already liked video from @{username}")
                await page.keyboard.press("Escape")
                return True
        except Exception:
            pass

        # Click like button
        await like_button.click()
        await asyncio.sleep(1)

        # Close video modal
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)

        # Mark as liked in Firebase
        mark_liked_in_firebase(username)

        logger.info(f"Liked video from @{username}")
        return True

    except Exception as e:
        logger.error(f"Failed to like video from @{username}: {e}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def run_auto_liker(args: argparse.Namespace, logger: logging.Logger):
    """Main automation loop."""
    # Time window check
    if not is_within_time_window() and not args.test:
        logger.warning(f"Outside allowed time window ({TIKTOK_START_HOUR}:00-{TIKTOK_END_HOUR}:00)")
        logger.warning("Use --test flag to override for testing")
        return

    playwright = None

    try:
        # Connect to Chrome
        playwright, browser = await connect_to_chrome(logger)

        # Get the first context and page
        contexts = browser.contexts
        if not contexts:
            logger.error("No browser contexts found")
            return

        pages = contexts[0].pages
        page = pages[0] if pages else await contexts[0].new_page()

        # Determine limit
        limit = args.limit
        if args.test:
            limit = min(args.test, limit)
            logger.info(f"Test mode: processing {limit} accounts")

        # Get following list from profile
        following = await get_following_list(page, args.username, logger)  # Get all following

        if not following:
            logger.warning("No accounts found in following list")
            return

        # Filter out accounts already liked (ever or today)
        if getattr(args, 'new_only', False):
            liked_ever = get_liked_ever()
            original_count = len(following)
            following = [u for u in following if u not in liked_ever]
            skipped = original_count - len(following)
            logger.info(f"Skipping {skipped} accounts already liked (new-only mode)")
            if not following:
                logger.info("All accounts have been liked! Cycle complete - run without --new-only to re-like.")
                return
        elif getattr(args, 'skip_liked_today', False):
            liked_today = get_liked_today()
            original_count = len(following)
            following = [u for u in following if u not in liked_today]
            logger.info(f"Skipping {original_count - len(following)} accounts already liked today")

        # Randomize order for natural behavior
        random.shuffle(following)

        # Limit to requested count
        following = following[:limit]
        logger.info(f"Processing {len(following)} accounts")

        # Process each account
        liked_count = 0
        failed_count = 0
        skipped_count = 0

        for i, username in enumerate(following):
            if liked_count >= args.limit:
                logger.info(f"Reached daily limit of {args.limit} likes")
                break

            success = await like_latest_video(page, username, logger, dry_run=args.dry_run)

            if success:
                liked_count += 1
            else:
                failed_count += 1

            # Progress update
            logger.info(f"Progress: {i+1}/{len(following)} | Liked: {liked_count} | Failed: {failed_count}")

            # Random delay between likes (skip for dry run)
            if not args.dry_run and i < len(following) - 1:
                delay = random_delay()
                logger.info(f"Waiting {delay:.1f}s before next account...")
                await asyncio.sleep(delay)

        # Summary
        logger.info("=" * 50)
        logger.info(f"Session complete: {liked_count} liked, {failed_count} failed")
        total = liked_count + failed_count
        if total > 0:
            logger.info(f"Success rate: {liked_count/total*100:.1f}%")

    except Exception as e:
        logger.error(f"Auto-liker error: {e}")
        raise
    finally:
        if playwright:
            await playwright.stop()


# ============== Firebase Integration ==============

def init_firebase():
    """Initialize Firebase for liked accounts tracking."""
    try:
        from firebase_admin import credentials, firestore
        import firebase_admin
        from config import FIREBASE_SERVICE_ACCOUNT, FIREBASE_PROJECT_ID

        if not FIREBASE_SERVICE_ACCOUNT.exists():
            return None

        # Check if already initialized
        try:
            app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(str(FIREBASE_SERVICE_ACCOUNT))
            app = firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})

        return firestore.client()
    except Exception:
        return None


def get_liked_from_firebase() -> set:
    """Get set of all liked accounts from Firebase."""
    db = init_firebase()
    if db is None:
        return set()

    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = db.collection("tiktok_accounts").where(
            filter=FieldFilter("liked", "==", True)
        ).stream()
        return {doc.to_dict()["username"] for doc in docs}
    except Exception:
        return set()


def mark_liked_in_firebase(username: str):
    """Mark an account as liked in Firebase."""
    db = init_firebase()
    if db is None:
        return

    try:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        ref = db.collection("tiktok_accounts").document(username)
        doc = ref.get()

        if doc.exists:
            data = doc.to_dict()
            like_count = data.get("like_count", 0) + 1
            ref.update({
                "liked": True,
                "liked_at": now,
                "like_count": like_count,
                "updated_at": now,
            })
        else:
            ref.set({
                "username": username,
                "sources": ["auto-liker"],
                "liked": True,
                "liked_at": now,
                "like_count": 1,
                "created_at": now,
                "updated_at": now,
            })
    except Exception:
        pass


def get_liked_today() -> set:
    """Get set of accounts already liked today from log file."""
    log_file = TIKTOK_AUTO_LIKER_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    liked = set()
    if log_file.exists():
        with open(log_file) as f:
            for line in f:
                if "Liked video from @" in line:
                    # Extract username after @
                    username = line.split("@")[-1].strip()
                    liked.add(username)
    return liked


def get_liked_ever() -> set:
    """Get set of all accounts ever liked from Firebase + log files."""
    # Try Firebase first
    firebase_liked = get_liked_from_firebase()
    if firebase_liked:
        return firebase_liked

    # Fallback to log files
    liked = set()
    if TIKTOK_AUTO_LIKER_LOG_DIR.exists():
        for log_file in TIKTOK_AUTO_LIKER_LOG_DIR.glob("*.log"):
            if log_file.name.startswith("launchd"):
                continue
            with open(log_file) as f:
                for line in f:
                    if "Liked video from @" in line:
                        username = line.split("@")[-1].strip()
                        liked.add(username)
    return liked


def main():
    parser = argparse.ArgumentParser(description="TikTok Auto-Liker")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be liked without actually liking")
    parser.add_argument("--limit", type=int, default=TIKTOK_DAILY_LIKE_MAX, help=f"Daily like limit (default: {TIKTOK_DAILY_LIKE_MAX})")
    parser.add_argument("--test", type=int, metavar="N", help="Test mode: only process first N accounts")
    parser.add_argument("--username", type=str, default=DEFAULT_USERNAME, help=f"TikTok username (default: {DEFAULT_USERNAME})")
    parser.add_argument("--skip-liked-today", action="store_true", help="Skip accounts already liked today")
    parser.add_argument("--new-only", action="store_true", help="Only like accounts never liked before (cycle through all first)")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("TikTok Auto-Liker starting...")
    logger.info(f"Config: limit={args.limit}, dry_run={args.dry_run}, test={args.test}, username={args.username}")

    try:
        asyncio.run(run_auto_liker(args, logger))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
