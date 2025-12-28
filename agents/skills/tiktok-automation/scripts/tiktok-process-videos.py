#!/usr/bin/env python3
"""
TikTok Video Processor
Moves raw videos to processed folder structure
"""

import shutil
from pathlib import Path
from datetime import datetime
import argparse

from config import EXPORTS_DIR
from utils import setup_logger, load_tracking_file, save_to_tracking_file

RAW_DIR = EXPORTS_DIR / "raw" / "procaffe"
PROCESSED_DIR = EXPORTS_DIR / "processed"
TRACKING_FILE = "processed-tiktok-videos.txt"

logger = setup_logger("tiktok-processor", "tiktok-processor.log")


def process_videos(dry_run: bool = False) -> int:
    """Move raw videos to processed folder structure."""

    if not RAW_DIR.exists():
        print(f"Raw directory not found: {RAW_DIR}")
        return 0

    # Already processed
    processed = load_tracking_file(TRACKING_FILE)
    print(f"Already processed: {len(processed)} videos")

    count = 0
    for video_dir in sorted(RAW_DIR.iterdir()):
        if not video_dir.is_dir():
            continue

        video_id = video_dir.name
        if video_id in processed:
            continue

        # Source files
        raw_video = video_dir / "video.mp4"
        raw_info = list(video_dir.glob("*.info.json"))

        if not raw_video.exists():
            print(f"  Skip {video_id}: no video.mp4")
            continue

        # Target directory
        target_dir = PROCESSED_DIR / video_id
        target_video = target_dir / "video-tiktok.mp4"

        print(f"  Processing: {video_id}")

        if dry_run:
            print(f"    Would copy to: {target_dir}")
            count += 1
            continue

        # Create target directory
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy video (renamed to video-tiktok.mp4)
        shutil.copy2(raw_video, target_video)

        # Copy metadata if exists
        if raw_info:
            target_info = target_dir / "metadata.json"
            shutil.copy2(raw_info[0], target_info)

        # Track as processed
        save_to_tracking_file(TRACKING_FILE, video_id)
        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Process TikTok videos")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    print("=" * 50)
    print("  TikTok Video Processor")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    if args.dry_run:
        print("DRY RUN MODE")

    print(f"Raw: {RAW_DIR}")
    print(f"Processed: {PROCESSED_DIR}")
    print()

    count = process_videos(args.dry_run)

    print()
    print("=" * 50)
    print(f"Processed: {count} videos")
    print("=" * 50)


if __name__ == "__main__":
    main()
