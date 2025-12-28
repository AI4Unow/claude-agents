#!/usr/bin/env python3
"""
Check Publer scheduled posts for duplicates
"""

import os
import sys
import requests
from collections import defaultdict

# Load env vars from .env
from pathlib import Path
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key] = value.strip('"').strip("'")

API_KEY = os.environ.get("PUBLER_API_KEY")
WORKSPACE_ID = os.environ.get("PUBLER_WORKSPACE_ID")
TIKTOK_ACCOUNT_ID = os.environ.get("PUBLER_TIKTOK_ACCOUNT_ID")

def get_headers():
    return {
        "Authorization": f"Bearer-API {API_KEY}",
        "Publer-Workspace-Id": WORKSPACE_ID
    }

def list_scheduled_posts():
    """Fetch all scheduled posts from Publer."""
    all_posts = []
    page = 0

    while True:
        url = f"https://app.publer.com/api/v1/posts?state=scheduled&page={page}"
        response = requests.get(url, headers=get_headers(), timeout=30)

        if response.status_code != 200:
            print(f"Error fetching page {page}: {response.status_code}")
            break

        data = response.json()
        posts = data.get("posts", [])

        if not posts:
            break

        all_posts.extend(posts)
        page += 1

        # Safety limit
        if page > 20:
            break

    return all_posts

def analyze_posts(posts):
    """Analyze posts for duplicates."""
    print(f"\n{'='*60}")
    print(f"PUBLER SCHEDULED POSTS ANALYSIS")
    print(f"{'='*60}\n")

    # Filter TikTok posts
    tiktok_posts = []
    for post in posts:
        for acc in post.get("accounts", []):
            if acc.get("id") == TIKTOK_ACCOUNT_ID:
                tiktok_posts.append(post)
                break

    print(f"Total scheduled posts: {len(posts)}")
    print(f"TikTok scheduled posts: {len(tiktok_posts)}\n")

    # Check for duplicate content
    content_map = defaultdict(list)
    media_map = defaultdict(list)

    for post in tiktok_posts:
        # Get text content
        text = post.get("networks", {}).get("tiktok", {}).get("text", "")
        content_map[text].append(post)

        # Get media IDs
        media_list = post.get("networks", {}).get("tiktok", {}).get("media", [])
        for media in media_list:
            media_id = media.get("id")
            if media_id:
                media_map[media_id].append(post)

    # Report duplicates
    print("DUPLICATE ANALYSIS:")
    print("-" * 60)

    duplicate_media_count = 0
    for media_id, post_list in media_map.items():
        if len(post_list) > 1:
            duplicate_media_count += 1
            print(f"\nMedia ID {media_id} appears in {len(post_list)} posts:")
            for p in post_list:
                scheduled_at = p.get("scheduled_at", "N/A")
                post_id = p.get("id", "N/A")
                print(f"  - Post {post_id}: scheduled for {scheduled_at}")

    if duplicate_media_count == 0:
        print("✓ No duplicate media found\n")
    else:
        print(f"\n⚠ Found {duplicate_media_count} duplicate media items\n")

    # Show schedule overview
    print("\nSCHEDULE OVERVIEW:")
    print("-" * 60)
    tiktok_posts_sorted = sorted(tiktok_posts, key=lambda p: p.get("scheduled_at", ""))
    for i, post in enumerate(tiktok_posts_sorted[:10], 1):
        post_id = post.get("id", "N/A")
        scheduled_at = post.get("scheduled_at", "N/A")
        media_count = len(post.get("networks", {}).get("tiktok", {}).get("media", []))
        print(f"{i}. Post {post_id}: {scheduled_at} ({media_count} media)")

    if len(tiktok_posts_sorted) > 10:
        print(f"... and {len(tiktok_posts_sorted) - 10} more posts")

if __name__ == "__main__":
    if not API_KEY or not WORKSPACE_ID or not TIKTOK_ACCOUNT_ID:
        print("ERROR: Missing environment variables")
        print(f"API_KEY: {'set' if API_KEY else 'NOT SET'}")
        print(f"WORKSPACE_ID: {'set' if WORKSPACE_ID else 'NOT SET'}")
        print(f"TIKTOK_ACCOUNT_ID: {'set' if TIKTOK_ACCOUNT_ID else 'NOT SET'}")
        sys.exit(1)

    posts = list_scheduled_posts()
    analyze_posts(posts)
