#!/usr/bin/env python3
"""
Video Processor: Convert horizontal video to vertical TikTok format.
Adds blur background to maintain aspect ratio.

Usage:
    python video-process.py <input.mp4> <output.mp4>
    python video-process.py --batch <input_dir> <output_dir>
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

# Environment configuration
OUTPUT_DIR = Path(os.environ.get("FB_TIKTOK_OUTPUT_DIR", Path.home() / "fb-tiktok-output"))


def get_video_info(video_path: Path) -> dict:
    """Get video dimensions using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "json", str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {}

    import json
    data = json.loads(result.stdout)
    streams = data.get("streams", [{}])
    if streams:
        return {
            "width": int(streams[0].get("width", 0)),
            "height": int(streams[0].get("height", 0)),
            "duration": float(streams[0].get("duration", 0))
        }
    return {}


def process_video(input_path: Path, output_path: Path) -> bool:
    """Convert video to 9:16 vertical format with blur background."""
    print(f"🎬 Processing: {input_path.name}")

    if not shutil.which("ffmpeg"):
        print("❌ FFmpeg not found")
        return False

    info = get_video_info(input_path)
    if not info.get("width"):
        print("❌ Could not read video info")
        return False

    w, h = info["width"], info["height"]
    print(f"  Input: {w}x{h}")

    # Target: 1080x1920 (9:16)
    target_w, target_h = 1080, 1920

    # Calculate scaling
    if w / h > 9 / 16:  # Wider than target
        scale_w = target_w
        scale_h = int(target_w * h / w)
    else:  # Taller or equal
        scale_h = target_h
        scale_w = int(target_h * w / h)

    # Ensure even dimensions
    scale_w = scale_w - (scale_w % 2)
    scale_h = scale_h - (scale_h % 2)

    # FFmpeg filter: blur background + overlay
    filter_complex = (
        f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},boxblur=20:5[bg];"
        f"[0:v]scale={scale_w}:{scale_h}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", filter_complex,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f"❌ FFmpeg error: {result.stderr[-200:]}")
            return False

        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"  ✅ Output: {output_path.name} ({size_mb:.1f}MB)")
        return True
    except subprocess.TimeoutExpired:
        print("❌ Processing timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def process_batch(input_dir: Path, output_dir: Path):
    """Process all videos in a directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    videos = list(input_dir.glob("**/*.mp4"))
    print(f"Found {len(videos)} video(s)")

    success = 0
    for video in videos:
        out_name = f"{video.stem}-tiktok.mp4"
        out_path = output_dir / out_name
        if process_video(video, out_path):
            success += 1

    print(f"✅ Processed: {success}/{len(videos)}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage:")
        print("  python video-process.py <input.mp4> <output.mp4>")
        print("  python video-process.py --batch <input_dir> <output_dir>")
        sys.exit(0 if sys.argv[1:] and sys.argv[1] in ("-h", "--help") else 1)

    if sys.argv[1] == "--batch":
        input_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_DIR / "raw"
        output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else OUTPUT_DIR / "processed"
        process_batch(input_dir, output_dir)
    else:
        input_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_stem(f"{input_path.stem}-tiktok")
        process_video(input_path, output_path)


if __name__ == "__main__":
    main()
