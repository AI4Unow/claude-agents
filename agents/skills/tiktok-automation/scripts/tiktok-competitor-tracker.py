#!/usr/bin/env python3
"""
TikTok Competitor Tracker using Apify

Fetches competitor TikTok profile data:
- Followers, following, likes
- Recent videos with engagement
- Top performing content

Usage:
    python tiktok-competitor-tracker.py              # Track all competitors
    python tiktok-competitor-tracker.py --profile @cubesasia  # Single profile
"""

import os
import sys
import json
import argparse
import requests
import time
from pathlib import Path
from datetime import datetime

from config import (
    PROJECT_DIR,
    DEFAULT_TIMEOUT,
)
from utils import setup_logger

# Apify configuration
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
APIFY_ACTOR = "clockworks~free-tiktok-scraper"
APIFY_API_BASE = "https://api.apify.com/v2"

# Paths
DATA_DIR = PROJECT_DIR / "data"
REPORTS_DIR = PROJECT_DIR / "plans" / "reports"
COMPETITORS_FILE = DATA_DIR / "competitors.json"

logger = setup_logger("tiktok-tracker", "tiktok-tracker.log")


def validate_env_vars() -> bool:
    """Validate required environment variables."""
    if not APIFY_TOKEN:
        print("ERROR: Missing APIFY_TOKEN")
        print("Get your token at: https://console.apify.com/account/integrations")
        print("Add to .env: APIFY_TOKEN=your_token_here")
        return False
    return True


def load_competitors() -> list:
    """Load competitors from JSON file."""
    if not COMPETITORS_FILE.exists():
        print(f"ERROR: {COMPETITORS_FILE} not found")
        return []

    with open(COMPETITORS_FILE) as f:
        data = json.load(f)

    # Filter only those with TikTok
    return [c for c in data.get("competitors", []) if c.get("has_tiktok")]


def run_apify_scraper(profiles: list[str]) -> dict:
    """Run Apify TikTok scraper for given profiles."""
    print(f"  Starting Apify scraper for {len(profiles)} profiles...")

    # Prepare input
    run_input = {
        "profiles": profiles,
        "resultsPerPage": 10,  # Get last 10 videos per profile
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }

    # Start the actor run
    try:
        response = requests.post(
            f"{APIFY_API_BASE}/acts/{APIFY_ACTOR}/runs",
            params={"token": APIFY_TOKEN},
            json=run_input,
            timeout=DEFAULT_TIMEOUT
        )

        if response.status_code != 201:
            print(f"  ERROR: Failed to start actor: {response.status_code}")
            print(f"  {response.text}")
            return {}

        run_data = response.json()
        run_id = run_data["data"]["id"]
        print(f"  Run started: {run_id}")

        # Poll for completion
        max_wait = 120  # 2 minutes
        waited = 0
        while waited < max_wait:
            status_response = requests.get(
                f"{APIFY_API_BASE}/actor-runs/{run_id}",
                params={"token": APIFY_TOKEN},
                timeout=DEFAULT_TIMEOUT
            )

            if status_response.status_code == 200:
                status = status_response.json()["data"]["status"]
                if status == "SUCCEEDED":
                    print("  ✓ Scraping completed")
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    print(f"  ✗ Run failed: {status}")
                    return {}

            time.sleep(5)
            waited += 5
            print(f"  Waiting... ({waited}s)")

        # Get results from dataset
        dataset_id = run_data["data"]["defaultDatasetId"]
        results_response = requests.get(
            f"{APIFY_API_BASE}/datasets/{dataset_id}/items",
            params={"token": APIFY_TOKEN},
            timeout=DEFAULT_TIMEOUT
        )

        if results_response.status_code == 200:
            return results_response.json()
        else:
            print(f"  ERROR: Failed to get results: {results_response.status_code}")
            return {}

    except Exception as e:
        print(f"  ERROR: {e}")
        return {}


def parse_profile_data(raw_data: list) -> dict:
    """Parse Apify results into structured data."""
    profiles = {}

    for item in raw_data:
        username = item.get("authorMeta", {}).get("name", "unknown")

        if username not in profiles:
            author = item.get("authorMeta", {})
            profiles[username] = {
                "username": username,
                "nickname": author.get("nickName", ""),
                "followers": author.get("fans", 0),
                "following": author.get("following", 0),
                "likes": author.get("heart", 0),
                "videos": author.get("video", 0),
                "verified": author.get("verified", False),
                "bio": author.get("signature", ""),
                "recent_videos": []
            }

        # Add video data
        video = {
            "id": item.get("id", ""),
            "desc": item.get("text", "")[:100],
            "views": item.get("playCount", 0),
            "likes": item.get("diggCount", 0),
            "comments": item.get("commentCount", 0),
            "shares": item.get("shareCount", 0),
            "created": item.get("createTimeISO", ""),
            "hashtags": [h.get("name", "") for h in item.get("hashtags", [])]
        }
        profiles[username]["recent_videos"].append(video)

    return profiles


def calculate_engagement_rate(profile: dict) -> float:
    """Calculate average engagement rate for profile."""
    videos = profile.get("recent_videos", [])
    if not videos:
        return 0.0

    followers = profile.get("followers", 1)
    total_engagement = sum(
        v.get("likes", 0) + v.get("comments", 0) + v.get("shares", 0)
        for v in videos
    )
    avg_engagement = total_engagement / len(videos)
    return round((avg_engagement / followers) * 100, 2) if followers > 0 else 0


def generate_report(profiles: dict) -> str:
    """Generate markdown report."""
    report = f"""# TikTok Competitor Analysis Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Profiles Analyzed:** {len(profiles)}

---

## 📊 Profile Overview

| Profile | Followers | Following | Total Likes | Videos | Engagement Rate |
|---------|-----------|-----------|-------------|--------|-----------------|
"""

    for username, data in profiles.items():
        eng_rate = calculate_engagement_rate(data)
        report += f"| @{username} | {data['followers']:,} | {data['following']:,} | {data['likes']:,} | {data['videos']} | {eng_rate}% |\n"

    report += "\n---\n\n## 🎬 Recent Top Videos\n\n"

    for username, data in profiles.items():
        report += f"### @{username}\n\n"

        videos = sorted(data["recent_videos"], key=lambda x: x.get("views", 0), reverse=True)[:5]

        if videos:
            report += "| Video | Views | Likes | Comments | Hashtags |\n"
            report += "|-------|-------|-------|----------|----------|\n"

            for v in videos:
                desc = v["desc"][:40] + "..." if len(v["desc"]) > 40 else v["desc"]
                hashtags = ", ".join(v["hashtags"][:3]) if v["hashtags"] else "-"
                report += f"| {desc} | {v['views']:,} | {v['likes']:,} | {v['comments']:,} | {hashtags} |\n"
        else:
            report += "*No recent videos found*\n"

        report += "\n"

    report += "---\n\n## 🏷️ Popular Hashtags Used\n\n"

    # Aggregate all hashtags
    all_hashtags = {}
    for data in profiles.values():
        for video in data["recent_videos"]:
            for tag in video.get("hashtags", []):
                all_hashtags[tag] = all_hashtags.get(tag, 0) + 1

    if all_hashtags:
        sorted_tags = sorted(all_hashtags.items(), key=lambda x: x[1], reverse=True)[:15]
        report += "| Hashtag | Usage Count |\n"
        report += "|---------|-------------|\n"
        for tag, count in sorted_tags:
            report += f"| #{tag} | {count} |\n"
    else:
        report += "*No hashtags found*\n"

    report += "\n---\n\n## 💡 Insights\n\n"
    report += "1. Study top-performing videos for content ideas\n"
    report += "2. Use popular hashtags in your posts\n"
    report += "3. Compare engagement rates to benchmark performance\n"

    return report


def main():
    parser = argparse.ArgumentParser(description="Track TikTok competitors using Apify")
    parser.add_argument("--profile", type=str, help="Single profile to track (e.g., @cubesasia)")
    parser.add_argument("--output", type=str, help="Custom output path")
    args = parser.parse_args()

    if not validate_env_vars():
        sys.exit(1)

    print("═" * 50)
    print("  TikTok Competitor Tracker (Apify)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 50)
    print()

    # Get profiles to track
    if args.profile:
        profiles = [args.profile.lstrip("@")]
        print(f"Tracking single profile: @{profiles[0]}")
    else:
        competitors = load_competitors()
        if not competitors:
            print("No competitors found with TikTok accounts")
            sys.exit(1)

        profiles = [c["tiktok"].lstrip("@") for c in competitors]
        print(f"Tracking {len(profiles)} competitors:")
        for p in profiles:
            print(f"  - @{p}")

    print()

    # Run scraper
    raw_data = run_apify_scraper(profiles)

    if not raw_data:
        print("No data retrieved")
        sys.exit(1)

    print(f"  Retrieved {len(raw_data)} items")
    print()

    # Parse data
    parsed = parse_profile_data(raw_data)
    print(f"Parsed {len(parsed)} profiles")

    # Save raw data
    raw_file = DATA_DIR / "competitor-tiktok-data.json"
    with open(raw_file, "w") as f:
        json.dump({"updated": datetime.now().isoformat(), "profiles": parsed}, f, indent=2)
    print(f"✓ Raw data saved: {raw_file}")

    # Generate report
    report = generate_report(parsed)

    if args.output:
        output_path = Path(args.output)
    else:
        date_str = datetime.now().strftime("%y%m%d")
        output_path = REPORTS_DIR / f"competitor-tiktok-{date_str}.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"✓ Report saved: {output_path}")

    print()
    print("Preview:")
    print("-" * 40)
    lines = report.split("\n")[:25]
    print("\n".join(lines))
    if len(report.split("\n")) > 25:
        print("...")


if __name__ == "__main__":
    main()
