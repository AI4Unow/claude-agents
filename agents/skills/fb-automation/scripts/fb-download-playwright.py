#!/usr/bin/env python3
"""
Facebook Video Downloader using Playwright
Downloads videos from Facebook reels/posts.

First run: Log into Facebook when browser opens, then the session will be saved.
Subsequent runs: Uses saved session.

Usage:
    python fb-download-playwright.py <facebook_url>
    python fb-download-playwright.py --batch fb-video-urls.txt
    python fb-download-playwright.py --login  # Just login, save session
"""

import sys
import os
import json
import re
import asyncio
from pathlib import Path
from datetime import datetime
import subprocess

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Playwright not installed")
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "exports/tiktok/raw"
USER_DATA_PATH = Path("/tmp/playwright-fb-profile")


async def wait_for_login(page):
    """Wait for user to log in to Facebook."""
    print("  Waiting for Facebook login...")
    print("  Please log in if prompted, then wait...")

    # Check if we're on a login page or need to log in
    for _ in range(60):  # Wait up to 60 seconds
        await asyncio.sleep(1)
        url = page.url

        # If we're on a content page (not login), we're good
        if "/reel/" in url or "/watch" in url or "/videos/" in url:
            # Check if there's a video element
            video = await page.query_selector("video")
            if video:
                print("  ✓ Logged in and video found!")
                return True

        # Check for login form
        login_form = await page.query_selector('input[name="email"]')
        if not login_form:
            # No login form and we're on FB = likely logged in
            content = await page.content()
            if "facebook.com" in url and len(content) > 50000:
                print("  ✓ Appears to be logged in")
                return True

    return False


async def download_fb_video(url: str, output_dir: Path, context) -> bool:
    """Download a Facebook video using Playwright."""
    print(f"🎬 Downloading: {url}")

    page = await context.new_page()
    captured_videos = []

    async def handle_response(response):
        try:
            content_type = response.headers.get("content-type", "")
            resp_url = response.url
            content_length = int(response.headers.get("content-length", "0"))

            if response.status == 200:
                # Skip DASH segment URLs (have byte ranges)
                if "bytestart" in resp_url or "byteend" in resp_url:
                    return
                # Skip init segments (small headers)
                if content_length < 5000:
                    return
                # Capture video URLs
                if "video/mp4" in content_type or "video/webm" in content_type:
                    print(f"    [captured] {content_length/1024/1024:.1f}MB video")
                    captured_videos.append((resp_url, content_length))
                elif "fbcdn" in resp_url and (".mp4" in resp_url or "video" in resp_url.lower()):
                    print(f"    [captured] {content_length/1024/1024:.1f}MB fbcdn")
                    captured_videos.append((resp_url, content_length))
        except:
            pass

    page.on("response", handle_response)

    try:
        print("  Loading page...")
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")

        # Wait longer for video to load
        await asyncio.sleep(5)

        # Check if login required
        content = await page.content()
        if 'name="email"' in content or "Log in" in content[:5000]:
            print("  ⚠️ Login required. Please log in to Facebook in the browser.")
            await wait_for_login(page)
            await asyncio.sleep(3)
            content = await page.content()

        # Try clicking the video multiple times to start playback
        for attempt in range(3):
            try:
                video = await page.query_selector("video")
                if video:
                    await video.click()
                    await asyncio.sleep(3)
                    # Try to seek forward to trigger more loading
                    await page.evaluate("""
                        const video = document.querySelector('video');
                        if (video) {
                            video.currentTime = 5;
                            video.play();
                        }
                    """)
                    await asyncio.sleep(3)
            except:
                pass

        # Wait more for network requests
        print("  Waiting for video stream...")
        await asyncio.sleep(10)

        # Re-fetch page content for URL extraction
        content = await page.content()

        # Get title
        video_title = "facebook_video"
        try:
            # Try different title sources
            for selector in ['meta[property="og:title"]', 'title', 'h1']:
                el = await page.query_selector(selector)
                if el:
                    if selector == 'title':
                        video_title = await el.inner_text()
                    else:
                        video_title = await el.get_attribute("content") or await el.inner_text()
                    if video_title:
                        break
        except:
            pass

        # Find video URLs in page source
        video_urls = []  # Start fresh

        # Add intercepted videos (tuples of url, size)
        for item in captured_videos:
            if isinstance(item, tuple):
                video_urls.append(item)
            else:
                video_urls.append((item, 0))

        patterns = [
            r'"playable_url(?:_quality_hd)?":"([^"]+)"',
            r'"sd_src(?:_no_ratelimit)?":"([^"]+)"',
            r'"hd_src(?:_no_ratelimit)?":"([^"]+)"',
            r'"browser_native_(?:hd|sd)_url":"([^"]+)"',
            r'data-video-source="([^"]+)"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                clean_url = (
                    match.replace("\\u0025", "%")
                    .replace("\\/", "/")
                    .replace("\\u0026", "&")
                    .replace("&amp;", "&")
                    .replace("\\u003C", "<")
                    .replace("\\u003E", ">")
                )
                # Remove any remaining backslash escapes
                clean_url = clean_url.replace("\\", "")
                # Add https:// if missing
                if clean_url.startswith("scontent") or clean_url.startswith("fbcdn"):
                    clean_url = "https://" + clean_url
                if clean_url.startswith("http") and "fbcdn" in clean_url:
                    video_urls.append((clean_url, 0))

        # Also extract BaseURL from DASH manifest for 1080p video
        if not video_urls:
            idx = content.find('1080p')
            if idx >= 0:
                base_idx = content.find('BaseURL', idx)
                if base_idx >= 0:
                    url_start = content.find('https', base_idx)
                    url_end = content.find('u003C', url_start)
                    if url_start >= 0 and url_end >= 0:
                        raw_url = content[url_start:url_end-1]
                        clean_url = raw_url.replace("\\/", "/").replace("&amp;", "&")
                        video_urls.append((clean_url, 1000))  # Priority for 1080p

        print(f"  Found {len(video_urls)} video URL(s)")

    except Exception as e:
        print(f"  ⚠️ Error: {e}")

    await page.close()

    if not video_urls:
        print("  ❌ No video URL found")
        print("  💡 Try running with --login first to establish session")
        return False

    # Dedupe by URL and prefer largest file
    seen = {}
    for url, size in video_urls:
        if url not in seen or size > seen[url]:
            seen[url] = size

    # Sort by size (largest first) and prefer HD URLs
    sorted_urls = sorted(seen.items(), key=lambda x: x[1], reverse=True)
    video_url = sorted_urls[0][0]

    # Prefer HD if available
    for url, size in sorted_urls:
        if "hd" in url.lower() or "quality_hd" in url.lower():
            video_url = url
            break

    # Clean title
    clean_title = re.sub(r'[^\w\s-]', '', video_title)[:50].strip() or "video"
    clean_title = clean_title.replace("Facebook", "").strip() or "video"
    timestamp = datetime.now().strftime("%Y%m%d")

    video_dir = output_dir / f"{timestamp}-{clean_title}"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_dir / f"{clean_title}.mp4"

    print(f"  📥 Downloading via FFmpeg...")

    try:
        # Use FFmpeg to download the video (handles DASH streams properly)
        cmd = [
            "ffmpeg",
            "-headers", "Referer: https://www.facebook.com/\r\nUser-Agent: Mozilla/5.0\r\n",
            "-i", video_url,
            "-c", "copy",
            "-y",
            str(video_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            print(f"  ❌ FFmpeg failed: {result.stderr[-200:]}")
            return False

        size = video_path.stat().st_size
        if size < 10000:
            print(f"  ⚠️ File too small ({size} bytes)")
            return False

        # Save metadata
        metadata = {
            "title": video_title,
            "source_url": url,
            "download_date": datetime.now().isoformat(),
        }
        with open(video_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"  ✅ Saved: {video_path.name} ({size // 1024 // 1024}MB)")
        return True

    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fb-download-playwright.py --login           # Login first")
        print("  python fb-download-playwright.py <facebook_url>    # Download video")
        print("  python fb-download-playwright.py --batch urls.txt  # Batch download")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("═══════════════════════════════════════════════")
    print("  ProCaffe Facebook Video Downloader")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═══════════════════════════════════════════════")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_PATH),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
            ],
        )

        if sys.argv[1] == "--login":
            print("Opening Facebook for login...")
            print("Log in, then close the browser when done.")
            page = await browser.new_page()
            await page.goto("https://www.facebook.com/login", timeout=120000)
            print("\nWaiting for you to log in...")
            print("Close the browser when done.")

            # Wait until browser is closed
            try:
                while True:
                    await asyncio.sleep(1)
            except:
                pass

            print("✓ Session saved!")

        elif sys.argv[1] == "--batch":
            url_file = Path(sys.argv[2]) if len(sys.argv) > 2 else SCRIPT_DIR / "fb-video-urls.txt"
            if not url_file.exists():
                print(f"❌ URL file not found: {url_file}")
                await browser.close()
                sys.exit(1)

            urls = [
                line.strip() for line in url_file.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]

            print(f"Found {len(urls)} URLs")
            print()

            success = 0
            for i, url in enumerate(urls):
                print(f"[{i+1}/{len(urls)}]")
                if await download_fb_video(url, OUTPUT_DIR, browser):
                    success += 1
                print()
                await asyncio.sleep(2)

            print(f"✅ Downloaded: {success}/{len(urls)}")
            await browser.close()

        else:
            url = sys.argv[1]
            await download_fb_video(url, OUTPUT_DIR, browser)
            await browser.close()

    print()
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
