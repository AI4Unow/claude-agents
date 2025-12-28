"""
Shared Utility Functions for ProCaffe Scripts

Consolidates common patterns used across multiple scripts.
"""

import logging
import re
from pathlib import Path
from typing import Iterator

from config import (
    EXPORTS_DIR,
    DATA_DIR,
    LOGS_DIR,
    MIN_VIDEO_SIZE,
    FB_URL_PATTERN,
    AI_GENERATED_DIR,
)


def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """Configure logger with file and console output."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(LOGS_DIR / log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def list_processed_videos() -> Iterator[tuple[str, Path]]:
    """Yield (video_id, video_path) for all processed TikTok videos."""
    processed_dir = EXPORTS_DIR / "processed"
    if not processed_dir.exists():
        return

    for video_dir in sorted(processed_dir.iterdir()):
        if not video_dir.is_dir():
            continue

        video_file = video_dir / "video-tiktok.mp4"
        if video_file.exists() and video_file.stat().st_size > MIN_VIDEO_SIZE:
            # Extract video ID from folder name (YYYYMMDD-{id})
            video_id = video_dir.name.split("-", 1)[-1] if "-" in video_dir.name else video_dir.name
            yield video_id, video_file


def validate_fb_url(url: str) -> bool:
    """Validate that URL is a Facebook URL."""
    return bool(re.match(FB_URL_PATTERN, url))


def load_tracking_file(filename: str) -> set[str]:
    """Load IDs from a tracking file (one per line)."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        content = filepath.read_text().strip()
        return set(content.split("\n")) if content else set()
    return set()


def save_to_tracking_file(filename: str, item_id: str) -> None:
    """Append ID to tracking file."""
    filepath = DATA_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a") as f:
        f.write(f"{item_id}\n")


def get_file_size_mb(filepath: Path) -> float:
    """Get file size in megabytes."""
    return filepath.stat().st_size / 1024 / 1024


def is_valid_video(filepath: Path) -> bool:
    """Check if file exists and is large enough to be valid."""
    return filepath.exists() and filepath.stat().st_size > MIN_VIDEO_SIZE


def list_ai_generated_videos() -> Iterator[tuple[str, Path]]:
    """Yield (video_id, video_path) for all AI-generated videos."""
    if not AI_GENERATED_DIR.exists():
        return

    for video_dir in sorted(AI_GENERATED_DIR.iterdir()):
        if not video_dir.is_dir():
            continue

        # Check both naming conventions
        video_file = video_dir / "video-tiktok.mp4"
        if not video_file.exists():
            video_file = video_dir / "video.mp4"

        if video_file.exists() and video_file.stat().st_size > MIN_VIDEO_SIZE:
            # Use folder name as ID with ai- prefix
            video_id = f"ai-{video_dir.name}"
            yield video_id, video_file


def list_all_tiktok_videos() -> Iterator[tuple[str, Path]]:
    """Yield all videos (processed + AI-generated) ready for upload."""
    yield from list_processed_videos()
    yield from list_ai_generated_videos()
