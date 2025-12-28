#!/usr/bin/env python3
"""
TikTok Firebase Sync - Manages TikTok accounts in Firestore.

Collections:
- tiktok_accounts: All tracked TikTok accounts
- tiktok_likes: Like history with timestamps

Usage:
    python3 tiktok-firebase-sync.py sync-following         # Sync following list to Firebase
    python3 tiktok-firebase-sync.py sync-followers         # Sync followers list to Firebase
    python3 tiktok-firebase-sync.py sync-competitor <user> # Sync competitor's followers
    python3 tiktok-firebase-sync.py get-unliked [--limit N]# Get accounts not yet liked
    python3 tiktok-firebase-sync.py mark-liked <username>  # Mark account as liked
    python3 tiktok-firebase-sync.py stats                  # Show database statistics
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from config import (
    FIREBASE_SERVICE_ACCOUNT,
    FIREBASE_PROJECT_ID,
    TIKTOK_CDP_PORT,
    TIKTOK_COMPETITORS,
)

# Firebase collections
COLLECTION_ACCOUNTS = "tiktok_accounts"
COLLECTION_LIKES = "tiktok_likes"

# Account sources
SOURCE_FOLLOWING = "following"
SOURCE_FOLLOWERS = "followers"
SOURCE_COMPETITOR = "competitor"

# Global Firebase app
_app = None
_db = None


def init_firebase():
    """Initialize Firebase Admin SDK."""
    global _app, _db
    if _app is not None:
        return _db

    if not FIREBASE_SERVICE_ACCOUNT.exists():
        print(f"ERROR: Service account not found: {FIREBASE_SERVICE_ACCOUNT}")
        sys.exit(1)

    cred = credentials.Certificate(str(FIREBASE_SERVICE_ACCOUNT))
    _app = firebase_admin.initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})
    _db = firestore.client()
    return _db


def get_account_ref(username: str):
    """Get Firestore reference for a TikTok account."""
    db = init_firebase()
    return db.collection(COLLECTION_ACCOUNTS).document(username)


def upsert_account(username: str, source: str, source_account: str = None):
    """
    Insert or update a TikTok account in Firestore.
    Returns True if new account, False if updated.
    """
    db = init_firebase()
    ref = get_account_ref(username)
    doc = ref.get()

    now = datetime.now(timezone.utc)

    if doc.exists:
        # Update existing - add source if new
        data = doc.to_dict()
        sources = data.get("sources", [])
        if source not in sources:
            sources.append(source)
        ref.update({
            "sources": sources,
            "updated_at": now,
        })
        return False
    else:
        # Create new account
        ref.set({
            "username": username,
            "sources": [source],
            "source_account": source_account,
            "liked": False,
            "liked_at": None,
            "like_count": 0,
            "created_at": now,
            "updated_at": now,
        })
        return True


def mark_account_liked(username: str):
    """Mark an account as liked in Firestore."""
    db = init_firebase()
    ref = get_account_ref(username)
    doc = ref.get()

    now = datetime.now(timezone.utc)

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
        # Create if not exists
        ref.set({
            "username": username,
            "sources": ["unknown"],
            "source_account": None,
            "liked": True,
            "liked_at": now,
            "like_count": 1,
            "created_at": now,
            "updated_at": now,
        })

    # Also log to likes collection
    db.collection(COLLECTION_LIKES).add({
        "username": username,
        "liked_at": now,
    })


def get_unliked_accounts(limit: int = 100, source: str = None) -> list:
    """Get accounts that haven't been liked yet."""
    db = init_firebase()
    query = db.collection(COLLECTION_ACCOUNTS).where(
        filter=FieldFilter("liked", "==", False)
    )

    if source:
        query = query.where(filter=FieldFilter("sources", "array_contains", source))

    query = query.limit(limit)
    docs = query.stream()

    return [doc.to_dict()["username"] for doc in docs]


def get_all_liked_usernames() -> set:
    """Get set of all liked usernames."""
    db = init_firebase()
    docs = db.collection(COLLECTION_ACCOUNTS).where(
        filter=FieldFilter("liked", "==", True)
    ).stream()

    return {doc.to_dict()["username"] for doc in docs}


def get_stats():
    """Get database statistics."""
    db = init_firebase()

    # Count totals
    all_accounts = list(db.collection(COLLECTION_ACCOUNTS).stream())
    total = len(all_accounts)

    liked = sum(1 for doc in all_accounts if doc.to_dict().get("liked", False))
    unliked = total - liked

    # Count by source
    source_counts = {}
    for doc in all_accounts:
        for source in doc.to_dict().get("sources", []):
            source_counts[source] = source_counts.get(source, 0) + 1

    return {
        "total": total,
        "liked": liked,
        "unliked": unliked,
        "by_source": source_counts,
    }


async def scrape_tiktok_list(username: str, list_type: str = "following") -> list:
    """
    Scrape TikTok following or followers list using Playwright CDP.
    Reuses logic from tiktok-auto-liker.py.
    """
    from playwright.async_api import async_playwright

    cdp_url = f"http://127.0.0.1:{TIKTOK_CDP_PORT}"
    print(f"Connecting to Chrome via CDP at {cdp_url}")

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
        print("Connected to Chrome successfully")

        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts found")
            return []

        page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()

        # Navigate to profile
        await page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)

        # Close any modal overlays
        await page.keyboard.press("Escape")
        await asyncio.sleep(1)

        # Click on Following or Followers count
        selector = f'[data-e2e="{list_type}-count"]'
        clicked = await page.evaluate(f'''
            () => {{
                const el = document.querySelector('{selector}');
                if (el) {{
                    const link = el.closest('a') || el.parentElement;
                    if (link) {{
                        link.click();
                        return true;
                    }}
                }}
                return false;
            }}
        ''')

        if not clicked:
            print(f"Could not find {list_type} link on profile")
            return []

        await asyncio.sleep(3)

        # Scroll to collect usernames
        usernames = set()
        prev_count = 0
        stale_scrolls = 0

        for scroll in range(500):
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

            if len(usernames) == prev_count:
                stale_scrolls += 1
                if stale_scrolls >= 50:
                    print(f"Stopped scrolling at {scroll} (stale)")
                    break
            else:
                stale_scrolls = 0
            prev_count = len(usernames)

            await page.evaluate('''
                const modal = document.querySelector('[class*="DivUserListContainer"]')
                    || document.querySelector('[role="dialog"]');
                if (modal) modal.scrollBy(0, 500);
            ''')
            await asyncio.sleep(0.8)

            if scroll % 20 == 0:
                print(f"Scroll {scroll}: found {len(usernames)} accounts")

        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)

        return list(usernames)

    finally:
        await playwright.stop()


def cmd_sync_following(args):
    """Sync following list to Firebase."""
    print(f"Syncing following list for @{args.username}...")

    usernames = asyncio.run(scrape_tiktok_list(args.username, "following"))
    print(f"Found {len(usernames)} accounts")

    new_count = 0
    for username in usernames:
        is_new = upsert_account(username, SOURCE_FOLLOWING, args.username)
        if is_new:
            new_count += 1

    print(f"Synced: {len(usernames)} total, {new_count} new")


def cmd_sync_followers(args):
    """Sync followers list to Firebase."""
    print(f"Syncing followers list for @{args.username}...")

    usernames = asyncio.run(scrape_tiktok_list(args.username, "followers"))
    print(f"Found {len(usernames)} accounts")

    new_count = 0
    for username in usernames:
        is_new = upsert_account(username, SOURCE_FOLLOWERS, args.username)
        if is_new:
            new_count += 1

    print(f"Synced: {len(usernames)} total, {new_count} new")


def cmd_sync_competitor(args):
    """Sync competitor's followers to Firebase."""
    competitor = args.competitor
    print(f"Syncing followers of competitor @{competitor}...")

    usernames = asyncio.run(scrape_tiktok_list(competitor, "followers"))
    print(f"Found {len(usernames)} accounts")

    new_count = 0
    for username in usernames:
        is_new = upsert_account(username, SOURCE_COMPETITOR, competitor)
        if is_new:
            new_count += 1

    print(f"Synced: {len(usernames)} total, {new_count} new")


def cmd_sync_all_competitors(args):
    """Sync all configured competitors' followers."""
    print(f"Syncing {len(TIKTOK_COMPETITORS)} competitors...")

    total_new = 0
    for competitor in TIKTOK_COMPETITORS:
        print(f"\n--- @{competitor} ---")
        usernames = asyncio.run(scrape_tiktok_list(competitor, "followers"))
        print(f"Found {len(usernames)} accounts")

        for username in usernames:
            if upsert_account(username, SOURCE_COMPETITOR, competitor):
                total_new += 1

    print(f"\nTotal new accounts added: {total_new}")


def cmd_get_unliked(args):
    """Get accounts that haven't been liked."""
    accounts = get_unliked_accounts(limit=args.limit, source=args.source)
    print(f"Found {len(accounts)} unliked accounts:")
    for username in accounts:
        print(f"  @{username}")


def cmd_mark_liked(args):
    """Mark an account as liked."""
    mark_account_liked(args.username)
    print(f"Marked @{args.username} as liked")


def cmd_stats(args):
    """Show database statistics."""
    stats = get_stats()
    print(f"TikTok Accounts Database Stats:")
    print(f"  Total accounts: {stats['total']}")
    print(f"  Liked: {stats['liked']}")
    print(f"  Unliked: {stats['unliked']}")
    print(f"\nBy source:")
    for source, count in stats["by_source"].items():
        print(f"  {source}: {count}")


def cmd_import_logs(args):
    """Import liked accounts from log files to Firebase."""
    from config import TIKTOK_AUTO_LIKER_LOG_DIR

    print(f"Importing from log directory: {TIKTOK_AUTO_LIKER_LOG_DIR}")

    if not TIKTOK_AUTO_LIKER_LOG_DIR.exists():
        print("ERROR: Log directory not found")
        return

    liked_accounts = set()
    for log_file in TIKTOK_AUTO_LIKER_LOG_DIR.glob("*.log"):
        if log_file.name.startswith("launchd"):
            continue
        with open(log_file) as f:
            for line in f:
                if "Liked video from @" in line:
                    username = line.split("@")[-1].strip()
                    liked_accounts.add(username)

    print(f"Found {len(liked_accounts)} liked accounts in logs")

    imported = 0
    for username in liked_accounts:
        mark_account_liked(username)
        imported += 1
        if imported % 100 == 0:
            print(f"  Imported {imported}...")

    print(f"Imported {imported} accounts to Firebase")


def main():
    parser = argparse.ArgumentParser(description="TikTok Firebase Sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync-following
    p_following = subparsers.add_parser("sync-following", help="Sync following list")
    p_following.add_argument("--username", default="procaffe26", help="TikTok username")
    p_following.set_defaults(func=cmd_sync_following)

    # sync-followers
    p_followers = subparsers.add_parser("sync-followers", help="Sync followers list")
    p_followers.add_argument("--username", default="procaffe26", help="TikTok username")
    p_followers.set_defaults(func=cmd_sync_followers)

    # sync-competitor
    p_competitor = subparsers.add_parser("sync-competitor", help="Sync competitor's followers")
    p_competitor.add_argument("competitor", help="Competitor username")
    p_competitor.set_defaults(func=cmd_sync_competitor)

    # sync-all-competitors
    p_all = subparsers.add_parser("sync-all-competitors", help="Sync all competitors")
    p_all.set_defaults(func=cmd_sync_all_competitors)

    # get-unliked
    p_unliked = subparsers.add_parser("get-unliked", help="Get unliked accounts")
    p_unliked.add_argument("--limit", type=int, default=100)
    p_unliked.add_argument("--source", help="Filter by source")
    p_unliked.set_defaults(func=cmd_get_unliked)

    # mark-liked
    p_liked = subparsers.add_parser("mark-liked", help="Mark account as liked")
    p_liked.add_argument("username", help="Username to mark")
    p_liked.set_defaults(func=cmd_mark_liked)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show database stats")
    p_stats.set_defaults(func=cmd_stats)

    # import-logs
    p_import = subparsers.add_parser("import-logs", help="Import liked accounts from log files")
    p_import.set_defaults(func=cmd_import_logs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
