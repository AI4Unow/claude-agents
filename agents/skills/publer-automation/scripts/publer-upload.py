#!/usr/bin/env python3
"""
Publer TikTok Video Publisher
Uploads processed videos to TikTok via Publer API
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone

from config import (
    PUBLER_API_BASE as API_BASE,
    MAX_FILE_SIZE_MB,
    MAX_FILE_SIZE,
    RATE_LIMIT_DELAY,
    UPLOAD_TIMEOUT,
    JOB_POLL_TIMEOUT,
    DEFAULT_TIMEOUT,
    DATA_DIR,
    EXPORTS_DIR,
    LOCAL_TIMEZONE_OFFSET,
)
from utils import (
    list_all_tiktok_videos,
    load_tracking_file,
    save_to_tracking_file,
    get_file_size_mb,
    setup_logger,
)

# Publer API configuration from environment
API_KEY = os.environ.get("PUBLER_API_KEY")
WORKSPACE_ID = os.environ.get("PUBLER_WORKSPACE_ID")
TIKTOK_ACCOUNT_ID = os.environ.get("PUBLER_TIKTOK_ACCOUNT_ID")

# Logger
logger = setup_logger("publer-upload", "publer-upload.log")


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
        print("Set them in .env or export them before running.")
        return False
    return True


def get_headers():
    return {
        "Authorization": f"Bearer-API {API_KEY}",
        "Publer-Workspace-Id": WORKSPACE_ID
    }


def upload_media(video_path: Path) -> str | None:
    """Upload video to Publer media library. Returns media ID."""
    file_size = video_path.stat().st_size
    file_size_mb = file_size / 1024 / 1024

    # Check file size before attempting upload
    if file_size > MAX_FILE_SIZE:
        print(f"  ✗ File too large: {file_size_mb:.1f}MB (max: {MAX_FILE_SIZE_MB}MB)")
        return None

    print(f"  Uploading video ({file_size_mb:.1f}MB)...")

    try:
        with open(video_path, "rb") as f:
            files = {"file": (video_path.name, f, "video/mp4")}
            response = requests.post(
                f"{API_BASE}/media",
                headers=get_headers(),
                files=files,
                timeout=UPLOAD_TIMEOUT  # from config
            )

        if response.status_code == 200:
            data = response.json()
            media_id = data.get("id")
            if data.get("validity", {}).get("tiktok"):
                print(f"  ✓ Media uploaded: {media_id}")
                return media_id
            else:
                print(f"  ✗ Video not valid for TikTok")
                return None
        else:
            print(f"  ✗ Upload failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"  ✗ Upload error: {e}")
        return None


def check_job_status(job_id: str, max_attempts: int = 10) -> dict | None:
    """Poll job status until complete."""
    for _ in range(max_attempts):
        try:
            response = requests.get(
                f"{API_BASE}/job_status/{job_id}",
                headers=get_headers(),
                timeout=JOB_POLL_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status == "complete":
                    failures = data.get("payload", {}).get("failures", {})
                    if failures:
                        return {"error": failures}
                    return {"success": True}
                elif status == "failed":
                    return {"error": data.get("payload")}
            time.sleep(1)
        except Exception:
            time.sleep(1)
    return {"error": "timeout"}


def create_tiktok_post(media_id: str, caption: str, state: str = "draft", scheduled_at: str = None, use_slots: bool = False) -> dict | None:
    """Create TikTok post with uploaded media.

    Args:
        scheduled_at: ISO timestamp for scheduling (manual timing)
        use_slots: If True, use Publer's auto-schedule to fill next available slot
    """
    if use_slots:
        print(f"  Auto-scheduling to next slot...")
    elif scheduled_at:
        print(f"  Scheduling post for {scheduled_at}...")
    else:
        print(f"  Creating {state} post...")

    # Media must be inside networks.tiktok, not at post level
    post_data = {
        "networks": {
            "tiktok": {
                "type": "video",
                "text": caption,
                "media": [{"id": media_id, "type": "video"}],
                "privacy_level": "PUBLIC_TO_EVERYONE"
            }
        },
        "accounts": [{"id": TIKTOK_ACCOUNT_ID}]
    }

    payload = {
        "bulk": {
            "state": state,
            "posts": [post_data]
        }
    }

    # Use Publer's native slot-based auto-scheduling
    if use_slots:
        payload["bulk"]["auto"] = True
        payload["bulk"]["state"] = "scheduled"
    # Or use manual timestamp scheduling
    elif scheduled_at:
        payload["bulk"]["posts"][0]["scheduled_at"] = scheduled_at

    # Use publish endpoint for immediate posting, otherwise schedule endpoint
    endpoint = f"{API_BASE}/posts/schedule/publish" if state == "publish" else f"{API_BASE}/posts/schedule"

    try:
        response = requests.post(
            endpoint,
            headers={**get_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=DEFAULT_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            job_id = data.get("job_id")

            # Check job status
            result = check_job_status(job_id)
            if result and result.get("success"):
                print(f"  ✓ Post created (job: {job_id})")
                return data
            else:
                error = result.get("error") if result else "unknown"
                print(f"  ✗ Post failed: {error}")
                return None
        else:
            print(f"  ✗ Post creation failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"  ✗ Post error: {e}")
        return None


def get_caption(video_dir: Path) -> str:
    """Get caption from caption.txt or generate default."""
    caption_file = video_dir / "caption.txt"
    if caption_file.exists():
        caption = caption_file.read_text().strip()
        if caption:
            return caption

    # Default caption with hashtags
    return "☕ ProCaffe - Giải pháp cà phê toàn diện #procaffe #coffee #caphe #vietnam"


def load_uploaded() -> set:
    """Load list of already uploaded video IDs."""
    return load_tracking_file("uploaded-videos.txt")


def save_uploaded(video_id: str):
    """Mark video as uploaded."""
    save_to_tracking_file("uploaded-videos.txt", video_id)


def list_videos() -> list[tuple[str, Path]]:
    """List all videos ready for upload (processed + AI-generated)."""
    return list(list_all_tiktok_videos())


def main():
    parser = argparse.ArgumentParser(description="Upload videos to TikTok via Publer")
    parser.add_argument("--limit", type=int, default=5, help="Max videos to upload (default: 5)")
    parser.add_argument("--state", choices=["draft", "scheduled"], default="draft",
                        help="Post state: draft or scheduled (requires posting schedule in Publer)")
    parser.add_argument("--publish", action="store_true", help="Publish immediately instead of draft")
    parser.add_argument("--auto-schedule", action="store_true",
                        help="Auto-schedule posts (90 min intervals, starting 1 hour from now)")
    parser.add_argument("--schedule-interval", type=int, default=0,
                        help="Hours between scheduled posts (0=no scheduling, posts as drafts)")
    parser.add_argument("--start-hour", type=int, default=8,
                        help="Hour of day to start scheduling (0-23, default: 8 AM)")
    parser.add_argument("--dry-run", action="store_true", help="List videos without uploading")
    parser.add_argument("--use-slots", action="store_true",
                        help="Use Publer's native posting schedule slots (auto: true)")
    args = parser.parse_args()

    # Validate environment variables (skip for dry-run listing)
    if not args.dry_run and not validate_env_vars():
        sys.exit(1)

    # Determine effective state
    if args.publish:
        effective_state = "publish"
    elif args.use_slots or args.auto_schedule or args.schedule_interval > 0:
        effective_state = "scheduled"
    else:
        effective_state = args.state

    print("═" * 50)
    print("  Publer TikTok Video Publisher")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 50)
    print()

    if args.publish:
        print("Mode: PUBLISH IMMEDIATELY")
    elif args.use_slots:
        print("Mode: USE PUBLER SLOTS (auto: true)")
    elif args.auto_schedule:
        print("Mode: AUTO-SCHEDULE (90 min intervals)")
    elif args.schedule_interval > 0:
        print(f"Mode: SCHEDULE (every {args.schedule_interval} hours)")
    else:
        print(f"Mode: {effective_state.upper()}")
    print()

    # Load tracking
    uploaded = load_uploaded()
    print(f"Already uploaded: {len(uploaded)} videos")

    # Find videos to upload
    all_videos = list_videos()
    print(f"Processed videos: {len(all_videos)} total")

    # Filter out already uploaded
    to_upload = [(vid, path) for vid, path in all_videos if vid not in uploaded]
    print(f"Ready to upload: {len(to_upload)} videos")
    print()

    if args.dry_run:
        print("DRY RUN - Videos that would be uploaded:")
        for i, (vid, path) in enumerate(to_upload[:args.limit]):
            print(f"  {i+1}. {vid} ({get_file_size_mb(path):.1f}MB)")
        return

    if not to_upload:
        print("No videos to upload!")
        return

    # Upload videos
    success = 0
    failed = 0

    # Calculate schedule start time for auto-schedule or manual interval
    if args.auto_schedule or args.schedule_interval > 0:
        # Use UTC timezone for Publer API
        now_utc = datetime.now(timezone.utc)

        if args.schedule_interval > 0:
            # Manual interval: use specified start hour
            target_hour_utc = (args.start_hour - LOCAL_TIMEZONE_OFFSET) % 24
            next_schedule_time = now_utc.replace(
                hour=target_hour_utc, minute=0, second=0, microsecond=0
            )
            # If start time already passed today, move to next slot
            if next_schedule_time <= now_utc:
                next_schedule_time += timedelta(hours=args.schedule_interval)
            schedule_interval = timedelta(hours=args.schedule_interval)
        else:
            # Auto-schedule: start 1 hour from now, 90 min intervals
            # Round to nearest minute for clean timestamps
            next_schedule_time = (now_utc + timedelta(hours=1)).replace(second=0, microsecond=0)
            schedule_interval = timedelta(minutes=90)

        local_time = next_schedule_time + timedelta(hours=LOCAL_TIMEZONE_OFFSET)
        print(f"Scheduling starts: {local_time.strftime('%Y-%m-%d %H:%M')} (GMT+{LOCAL_TIMEZONE_OFFSET})")
        if args.schedule_interval > 0:
            print(f"Interval: every {args.schedule_interval} hours")
        else:
            print(f"Interval: every 90 minutes (auto)")
        print()
    else:
        next_schedule_time = None
        schedule_interval = None

    for i, (video_id, video_path) in enumerate(to_upload[:args.limit]):
        print(f"[{i+1}/{min(len(to_upload), args.limit)}] Processing: {video_id}")

        # Get caption
        caption = get_caption(video_path.parent)

        # Upload media
        media_id = upload_media(video_path)
        if not media_id:
            failed += 1
            continue

        time.sleep(RATE_LIMIT_DELAY)

        # Determine scheduled time (skip if using slots - Publer handles it)
        scheduled_at = None
        if not args.use_slots and next_schedule_time is not None:
            scheduled_at = next_schedule_time.isoformat()
            next_schedule_time += schedule_interval

        # Create post
        result = create_tiktok_post(media_id, caption, effective_state, scheduled_at, use_slots=args.use_slots)
        if result:
            save_uploaded(video_id)
            success += 1
        else:
            failed += 1

        time.sleep(RATE_LIMIT_DELAY)
        print()

    print("═" * 50)
    print("Upload Summary:")
    print(f"  Success: {success}")
    print(f"  Failed:  {failed}")
    print(f"  Remaining: {len(to_upload) - args.limit if len(to_upload) > args.limit else 0}")
    print("═" * 50)


if __name__ == "__main__":
    main()
