#!/usr/bin/env python3
"""
TikTok Profile Video Scraper
Downloads all videos from a TikTok profile using yt-dlp
"""

import re
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

from config import EXPORTS_DIR, PROJECT_DIR
from utils import setup_logger, load_tracking_file, save_to_tracking_file, is_valid_video

# Output directories
RAW_DIR = EXPORTS_DIR / "raw"
COOKIES_FILE = PROJECT_DIR / "cookies.txt"
TRACKING_FILE = "scraped-tiktok-videos.txt"

# Use bundled yt-dlp binary with curl_cffi support
YTDLP_BINARY = PROJECT_DIR / "yt-dlp_macos"

# Username validation pattern (TikTok usernames: alphanumeric, dots, underscores)
USERNAME_PATTERN = re.compile(r'^@?[a-zA-Z0-9._]{2,24}$')

# Subprocess timeout (10 minutes for large profiles)
SUBPROCESS_TIMEOUT = 600

logger = setup_logger("tiktok-scraper", "tiktok-scraper.log")


def validate_username(username: str) -> str:
    """Validate and normalize TikTok username. Raises ValueError if invalid."""
    if not USERNAME_PATTERN.match(username):
        raise ValueError(f"Invalid TikTok username: {username}")
    # Normalize: ensure @ prefix
    return username if username.startswith("@") else f"@{username}"


def scrape_profile(username: str, limit: int = 0) -> list[str]:
    """Download all videos from a TikTok profile."""

    # Validate username to prevent command injection
    username = validate_username(username)
    profile_name = username.replace("@", "")

    # Ensure raw directory exists
    profile_dir = RAW_DIR / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Output template: {profile}/{upload_date}_{id}/video.mp4
    output_template = str(profile_dir / "%(upload_date)s_%(id)s/video.%(ext)s")

    # Use bundled binary or fallback to system yt-dlp
    ytdlp_cmd = str(YTDLP_BINARY) if YTDLP_BINARY.exists() else "yt-dlp"

    # Build yt-dlp command
    cmd = [
        ytdlp_cmd,
        f"https://www.tiktok.com/{username}",
        "-o", output_template,
        "--write-info-json",  # Save metadata
        "--no-overwrites",    # Skip existing
    ]

    # Add impersonation for TikTok anti-bot protection
    if YTDLP_BINARY.exists():
        cmd.extend(["--impersonate", "chrome"])

    # Add cookies if available
    if COOKIES_FILE.exists():
        cmd.extend(["--cookies", str(COOKIES_FILE)])
        print(f"Using cookies from: {COOKIES_FILE}")
    else:
        cmd.append("--cookies-from-browser")
        cmd.append("chrome")
        print("Using cookies from Chrome browser")

    # Add limit if specified
    if limit > 0:
        cmd.extend(["--playlist-end", str(limit)])

    logger.info(f"Scraping {username}...")
    logger.info(f"Output: {profile_dir}")

    # Run yt-dlp with timeout
    try:
        result = subprocess.run(cmd, capture_output=False, timeout=SUBPROCESS_TIMEOUT)
        if result.returncode != 0:
            logger.warning(f"yt-dlp exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        logger.error(f"yt-dlp timed out after {SUBPROCESS_TIMEOUT}s")
        return []
    except FileNotFoundError:
        logger.error("yt-dlp not found. Install with: pip install yt-dlp")
        return []

    # Find downloaded videos (validate each file)
    downloaded = []
    already_tracked = load_tracking_file(TRACKING_FILE)

    for video_dir in profile_dir.iterdir():
        if video_dir.is_dir():
            video_file = video_dir / "video.mp4"
            if video_file.exists() and is_valid_video(video_file):
                if video_dir.name not in already_tracked:
                    save_to_tracking_file(TRACKING_FILE, video_dir.name)
                downloaded.append(video_dir.name)

    return downloaded


def main():
    parser = argparse.ArgumentParser(description="Scrape TikTok profile videos")
    parser.add_argument("username", help="TikTok username (e.g., @procaffe)")
    parser.add_argument("--limit", type=int, default=0, help="Max videos to download (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Show command without running")
    args = parser.parse_args()

    # Validate and normalize username
    try:
        username = validate_username(args.username)
    except ValueError as e:
        logger.error(str(e))
        return

    print("=" * 50)
    print("  TikTok Profile Scraper")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print()

    # Check already scraped
    already_scraped = load_tracking_file(TRACKING_FILE)
    print(f"Previously scraped: {len(already_scraped)} videos")

    if args.dry_run:
        print(f"\nDRY RUN: Would scrape {username}")
        print(f"Limit: {args.limit if args.limit > 0 else 'all'}")
        return

    # Scrape
    downloaded = scrape_profile(username, args.limit)

    print()
    print("=" * 50)
    print(f"Downloaded: {len(downloaded)} videos")
    print("=" * 50)


if __name__ == "__main__":
    main()
