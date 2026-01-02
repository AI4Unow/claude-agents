"""Suggestion engine - Proactive suggestions based on patterns."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from src.services.activity import get_skill_sequence, get_time_patterns
from src.services.user_context import get_context
from src.utils.logging import get_logger

logger = get_logger()


async def get_proactive_suggestion(user_id: int) -> Optional[str]:
    """Generate proactive suggestion based on patterns.

    Priority:
    1. Due reminders
    2. Incomplete context (project mentioned, no recent activity)
    3. Skill sequence prediction
    4. Time-based patterns

    Args:
        user_id: Telegram user ID

    Returns:
        Suggestion message or None
    """
    # 1. Check reminders first
    reminder_suggestion = await _check_reminders(user_id)
    if reminder_suggestion:
        return reminder_suggestion

    # 2. Check context continuity
    context_suggestion = await _check_context(user_id)
    if context_suggestion:
        return context_suggestion

    # 3. Skill sequence prediction
    sequence_suggestion = await _check_skill_sequence(user_id)
    if sequence_suggestion:
        return sequence_suggestion

    # 4. Time-based patterns
    time_suggestion = await _check_time_patterns(user_id)
    if time_suggestion:
        return time_suggestion

    return None


async def _check_reminders(user_id: int) -> Optional[str]:
    """Check for due or upcoming tasks with reminders."""
    try:
        from src.services.firebase import get_due_tasks
        tasks = await get_due_tasks(user_id, limit=1)
        if tasks:
            task = tasks[0]
            content = task.content[:100]
            return f"⏰ <b>Due Task:</b> {content}"
        return None
    except Exception:
        return None


async def _check_context(user_id: int) -> Optional[str]:
    """Check if user has stale context."""
    try:
        context = await get_context(user_id)
        if not context:
            return None

        # If there's a project but no recent activity in last 2 hours
        if context.current_project and context.last_active:
            inactive_threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            last_active = context.last_active
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            if last_active < inactive_threshold:
                return f"📁 Still working on <b>{context.current_project}</b>? Use /context clear to reset."

        return None
    except Exception:
        return None


async def _check_skill_sequence(user_id: int) -> Optional[str]:
    """Suggest next skill based on sequence patterns."""
    try:
        context = await get_context(user_id)
        if not context or not context.recent_skills:
            return None

        last_skill = context.recent_skills[0]
        predicted = await get_skill_sequence(user_id, last_skill, limit=1)

        if predicted:
            return f"💡 After <b>{last_skill}</b>, you often use <b>{predicted[0]}</b>. Need it?"

        return None
    except Exception:
        return None


async def _check_time_patterns(user_id: int) -> Optional[str]:
    """Suggest based on time-of-day patterns."""
    try:
        patterns = await get_time_patterns(user_id)

        hour = datetime.now(timezone.utc).hour
        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        else:
            period = "evening"

        skills = patterns.get(period, [])
        if skills:
            return f"🕐 You often use <b>{skills[0]}</b> in the {period}. Want to try it?"

        return None
    except Exception:
        return None


async def get_suggestions_list(user_id: int) -> List[str]:
    """Get multiple suggestions for display."""
    suggestions = []

    # Try all sources
    for check_fn in [_check_reminders, _check_context, _check_skill_sequence, _check_time_patterns]:
        try:
            s = await check_fn(user_id)
            if s:
                suggestions.append(s)
        except Exception:
            continue

    return suggestions


def format_suggestions_display(suggestions: List[str]) -> str:
    """Format suggestions for Telegram display."""
    if not suggestions:
        return "<i>No suggestions right now. Keep using the bot to build patterns!</i>"

    lines = ["<b>Suggestions</b>\n"]
    for s in suggestions:
        lines.append(f"• {s}")

    return "\n".join(lines)
