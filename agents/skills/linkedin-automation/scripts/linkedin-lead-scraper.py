#!/usr/bin/env python3
"""
LinkedIn Lead Scraper for ProCaffe CRM.

Collects leads from LinkedIn connections, viewers, and engagers.

Usage:
    python3 linkedin-lead-scraper.py connections --limit 100
    python3 linkedin-lead-scraper.py viewers --limit 50
    python3 linkedin-lead-scraper.py sync-local
    python3 linkedin-lead-scraper.py --dry-run connections

Requirements:
    - Chrome running with: ./linkedin-chrome-launcher.sh
    - Logged into LinkedIn in Chrome
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
    LINKEDIN_CDP_PORT,
    LOGS_DIR,
    LINKEDIN_LEADS_FILE,
    DATA_DIR,
)
from lead_model import create_lead

# Logging setup
LOG_DIR = LOGS_DIR / "linkedin-lead-scraper"


def setup_logging() -> logging.Logger:
    """Configure logging."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"scraper-{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("linkedin-lead-scraper")
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
    """Connect to Chrome via CDP (reused pattern)."""
    cdp_url = f"http://127.0.0.1:{LINKEDIN_CDP_PORT}"
    logger.info(f"Connecting to Chrome via CDP at {cdp_url}")

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
        logger.info("Connected to Chrome successfully")
        return playwright, browser
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        logger.error("Start Chrome with: ./linkedin-chrome-launcher.sh")
        await playwright.stop()
        raise


async def scrape_connections(
    page: Page,
    limit: int,
    logger: logging.Logger
) -> list[dict]:
    """
    Scrape existing LinkedIn connections.

    Returns:
        List of lead dicts with name, headline, profile_url
    """
    url = "https://www.linkedin.com/mynetwork/invite-connect/connections/"
    logger.info(f"Navigating to {url}")

    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(4)

    # Check if logged in
    if "login" in page.url.lower() or "checkpoint" in page.url.lower():
        logger.error("Not logged in to LinkedIn. Please log in manually.")
        return []

    leads = []
    seen_usernames = set()
    prev_count = 0
    stale_scrolls = 0

    for scroll in range(200):  # Max scrolls
        # Find all profile links - LinkedIn has multiple links per connection
        links = await page.query_selector_all('a[href*="/in/"]')

        for link in links:
            try:
                href = await link.get_attribute("href")
                if not href or "/in/" not in href:
                    continue

                # Extract username
                username = href.split("/in/")[-1].split("/")[0].split("?")[0]
                if not username or username in seen_usernames:
                    continue

                # Get link text (may contain name + headline)
                text = await link.inner_text()
                text = text.strip()

                # Skip empty links (avatar images)
                if not text:
                    continue

                # Parse name and headline from text
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                name = lines[0] if lines else ""
                headline = lines[1] if len(lines) > 1 else ""

                seen_usernames.add(username)
                leads.append({
                    "username": username,
                    "name": name,
                    "bio": headline,
                    "profile_url": f"https://www.linkedin.com/in/{username}/",
                })
            except Exception:
                continue

        if len(leads) >= limit:
            break

        # Check for stale scrolling
        if len(leads) == prev_count:
            stale_scrolls += 1
            if stale_scrolls >= 8:
                logger.info(f"No new connections after {stale_scrolls} scrolls, stopping")
                break
        else:
            stale_scrolls = 0
        prev_count = len(leads)

        # Human-like scroll
        scroll_amount = random.randint(600, 1000)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(1.5, 2.5))

        if scroll % 20 == 0:
            logger.info(f"Scroll {scroll}: found {len(leads)} connections")

    logger.info(f"Collected {len(leads)} connections")
    return leads[:limit]


async def scrape_profile_viewers(
    page: Page,
    limit: int,
    logger: logging.Logger
) -> list[dict]:
    """
    Scrape profile viewers (may require Premium).

    Returns:
        List of lead dicts
    """
    url = "https://www.linkedin.com/me/profile-views/"
    logger.info(f"Navigating to {url}")

    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(4)

    if "login" in page.url.lower():
        logger.error("Not logged in to LinkedIn.")
        return []

    leads = []
    seen_usernames = set()

    for scroll in range(50):
        # Find viewer cards
        cards = await page.query_selector_all('.profile-view-card, .pv-profile-view-card')

        for card in cards:
            try:
                name_el = await card.query_selector('.profile-view-card__name, .pv-profile-view-card__name')
                name = await name_el.inner_text() if name_el else ""

                headline_el = await card.query_selector('.profile-view-card__headline, .pv-profile-view-card__headline')
                headline = await headline_el.inner_text() if headline_el else ""

                link_el = await card.query_selector('a[href*="/in/"]')
                href = await link_el.get_attribute("href") if link_el else ""

                if href and "/in/" in href:
                    username = href.split("/in/")[-1].split("/")[0].split("?")[0]
                    profile_url = f"https://www.linkedin.com/in/{username}/"

                    if username and username not in seen_usernames:
                        seen_usernames.add(username)
                        leads.append({
                            "username": username,
                            "name": name.strip(),
                            "bio": headline.strip(),
                            "profile_url": profile_url,
                        })
            except Exception:
                continue

        if len(leads) >= limit:
            break

        await page.evaluate("window.scrollBy(0, 500)")
        await asyncio.sleep(random.uniform(1.0, 2.0))

    logger.info(f"Collected {len(leads)} profile viewers")
    return leads[:limit]


def sync_local_leads(dry_run: bool, logger: logging.Logger) -> int:
    """
    Import existing linkedin-leads.json to Firestore.

    Handles both standard profiles (/in/) and Sales Navigator leads (/sales/lead/).

    Returns:
        Number of leads synced
    """
    if not LINKEDIN_LEADS_FILE.exists():
        logger.warning(f"No local leads file found: {LINKEDIN_LEADS_FILE}")
        return 0

    try:
        with open(LINKEDIN_LEADS_FILE) as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read leads file: {e}")
        return 0

    # Handle nested structure: {"leads": {...}}
    if "leads" in data:
        data = data["leads"]

    synced = 0
    for profile_url, lead_data in data.items():
        # Extract username from various LinkedIn URL formats
        username = None

        if "/in/" in profile_url:
            # Standard profile: /in/username
            username = profile_url.split("/in/")[-1].rstrip("/").split("?")[0].split(",")[0]
        elif "/sales/lead/" in profile_url:
            # Sales Navigator: /sales/lead/ACwAAA...,NAME_SEARCH,XXX
            # Use the Sales Nav ID as username (it's unique)
            lead_id = profile_url.split("/sales/lead/")[-1].split(",")[0]
            if lead_id:
                username = f"salesnav_{lead_id[:20]}"  # Truncate for readability

        if not username:
            logger.debug(f"Skipping unrecognized URL format: {profile_url[:50]}")
            continue

        if dry_run:
            logger.info(f"[DRY-RUN] Would sync: {username}")
            synced += 1
            continue

        try:
            lead = create_lead(
                platform="linkedin",
                username=username,
                profile_url=profile_url if profile_url.startswith("http") else f"https://www.linkedin.com{profile_url}",
                engagement_type="sales_nav_search",
                platform_data={
                    "query": lead_data.get("query", ""),
                    "tier_original": lead_data.get("tier", ""),
                    "sales_nav_url": profile_url if "/sales/lead/" in profile_url else "",
                },
            )
            logger.info(f"Synced: {lead['id']}")
            synced += 1
        except Exception as e:
            logger.error(f"Failed to sync {username}: {e}")

    return synced


def save_leads_to_firestore(
    users: list[dict],
    engagement_type: str,
    dry_run: bool,
    logger: logging.Logger
) -> int:
    """Save scraped users to Firestore as leads."""
    saved = 0

    for user in users:
        if dry_run:
            logger.info(f"[DRY-RUN] Would save: {user['username']} ({engagement_type})")
            saved += 1
            continue

        try:
            lead = create_lead(
                platform="linkedin",
                username=user["username"],
                profile_url=user["profile_url"],
                engagement_type=engagement_type,
                name=user.get("name", ""),
                bio=user.get("bio", ""),
            )
            logger.info(f"Saved lead: {lead['id']} (score: {lead['engagement_score']})")
            saved += 1
        except Exception as e:
            logger.error(f"Failed to save {user['username']}: {e}")

    return saved


async def main():
    parser = argparse.ArgumentParser(description="LinkedIn Lead Scraper")
    parser.add_argument("command", choices=["connections", "viewers", "sync-local"],
                        help="What to scrape")
    parser.add_argument("--limit", type=int, default=100, help="Max leads to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to Firestore")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info(f"LinkedIn Lead Scraper starting: {args.command}")

    # Handle sync-local without browser
    if args.command == "sync-local":
        synced = sync_local_leads(args.dry_run, logger)
        logger.info(f"{'[DRY-RUN] ' if args.dry_run else ''}Synced {synced} leads from local file")
        return

    # Browser-based scraping
    playwright = None
    try:
        playwright, browser = await connect_to_chrome(logger)
        page = browser.contexts[0].pages[0]

        if args.command == "connections":
            users = await scrape_connections(page, args.limit, logger)
            engagement_type = "connection"
        elif args.command == "viewers":
            users = await scrape_profile_viewers(page, args.limit, logger)
            engagement_type = "profile_viewer"
        else:
            logger.error(f"Unknown command: {args.command}")
            return

        # Save to Firestore
        if users:
            saved = save_leads_to_firestore(users, engagement_type, args.dry_run, logger)
            logger.info(f"{'[DRY-RUN] ' if args.dry_run else ''}Saved {saved}/{len(users)} leads")
        else:
            logger.warning("No users found to save")

    except Exception as e:
        logger.error(f"Scraper error: {e}")
        sys.exit(1)
    finally:
        if playwright:
            await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())
