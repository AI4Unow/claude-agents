#!/usr/bin/env python3
"""
Facebook Video Discovery via CDP.

Scrapes video/reel URLs from ProCaffeGroup Facebook page using Chrome DevTools Protocol.
Compares with already-downloaded videos to find missing ones.

Usage:
    # First, launch Chrome with CDP:
    ./fb-chrome-launcher.sh

    # Then run discovery:
    python3 fb-video-discovery.py                  # Discover and compare
    python3 fb-video-discovery.py --download       # Download missing videos
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from config import (
    FB_PAGE_URL,
    FB_CDP_PORT,
    FB_VIDEO_IDS_FILE,
    DATA_DIR,
    PROJECT_DIR,
)

# Directory where FB videos were downloaded
FB_DOWNLOADED_DIR = PROJECT_DIR / "exports" / "tiktok" / "processed"


def get_downloaded_fb_ids() -> set:
    """Get FB video IDs from already-downloaded folders."""
    ids = set()

    if not FB_DOWNLOADED_DIR.exists():
        return ids

    # Pattern: 20251216-{FB_ID} or direct FB ID
    for folder in FB_DOWNLOADED_DIR.iterdir():
        if folder.is_dir():
            name = folder.name
            # Extract FB ID from folder name
            if "-" in name and name.split("-")[0].startswith("2025"):
                # Format: 20251216-1180293703802255
                parts = name.split("-", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    ids.add(parts[1])
            elif name.isdigit():
                ids.add(name)

    return ids


async def scrape_fb_video_urls() -> list:
    """Scrape video URLs from ProCaffe FB page via CDP."""
    cdp_url = f"http://127.0.0.1:{FB_CDP_PORT}"
    print(f"Connecting to Chrome via CDP at {cdp_url}")

    videos = []

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()

            # Navigate to videos/reels section
            videos_url = f"{FB_PAGE_URL}/videos"
            print(f"Loading: {videos_url}")
            await page.goto(videos_url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)

            # Scroll to load more videos
            print("Scrolling to load all videos...")
            last_count = 0
            scroll_attempts = 0
            max_scrolls = 20

            while scroll_attempts < max_scrolls:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # Get current video count
                content = await page.content()
                current_urls = extract_video_ids(content)

                if len(current_urls) == last_count:
                    scroll_attempts += 1
                    if scroll_attempts >= 3:  # No new content after 3 scrolls
                        break
                else:
                    scroll_attempts = 0
                    last_count = len(current_urls)

                print(f"  Found {len(current_urls)} videos so far...")

            # Final extraction
            content = await page.content()
            videos = extract_video_ids(content)

            await page.close()

        except Exception as e:
            print(f"ERROR: Failed to connect via CDP: {e}")
            print("Make sure Chrome is running with:")
            print("  ./fb-chrome-launcher.sh")
            return []

    return videos


def extract_video_ids(html: str) -> list:
    """Extract video IDs from FB page HTML."""
    videos = []
    seen_ids = set()

    # Patterns for FB video URLs
    patterns = [
        r'/videos/(\d+)',
        r'/reel/(\d+)',
        r'video_id["\s:=]+(\d{10,})',
        r'/watch/\?v=(\d+)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, html):
            video_id = match.group(1)
            if video_id not in seen_ids and len(video_id) >= 10:
                seen_ids.add(video_id)
                videos.append({
                    "id": video_id,
                    "url": f"https://www.facebook.com/watch/?v={video_id}"
                })

    return videos


def download_video(video_id: str, output_dir: Path) -> bool:
    """Download FB video using yt-dlp."""
    url = f"https://www.facebook.com/watch/?v={video_id}"
    output_file = output_dir / f"{video_id}.mp4"

    if output_file.exists():
        print(f"  [SKIP] Already exists: {video_id}")
        return True

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "chrome",
            "-o", str(output_file),
            "--no-playlist",
            url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0 and output_file.exists():
            print(f"  [OK] Downloaded: {video_id}")
            return True
        else:
            print(f"  [FAIL] {video_id}: {result.stderr[:100] if result.stderr else 'Unknown error'}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {video_id}")
        return False
    except Exception as e:
        print(f"  [ERROR] {video_id}: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Facebook Video Discovery via CDP")
    parser.add_argument("--download", action="store_true", help="Download missing videos")
    parser.add_argument("--from-cache", action="store_true", help="Use cached video list")
    args = parser.parse_args()

    print("=" * 60)
    print("Facebook Video Discovery")
    print("=" * 60)

    # Get downloaded IDs
    downloaded_ids = get_downloaded_fb_ids()
    print(f"\nAlready downloaded: {len(downloaded_ids)} videos")

    # Get all video IDs from FB page
    if args.from_cache and FB_VIDEO_IDS_FILE.exists():
        print(f"Loading from cache: {FB_VIDEO_IDS_FILE}")
        with open(FB_VIDEO_IDS_FILE, "r") as f:
            data = json.load(f)
            all_videos = data.get("videos", [])
    else:
        all_videos = await scrape_fb_video_urls()

        # Save to cache
        if all_videos:
            FB_VIDEO_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(FB_VIDEO_IDS_FILE, "w") as f:
                json.dump({
                    "videos": all_videos,
                    "scrapedAt": datetime.now().isoformat(),
                    "count": len(all_videos)
                }, f, indent=2)
            print(f"Saved {len(all_videos)} videos to {FB_VIDEO_IDS_FILE}")

            # Also save in apify-output format for orchestrator compatibility
            apify_output_file = DATA_DIR / "apify-output.json"
            with open(apify_output_file, "w") as f:
                json.dump(all_videos, f, indent=2)
            print(f"Saved apify-output.json for orchestrator")

    print(f"Total videos on FB page: {len(all_videos)}")

    # Find missing videos
    all_ids = {v["id"] for v in all_videos}
    missing_ids = all_ids - downloaded_ids

    print(f"\nMissing videos: {len(missing_ids)}")

    if missing_ids:
        print("\nMissing video IDs:")
        for vid in sorted(missing_ids):
            print(f"  - {vid}")

        if args.download:
            print(f"\nDownloading {len(missing_ids)} missing videos...")
            output_dir = PROJECT_DIR / "exports" / "fb" / "videos"

            success = 0
            for vid in missing_ids:
                if download_video(vid, output_dir):
                    success += 1

            print(f"\nDownloaded: {success}/{len(missing_ids)}")
    else:
        print("\nAll videos already downloaded!")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Downloaded: {len(downloaded_ids)}")
    print(f"On FB page: {len(all_ids)}")
    print(f"Missing: {len(missing_ids)}")


if __name__ == "__main__":
    asyncio.run(main())
