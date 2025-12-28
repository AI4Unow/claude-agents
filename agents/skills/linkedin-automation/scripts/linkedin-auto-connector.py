#!/usr/bin/env python3
"""
LinkedIn Auto-Connector: Search by job title and send connection requests.

Uses Chrome DevTools Protocol (CDP) to control a real Chrome browser with
persistent session, minimizing detection risk.

Usage:
    1. First run: ./linkedin-chrome-launcher.sh and log in to LinkedIn manually
    2. Keep Chrome open, then run: python3 linkedin-auto-connector.py

Options:
    --dry-run       Show what would be sent without actually connecting
    --limit N       Override daily limit (default: 25)
    --test N        Test mode: only process first N profiles
    --title "..."   Search specific title only
    --sales-nav     Use Sales Navigator search (requires subscription)
    --query NAME    Use specific Sales Nav query by name
"""

import argparse
import asyncio
import json
import logging
import random
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page

from config import (
    LINKEDIN_CDP_PORT,
    LINKEDIN_CONNECT_DELAY_MIN,
    LINKEDIN_CONNECT_DELAY_MAX,
    LINKEDIN_DAILY_CONNECT_MAX,
    LINKEDIN_START_HOUR,
    LINKEDIN_END_HOUR,
    LINKEDIN_AUTO_LOG_DIR,
    LINKEDIN_CONNECTIONS_FILE,
    LINKEDIN_TARGET_TITLES,
    LINKEDIN_VIETNAM_GEO_URN,
    # Sales Navigator
    SALES_NAV_SEARCH_URL,
    SALES_NAV_QUERIES,
    SALES_NAV_CONNECT_TEMPLATES,
    LINKEDIN_LEADS_FILE,
)

# Connection note template (Vietnamese)
CONNECTION_NOTE = """Xin chào! Tôi là từ ProCaffe Vietnam.
Chúng tôi cung cấp máy pha cà phê chuyên nghiệp cho khách sạn, nhà hàng và quán cà phê.
Rất mong được kết nối với anh/chị!"""


def setup_logging() -> logging.Logger:
    """Configure logging to file and console."""
    LINKEDIN_AUTO_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LINKEDIN_AUTO_LOG_DIR / f"connector-{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("linkedin-connector")
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
    """Check if current time is within allowed window (8 AM - 11 AM Vietnam)."""
    now = datetime.now()
    return LINKEDIN_START_HOUR <= now.hour < LINKEDIN_END_HOUR


def random_delay() -> float:
    """Generate human-like random delay with gaussian distribution (2-5 min)."""
    mean = (LINKEDIN_CONNECT_DELAY_MIN + LINKEDIN_CONNECT_DELAY_MAX) / 2
    std = (LINKEDIN_CONNECT_DELAY_MAX - LINKEDIN_CONNECT_DELAY_MIN) / 4
    delay = random.gauss(mean, std)
    return max(LINKEDIN_CONNECT_DELAY_MIN, min(LINKEDIN_CONNECT_DELAY_MAX, delay))


async def connect_to_chrome(logger: logging.Logger):
    """Connect to existing Chrome instance via CDP."""
    cdp_url = f"http://127.0.0.1:{LINKEDIN_CDP_PORT}"
    logger.info(f"Connecting to Chrome via CDP at {cdp_url}")

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
        logger.info("Connected to Chrome successfully")
        return playwright, browser
    except Exception as e:
        logger.error(f"Failed to connect to Chrome: {e}")
        logger.error("Make sure Chrome is running with: ./linkedin-chrome-launcher.sh")
        await playwright.stop()
        raise


def load_sent_connections(logger: logging.Logger) -> set:
    """Load already-sent connections from JSON file."""
    if not LINKEDIN_CONNECTIONS_FILE.exists():
        return set()

    try:
        with open(LINKEDIN_CONNECTIONS_FILE) as f:
            data = json.load(f)
            sent = set(data.get("sent", []))
            logger.info(f"Loaded {len(sent)} already-sent connections")
            return sent
    except Exception as e:
        logger.warning(f"Could not load connections file: {e}")
        return set()


def save_connection(profile_url: str, logger: logging.Logger, dry_run: bool = False):
    """Append profile URL to sent connections."""
    if dry_run:
        return

    LINKEDIN_CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {"sent": [], "accepted": [], "updated": None}
    if LINKEDIN_CONNECTIONS_FILE.exists():
        try:
            with open(LINKEDIN_CONNECTIONS_FILE) as f:
                data = json.load(f)
        except Exception:
            pass

    if profile_url not in data.get("sent", []):
        data.setdefault("sent", []).append(profile_url)
        data["updated"] = datetime.now().isoformat()

        with open(LINKEDIN_CONNECTIONS_FILE, 'w') as f:
            json.dump(data, f, indent=2)


async def search_by_title(page: Page, title: str, logger: logging.Logger, limit: int = 50) -> list:
    """
    Search LinkedIn for people with given job title in Vietnam.
    Returns list of profile URLs.
    """
    profiles = set()
    logger.info(f"Searching for: {title}")

    try:
        # Build search URL with Vietnam geo filter
        encoded_title = urllib.parse.quote(title)
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_title}&geoUrn=%5B%22{LINKEDIN_VIETNAM_GEO_URN}%22%5D"

        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # Scroll and collect profiles
        prev_count = 0
        stale_scrolls = 0

        for scroll in range(20):  # Max 20 scroll attempts
            # Find profile links
            links = await page.query_selector_all('a[href*="/in/"]')

            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href and "/in/" in href:
                        # Clean URL
                        profile_url = href.split("?")[0]
                        if profile_url and len(profile_url) > 20:
                            profiles.add(profile_url)
                except Exception:
                    continue

            if len(profiles) >= limit:
                break

            # Check for stale scrolling
            if len(profiles) == prev_count:
                stale_scrolls += 1
                if stale_scrolls >= 3:
                    break
            else:
                stale_scrolls = 0
            prev_count = len(profiles)

            # Scroll down
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(1.5)

        logger.info(f"  Found {len(profiles)} profiles for '{title}'")
        return list(profiles)[:limit]

    except Exception as e:
        logger.error(f"Error searching for '{title}': {e}")
        return []


async def human_click(element, page: Page):
    """Click with human-like behavior - randomized position and mouse movement."""
    box = await element.bounding_box()
    if box:
        # Randomize click position within element
        x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
        y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        await page.mouse.move(x, y, steps=random.randint(5, 10))
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.click(x, y)
    else:
        # Fallback to regular click
        await element.click()


async def search_sales_nav(page: Page, query: dict, logger: logging.Logger, limit: int = 25) -> list:
    """
    Search Sales Navigator with Boolean query and Spotlight filters.
    Returns list of lead profile URLs.

    Args:
        page: Playwright page object
        query: Dict with 'name', 'query', 'spotlight', 'priority', 'tier'
        logger: Logger instance
        limit: Max profiles to return
    """
    profiles = []
    query_name = query.get("name", "unknown")
    boolean_query = query.get("query", "")
    spotlight = query.get("spotlight", "")

    logger.info(f"Sales Nav search: {query_name}")
    logger.info(f"  Query: {boolean_query}")
    logger.info(f"  Spotlight: {spotlight}")

    try:
        # Sales Navigator uses 'keywords=' parameter (not 'query=')
        encoded_query = urllib.parse.quote(boolean_query)

        # Build Sales Navigator search URL with keywords parameter
        search_url = f"{SALES_NAV_SEARCH_URL}?keywords={encoded_query}"

        logger.info(f"  URL: {search_url[:100]}...")

        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

        # Wait for search results to load - try waiting for lead links to appear
        try:
            await page.wait_for_selector('a[href*="/sales/lead/"]', timeout=15000)
        except Exception:
            logger.warning("  No lead links found after waiting - page may be empty")

        await asyncio.sleep(random.uniform(2, 3))

        # Check if we're on Sales Navigator (not redirected to regular LinkedIn)
        current_url = page.url
        if "/sales/" not in current_url:
            logger.warning("Not on Sales Navigator - may need subscription")
            logger.warning(f"  Redirected to: {current_url[:60]}...")
            return []

        # Scroll and collect leads
        prev_count = 0
        stale_scrolls = 0

        for scroll in range(15):  # Max 15 scroll attempts
            # Sales Navigator lead links are relative paths like /sales/lead/ABC...
            links = await page.query_selector_all('a[href*="/sales/lead/"]')

            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href:
                        # Convert relative to absolute URL if needed
                        if href.startswith("/"):
                            href = "https://www.linkedin.com" + href
                        # Clean URL - remove query params
                        clean_url = href.split("?")[0]
                        if clean_url and clean_url not in profiles:
                            profiles.append(clean_url)
                except Exception:
                    continue

            if len(profiles) >= limit:
                break

            # Check for stale scrolling
            if len(profiles) == prev_count:
                stale_scrolls += 1
                if stale_scrolls >= 3:
                    break
            else:
                stale_scrolls = 0
            prev_count = len(profiles)

            # Scroll down with human-like behavior
            scroll_amount = random.randint(600, 900)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(1.5, 2.5))

        logger.info(f"  Found {len(profiles)} leads from Sales Navigator")
        return profiles[:limit]

    except Exception as e:
        logger.error(f"Error in Sales Nav search '{query_name}': {e}")
        return []


def save_lead_to_tracker(profile_url: str, query: dict, logger: logging.Logger, dry_run: bool = False):
    """Save lead to the lead tracker JSON file with tier and query info."""
    if dry_run:
        return

    LINKEDIN_LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data
    data = {"leads": {}, "stats": {}}
    if LINKEDIN_LEADS_FILE.exists():
        try:
            with open(LINKEDIN_LEADS_FILE) as f:
                data = json.load(f)
        except Exception:
            pass

    # Add or update lead
    if profile_url not in data.get("leads", {}):
        data.setdefault("leads", {})[profile_url] = {
            "tier": query.get("tier", "tier3"),
            "query": query.get("name", "unknown"),
            "status": "cold",
            "added_date": datetime.now().strftime("%Y-%m-%d"),
            "actions": [],
            "last_updated": datetime.now().isoformat()
        }

        # Update stats
        data.setdefault("stats", {})
        data["stats"]["total"] = len(data["leads"])
        tier_key = query.get("tier", "tier3")
        data["stats"][tier_key] = sum(1 for l in data["leads"].values() if l.get("tier") == tier_key)

        with open(LINKEDIN_LEADS_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


async def send_connection(page: Page, profile_url: str, logger: logging.Logger, dry_run: bool = False) -> bool:
    """
    Navigate to profile and send connection request with note.
    Handles both regular LinkedIn profiles and Sales Navigator lead pages.
    Returns True if successful, False otherwise.
    """
    try:
        logger.info(f"Processing: {profile_url}")

        if dry_run:
            logger.info(f"[DRY RUN] Would connect to: {profile_url}")
            return True

        # Determine if this is a Sales Navigator URL
        is_sales_nav_url = "/sales/lead/" in profile_url

        # Navigate to profile
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(2, 4))

        connect_btn = None

        if is_sales_nav_url:
            # Sales Navigator lead page - different UI
            # Look for Connect button in Sales Nav interface
            connect_selectors = [
                'button[data-control-name="connect"]',
                'button:has-text("Connect")',
                'button:has-text("Kết nối")',
                '[class*="connect-button"]',
                'button[aria-label*="Connect"]',
                # Sales Nav often has action buttons in a specific container
                '[class*="action-buttons"] button:has-text("Connect")',
                '[class*="actions"] button:has-text("Connect")',
            ]

            for selector in connect_selectors:
                connect_btn = await page.query_selector(selector)
                if connect_btn:
                    btn_text = await connect_btn.inner_text()
                    if "Connect" in btn_text or "Kết nối" in btn_text:
                        break
                    connect_btn = None

            # If no direct Connect button, try the dropdown menu
            if not connect_btn:
                # Sales Nav uses "..." or "More" dropdown
                more_selectors = [
                    'button[aria-label*="more"]',
                    'button[aria-label*="More"]',
                    'button:has-text("More")',
                    'button:has-text("...")',
                    '[class*="overflow-menu"] button',
                ]
                for sel in more_selectors:
                    more_btn = await page.query_selector(sel)
                    if more_btn:
                        await more_btn.click()
                        await asyncio.sleep(1)
                        # Look for Connect in dropdown
                        connect_btn = await page.query_selector('[role="menuitem"]:has-text("Connect")')
                        if not connect_btn:
                            connect_btn = await page.query_selector('[role="option"]:has-text("Connect")')
                        if connect_btn:
                            break
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)

        else:
            # Regular LinkedIn profile page
            connect_selectors = [
                'button:has-text("Connect")',
                'button:has-text("Kết nối")',
                'button[aria-label*="connect" i]',
                'button[aria-label*="Connect"]',
                'button[aria-label*="Kết nối"]',
                'main button:has-text("Connect")',
                'main button:has-text("Kết nối")',
            ]

            for selector in connect_selectors:
                connect_btn = await page.query_selector(selector)
                if connect_btn:
                    btn_text = await connect_btn.inner_text()
                    if ("Connect" in btn_text or "Kết nối" in btn_text) and "Disconnect" not in btn_text:
                        break
                    connect_btn = None

            if not connect_btn:
                # Try "More" dropdown
                more_btn = await page.query_selector('button:has-text("More")')
                if not more_btn:
                    more_btn = await page.query_selector('button:has-text("Khác")')
                if more_btn:
                    await more_btn.click()
                    await asyncio.sleep(1)
                    connect_btn = await page.query_selector('div[role="menuitem"]:has-text("Connect")')
                    if not connect_btn:
                        connect_btn = await page.query_selector('div[role="menuitem"]:has-text("Kết nối")')
                    if not connect_btn:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)

        if not connect_btn:
            # Check if already connected or pending
            pending = await page.query_selector('button:has-text("Pending")')
            if not pending:
                pending = await page.query_selector('button:has-text("Đang chờ")')
            if not pending:
                pending = await page.query_selector('[class*="pending"]')

            following = await page.query_selector('button:has-text("Following")')
            if not following:
                following = await page.query_selector('button:has-text("Đang theo dõi")')

            message = await page.query_selector('button:has-text("Message")')
            if not message:
                message = await page.query_selector('button:has-text("Tin nhắn")')

            if pending:
                logger.info(f"Connection already pending: {profile_url}")
            elif following or message:
                logger.info(f"Already connected/following: {profile_url}")
            else:
                logger.warning(f"No Connect button found on {profile_url}")
            return False

        # Click Connect
        await human_click(connect_btn, page)
        await asyncio.sleep(1.5)

        # Look for "Add a note" button
        add_note_btn = await page.query_selector('button:has-text("Add a note")')
        if not add_note_btn:
            add_note_btn = await page.query_selector('button:has-text("Thêm ghi chú")')
        if add_note_btn:
            await add_note_btn.click()
            await asyncio.sleep(1)

            # Find textarea and type note
            textarea = await page.query_selector('textarea[name="message"]')
            if not textarea:
                textarea = await page.query_selector('textarea')

            if textarea:
                await textarea.fill(CONNECTION_NOTE)
                await asyncio.sleep(0.5)

        # Click Send
        send_selectors = [
            'button:has-text("Send")',
            'button:has-text("Gửi")',
            'button[aria-label*="Send"]',
            'button[aria-label*="Gửi"]',
            'button[type="submit"]:has-text("Send")',
        ]

        send_btn = None
        for sel in send_selectors:
            send_btn = await page.query_selector(sel)
            if send_btn:
                break

        if send_btn:
            await human_click(send_btn, page)
            await asyncio.sleep(1)
            logger.info(f"Connection sent to: {profile_url}")
            return True
        else:
            logger.warning(f"Could not find Send button for {profile_url}")
            await page.keyboard.press("Escape")
            return False

    except Exception as e:
        logger.error(f"Failed to connect to {profile_url}: {e}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def run_connector(args: argparse.Namespace, logger: logging.Logger):
    """Main connector loop."""
    # Time window check
    if not is_within_time_window() and not args.test:
        logger.warning(f"Outside allowed time window ({LINKEDIN_START_HOUR}:00-{LINKEDIN_END_HOUR}:00)")
        logger.warning("Use --test flag to override for testing")
        return

    playwright = None
    is_sales_nav = getattr(args, 'sales_nav', False)

    try:
        # Load already-sent connections
        sent = load_sent_connections(logger)

        # Connect to Chrome
        playwright, browser = await connect_to_chrome(logger)

        # Get the first context and page
        contexts = browser.contexts
        if not contexts:
            logger.error("No browser contexts found")
            return

        pages = contexts[0].pages
        page = pages[0] if pages else await contexts[0].new_page()

        all_profiles = []
        current_query = None  # Track which query was used (for lead tracking)

        if is_sales_nav:
            # Sales Navigator mode
            logger.info("=" * 50)
            logger.info("SALES NAVIGATOR MODE")
            logger.info("=" * 50)

            # Determine which queries to run
            if args.query:
                # Find specific query by name
                queries = [q for q in SALES_NAV_QUERIES if q["name"] == args.query]
                if not queries:
                    logger.error(f"Query '{args.query}' not found. Available: {[q['name'] for q in SALES_NAV_QUERIES]}")
                    return
            else:
                # Run all queries sorted by priority
                queries = sorted(SALES_NAV_QUERIES, key=lambda x: x.get("priority", 99))

            # Collect profiles from Sales Nav searches
            for query in queries:
                current_query = query
                profiles = await search_sales_nav(page, query, logger, limit=15)
                new_profiles = [p for p in profiles if p not in sent]

                # Save new leads to tracker
                for profile_url in new_profiles:
                    save_lead_to_tracker(profile_url, query, logger, dry_run=args.dry_run)

                all_profiles.extend(new_profiles)
                await asyncio.sleep(random.uniform(3, 6))

                if len(all_profiles) >= args.limit * 2:
                    break  # Collected enough candidates

        else:
            # Regular LinkedIn mode
            # Determine which titles to search
            titles = [args.title] if args.title else LINKEDIN_TARGET_TITLES

            # Collect profiles from all titles
            for title in titles:
                profiles = await search_by_title(page, title, logger, limit=10)
                new_profiles = [p for p in profiles if p not in sent]
                all_profiles.extend(new_profiles)
                await asyncio.sleep(random.uniform(3, 6))

        # Deduplicate
        all_profiles = list(dict.fromkeys(all_profiles))
        logger.info(f"Total new profiles to process: {len(all_profiles)}")

        if not all_profiles:
            logger.warning("No new profiles found to connect")
            return

        # Shuffle for randomness
        random.shuffle(all_profiles)

        # Determine limit
        limit = args.limit
        if args.test:
            limit = min(args.test, limit)
            logger.info(f"Test mode: processing {limit} profiles")

        to_process = all_profiles[:limit]

        # Process each profile
        sent_count = 0
        failed_count = 0

        for i, profile_url in enumerate(to_process):
            if sent_count >= args.limit:
                logger.info(f"Reached daily limit of {args.limit} connections")
                break

            success = await send_connection(page, profile_url, logger, dry_run=args.dry_run)

            if success:
                sent_count += 1
                save_connection(profile_url, logger, dry_run=args.dry_run)
            else:
                failed_count += 1

            # Progress update
            logger.info(f"Progress: {i+1}/{len(to_process)} | Sent: {sent_count} | Failed: {failed_count}")

            # Random delay between connections (skip for dry run)
            if not args.dry_run and i < len(to_process) - 1:
                delay = random_delay()
                logger.info(f"Waiting {delay:.1f}s before next connection...")
                await asyncio.sleep(delay)

        # Summary
        logger.info("=" * 50)
        logger.info(f"Session complete: {sent_count} sent, {failed_count} failed")
        total = sent_count + failed_count
        if total > 0:
            logger.info(f"Success rate: {sent_count/total*100:.1f}%")

    except Exception as e:
        logger.error(f"Connector error: {e}")
        raise
    finally:
        if playwright:
            await playwright.stop()


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Auto-Connector")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without connecting")
    parser.add_argument("--limit", type=int, default=LINKEDIN_DAILY_CONNECT_MAX, help=f"Daily limit (default: {LINKEDIN_DAILY_CONNECT_MAX})")
    parser.add_argument("--test", type=int, metavar="N", help="Test mode: only process first N profiles")
    parser.add_argument("--title", type=str, help="Search specific title only")
    parser.add_argument("--sales-nav", action="store_true", help="Use Sales Navigator search (requires subscription)")
    parser.add_argument("--query", type=str, metavar="NAME", help="Use specific Sales Nav query by name (e.g., hotel_decision_makers)")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("LinkedIn Auto-Connector starting...")

    mode = "Sales Navigator" if args.sales_nav else "Regular LinkedIn"
    logger.info(f"Mode: {mode}")
    logger.info(f"Config: limit={args.limit}, dry_run={args.dry_run}, test={args.test}")
    if args.sales_nav and args.query:
        logger.info(f"Query: {args.query}")
    elif args.title:
        logger.info(f"Title: {args.title}")

    try:
        asyncio.run(run_connector(args, logger))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
