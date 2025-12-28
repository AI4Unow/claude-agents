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
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.firebase import (
    init_firebase,
    get_pending_local_tasks,
    claim_local_task,
    complete_local_task,
    get_task_result
)
from src.skills.registry import SkillRegistry
from src.services.llm import get_llm_client
from src.utils.logging import get_logger

logger = get_logger()


async def execute_local_skill(skill_name: str, task: str) -> str:
    """Execute a local skill with LLM."""
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

    return response if isinstance(response, str) else str(response)


async def notify_task_complete(
    user_id: int,
    skill_name: str,
    task_id: str,
    result: str,
    success: bool = True,
    error: str = None
):
    """Notify user that task completed."""
    import httpx

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token or not user_id:
        return

    if success:
        # Truncate result for Telegram (max 4096 chars)
        result_preview = result[:500] + "..." if len(result) > 500 else result
        message = (
            f"✅ *Task Completed*\n\n"
            f"Skill: `{skill_name}`\n"
            f"Task ID: `{task_id[:8]}...`\n\n"
            f"*Result:*\n{result_preview}"
        )
    else:
        message = (
            f"❌ *Task Failed*\n\n"
            f"Skill: `{skill_name}`\n"
            f"Task ID: `{task_id[:8]}...`\n\n"
            f"*Error:* {error}"
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
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
        # Execute the skill
        result = await execute_local_skill(skill_name, task_text)

        # Mark as complete
        await complete_local_task(task_id, result, success=True)

        # Notify user
        await notify_task_complete(user_id, skill_name, task_id, result)

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
