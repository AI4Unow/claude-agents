#!/usr/bin/env python3
"""
Publer Schedule Clearer
Removes all scheduled posts from Publer.
"""

import os
import sys
import argparse
import requests
import time
from datetime import datetime

from config import PUBLER_API_BASE as API_BASE, RATE_LIMIT_DELAY

API_KEY = os.environ.get("PUBLER_API_KEY")
WORKSPACE_ID = os.environ.get("PUBLER_WORKSPACE_ID")


def get_headers():
    return {
        "Authorization": f"Bearer-API {API_KEY}",
        "Publer-Workspace-Id": WORKSPACE_ID
    }


def validate_env():
    if not API_KEY or not WORKSPACE_ID:
        print("ERROR: Missing PUBLER_API_KEY or PUBLER_WORKSPACE_ID")
        return False
    return True


def fetch_scheduled_posts() -> list:
    """Fetch all scheduled posts with pagination."""
    all_posts = []
    page = 1

    while True:
        print(f"  Fetching page {page}...")
        response = requests.get(
            f"{API_BASE}/posts",
            headers=get_headers(),
            params={"state": "scheduled", "limit": 50, "page": page},
            timeout=30
        )

        if response.status_code != 200:
            print(f"  Error: {response.status_code} - {response.text}")
            break

        data = response.json()
        posts = data if isinstance(data, list) else data.get("posts", [])

        if not posts:
            break

        all_posts.extend(posts)
        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_posts


def delete_posts(post_ids: list, dry_run: bool = True) -> int:
    """Delete posts in batches of 20."""
    if dry_run:
        print(f"  DRY RUN: Would delete {len(post_ids)} posts")
        return 0

    deleted = 0
    batch_size = 20

    for i in range(0, len(post_ids), batch_size):
        batch = post_ids[i:i+batch_size]
        params = "&".join([f"post_ids[]={pid}" for pid in batch])
        url = f"{API_BASE}/posts?{params}"

        print(f"  Deleting batch {i//batch_size + 1} ({len(batch)} posts)...")

        response = requests.delete(url, headers=get_headers(), timeout=30)

        if response.status_code == 200:
            deleted += len(batch)
        else:
            print(f"  Error: {response.status_code} - {response.text}")

        time.sleep(RATE_LIMIT_DELAY)

    return deleted


def main():
    parser = argparse.ArgumentParser(description="Clear Publer scheduled posts")
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete (default: dry-run)")
    args = parser.parse_args()

    if not validate_env():
        sys.exit(1)

    print("=" * 50)
    print("  Publer Schedule Clearer")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print()

    print("Fetching scheduled posts...")
    posts = fetch_scheduled_posts()
    print(f"Found {len(posts)} scheduled posts")
    print()

    if not posts:
        print("No posts to delete.")
        return

    post_ids = [p.get("id") for p in posts if p.get("id")]

    print("Posts to delete:")
    for i, post in enumerate(posts[:10]):
        scheduled = post.get("scheduled_at", "unknown")
        text = (post.get("text") or "")[:40]
        print(f"  {i+1}. {scheduled} - {text}...")
    if len(posts) > 10:
        print(f"  ... and {len(posts) - 10} more")
    print()

    if args.execute:
        print("Deleting posts...")
        deleted = delete_posts(post_ids, dry_run=False)
        print(f"\nDeleted {deleted} posts")
    else:
        delete_posts(post_ids, dry_run=True)
        print("\nRun with --execute to delete posts")


if __name__ == "__main__":
    main()
