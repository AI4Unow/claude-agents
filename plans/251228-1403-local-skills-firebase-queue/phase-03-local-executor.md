---
phase: 3
title: "Claude Code Local Executor"
parent: plan.md
status: completed
effort: 1.5h
---

# Phase 3: Claude Code Local Executor

## Context

- Parent: [plan.md](./plan.md)
- Depends on: [Phase 1](./phase-01-firebase-task-queue.md), [Phase 2](./phase-02-modal-detection-queueing.md)
- Code: New script `agents/scripts/local-executor.py`

## Overview

Create a Claude Code script that polls Firebase for pending local tasks and executes them using the local skill system.

## Requirements

1. Poll Firebase for pending tasks
2. Claim and execute tasks atomically
3. Run skill with local agentic loop
4. Write results back to Firebase
5. Notify user via Telegram when complete

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL EXECUTOR FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐                                           │
│  │ Poll Firebase    │ ◄──── Every 30s or manual trigger         │
│  │ (pending tasks)  │                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ Claim task       │ ◄──── Atomic update (pending→processing)  │
│  │ (if available)   │                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ Load skill       │ ◄──── From local skills/ directory        │
│  │ (info.md)        │                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ Execute skill    │ ◄──── LLM + tools (browser, desktop)      │
│  │ (agentic loop)   │                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ Write result     │ ◄──── Firebase update                     │
│  │ Notify user      │ ◄──── Telegram API                        │
│  └──────────────────┘                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Related Code Files

- NEW: `agents/scripts/local-executor.py`
- `agents/src/services/firebase.py` - Task queue functions
- `agents/skills/` - Local skill info.md files

## Implementation Steps

### Step 1: Create local-executor.py script

```python
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
    response = await llm.chat(
        system=skill.get_system_prompt(),
        messages=[{"role": "user", "content": task}],
        max_tokens=4096
    )

    return response.content[0].text if response.content else ""


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

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": user_id,
                "text": message,
                "parse_mode": "Markdown"
            }
        )


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

    for task in tasks:
        await process_task(task)


async def run_poll(interval: int = 30):
    """Continuously poll for tasks."""
    init_firebase()
    logger.info("starting_poll", interval=interval)

    while True:
        try:
            tasks = await get_pending_local_tasks(limit=5)
            if tasks:
                logger.info("found_tasks", count=len(tasks))
                for task in tasks:
                    await process_task(task)
            else:
                logger.debug("no_pending_tasks")
        except Exception as e:
            logger.error("poll_error", error=str(e))

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


def main():
    parser = argparse.ArgumentParser(description="Local Skill Executor")
    parser.add_argument("--poll", action="store_true", help="Continuous polling")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval (seconds)")
    parser.add_argument("--task", type=str, help="Execute specific task ID")
    args = parser.parse_args()

    if args.task:
        asyncio.run(run_specific(args.task))
    elif args.poll:
        asyncio.run(run_poll(args.interval))
    else:
        asyncio.run(run_once())


if __name__ == "__main__":
    main()
```

### Step 2: Add environment setup

Create `.env.local` template:
```bash
# Firebase credentials (same as Modal secrets)
FIREBASE_CREDENTIALS='{"type":"service_account",...}'
FIREBASE_PROJECT_ID=your-project-id

# Telegram (for notifications)
TELEGRAM_BOT_TOKEN=your-bot-token

# Anthropic (for LLM calls)
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 3: Add Claude Code command (optional)

Add to project CLAUDE.md or skills:
```markdown
## Local Executor Command

Run local skill executor:
\`\`\`bash
# Process pending tasks once
python3 agents/scripts/local-executor.py

# Continuous polling (30s interval)
python3 agents/scripts/local-executor.py --poll

# Custom interval
python3 agents/scripts/local-executor.py --poll --interval 60
\`\`\`
```

## Todo List

- [ ] Create `agents/scripts/local-executor.py`
- [ ] Implement execute_local_skill function
- [ ] Implement notify_task_complete function
- [ ] Implement process_task function
- [ ] Implement run_once, run_poll, run_specific
- [ ] Add CLI argument parsing
- [ ] Create .env.local template
- [ ] Document in CLAUDE.md

## Success Criteria

- [ ] Script runs without errors
- [ ] Can poll and find pending tasks
- [ ] Can claim tasks atomically
- [ ] Can execute skills with LLM
- [ ] Results written to Firebase
- [ ] User notified via Telegram

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM API failure | High | Retry logic, error handling |
| Firebase connection | Medium | Circuit breaker, reconnect |
| Long-running task | Medium | Timeout (5 min max) |
| Missing env vars | High | Validate on startup |

## Security Considerations

- Store credentials in .env.local (gitignored)
- Validate task content before execution
- Limit execution time to prevent abuse
- Log all executions for audit

## Next Steps

After all phases complete:
1. Deploy Phase 1 & 2 changes to Modal
2. Test with manual task creation in Firebase
3. Run local executor and verify end-to-end flow
4. Set up cron/launchd for continuous polling
