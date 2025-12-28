#!/usr/bin/env python3
"""
TikTok Video Uploader using Playwright with stealth mode.
More reliable than Selenium-based libraries.

Usage:
    python tiktok-upload.py --login           # Login and save session
    python tiktok-upload.py --dry-run         # Preview uploads
    python tiktok-upload.py <video.mp4>       # Upload single video
    python tiktok-upload.py --batch <dir>     # Upload all videos in directory
"""

import sys
import os
import json
import asyncio
import argparse
import random
from pathlib import Path
from datetime import datetime

# Environment configuration
OUTPUT_DIR = Path(os.environ.get("FB_TIKTOK_OUTPUT_DIR", Path.home() / "fb-tiktok-output"))
SESSION_DIR = Path(os.environ.get("FB_TIKTOK_SESSION_DIR", Path.home() / ".fb-tiktok-sessions"))
SESSION_FILE = SESSION_DIR / "tiktok-session.json"
DEFAULT_HASHTAG = os.environ.get("FB_TIKTOK_HASHTAG", "#video")
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
DELAY_BETWEEN_UPLOADS = 120

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
except ImportError:
    print("Missing: pip install playwright playwright-stealth && playwright install chromium")
    sys.exit(1)

stealth = Stealth()


async def human_delay(min_ms=500, max_ms=1500):
    await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)


async def login_and_save_session(playwright):
    """Open browser for manual login, save session."""
    print("Opening TikTok for login...")
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(viewport={"width": 1280, "height": 800})
    page = await context.new_page()
    await stealth.apply_stealth_async(page)
    await page.goto("https://www.tiktok.com/login", timeout=60000)

    print("Log in manually. Browser will detect when done...")
    try:
        while True:
            await asyncio.sleep(2)
            try:
                await page.wait_for_selector('[data-e2e="upload-icon"]', timeout=2000)
                print("Login detected!")
                break
            except asyncio.TimeoutError:
                pass
    except Exception:
        pass

    await context.storage_state(path=str(SESSION_FILE))
    print(f"Session saved: {SESSION_FILE}")
    await browser.close()


async def upload_video(page, video_path: Path, caption: str) -> bool:
    """Upload a single video to TikTok."""
    print(f"  Uploading: {video_path.name}")
    print(f"  Caption: {caption[:50]}...")

    try:
        await page.goto(UPLOAD_URL, timeout=90000, wait_until="domcontentloaded")
        await human_delay(5000, 8000)

        current_url = page.url
        print(f"  Current URL: {current_url}")
        if "login" in current_url.lower():
            print("  Session expired! Run --login")
            return False

        # Wait for page to be fully interactive
        await page.wait_for_load_state("domcontentloaded")
        await human_delay(8000, 12000)  # Long wait for JS to render

        # Find file input - wait for it to appear
        print("  Looking for file input...")
        file_input = None

        # First try: direct selector with video accept
        try:
            file_input = await page.wait_for_selector('input[type="file"][accept="video/*"]', timeout=20000, state="attached")
            print("  Found file input (video)")
        except Exception as e:
            print(f"  Video input not found: {e}")

        # Second try: any file input
        if not file_input:
            try:
                file_input = await page.wait_for_selector('input[type="file"]', timeout=10000, state="attached")
                print("  Found file input (generic)")
            except Exception as e:
                print(f"  Generic input not found: {e}")

        # Third try: use JavaScript to find hidden input
        if not file_input:
            try:
                file_input = await page.query_selector('input[type="file"]')
                if file_input:
                    print("  Found file input via query_selector")
            except Exception:
                pass

        # Fourth try: search in frames
        if not file_input:
            for frame in page.frames:
                try:
                    file_input = await frame.query_selector('input[type="file"]')
                    if file_input:
                        print("  Found file input in iframe")
                        break
                except Exception:
                    continue

        if not file_input:
            print("  Could not find file input")
            # Save screenshot and HTML for debugging
            debug_dir = OUTPUT_DIR / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(debug_dir / "tiktok-page.png"))
            content = await page.content()
            (debug_dir / "tiktok-page.html").write_text(content)
            print(f"  Debug files saved to: {debug_dir}")
            return False

        await file_input.set_input_files(str(video_path))
        print("  File selected, waiting for processing...")
        await asyncio.sleep(20)  # TikTok needs time to process

        # Find caption field - multiple selectors for different TikTok versions
        caption_selectors = [
            '[data-e2e="caption-editor"]',
            '.public-DraftEditor-content',
            '.DraftEditor-root',
            '[contenteditable="true"]',
            'div[data-contents="true"]',
            '.notranslate'
        ]
        caption_found = False
        for selector in caption_selectors:
            try:
                print(f"  Trying caption selector: {selector}")
                caption_element = await page.wait_for_selector(selector, timeout=8000)
                if caption_element:
                    await caption_element.click()
                    await human_delay(300, 500)
                    await page.keyboard.press("Meta+a")
                    for char in caption:
                        await page.keyboard.type(char, delay=random.randint(30, 80))
                    caption_found = True
                    print(f"  Caption entered with selector: {selector}")
                    break
            except Exception:
                continue

        if not caption_found:
            print("  Warning: Could not find caption field, continuing anyway...")

        await asyncio.sleep(15)

        # Click post button
        post_selectors = ['[data-e2e="post-button"]', 'button:has-text("Post")', 'button:has-text("Đăng")']
        for selector in post_selectors:
            try:
                post_button = await page.wait_for_selector(selector, timeout=5000)
                if post_button:
                    is_disabled = await post_button.get_attribute("disabled")
                    if not is_disabled:
                        await post_button.click()
                        print("  Post button clicked!")

                        # Wait for upload to complete - verify success
                        print("  Waiting for upload to complete...")
                        upload_success = False

                        for check in range(12):  # Check for up to 60 seconds
                            await asyncio.sleep(5)

                            # Check for success indicators
                            current_url = page.url
                            content = await page.content()

                            # Success: redirected away from upload page
                            if "upload" not in current_url.lower():
                                print(f"  Redirected to: {current_url}")
                                upload_success = True
                                break

                            # Success: success message appeared
                            if "successfully" in content.lower() or "posted" in content.lower():
                                print("  Success message detected")
                                upload_success = True
                                break

                            # Success: Vietnamese success message
                            if "thành công" in content.lower():
                                print("  Success message detected (VN)")
                                upload_success = True
                                break

                            # Failure: error message
                            if "error" in content.lower() or "failed" in content.lower() or "lỗi" in content.lower():
                                print("  Error message detected")
                                break

                            print(f"  Still processing... ({(check+1)*5}s)")

                        if upload_success:
                            return True
                        else:
                            print("  Upload may not have completed successfully")
                            # Save debug screenshot
                            debug_dir = OUTPUT_DIR / "debug"
                            debug_dir.mkdir(parents=True, exist_ok=True)
                            await page.screenshot(path=str(debug_dir / "post-upload-state.png"))
                            print(f"  Debug screenshot saved to: {debug_dir}")
                            return False
            except (asyncio.TimeoutError, Exception):
                continue

        print("  Could not find/click Post button")
        return False

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="TikTok Uploader")
    parser.add_argument("video", nargs="?", help="Video file to upload")
    parser.add_argument("--login", action="store_true", help="Login and save session")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    parser.add_argument("--batch", type=str, help="Upload all videos in directory")
    parser.add_argument("--caption", type=str, default=DEFAULT_HASHTAG, help="Video caption")
    args = parser.parse_args()

    print("═" * 47)
    print("  TikTok Uploader (Playwright)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 47)

    async with async_playwright() as p:
        if args.login:
            await login_and_save_session(p)
            return

        if not SESSION_FILE.exists():
            print("No session. Run with --login first.")
            sys.exit(1)

        # Collect videos
        videos = []
        if args.batch:
            batch_dir = Path(args.batch)
            videos = [(v, args.caption) for v in batch_dir.glob("**/*.mp4")]
        elif args.video:
            videos = [(Path(args.video), args.caption)]
        else:
            # Default: processed directory
            processed = OUTPUT_DIR / "processed"
            videos = [(v, args.caption) for v in processed.glob("**/*-tiktok.mp4")]

        if not videos:
            print("No videos found")
            sys.exit(0)

        print(f"Found {len(videos)} video(s)")

        if args.dry_run:
            for v, c in videos:
                print(f"[DRY RUN] {v.name} - {c}")
            return

        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=str(SESSION_FILE), viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        await stealth.apply_stealth_async(page)

        success = 0
        for i, (video_path, caption) in enumerate(videos):
            print(f"[{i+1}/{len(videos)}] {video_path.name}")
            if await upload_video(page, video_path, caption):
                print("  ✅ Uploaded!")
                success += 1
            else:
                print("  ❌ Failed")
            if i < len(videos) - 1:
                print(f"  Waiting {DELAY_BETWEEN_UPLOADS}s...")
                await asyncio.sleep(DELAY_BETWEEN_UPLOADS)

        await context.storage_state(path=str(SESSION_FILE))
        await browser.close()

        print()
        print(f"✅ Uploaded: {success}/{len(videos)}")


if __name__ == "__main__":
    asyncio.run(main())
