#!/usr/bin/env python3
"""
Local Skill Executor for Claude Code.

Polls Firebase for pending local skill tasks and executes them.

Usage:
    python3 agents/scripts/local-executor.py           # Run once
    python3 agents/scripts/local-executor.py --poll    # Continuous polling
    python3 agents/scripts/local-executor.py --task ID # Execute specific task
"""
import argparse
import asyncio
import mimetypes
import os
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.firebase import (
    init_firebase,
    get_pending_local_tasks,
    claim_local_task,
    complete_local_task,
    get_task_result,
    save_file,
)
from src.skills.registry import SkillRegistry
from src.services.llm import get_llm_client
from src.utils.logging import get_logger

logger = get_logger()

# File patterns to detect skill output
OUTPUT_PATTERNS = ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.docx", "*.pptx", "*.xlsx"]


async def execute_local_skill(skill_name: str, task: str, user_id: int = 0) -> dict:
    """Execute a local skill with LLM.

    Returns:
        Dict with 'text' and optional 'download_url', 'file_name'
    """
    # Load skill from local filesystem
    skills_path = Path(__file__).parent.parent / "skills"
    registry = SkillRegistry(skills_path)

    skill = registry.get_full(skill_name)
    if not skill:
        raise ValueError(f"Skill not found: {skill_name}")

    # Get LLM client
    llm = get_llm_client()

    # Execute with skill as system prompt
    response = llm.chat(
        system=skill.get_system_prompt(),
        messages=[{"role": "user", "content": task}],
        max_tokens=4096
    )

    result = {"text": response if isinstance(response, str) else str(response)}

    # Check for file outputs in current directory
    # Local skills often save files to cwd
    for pattern in OUTPUT_PATTERNS:
        for output_file in Path(".").glob(pattern):
            # Skip files older than 1 minute (not from this execution)
            if output_file.stat().st_mtime < (asyncio.get_event_loop().time() - 60):
                continue

            # Upload to Storage if user_id provided
            if user_id:
                try:
                    content_type = mimetypes.guess_type(str(output_file))[0] or "application/octet-stream"
                    file_id = f"{skill_name}-{uuid.uuid4().hex[:8]}"

                    with open(output_file, "rb") as f:
                        content = f.read()

                    url = await save_file(
                        user_id=user_id,
                        file_id=file_id,
                        content=content,
                        content_type=content_type,
                        metadata={"title": output_file.name, "skill": skill_name}
                    )
                    result["download_url"] = url
                    result["file_name"] = output_file.name
                    logger.info("file_uploaded", skill=skill_name, file=output_file.name)

                    # Clean up local file
                    output_file.unlink()
                    break
                except Exception as e:
                    logger.warning("upload_failed", error=str(e)[:50])

    return result


async def notify_task_complete(
    user_id: int,
    skill_name: str,
    task_id: str,
    result: str,
    success: bool = True,
    error: str = None,
    download_url: str = None,
):
    """Notify user that task completed with optional download link."""
    import httpx

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token or not user_id:
        return

    if success:
        # Truncate result for Telegram (max 4096 chars)
        result_preview = result[:500] + "..." if len(result) > 500 else result
        message = (
            f"*Task Completed*\n\n"
            f"Skill: `{skill_name}`\n"
            f"Task ID: `{task_id[:8]}...`\n\n"
            f"*Result:*\n{result_preview}"
        )

        # Add inline download button if URL provided
        keyboard = None
        if download_url:
            keyboard = {
                "inline_keyboard": [[
                    {"text": "Download", "url": download_url}
                ]]
            }
    else:
        message = (
            f"*Task Failed*\n\n"
            f"Skill: `{skill_name}`\n"
            f"Task ID: `{task_id[:8]}...`\n\n"
            f"*Error:* {error}"
        )
        keyboard = None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "chat_id": user_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            if keyboard:
                payload["reply_markup"] = keyboard

            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload
            )
    except Exception as e:
        logger.error("notification_failed", error=str(e))


async def process_task(task: dict) -> bool:
    """Process a single task. Returns True if successful."""
    task_id = task["id"]
    skill_name = task["skill"]
    task_text = task["task"]
    user_id = task.get("user_id", 0)

    logger.info("processing_task", task_id=task_id, skill=skill_name)

    # Claim the task
    claimed = await claim_local_task(task_id)
    if not claimed:
        logger.warning("task_already_claimed", task_id=task_id)
        return False

    try:
        # Execute the skill - returns dict with text and optional download_url
        result = await execute_local_skill(skill_name, task_text, user_id)

        # Build result text with download link if present
        result_text = result.get("text", "")
        if result.get("download_url"):
            result_text += f"\n\nDownload: {result['download_url']}"

        # Mark as complete
        await complete_local_task(task_id, result_text, success=True)

        # Notify user with download link
        await notify_task_complete(
            user_id, skill_name, task_id, result.get("text", ""),
            download_url=result.get("download_url")
        )

        logger.info("task_completed", task_id=task_id, skill=skill_name)
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error("task_failed", task_id=task_id, error=error_msg)

        # Mark as failed
        await complete_local_task(task_id, "", success=False, error=error_msg)

        # Notify user
        await notify_task_complete(
            user_id, skill_name, task_id, "",
            success=False, error=error_msg
        )
        return False


async def run_once():
    """Process all pending tasks once."""
    init_firebase()

    tasks = await get_pending_local_tasks(limit=10)
    logger.info("pending_tasks", count=len(tasks))

    if not tasks:
        print("No pending tasks found.")
        return

    for task in tasks:
        await process_task(task)


async def run_poll(interval: int = 30):
    """Continuously poll for tasks."""
    init_firebase()
    logger.info("starting_poll", interval=interval)
    print(f"Polling for local tasks every {interval}s... (Ctrl+C to stop)")

    while True:
        try:
            tasks = await get_pending_local_tasks(limit=5)
            if tasks:
                logger.info("found_tasks", count=len(tasks))
                print(f"Found {len(tasks)} pending task(s)")
                for task in tasks:
                    await process_task(task)
            else:
                logger.debug("no_pending_tasks")
        except Exception as e:
            logger.error("poll_error", error=str(e))
            print(f"Poll error: {e}")

        await asyncio.sleep(interval)


async def run_specific(task_id: str):
    """Execute a specific task by ID."""
    init_firebase()

    task = await get_task_result(task_id)
    if not task:
        print(f"Task not found: {task_id}")
        return

    if task.get("status") != "pending":
        print(f"Task not pending: {task.get('status')}")
        return

    await process_task(task)


def validate_env():
    """Validate required environment variables."""
    required = ["FIREBASE_CREDENTIALS", "ANTHROPIC_API_KEY"]
    missing = [v for v in required if not os.environ.get(v)]

    if missing:
        print(f"Missing required env vars: {', '.join(missing)}")
        print("\nRequired environment variables:")
        print("  FIREBASE_CREDENTIALS - Firebase service account JSON")
        print("  ANTHROPIC_API_KEY - Anthropic API key")
        print("  TELEGRAM_BOT_TOKEN - (optional) For notifications")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Local Skill Executor")
    parser.add_argument("--poll", action="store_true", help="Continuous polling")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval (seconds)")
    parser.add_argument("--task", type=str, help="Execute specific task ID")
    parser.add_argument("--skip-validation", action="store_true", help="Skip env validation")
    args = parser.parse_args()

    if not args.skip_validation:
        validate_env()

    if args.task:
        asyncio.run(run_specific(args.task))
    elif args.poll:
        try:
            asyncio.run(run_poll(args.interval))
        except KeyboardInterrupt:
            print("\nStopped polling.")
    else:
        asyncio.run(run_once())


if __name__ == "__main__":
    main()
