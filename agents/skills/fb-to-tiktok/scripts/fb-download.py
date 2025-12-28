#!/usr/bin/env python3
"""
Facebook Video Downloader using Playwright
Downloads videos from Facebook reels/posts with session persistence.

Usage:
    python fb-download.py <facebook_url>
    python fb-download.py --login          # Login and save session
    python fb-download.py --batch urls.txt # Batch download
"""

import sys
import os
import json
import re
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

# Environment configuration
OUTPUT_DIR = Path(os.environ.get("FB_TIKTOK_OUTPUT_DIR", Path.home() / "fb-tiktok-output")) / "raw"
SESSION_DIR = Path(os.environ.get("FB_TIKTOK_SESSION_DIR", Path.home() / ".fb-tiktok-sessions"))
FB_SESSION_FILE = SESSION_DIR / "fb-session.json"

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Missing: pip install playwright && playwright install chromium")
    sys.exit(1)


async def wait_for_login(page, timeout=60):
    """Wait for user to log in to Facebook."""
    print("  Waiting for Facebook login...")
    for _ in range(timeout):
        await asyncio.sleep(1)
        url = page.url
        if "/reel/" in url or "/watch" in url or "/videos/" in url:
            video = await page.query_selector("video")
            if video:
                print("  ✓ Logged in!")
                return True
        login_form = await page.query_selector('input[name="email"]')
        if not login_form:
            content = await page.content()
            if "facebook.com" in url and len(content) > 50000:
                print("  ✓ Appears logged in")
                return True
    return False


async def download_fb_video(url: str, context) -> bool:
    """Download a Facebook video."""
    print(f"🎬 Downloading: {url}")
    page = await context.new_page()
    captured_videos = []

    async def handle_response(response):
        try:
            content_type = response.headers.get("content-type", "")
            resp_url = response.url
            content_length = int(response.headers.get("content-length", "0"))
            if response.status == 200 and "bytestart" not in resp_url and content_length > 5000:
                if "video/mp4" in content_type or "video/" in content_type:
                    print(f"    [captured] video {content_length/1024/1024:.1f}MB")
                    captured_videos.append((resp_url, content_length))
                elif "fbcdn" in resp_url and (".mp4" in resp_url or "/v/" in resp_url):
                    print(f"    [captured] fbcdn {content_length/1024/1024:.1f}MB")
                    captured_videos.append((resp_url, content_length))
        except Exception:
            pass

    page.on("response", handle_response)

    try:
        print("  Loading page...")
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(8)

        # Try clicking video multiple times to start playback
        print("  Looking for video element...")
        for attempt in range(5):
            try:
                video = await page.query_selector("video")
                if video:
                    print(f"  Clicking video (attempt {attempt+1})...")
                    await video.click()
                    await asyncio.sleep(4)
                    # Try to play and seek
                    await page.evaluate("""
                        const video = document.querySelector('video');
                        if (video) {
                            video.play();
                            video.currentTime = 2;
                        }
                    """)
                    await asyncio.sleep(3)
            except Exception:
                pass

        # Wait more for network requests
        print("  Waiting for video stream...")
        await asyncio.sleep(15)
        content = await page.content()

        # Extract video URLs from page
        patterns = [
            r'"playable_url(?:_quality_hd)?":"([^"]+)"',
            r'"sd_src(?:_no_ratelimit)?":"([^"]+)"',
            r'"hd_src(?:_no_ratelimit)?":"([^"]+)"',
        ]
        for pattern in patterns:
            for match in re.findall(pattern, content):
                clean_url = match.replace("\\u0025", "%").replace("\\/", "/").replace("\\u0026", "&")
                if clean_url.startswith("http") and "fbcdn" in clean_url:
                    captured_videos.append((clean_url, 0))

        # Get title
        video_title = "facebook_video"
        try:
            el = await page.query_selector('meta[property="og:title"]')
            if el:
                video_title = await el.get_attribute("content") or video_title
        except Exception:
            pass

    except Exception as e:
        print(f"  Error: {e}")

    await page.close()

    if not captured_videos:
        print("  ❌ No video URL found")
        return False

    # Get best quality video
    seen = {}
    for url, size in captured_videos:
        if url not in seen or size > seen[url]:
            seen[url] = size
    sorted_urls = sorted(seen.items(), key=lambda x: x[1], reverse=True)
    video_url = sorted_urls[0][0]

    # Prepare output
    clean_title = re.sub(r'[^\w\s-]', '', video_title)[:50].strip() or "video"
    timestamp = datetime.now().strftime("%Y%m%d")
    video_dir = OUTPUT_DIR / f"{timestamp}-{clean_title}"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_dir / f"{clean_title}.mp4"

    # Download via FFmpeg
    print("  📥 Downloading...")
    try:
        result = subprocess.run([
            "ffmpeg", "-headers", "Referer: https://www.facebook.com/\r\n",
            "-i", video_url, "-c", "copy", "-y", str(video_path)
        ], capture_output=True, timeout=300)

        if result.returncode != 0 or video_path.stat().st_size < 10000:
            print("  ❌ Download failed")
            return False

        # Save metadata
        with open(video_dir / "metadata.json", "w") as f:
            json.dump({"title": video_title, "source_url": url, "date": datetime.now().isoformat()}, f)

        print(f"  ✅ Saved: {video_path}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def main():
    if len(sys.argv) < 2:
        print("Usage: python fb-download.py <url> | --login | --batch <file>")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Check for session file
        if sys.argv[1] != "--login" and not FB_SESSION_FILE.exists():
            print(f"No session found: {FB_SESSION_FILE}")
            print("Export FB cookies to scripts/fb-cookies.txt and convert,")
            print("or run with --login to authenticate manually.")
            sys.exit(1)

        if sys.argv[1] == "--login":
            # Manual login mode - use persistent context
            print("Opening Facebook for login...")
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://www.facebook.com/login", timeout=120000)
            print("Log in, then close browser when done.")
            try:
                while True:
                    await asyncio.sleep(2)
                    # Check if logged in
                    try:
                        await page.wait_for_selector('[aria-label="Facebook"]', timeout=2000)
                        print("Login detected!")
                        break
                    except Exception:
                        pass
            except Exception:
                pass
            await context.storage_state(path=str(FB_SESSION_FILE))
            print(f"Session saved: {FB_SESSION_FILE}")
            await browser.close()
            return

        # Use session-based context for downloads
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=str(FB_SESSION_FILE),
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        if sys.argv[1] == "--batch":
            url_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("urls.txt")
            urls = [l.strip() for l in url_file.read_text().splitlines() if l.strip() and not l.startswith("#")]
            success = sum([await download_fb_video(u, context) for u in urls])
            print(f"✅ Downloaded: {success}/{len(urls)}")
            await browser.close()

        else:
            await download_fb_video(sys.argv[1], context)
            await browser.close()

    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
