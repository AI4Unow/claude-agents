#!/usr/bin/env python3
"""
Facebook Content Scraper for ProCaffe.

Scrapes posts, images, videos from ProCaffeGroup Facebook page using Apify.
Downloads media locally for Firebase import.

Usage:
    python3 fb-scrape-content.py                    # Full scrape
    python3 fb-scrape-content.py --max-posts 10     # Limit to 10 posts
    python3 fb-scrape-content.py --skip-media       # Metadata only (no downloads)
    python3 fb-scrape-content.py --dry-run          # Show what would be done

Requirements:
    - APIFY_API_KEY env var or apify CLI authenticated
    - yt-dlp for video downloads
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from config import (
    FB_PAGE_URL,
    FB_EXPORTS_DIR,
    FB_VIDEOS_DIR,
    FB_IMAGES_DIR,
    FB_POSTS_FILE,
    FB_SCRAPE_PROGRESS_FILE,
    FB_APIFY_RAW_FILE,
    DATA_DIR,
    RATE_LIMIT_DELAY,
)

# Apify actor for Facebook scraping (use ~ instead of / in API URL)
APIFY_ACTOR = "apify~facebook-pages-scraper"


def get_apify_token() -> str:
    """Get Apify API token from env."""
    token = os.environ.get("APIFY_API_KEY") or os.environ.get("APIFY_TOKEN")
    if not token:
        print("ERROR: APIFY_API_KEY or APIFY_TOKEN env var required")
        print("Get your token at: https://console.apify.com/account/integrations")
        sys.exit(1)
    return token


def run_apify_scraper(max_posts: int, include_comments: bool = True) -> list:
    """Run Apify Facebook scraper and return posts data."""
    token = get_apify_token()

    # Apify API endpoint
    api_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"

    # Scraper input
    input_data = {
        "startUrls": [{"url": FB_PAGE_URL}],
        "maxPosts": max_posts,
        "maxPostComments": 50 if include_comments else 0,
        "commentsMode": "RANKED_THREADED" if include_comments else "NONE",
        "maxReviews": 0,  # Skip reviews
        "language": "vi-VN",
        "proxy": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]
        }
    }

    print(f"Starting Apify scraper for {FB_PAGE_URL}")
    print(f"  Max posts: {max_posts}")
    print(f"  Comments: {'enabled' if include_comments else 'disabled'}")

    try:
        response = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=input_data,
            timeout=600  # 10 min timeout for large scrapes
        )
        response.raise_for_status()

        posts = response.json()
        print(f"  Scraped {len(posts)} posts")

        # Save raw output
        FB_APIFY_RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FB_APIFY_RAW_FILE, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
        print(f"  Saved raw data to {FB_APIFY_RAW_FILE}")

        return posts

    except requests.RequestException as e:
        print(f"ERROR: Apify request failed: {e}")
        sys.exit(1)


def compute_md5(file_path: Path) -> str:
    """Compute MD5 hash of file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def download_video(url: str, output_dir: Path, progress: dict) -> dict | None:
    """Download video using yt-dlp. Returns media info or None if failed."""
    if url in progress.get("downloadedVideos", []):
        print(f"    [SKIP] Already downloaded: {url[:60]}...")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    temp_file = output_dir / "temp_video.mp4"

    try:
        # Use yt-dlp with cookies from browser
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "chrome",
            "-o", str(temp_file),
            "--no-playlist",
            "--quiet",
            url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0 or not temp_file.exists():
            print(f"    [FAIL] Video download failed: {url[:60]}...")
            return None

        # Rename to MD5 hash
        md5 = compute_md5(temp_file)
        final_path = output_dir / f"{md5}.mp4"

        if final_path.exists():
            temp_file.unlink()
            print(f"    [DUP] Video already exists: {md5}.mp4")
        else:
            temp_file.rename(final_path)
            print(f"    [OK] Video: {md5}.mp4")

        return {
            "type": "video",
            "localPath": str(final_path),
            "md5": md5,
            "originalUrl": url
        }

    except subprocess.TimeoutExpired:
        print(f"    [TIMEOUT] Video download: {url[:60]}...")
        if temp_file.exists():
            temp_file.unlink()
        return None
    except Exception as e:
        print(f"    [ERROR] Video download: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return None


def download_image(url: str, output_dir: Path, progress: dict) -> dict | None:
    """Download image. Returns media info or None if failed."""
    if url in progress.get("downloadedImages", []):
        print(f"    [SKIP] Already downloaded: {url[:60]}...")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()

        # Determine extension from content-type
        content_type = response.headers.get("content-type", "image/jpeg")
        ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]

        # Compute MD5 from content
        content = response.content
        md5 = hashlib.md5(content).hexdigest()

        final_path = output_dir / f"{md5}.{ext}"

        if final_path.exists():
            print(f"    [DUP] Image already exists: {md5}.{ext}")
        else:
            with open(final_path, "wb") as f:
                f.write(content)
            print(f"    [OK] Image: {md5}.{ext}")

        return {
            "type": "image",
            "localPath": str(final_path),
            "md5": md5,
            "originalUrl": url
        }

    except Exception as e:
        print(f"    [ERROR] Image download: {e}")
        return None


def parse_apify_post(raw_post: dict) -> dict:
    """Parse Apify post format to our schema."""
    post_id = raw_post.get("postId") or raw_post.get("id", "")

    # Parse comments
    comments = []
    for comment in raw_post.get("comments", []):
        parsed_comment = {
            "id": comment.get("id", ""),
            "author": {
                "name": comment.get("profileName", ""),
                "fbId": comment.get("profileUrl", "").split("/")[-1] if comment.get("profileUrl") else ""
            },
            "text": comment.get("text", ""),
            "createdAt": comment.get("date", ""),
            "likes": comment.get("likesCount", 0),
            "parentId": None
        }

        # Handle replies
        replies = []
        for reply in comment.get("replies", []):
            replies.append({
                "id": reply.get("id", ""),
                "author": {
                    "name": reply.get("profileName", ""),
                    "fbId": reply.get("profileUrl", "").split("/")[-1] if reply.get("profileUrl") else ""
                },
                "text": reply.get("text", ""),
                "createdAt": reply.get("date", ""),
                "likes": reply.get("likesCount", 0),
                "parentId": parsed_comment["id"]
            })

        parsed_comment["replies"] = replies
        comments.append(parsed_comment)

    # Determine post type
    post_type = "status"
    if raw_post.get("videoUrl"):
        post_type = "video"
    elif raw_post.get("media") or raw_post.get("imageUrl"):
        post_type = "image"

    return {
        "id": post_id,
        "text": raw_post.get("text", ""),
        "publishedAt": raw_post.get("time", ""),
        "type": post_type,
        "stats": {
            "likes": raw_post.get("likes", 0) or raw_post.get("likesCount", 0),
            "shares": raw_post.get("shares", 0) or raw_post.get("sharesCount", 0),
            "commentCount": len(comments)
        },
        "media": [],  # Will be populated after download
        "comments": comments,
        "rawUrls": {
            "video": raw_post.get("videoUrl"),
            "images": raw_post.get("media", []) or ([raw_post.get("imageUrl")] if raw_post.get("imageUrl") else [])
        }
    }


def load_progress() -> dict:
    """Load scrape progress from file."""
    if FB_SCRAPE_PROGRESS_FILE.exists():
        with open(FB_SCRAPE_PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"downloadedVideos": [], "downloadedImages": [], "processedPosts": []}


def save_progress(progress: dict):
    """Save scrape progress to file."""
    FB_SCRAPE_PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FB_SCRAPE_PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Facebook Content Scraper for ProCaffe")
    parser.add_argument("--max-posts", type=int, default=500, help="Max posts to scrape")
    parser.add_argument("--skip-media", action="store_true", help="Skip media downloads")
    parser.add_argument("--no-comments", action="store_true", help="Skip comments")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--from-cache", action="store_true", help="Use cached Apify data")
    args = parser.parse_args()

    print("=" * 60)
    print("Facebook Content Scraper for ProCaffe")
    print("=" * 60)

    progress = load_progress()

    # Step 1: Get posts from Apify or cache
    if args.from_cache and FB_APIFY_RAW_FILE.exists():
        print(f"\nLoading cached data from {FB_APIFY_RAW_FILE}")
        with open(FB_APIFY_RAW_FILE, "r") as f:
            raw_posts = json.load(f)
        print(f"  Loaded {len(raw_posts)} posts")
    else:
        if args.dry_run:
            print("\n[DRY RUN] Would scrape from Apify")
            raw_posts = []
        else:
            raw_posts = run_apify_scraper(args.max_posts, not args.no_comments)

    # Step 2: Parse and download media
    parsed_posts = []

    for i, raw_post in enumerate(raw_posts):
        post = parse_apify_post(raw_post)
        print(f"\n[{i+1}/{len(raw_posts)}] Post: {post['id']}")
        print(f"  Type: {post['type']}, Text: {post['text'][:50]}..." if post['text'] else f"  Type: {post['type']}")

        if args.skip_media or args.dry_run:
            if args.dry_run:
                print("  [DRY RUN] Would download media")
        else:
            # Download video
            if post["rawUrls"]["video"]:
                media = download_video(post["rawUrls"]["video"], FB_VIDEOS_DIR, progress)
                if media:
                    post["media"].append(media)
                    progress["downloadedVideos"].append(post["rawUrls"]["video"])
                time.sleep(RATE_LIMIT_DELAY)

            # Download images
            for img_url in post["rawUrls"]["images"]:
                if img_url:
                    media = download_image(img_url, FB_IMAGES_DIR, progress)
                    if media:
                        post["media"].append(media)
                        progress["downloadedImages"].append(img_url)
                    time.sleep(RATE_LIMIT_DELAY / 2)

        # Remove rawUrls from final output
        del post["rawUrls"]
        parsed_posts.append(post)

        # Save progress periodically
        if (i + 1) % 10 == 0:
            save_progress(progress)

    # Step 3: Save final output
    if not args.dry_run:
        output = {
            "posts": parsed_posts,
            "scrapedAt": datetime.now().isoformat(),
            "totalPosts": len(parsed_posts)
        }

        FB_POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FB_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        save_progress(progress)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Posts scraped: {len(parsed_posts)}")
        print(f"Videos downloaded: {len(progress.get('downloadedVideos', []))}")
        print(f"Images downloaded: {len(progress.get('downloadedImages', []))}")
        print(f"Output: {FB_POSTS_FILE}")
    else:
        print("\n[DRY RUN] No files written")


if __name__ == "__main__":
    main()
