"""User context service - Work context management."""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from src.models.personalization import WorkContext
from src.core.state import get_state_manager
from src.services.firebase import get_db
from src.utils.logging import get_logger

logger = get_logger()

# Session timeout
SESSION_TIMEOUT_HOURS = 2

# Patterns for context extraction
PROJECT_PATTERNS = [
    r"working on (\w+[-\w]*)",
    r"project[:\s]+(\w+[-\w]*)",
    r"repo[:\s]+(\w+[-\w]*)",
]

TASK_PATTERNS = [
    r"implementing (.+?)(?:\.|$)",
    r"fixing (.+?)(?:\.|$)",
    r"building (.+?)(?:\.|$)",
    r"adding (.+?)(?:\.|$)",
]

BRANCH_PATTERNS = [
    r"branch[:\s]+(\S+)",
    r"on (\S+) branch",
]


async def get_context(user_id: int) -> Optional[WorkContext]:
    """Get user's work context."""
    state = get_state_manager()
    data = await state.get_work_context(user_id)

    if not data:
        return None

    context = WorkContext.from_dict(data)

    # Check session timeout
    if context.last_active:
        timeout = datetime.now(timezone.utc) - timedelta(hours=SESSION_TIMEOUT_HOURS)
        if context.last_active.replace(tzinfo=timezone.utc) < timeout:
            logger.info("session_expired", user_id=user_id)
            return await reset_context(user_id)

    return context


async def reset_context(user_id: int) -> WorkContext:
    """Reset context to empty state."""
    context = WorkContext(
        user_id=user_id,
        session_start=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc)
    )

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())

    return context


async def update_context(user_id: int, updates: Dict) -> WorkContext:
    """Update work context fields."""
    context = await get_context(user_id)
    if not context:
        context = WorkContext(
            user_id=user_id,
            session_start=datetime.now(timezone.utc)
        )

    # Apply updates
    for key, value in updates.items():
        if hasattr(context, key):
            setattr(context, key, value)

    context.last_active = datetime.now(timezone.utc)

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())

    return context


async def add_recent_skill(user_id: int, skill: str) -> None:
    """Add skill to recent skills list."""
    context = await get_context(user_id)
    if not context:
        context = WorkContext(user_id=user_id)

    # Add to front, remove duplicates, limit size
    skills = [skill] + [s for s in context.recent_skills if s != skill]
    context.recent_skills = skills[:WorkContext.MAX_RECENT_SKILLS]

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())


async def add_session_fact(user_id: int, fact: str) -> None:
    """Add fact to session facts."""
    context = await get_context(user_id)
    if not context:
        context = WorkContext(user_id=user_id)

    # Avoid duplicates, limit size
    if fact not in context.session_facts:
        context.session_facts.append(fact)
        context.session_facts = context.session_facts[-WorkContext.MAX_SESSION_FACTS:]

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())


async def extract_and_update_context(user_id: int, message: str, skill_used: Optional[str] = None) -> None:
    """Extract context from message and update.

    This is called after each message to auto-update context.

    Args:
        user_id: Telegram user ID
        message: User's message text
        skill_used: Skill that was executed (if any)
    """
    updates = {}
    message_lower = message.lower()

    # Extract project
    for pattern in PROJECT_PATTERNS:
        match = re.search(pattern, message_lower)
        if match:
            updates["current_project"] = match.group(1)
            break

    # Extract task
    for pattern in TASK_PATTERNS:
        match = re.search(pattern, message_lower)
        if match:
            updates["current_task"] = match.group(1)[:100]  # Limit length
            break

    # Extract branch
    for pattern in BRANCH_PATTERNS:
        match = re.search(pattern, message_lower)
        if match:
            updates["active_branch"] = match.group(1)
            break

    # Update context if we found anything
    if updates:
        await update_context(user_id, updates)

    # Add skill to recent
    if skill_used:
        await add_recent_skill(user_id, skill_used)

    # Update last_active
    await update_context(user_id, {"last_active": datetime.now(timezone.utc)})


def format_context_display(context: WorkContext) -> str:
    """Format work context for Telegram display."""
    lines = ["<b>Work Context</b>\n"]

    if context.current_project:
        lines.append(f"📁 <b>Project:</b> {context.current_project}")
    if context.current_task:
        lines.append(f"📋 <b>Task:</b> {context.current_task}")
    if context.active_branch:
        lines.append(f"🌿 <b>Branch:</b> {context.active_branch}")
    if context.recent_skills:
        lines.append(f"🔧 <b>Recent skills:</b> {', '.join(context.recent_skills)}")
    if context.session_facts:
        lines.append(f"📝 <b>Session facts:</b>")
        for fact in context.session_facts[-5:]:
            lines.append(f"  • {fact}")

    if context.session_start:
        lines.append(f"\n<i>Session started:</i> {context.session_start.strftime('%H:%M')}")

    if len(lines) == 1:
        lines.append("<i>No context captured yet. Keep chatting!</i>")

    return "\n".join(lines)


async def clear_context(user_id: int) -> None:
    """Clear user's work context."""
    await reset_context(user_id)
    logger.info("context_cleared", user_id=user_id)
