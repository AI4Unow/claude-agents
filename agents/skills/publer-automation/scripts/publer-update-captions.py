#!/usr/bin/env python3
"""
Publer Caption Updater

Updates draft posts on Publer with new captions from local caption.txt files.
Uses optimized hashtags from competitor analysis.

Usage:
    python publer-update-captions.py           # Update all drafts
    python publer-update-captions.py --dry-run # List drafts without updating
    python publer-update-captions.py --limit 5 # Update first 5 drafts only
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

from config import (
    PUBLER_API_BASE as API_BASE,
    EXPORTS_DIR,
    DATA_DIR,
    RATE_LIMIT_DELAY,
    DEFAULT_TIMEOUT,
)
from utils import setup_logger

# Publer API configuration from environment
API_KEY = os.environ.get("PUBLER_API_KEY")
WORKSPACE_ID = os.environ.get("PUBLER_WORKSPACE_ID")
TIKTOK_ACCOUNT_ID = os.environ.get("PUBLER_TIKTOK_ACCOUNT_ID")

logger = setup_logger("publer-update", "publer-update.log")


def validate_env_vars() -> bool:
    """Validate required environment variables are set."""
    missing = []
    if not API_KEY:
        missing.append("PUBLER_API_KEY")
    if not WORKSPACE_ID:
        missing.append("PUBLER_WORKSPACE_ID")
    if not TIKTOK_ACCOUNT_ID:
        missing.append("PUBLER_TIKTOK_ACCOUNT_ID")

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        return False
    return True


def get_headers():
    """Get API headers for Publer requests."""
    return {
        "Authorization": f"Bearer-API {API_KEY}",
        "Publer-Workspace-Id": WORKSPACE_ID
    }


def get_draft_posts() -> list:
    """Get all draft posts from Publer for TikTok account."""
    print("  Fetching draft posts from Publer...")

    try:
        response = requests.get(
            f"{API_BASE}/posts",
            headers=get_headers(),
            params={
                "state": "draft",
                "account_ids[]": TIKTOK_ACCOUNT_ID
            },
            timeout=DEFAULT_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            # API returns {"posts": [...], "total": N}
            posts = data.get("posts", []) if isinstance(data, dict) else data
            print(f"  ✓ Found {len(posts)} draft posts")
            return posts
        else:
            print(f"  ✗ Failed to fetch posts: {response.status_code}")
            print(f"    {response.text[:200]}")
            return []

    except Exception as e:
        print(f"  ✗ Error fetching posts: {e}")
        return []


def update_post_caption(post_id: str, caption: str) -> bool:
    """Update post caption via Publer API."""
    try:
        # Publer uses PUT for updates on posts
        response = requests.put(
            f"{API_BASE}/posts/{post_id}",
            headers={**get_headers(), "Content-Type": "application/json"},
            json={
                "networks": {
                    "tiktok": {
                        "text": caption
                    }
                }
            },
            timeout=DEFAULT_TIMEOUT
        )

        if response.status_code == 200:
            return True
        else:
            print(f"    ✗ Update failed: {response.status_code} - {response.text[:100]}")
            return False

    except Exception as e:
        print(f"    ✗ Update error: {e}")
        return False


def load_local_captions() -> dict:
    """Load all caption.txt files from processed videos.

    Returns:
        dict: {video_id: caption_text}
    """
    captions = {}
    processed_dir = EXPORTS_DIR / "processed"

    if not processed_dir.exists():
        print("  Warning: Processed directory not found")
        return captions

    for video_dir in processed_dir.iterdir():
        if not video_dir.is_dir():
            continue

        caption_file = video_dir / "caption.txt"
        if caption_file.exists():
            # Extract video ID from folder name (format: YYYYMMDD-{video_id})
            folder_name = video_dir.name
            if "-" in folder_name:
                video_id = folder_name.split("-", 1)[-1]
            else:
                video_id = folder_name

            caption = caption_file.read_text().strip()
            if caption:
                captions[video_id] = caption

    print(f"  ✓ Loaded {len(captions)} local captions")
    return captions


def extract_video_id_from_post(post: dict) -> str | None:
    """Extract video ID from Publer post text.

    Since Publer doesn't store our original video IDs,
    we look for Facebook video ID patterns in the text.
    Facebook video IDs are typically 15-20 digit numbers.
    """
    import re

    text = post.get("text", "")

    # Look for video ID patterns (15-20 digit numbers)
    matches = re.findall(r'\b(\d{15,20})\b', text)
    if matches:
        return matches[0]

    return None


def find_matching_caption(post: dict, captions: dict) -> tuple[str | None, str | None]:
    """Find matching local caption for a Publer post.

    Returns:
        tuple: (video_id, caption) or (None, None)
    """
    # Try extracting video ID from post text
    video_id = extract_video_id_from_post(post)
    if video_id and video_id in captions:
        return video_id, captions[video_id]

    # Fallback: check if current text starts with same hook as any local caption
    current_text = post.get("text", "")[:50].lower()

    for vid, caption in captions.items():
        caption_start = caption[:50].lower()
        # If same opening hook, likely a match
        if current_text and caption_start and current_text[:30] == caption_start[:30]:
            return vid, caption

    return None, None


def main():
    parser = argparse.ArgumentParser(description="Update Publer drafts with new captions")
    parser.add_argument("--dry-run", action="store_true", help="List drafts without updating")
    parser.add_argument("--limit", type=int, default=0, help="Limit posts to update (0=all)")
    parser.add_argument("--force", action="store_true", help="Update even if caption seems same")
    args = parser.parse_args()

    if not validate_env_vars():
        sys.exit(1)

    print("═" * 50)
    print("  Publer Caption Updater")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 50)
    print()

    if args.dry_run:
        print("DRY RUN - No updates will be made")
        print()

    # Load local captions
    captions = load_local_captions()
    if not captions:
        print("No local captions found. Run caption-generator.py first.")
        sys.exit(1)

    print()

    # Get draft posts
    posts = get_draft_posts()
    if not posts:
        print("No draft posts found in Publer.")
        return

    print()

    # Process posts
    if args.limit > 0:
        posts = posts[:args.limit]

    updated = 0
    skipped = 0
    failed = 0
    no_match = 0

    for i, post in enumerate(posts):
        post_id = post.get("id", "unknown")
        current_text = post.get("text", "")[:40]
        print(f"[{i+1}/{len(posts)}] Post: {post_id}")
        print(f"  Current: {current_text}...")

        # Find matching caption
        video_id, new_caption = find_matching_caption(post, captions)

        if not new_caption:
            print(f"  ✗ No matching local caption found")
            no_match += 1
            continue

        if video_id:
            print(f"  Matched video: {video_id}")
        print(f"  New caption: {new_caption[:60]}...")

        if args.dry_run:
            print(f"  [DRY RUN] Would update caption")
            updated += 1
        else:
            if update_post_caption(post_id, new_caption):
                print(f"  ✓ Updated")
                updated += 1
            else:
                failed += 1

        time.sleep(RATE_LIMIT_DELAY)
        print()

    # Summary
    print("═" * 50)
    print("Update Summary:")
    print(f"  Updated:  {updated}")
    print(f"  Failed:   {failed}")
    print(f"  No match: {no_match}")
    print(f"  Skipped:  {skipped}")
    print("═" * 50)


if __name__ == "__main__":
    main()
