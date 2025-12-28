#!/usr/bin/env python3
"""
TikTok Auto-Follower: Follow accounts from queue with human-like behavior.

Runs hourly from 10 AM - 10 PM Vietnam time, following ~10 accounts per batch.
Uses Chrome DevTools Protocol (CDP) to control a real Chrome browser.

Usage:
    1. First run: ./tiktok-chrome-launcher.sh and log in to TikTok manually
    2. Keep Chrome open, then run: python3 tiktok-auto-follower.py

Options:
    --dry-run       Show what would be followed without actually following
    --batch N       Accounts per batch (default: 10)
    --test N        Test mode: only process first N accounts
"""

import argparse
import asyncio
import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page

from config import (
    TIKTOK_CDP_PORT,
    TIKTOK_FOLLOW_DELAY_MIN,
    TIKTOK_FOLLOW_DELAY_MAX,
    TIKTOK_HOURLY_FOLLOW_MAX,
    TIKTOK_FOLLOW_START_HOUR,
    TIKTOK_FOLLOW_END_HOUR,
    TIKTOK_AUTO_FOLLOWER_LOG_DIR,
    TIKTOK_FOLLOW_QUEUE_FILE,
    TIKTOK_FOLLOWED_FILE,
)


def setup_logging() -> logging.Logger:
    """Configure logging to file and console."""
    TIKTOK_AUTO_FOLLOWER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = TIKTOK_AUTO_FOLLOWER_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("tiktok-auto-follower")
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
    """Check if current time is within allowed window (10 AM - 10 PM Vietnam)."""
    now = datetime.now()
    return TIKTOK_FOLLOW_START_HOUR <= now.hour < TIKTOK_FOLLOW_END_HOUR


def random_delay() -> float:
    """Generate human-like random delay with gaussian distribution."""
    mean = (TIKTOK_FOLLOW_DELAY_MIN + TIKTOK_FOLLOW_DELAY_MAX) / 2
    std = (TIKTOK_FOLLOW_DELAY_MAX - TIKTOK_FOLLOW_DELAY_MIN) / 4
    delay = random.gauss(mean, std)
    return max(TIKTOK_FOLLOW_DELAY_MIN, min(TIKTOK_FOLLOW_DELAY_MAX, delay))


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


def load_queue(logger: logging.Logger) -> list:
    """Load follow queue from JSON file."""
    if not TIKTOK_FOLLOW_QUEUE_FILE.exists():
        logger.warning(f"Queue file not found: {TIKTOK_FOLLOW_QUEUE_FILE}")
        logger.warning("Run tiktok-account-discoverer.py first to build the queue")
        return []

    try:
        with open(TIKTOK_FOLLOW_QUEUE_FILE) as f:
            data = json.load(f)
            queue = data.get("queue", [])
            logger.info(f"Loaded {len(queue)} accounts from queue")
            return queue
    except Exception as e:
        logger.error(f"Could not load queue: {e}")
        return []


def load_followed(logger: logging.Logger) -> set:
    """Load already-followed accounts from JSON file."""
    if not TIKTOK_FOLLOWED_FILE.exists():
        return set()

    try:
        with open(TIKTOK_FOLLOWED_FILE) as f:
            data = json.load(f)
            followed = set(data.get("followed", []))
            logger.info(f"Loaded {len(followed)} already-followed accounts")
            return followed
    except Exception as e:
        logger.warning(f"Could not load followed file: {e}")
        return set()


def save_followed(username: str, logger: logging.Logger, dry_run: bool = False):
    """Append username to followed accounts file."""
    if dry_run:
        return

    TIKTOK_FOLLOWED_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data
    data = {"followed": [], "updated": None}
    if TIKTOK_FOLLOWED_FILE.exists():
        try:
            with open(TIKTOK_FOLLOWED_FILE) as f:
                data = json.load(f)
        except Exception:
            pass

    # Add new username
    if username not in data.get("followed", []):
        data.setdefault("followed", []).append(username)
        data["updated"] = datetime.now().isoformat()

        with open(TIKTOK_FOLLOWED_FILE, 'w') as f:
            json.dump(data, f, indent=2)


def update_queue(queue: list, to_remove: list, logger: logging.Logger, dry_run: bool = False):
    """Remove followed accounts from queue and save."""
    if dry_run or not to_remove:
        return

    if not TIKTOK_FOLLOW_QUEUE_FILE.exists():
        return

    try:
        with open(TIKTOK_FOLLOW_QUEUE_FILE) as f:
            data = json.load(f)

        # Remove followed accounts from queue
        original_count = len(data.get("queue", []))
        data["queue"] = [u for u in data.get("queue", []) if u not in to_remove]
        data["updated"] = datetime.now().isoformat()
        data["total"] = len(data["queue"])

        with open(TIKTOK_FOLLOW_QUEUE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Updated queue: removed {original_count - len(data['queue'])} accounts")
    except Exception as e:
        logger.warning(f"Could not update queue: {e}")


async def follow_account(page: Page, username: str, logger: logging.Logger, dry_run: bool = False) -> str:
    """
    Navigate to user's profile and click Follow button.
    Returns: 'followed', 'already_following', 'failed'
    """
    try:
        logger.info(f"Processing @{username}")

        if dry_run:
            logger.info(f"[DRY RUN] Would follow @{username}")
            return "followed"

        # Navigate to profile
        await page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(2, 3))  # View profile like a human

        # Find Follow button
        follow_btn = await page.query_selector('[data-e2e="follow-button"]')
        if not follow_btn:
            follow_btn = await page.query_selector('button:has-text("Follow")')

        if not follow_btn:
            logger.warning(f"Could not find Follow button for @{username}")
            return "failed"

        # Check if already following
        try:
            text = await follow_btn.text_content()
            if text and ("Following" in text or "Friends" in text):
                logger.info(f"Already following @{username}")
                return "already_following"
        except Exception:
            pass

        # Click follow
        await follow_btn.click()
        await asyncio.sleep(1)

        # Verify follow was successful
        try:
            new_text = await follow_btn.text_content()
            if new_text and ("Following" in new_text or "Friends" in new_text):
                logger.info(f"Successfully followed @{username}")
                return "followed"
        except Exception:
            pass

        logger.info(f"Clicked follow for @{username}")
        return "followed"

    except Exception as e:
        logger.error(f"Failed to follow @{username}: {e}")
        return "failed"


async def run_auto_follower(args: argparse.Namespace, logger: logging.Logger):
    """Main automation loop."""
    # Time window check
    if not is_within_time_window() and not args.test:
        logger.warning(f"Outside allowed time window ({TIKTOK_FOLLOW_START_HOUR}:00-{TIKTOK_FOLLOW_END_HOUR}:00)")
        logger.warning("Use --test flag to override for testing")
        return

    playwright = None

    try:
        # Load queue and followed list
        queue = load_queue(logger)
        followed = load_followed(logger)

        if not queue:
            logger.warning("Queue is empty. Run tiktok-account-discoverer.py first.")
            return

        # Filter out already-followed accounts
        available = [u for u in queue if u not in followed]
        logger.info(f"{len(available)} accounts available (filtered out {len(queue) - len(available)} already followed)")

        if not available:
            logger.warning("No new accounts to follow. Run discoverer to add more.")
            return

        # Shuffle for random order
        random.shuffle(available)

        # Determine batch size
        batch_size = args.batch
        if args.test:
            batch_size = min(args.test, batch_size)
            logger.info(f"Test mode: processing {batch_size} accounts")

        # Limit to batch size
        to_process = available[:batch_size]
        logger.info(f"Processing {len(to_process)} accounts this batch")

        # Connect to Chrome
        playwright, browser = await connect_to_chrome(logger)

        # Get the first context and page
        contexts = browser.contexts
        if not contexts:
            logger.error("No browser contexts found")
            return

        pages = contexts[0].pages
        page = pages[0] if pages else await contexts[0].new_page()

        # Process each account
        followed_count = 0
        already_count = 0
        failed_count = 0
        processed_users = []

        for i, username in enumerate(to_process):
            result = await follow_account(page, username, logger, dry_run=args.dry_run)

            if result == "followed":
                followed_count += 1
                save_followed(username, logger, dry_run=args.dry_run)
                processed_users.append(username)
            elif result == "already_following":
                already_count += 1
                save_followed(username, logger, dry_run=args.dry_run)
                processed_users.append(username)
            else:
                failed_count += 1

            # Progress update
            logger.info(f"Progress: {i+1}/{len(to_process)} | Followed: {followed_count} | Already: {already_count} | Failed: {failed_count}")

            # Random delay between follows (skip for dry run)
            if not args.dry_run and i < len(to_process) - 1:
                delay = random_delay()
                logger.info(f"Waiting {delay:.1f}s before next account...")
                await asyncio.sleep(delay)

        # Update queue to remove processed accounts
        update_queue(queue, processed_users, logger, dry_run=args.dry_run)

        # Summary
        logger.info("=" * 50)
        logger.info(f"Batch complete: {followed_count} followed, {already_count} already, {failed_count} failed")
        total = followed_count + already_count + failed_count
        if total > 0:
            success_rate = (followed_count + already_count) / total * 100
            logger.info(f"Success rate: {success_rate:.1f}%")

    except Exception as e:
        logger.error(f"Auto-follower error: {e}")
        raise
    finally:
        if playwright:
            await playwright.stop()


def main():
    parser = argparse.ArgumentParser(description="TikTok Auto-Follower")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be followed without actually following")
    parser.add_argument("--batch", type=int, default=TIKTOK_HOURLY_FOLLOW_MAX, help=f"Accounts per batch (default: {TIKTOK_HOURLY_FOLLOW_MAX})")
    parser.add_argument("--test", type=int, metavar="N", help="Test mode: only process first N accounts")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("TikTok Auto-Follower starting...")
    logger.info(f"Config: batch={args.batch}, dry_run={args.dry_run}, test={args.test}")

    try:
        asyncio.run(run_auto_follower(args, logger))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
