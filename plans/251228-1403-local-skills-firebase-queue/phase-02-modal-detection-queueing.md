---
phase: 2
title: "Modal Detection & Queueing"
parent: plan.md
status: completed
effort: 1.5h
---

# Phase 2: Modal Detection & Queueing

## Context

- Parent: [plan.md](./plan.md)
- Depends on: [Phase 1](./phase-01-firebase-task-queue.md)
- Code: `agents/main.py`, `agents/src/skills/registry.py`

## Overview

Modify Modal.com skill execution to detect local skills and queue them to Firebase instead of executing directly.

## Requirements

1. Add `deployment` field to SkillSummary dataclass
2. Detect local skills in `/api/skill` endpoint
3. Queue local tasks to Firebase
4. Return queued response with task_id
5. Add Telegram notification for queued tasks

## Architecture

```
/api/skill endpoint
        │
        ▼
┌───────────────────┐
│ Load skill summary│
│ (with deployment) │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │ deployment│
    │ == local? │
    └─────┬─────┘
      yes │ no
          │
    ┌─────┴─────────────┐
    ▼                   ▼
Queue to           Execute on
Firebase           Modal (existing)
    │
    ▼
Return {queued: true, task_id}
    │
    ▼
Notify user (Telegram)
```

## Related Code Files

- `agents/src/skills/registry.py` - Add deployment to SkillSummary
- `agents/main.py` - Modify skill_api endpoint
- `agents/src/services/firebase.py` - Use create_local_task

## Implementation Steps

### Step 1: Update SkillSummary in registry.py

```python
@dataclass
class SkillSummary:
    """Minimal skill info for progressive disclosure (Layer 1)."""
    name: str
    description: str
    category: Optional[str] = None
    deployment: str = "remote"  # NEW: "local" | "remote" | "both"
    path: Optional[Path] = None
```

### Step 2: Extract deployment in _extract_summary

```python
def _extract_summary(self, skill_dir: Path) -> Optional[SkillSummary]:
    """Extract summary from skill's info.md frontmatter."""
    info_file = skill_dir / "info.md"
    if not info_file.exists():
        return None

    content = info_file.read_text()
    frontmatter = self._parse_frontmatter(content)

    if not frontmatter:
        return SkillSummary(
            name=skill_dir.name,
            description="",
            path=skill_dir
        )

    return SkillSummary(
        name=frontmatter.get('name', skill_dir.name),
        description=frontmatter.get('description', ''),
        category=frontmatter.get('category'),
        deployment=frontmatter.get('deployment', 'remote'),  # NEW
        path=skill_dir
    )
```

### Step 3: Add is_local_skill helper in main.py

```python
def is_local_skill(skill_name: str) -> bool:
    """Check if skill requires local execution."""
    from src.skills.registry import get_registry
    registry = get_registry()
    summaries = registry.discover()

    for s in summaries:
        if s.name == skill_name:
            return s.deployment == "local"
    return False
```

### Step 4: Modify skill_api endpoint in main.py

```python
@web_app.post("/api/skill")
async def skill_api(request: Request):
    """II Framework Skill API endpoint."""
    from src.services.firebase import create_local_task

    try:
        payload = await request.json()
        skill_name = payload.get("skill")
        task = payload.get("task", "")
        context = payload.get("context", {})
        mode = payload.get("mode", "simple")
        user_id = context.get("user_id", 0)

        # Check if local skill
        if is_local_skill(skill_name):
            # Queue for local execution
            task_id = await create_local_task(
                skill=skill_name,
                task=task,
                user_id=user_id
            )

            logger.info("local_skill_queued",
                skill=skill_name,
                task_id=task_id
            )

            # Notify user
            if user_id:
                await notify_task_queued(user_id, skill_name, task_id)

            return {
                "ok": True,
                "queued": True,
                "task_id": task_id,
                "skill": skill_name,
                "message": f"Skill '{skill_name}' queued for local execution"
            }

        # ... existing remote execution logic ...
```

### Step 5: Add notification helper

```python
async def notify_task_queued(user_id: int, skill_name: str, task_id: str):
    """Notify user that task was queued for local execution."""
    import httpx

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return

    message = (
        f"⏳ *Task Queued*\n\n"
        f"Skill: `{skill_name}`\n"
        f"Task ID: `{task_id[:8]}...`\n\n"
        f"This skill requires local execution. "
        f"You'll be notified when it completes."
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
```

### Step 6: Add task status endpoint

```python
@web_app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """Get local task status."""
    from src.services.firebase import get_task_result

    task = await get_task_result(task_id)
    if not task:
        return {"ok": False, "error": "Task not found"}

    return {
        "ok": True,
        "task": {
            "id": task["id"],
            "skill": task.get("skill"),
            "status": task.get("status"),
            "result": task.get("result"),
            "error": task.get("error")
        }
    }
```

## Todo List

- [ ] Add `deployment` field to SkillSummary
- [ ] Update _extract_summary to read deployment
- [ ] Add is_local_skill helper function
- [ ] Modify skill_api to detect and queue local skills
- [ ] Add notify_task_queued helper
- [ ] Add /api/task/{id} endpoint for status checks
- [ ] Update /api/skills to include deployment field

## Success Criteria

- [ ] Local skills detected correctly
- [ ] Tasks queued to Firebase (not executed)
- [ ] User notified via Telegram
- [ ] Task status queryable via API

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wrong detection | High | Test with all 8 local skills |
| Notification failure | Low | Non-blocking, log errors |
| Missing user_id | Medium | Default to 0, skip notification |

## Security Considerations

- Validate skill_name against registry
- Sanitize task content before storage
- Rate limit task creation per user

## Next Steps

After completion, proceed to [Phase 3](./phase-03-local-executor.md).
