#!/usr/bin/env python3
"""
TikTok Account Discoverer: Build a pool of accounts to follow.

Sources:
1. Competitor followers - Scrape from @cubesasia, @copen_coffee, @thegioimaypha
2. Business accounts - Search TikTok for Vietnam hotels/cafes/restaurants/offices

Uses Chrome DevTools Protocol (CDP) to control a real Chrome browser.

Usage:
    1. First run: ./tiktok-chrome-launcher.sh and log in to TikTok manually
    2. Keep Chrome open, then run: python3 tiktok-account-discoverer.py

Options:
    --dry-run           Show what would be discovered without saving
    --keywords-only     Only search keywords, skip competitor scraping
    --competitors-only  Only scrape competitors, skip keyword search
    --limit N           Max accounts per source (default: 100)
"""

import argparse
import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page

from config import (
    TIKTOK_CDP_PORT,
    TIKTOK_FOLLOW_QUEUE_FILE,
    TIKTOK_FOLLOWED_FILE,
    TIKTOK_SEARCH_KEYWORDS,
    TIKTOK_COMPETITORS,
    LOGS_DIR,
)

# Discovery log directory
DISCOVERY_LOG_DIR = LOGS_DIR / "tiktok-discoverer"


def setup_logging() -> logging.Logger:
    """Configure logging to file and console."""
    DISCOVERY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DISCOVERY_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("tiktok-discoverer")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)

    return logger


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


async def search_by_keyword(page: Page, keyword: str, logger: logging.Logger, limit: int = 100) -> list:
    """
    Search TikTok for accounts matching keyword.
    Returns list of usernames.
    """
    usernames = set()
    logger.info(f"Searching for keyword: {keyword}")

    try:
        # Navigate to TikTok search
        search_url = f"https://www.tiktok.com/search/user?q={keyword.replace(' ', '%20')}"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # Scroll and collect usernames
        prev_count = 0
        stale_scrolls = 0

        for scroll in range(50):  # Max 50 scroll attempts
            # Find all user profile links
            links = await page.query_selector_all('a[href*="/@"]')

            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href and "/@" in href:
                        u = href.split("/@")[-1].split("/")[0].split("?")[0]
                        if u and len(u) > 0:
                            usernames.add(u)
                except Exception:
                    continue

            # Check if we've collected enough
            if len(usernames) >= limit:
                break

            # Check for stale scrolling
            if len(usernames) == prev_count:
                stale_scrolls += 1
                if stale_scrolls >= 5:
                    break
            else:
                stale_scrolls = 0
            prev_count = len(usernames)

            # Scroll down
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(1.5)

            if scroll % 10 == 0:
                logger.info(f"  Scroll {scroll}: found {len(usernames)} accounts")

        logger.info(f"  Found {len(usernames)} accounts for '{keyword}'")
        return list(usernames)[:limit]

    except Exception as e:
        logger.error(f"Error searching for '{keyword}': {e}")
        return []


async def scrape_competitor_followers(page: Page, competitor: str, logger: logging.Logger, limit: int = 200) -> list:
    """
    Scrape followers from a competitor's profile.
    Returns list of usernames.
    """
    usernames = set()
    logger.info(f"Scraping followers from @{competitor}...")

    try:
        # Navigate to competitor profile
        await page.goto(f"https://www.tiktok.com/@{competitor}", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)

        # Click on Followers count to open modal
        followers_link = await page.query_selector('[data-e2e="followers-count"]')
        if not followers_link:
            followers_link = await page.query_selector('a[href*="/followers"]')

        if not followers_link:
            logger.warning(f"Could not find Followers link on @{competitor}'s profile")
            return []

        await followers_link.click()
        await asyncio.sleep(2)

        # Scroll the modal to load followers
        prev_count = 0
        stale_scrolls = 0

        for scroll in range(100):  # Max 100 scroll attempts
            # Find all user links in modal
            links = await page.query_selector_all('a[href*="/@"]')

            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href and "/@" in href:
                        u = href.split("/@")[-1].split("/")[0].split("?")[0]
                        if u and u != competitor:
                            usernames.add(u)
                except Exception:
                    continue

            # Check if we've collected enough
            if len(usernames) >= limit:
                break

            # Check for stale scrolling
            if len(usernames) == prev_count:
                stale_scrolls += 1
                if stale_scrolls >= 5:
                    break
            else:
                stale_scrolls = 0
            prev_count = len(usernames)

            # Scroll the modal container
            await page.evaluate('''
                const modal = document.querySelector('[class*="DivUserListContainer"]')
                    || document.querySelector('[class*="FollowerList"]')
                    || document.querySelector('[role="dialog"]');
                if (modal) modal.scrollBy(0, 500);
            ''')
            await asyncio.sleep(0.8)

            if scroll % 10 == 0:
                logger.info(f"  Scroll {scroll}: found {len(usernames)} followers")

        # Close modal
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)

        logger.info(f"  Scraped {len(usernames)} followers from @{competitor}")
        return list(usernames)[:limit]

    except Exception as e:
        logger.error(f"Error scraping @{competitor}: {e}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return []


def load_existing_data(logger: logging.Logger) -> tuple:
    """Load existing queue and followed accounts."""
    queue = []
    followed = set()

    if TIKTOK_FOLLOW_QUEUE_FILE.exists():
        try:
            with open(TIKTOK_FOLLOW_QUEUE_FILE) as f:
                data = json.load(f)
                queue = data.get("queue", [])
                logger.info(f"Loaded {len(queue)} accounts from existing queue")
        except Exception as e:
            logger.warning(f"Could not load queue file: {e}")

    if TIKTOK_FOLLOWED_FILE.exists():
        try:
            with open(TIKTOK_FOLLOWED_FILE) as f:
                data = json.load(f)
                followed = set(data.get("followed", []))
                logger.info(f"Loaded {len(followed)} already-followed accounts")
        except Exception as e:
            logger.warning(f"Could not load followed file: {e}")

    return queue, followed


def save_queue(queue: list, sources: dict, logger: logging.Logger, dry_run: bool = False):
    """Save updated queue to file."""
    if dry_run:
        logger.info("[DRY RUN] Would save queue with:")
        logger.info(f"  Total: {len(queue)} accounts")
        for source, count in sources.items():
            logger.info(f"  {source}: {count}")
        return

    TIKTOK_FOLLOW_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "updated": datetime.now().isoformat(),
        "queue": queue,
        "sources": sources,
        "total": len(queue)
    }

    with open(TIKTOK_FOLLOW_QUEUE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved {len(queue)} accounts to {TIKTOK_FOLLOW_QUEUE_FILE}")


async def run_discovery(args: argparse.Namespace, logger: logging.Logger):
    """Main discovery loop."""
    playwright = None
    all_usernames = set()
    sources = {}

    try:
        # Load existing data
        existing_queue, followed = load_existing_data(logger)
        all_usernames.update(existing_queue)

        # Connect to Chrome
        playwright, browser = await connect_to_chrome(logger)

        # Get the first context and page
        contexts = browser.contexts
        if not contexts:
            logger.error("No browser contexts found")
            return

        pages = contexts[0].pages
        page = pages[0] if pages else await contexts[0].new_page()

        # Scrape competitor followers
        if not args.keywords_only:
            for competitor in TIKTOK_COMPETITORS:
                followers = await scrape_competitor_followers(page, competitor, logger, limit=args.limit)
                new_followers = [u for u in followers if u not in followed]
                all_usernames.update(new_followers)
                sources[f"competitor_{competitor}"] = len(new_followers)
                logger.info(f"Added {len(new_followers)} new accounts from @{competitor}")

                # Random delay between competitors
                await asyncio.sleep(random.uniform(5, 10))

        # Search by keywords
        if not args.competitors_only:
            for keyword in TIKTOK_SEARCH_KEYWORDS:
                results = await search_by_keyword(page, keyword, logger, limit=args.limit)
                new_results = [u for u in results if u not in followed]
                all_usernames.update(new_results)
                keyword_key = keyword.replace(" ", "_")[:20]
                sources[f"search_{keyword_key}"] = len(new_results)
                logger.info(f"Added {len(new_results)} new accounts from '{keyword}'")

                # Random delay between searches
                await asyncio.sleep(random.uniform(3, 7))

        # Save results
        queue_list = list(all_usernames)
        random.shuffle(queue_list)  # Randomize order
        save_queue(queue_list, sources, logger, dry_run=args.dry_run)

        # Summary
        logger.info("=" * 50)
        logger.info(f"Discovery complete!")
        logger.info(f"Total accounts in queue: {len(queue_list)}")
        for source, count in sources.items():
            logger.info(f"  {source}: {count}")

    except Exception as e:
        logger.error(f"Discovery error: {e}")
        raise
    finally:
        if playwright:
            await playwright.stop()


def main():
    parser = argparse.ArgumentParser(description="TikTok Account Discoverer")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be discovered without saving")
    parser.add_argument("--keywords-only", action="store_true", help="Only search keywords")
    parser.add_argument("--competitors-only", action="store_true", help="Only scrape competitors")
    parser.add_argument("--limit", type=int, default=100, help="Max accounts per source (default: 100)")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("TikTok Account Discoverer starting...")
    logger.info(f"Config: keywords_only={args.keywords_only}, competitors_only={args.competitors_only}, limit={args.limit}")

    try:
        asyncio.run(run_discovery(args, logger))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
