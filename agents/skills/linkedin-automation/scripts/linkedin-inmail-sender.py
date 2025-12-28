#!/usr/bin/env python3
"""
LinkedIn InMail Sender: Send personalized InMails to Tier 1 prospects via Sales Navigator.

Uses Chrome DevTools Protocol (CDP) to control a real Chrome browser with
persistent session, minimizing detection risk.

Usage:
    1. First run: ./linkedin-chrome-launcher.sh and log in to LinkedIn + Sales Nav
    2. Populate queue: Add leads to data/linkedin-inmail-queue.json
    3. Run: python3 linkedin-inmail-sender.py

Options:
    --dry-run       Show what would be sent without actually sending
    --limit N       Override daily limit (default: 5)
    --test N        Test mode: only process first N InMails
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
    LINKEDIN_START_HOUR,
    LINKEDIN_END_HOUR,
    LINKEDIN_AUTO_LOG_DIR,
    SALES_NAV_LEAD_URL,
    SALES_NAV_INMAIL_TEMPLATE,
    SALES_NAV_DAILY_INMAIL_MAX,
    LINKEDIN_INMAIL_QUEUE_FILE,
    LINKEDIN_INMAIL_SENT_FILE,
    LINKEDIN_LEADS_FILE,
)


def setup_logging() -> logging.Logger:
    """Configure logging to file and console."""
    LINKEDIN_AUTO_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LINKEDIN_AUTO_LOG_DIR / f"inmail-{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger("linkedin-inmail")
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


def random_delay(min_sec: int = 60, max_sec: int = 180) -> float:
    """Generate human-like random delay with gaussian distribution."""
    mean = (min_sec + max_sec) / 2
    std = (max_sec - min_sec) / 4
    delay = random.gauss(mean, std)
    return max(min_sec, min(max_sec, delay))


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


def load_inmail_queue(logger: logging.Logger) -> list:
    """Load InMail queue from JSON file."""
    if not LINKEDIN_INMAIL_QUEUE_FILE.exists():
        logger.warning(f"InMail queue file not found: {LINKEDIN_INMAIL_QUEUE_FILE}")
        return []

    try:
        with open(LINKEDIN_INMAIL_QUEUE_FILE) as f:
            data = json.load(f)
            queue = data.get("queue", [])
            logger.info(f"Loaded {len(queue)} InMails from queue")
            return queue
    except Exception as e:
        logger.error(f"Could not load InMail queue: {e}")
        return []


def load_sent_inmails(logger: logging.Logger) -> set:
    """Load already-sent InMails from JSON file."""
    if not LINKEDIN_INMAIL_SENT_FILE.exists():
        return set()

    try:
        with open(LINKEDIN_INMAIL_SENT_FILE) as f:
            data = json.load(f)
            sent = set(data.get("sent", []))
            logger.info(f"Loaded {len(sent)} already-sent InMails")
            return sent
    except Exception as e:
        logger.warning(f"Could not load sent InMails: {e}")
        return set()


def save_sent_inmail(profile_url: str, logger: logging.Logger, dry_run: bool = False):
    """Record InMail as sent."""
    if dry_run:
        return

    LINKEDIN_INMAIL_SENT_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {"sent": [], "details": [], "updated": None}
    if LINKEDIN_INMAIL_SENT_FILE.exists():
        try:
            with open(LINKEDIN_INMAIL_SENT_FILE) as f:
                data = json.load(f)
        except Exception:
            pass

    if profile_url not in data.get("sent", []):
        data.setdefault("sent", []).append(profile_url)
        data.setdefault("details", []).append({
            "profile_url": profile_url,
            "sent_at": datetime.now().isoformat()
        })
        data["updated"] = datetime.now().isoformat()

        with open(LINKEDIN_INMAIL_SENT_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def update_lead_status(profile_url: str, new_status: str, action_type: str, logger: logging.Logger):
    """Update lead status in the lead tracker."""
    if not LINKEDIN_LEADS_FILE.exists():
        return

    try:
        with open(LINKEDIN_LEADS_FILE) as f:
            data = json.load(f)

        if profile_url in data.get("leads", {}):
            data["leads"][profile_url]["status"] = new_status
            data["leads"][profile_url]["last_updated"] = datetime.now().isoformat()
            data["leads"][profile_url].setdefault("actions", []).append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "type": action_type
            })

            with open(LINKEDIN_LEADS_FILE, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.warning(f"Could not update lead status: {e}")


def remove_from_queue(profile_url: str, logger: logging.Logger):
    """Remove lead from InMail queue after sending."""
    if not LINKEDIN_INMAIL_QUEUE_FILE.exists():
        return

    try:
        with open(LINKEDIN_INMAIL_QUEUE_FILE) as f:
            data = json.load(f)

        data["queue"] = [item for item in data.get("queue", []) if item.get("profile_url") != profile_url]
        data["updated"] = datetime.now().isoformat()

        with open(LINKEDIN_INMAIL_QUEUE_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.warning(f"Could not update queue: {e}")


async def human_click(element, page: Page):
    """Click with human-like behavior."""
    box = await element.bounding_box()
    if box:
        x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
        y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        await page.mouse.move(x, y, steps=random.randint(5, 10))
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.click(x, y)
    else:
        await element.click()


async def send_inmail(page: Page, lead: dict, logger: logging.Logger, dry_run: bool = False) -> bool:
    """
    Navigate to Sales Navigator lead page and send InMail.

    Args:
        page: Playwright page object
        lead: Dict with profile_url, name, company, city, etc.
        logger: Logger instance
        dry_run: If True, don't actually send

    Returns:
        True if successful, False otherwise.
    """
    profile_url = lead.get("profile_url", "")
    name = lead.get("name", "")
    company = lead.get("company", "")
    city = lead.get("city", "Vietnam")

    try:
        logger.info(f"Processing InMail: {name} at {company}")
        logger.info(f"  URL: {profile_url}")

        if dry_run:
            logger.info(f"[DRY RUN] Would send InMail to: {name}")
            return True

        # Navigate to profile (Sales Nav or regular)
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(2, 4))

        # Look for Message/InMail button
        # Sales Navigator: "Message" button that opens InMail for non-connections
        message_btn = None
        message_selectors = [
            'button:has-text("Message")',
            'button:has-text("Tin nhắn")',
            'button[aria-label*="Message"]',
            'button[aria-label*="InMail"]',
            '[data-control-name="message"]',
        ]

        for selector in message_selectors:
            message_btn = await page.query_selector(selector)
            if message_btn:
                break

        if not message_btn:
            logger.warning(f"No Message button found for {name}")
            return False

        await human_click(message_btn, page)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Fill subject line (InMail specific)
        subject_input = await page.query_selector('input[name="subject"]')
        if not subject_input:
            subject_input = await page.query_selector('input[placeholder*="Subject"]')
        if not subject_input:
            subject_input = await page.query_selector('input[placeholder*="Chủ đề"]')

        if subject_input:
            subject = SALES_NAV_INMAIL_TEMPLATE["subject"].format(
                company=company or "quý công ty",
                name=name
            )
            await subject_input.fill(subject)
            await asyncio.sleep(0.5)

        # Fill message body
        body_textarea = await page.query_selector('textarea[name="message"]')
        if not body_textarea:
            body_textarea = await page.query_selector('div[role="textbox"]')
        if not body_textarea:
            body_textarea = await page.query_selector('textarea')

        if body_textarea:
            body = SALES_NAV_INMAIL_TEMPLATE["body"].format(
                name=name or "anh/chị",
                company=company or "quý công ty",
                city=city or "Vietnam"
            )
            await body_textarea.fill(body)
            await asyncio.sleep(0.5)
        else:
            logger.warning(f"Could not find message body field for {name}")
            await page.keyboard.press("Escape")
            return False

        # Click Send button
        send_btn = await page.query_selector('button:has-text("Send")')
        if not send_btn:
            send_btn = await page.query_selector('button:has-text("Gửi")')
        if not send_btn:
            send_btn = await page.query_selector('button[type="submit"]')

        if send_btn:
            await human_click(send_btn, page)
            await asyncio.sleep(random.uniform(1, 2))
            logger.info(f"InMail sent to: {name}")
            return True
        else:
            logger.warning(f"Could not find Send button for {name}")
            await page.keyboard.press("Escape")
            return False

    except Exception as e:
        logger.error(f"Failed to send InMail to {name}: {e}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


async def run_inmail_sender(args: argparse.Namespace, logger: logging.Logger):
    """Main InMail sender loop."""
    # Time window check
    if not is_within_time_window() and not args.test:
        logger.warning(f"Outside allowed time window ({LINKEDIN_START_HOUR}:00-{LINKEDIN_END_HOUR}:00)")
        logger.warning("Use --test flag to override for testing")
        return

    playwright = None

    try:
        # Load queue and sent list
        queue = load_inmail_queue(logger)
        sent = load_sent_inmails(logger)

        # Filter out already-sent
        pending = [item for item in queue if item.get("profile_url") not in sent]
        logger.info(f"Pending InMails: {len(pending)}")

        if not pending:
            logger.warning("No pending InMails to send")
            return

        # Connect to Chrome
        playwright, browser = await connect_to_chrome(logger)

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
            logger.info(f"Test mode: processing {limit} InMails")

        to_process = pending[:limit]

        # Process each InMail
        sent_count = 0
        failed_count = 0

        for i, lead in enumerate(to_process):
            if sent_count >= args.limit:
                logger.info(f"Reached daily limit of {args.limit} InMails")
                break

            profile_url = lead.get("profile_url", "")
            success = await send_inmail(page, lead, logger, dry_run=args.dry_run)

            if success:
                sent_count += 1
                save_sent_inmail(profile_url, logger, dry_run=args.dry_run)
                update_lead_status(profile_url, "inmail_sent", "inmail_sent", logger)
                remove_from_queue(profile_url, logger)
            else:
                failed_count += 1

            logger.info(f"Progress: {i+1}/{len(to_process)} | Sent: {sent_count} | Failed: {failed_count}")

            # Random delay between InMails
            if not args.dry_run and i < len(to_process) - 1:
                delay = random_delay(90, 300)  # 1.5-5 min between InMails
                logger.info(f"Waiting {delay:.1f}s before next InMail...")
                await asyncio.sleep(delay)

        # Summary
        logger.info("=" * 50)
        logger.info(f"Session complete: {sent_count} sent, {failed_count} failed")
        if sent_count + failed_count > 0:
            logger.info(f"Success rate: {sent_count/(sent_count+failed_count)*100:.1f}%")

    except Exception as e:
        logger.error(f"InMail sender error: {e}")
        raise
    finally:
        if playwright:
            await playwright.stop()


def main():
    parser = argparse.ArgumentParser(description="LinkedIn InMail Sender")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without sending")
    parser.add_argument("--limit", type=int, default=SALES_NAV_DAILY_INMAIL_MAX,
                        help=f"Daily limit (default: {SALES_NAV_DAILY_INMAIL_MAX})")
    parser.add_argument("--test", type=int, metavar="N", help="Test mode: only process first N InMails")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("LinkedIn InMail Sender starting...")
    logger.info(f"Config: limit={args.limit}, dry_run={args.dry_run}, test={args.test}")

    try:
        asyncio.run(run_inmail_sender(args, logger))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
