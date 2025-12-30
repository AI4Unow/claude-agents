# Phase 4: Activity Learning

**Duration:** 2-3 days
**Dependencies:** Phase 1, Phase 2, Phase 3
**Output:** Activity logging, pattern analysis, proactive suggestions, /activity & /suggest commands

## Objectives

1. Implement activity logging to Qdrant
2. Build pattern analysis for skill sequences
3. Implement proactive suggestion engine
4. Add `/activity` and `/suggest` commands
5. Add `/forget` command for data deletion
6. Integrate activity tracking into message flow

## Files to Create/Modify

### 1. `src/services/activity.py`

Activity logging and pattern analysis.

```python
"""Activity service - Logging and pattern analysis."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from collections import Counter

from src.services.qdrant import store_user_activity, search_user_activities
from src.services.embeddings import get_embedding
from src.services.firebase import get_db, firestore
from src.utils.logging import get_logger

logger = get_logger()

# Constants
MAX_ACTIVITIES_DISPLAY = 10
PATTERN_MIN_COUNT = 3  # Minimum occurrences to be considered a pattern


async def log_activity(
    user_id: int,
    action_type: str,
    summary: str,
    skill: Optional[str] = None,
    duration_ms: int = 0,
    metadata: Optional[Dict] = None
) -> Optional[str]:
    """Log user activity to Qdrant and Firebase.

    Args:
        user_id: Telegram user ID
        action_type: Type of action (chat, skill_invoke, macro, command)
        summary: Brief summary of the action
        skill: Skill name if applicable
        duration_ms: Execution duration
        metadata: Additional metadata

    Returns:
        Activity ID or None
    """
    try:
        # Get embedding for semantic search
        embedding = get_embedding(summary[:200])  # Limit for embedding

        # Store in Qdrant for semantic search
        activity_id = await store_user_activity(
            user_id=user_id,
            action_type=action_type,
            summary=summary,
            embedding=embedding,
            skill=skill,
            duration_ms=duration_ms
        )

        # Also store in Firebase for aggregation/listing
        db = get_db()
        db.collection("user_activities").document(str(user_id)) \
            .collection("logs").add({
                "action_type": action_type,
                "summary": summary[:200],
                "skill": skill,
                "duration_ms": duration_ms,
                "metadata": metadata or {},
                "timestamp": firestore.SERVER_TIMESTAMP,
                "hour": datetime.now(timezone.utc).hour,
                "weekday": datetime.now(timezone.utc).weekday()
            })

        logger.debug("activity_logged", user_id=user_id, action=action_type)
        return activity_id

    except Exception as e:
        logger.error("log_activity_error", error=str(e)[:50])
        return None


async def get_recent_activities(user_id: int, limit: int = 10) -> List[Dict]:
    """Get recent activities from Firebase."""
    try:
        db = get_db()
        docs = db.collection("user_activities").document(str(user_id)) \
            .collection("logs") \
            .order_by("timestamp", direction=firestore.Query.DESCENDING) \
            .limit(limit) \
            .get()

        return [doc.to_dict() for doc in docs]

    except Exception as e:
        logger.error("get_activities_error", error=str(e)[:50])
        return []


async def get_skill_sequence(user_id: int, last_skill: str, limit: int = 5) -> List[str]:
    """Get common skills that follow a given skill.

    Args:
        user_id: Telegram user ID
        last_skill: The skill that was just used
        limit: Number of suggestions

    Returns:
        List of skill names that commonly follow
    """
    try:
        db = get_db()

        # Get recent skill activities
        docs = db.collection("user_activities").document(str(user_id)) \
            .collection("logs") \
            .where("skill", "!=", None) \
            .order_by("skill") \
            .order_by("timestamp", direction=firestore.Query.DESCENDING) \
            .limit(100) \
            .get()

        activities = [doc.to_dict() for doc in docs]

        # Find sequences where last_skill is followed by another skill
        sequences = []
        for i in range(len(activities) - 1):
            if activities[i].get("skill") == last_skill:
                next_skill = activities[i + 1].get("skill")
                if next_skill and next_skill != last_skill:
                    sequences.append(next_skill)

        # Count and rank
        if not sequences:
            return []

        counter = Counter(sequences)
        return [skill for skill, count in counter.most_common(limit)
                if count >= 2]  # At least 2 occurrences

    except Exception as e:
        logger.error("get_skill_sequence_error", error=str(e)[:50])
        return []


async def get_time_patterns(user_id: int) -> Dict[str, List[str]]:
    """Get activity patterns by time of day.

    Returns:
        Dict with 'morning', 'afternoon', 'evening' keys
        Each containing list of common skills for that period
    """
    try:
        db = get_db()

        docs = db.collection("user_activities").document(str(user_id)) \
            .collection("logs") \
            .where("skill", "!=", None) \
            .limit(200) \
            .get()

        # Categorize by time period
        morning = []    # 6-12
        afternoon = []  # 12-18
        evening = []    # 18-24, 0-6

        for doc in docs:
            data = doc.to_dict()
            hour = data.get("hour", 12)
            skill = data.get("skill")

            if skill:
                if 6 <= hour < 12:
                    morning.append(skill)
                elif 12 <= hour < 18:
                    afternoon.append(skill)
                else:
                    evening.append(skill)

        return {
            "morning": [s for s, c in Counter(morning).most_common(3) if c >= PATTERN_MIN_COUNT],
            "afternoon": [s for s, c in Counter(afternoon).most_common(3) if c >= PATTERN_MIN_COUNT],
            "evening": [s for s, c in Counter(evening).most_common(3) if c >= PATTERN_MIN_COUNT]
        }

    except Exception as e:
        logger.error("get_time_patterns_error", error=str(e)[:50])
        return {"morning": [], "afternoon": [], "evening": []}


async def get_activity_stats(user_id: int) -> Dict:
    """Get activity statistics for user."""
    try:
        db = get_db()

        # Get all activities (last 30 days would be better with date filter)
        docs = db.collection("user_activities").document(str(user_id)) \
            .collection("logs") \
            .limit(500) \
            .get()

        activities = [doc.to_dict() for doc in docs]

        if not activities:
            return {"total": 0}

        # Calculate stats
        skills = [a.get("skill") for a in activities if a.get("skill")]
        skill_counts = Counter(skills)

        return {
            "total": len(activities),
            "skill_invocations": len(skills),
            "top_skills": skill_counts.most_common(5),
            "action_types": Counter(a.get("action_type", "unknown") for a in activities)
        }

    except Exception as e:
        logger.error("get_activity_stats_error", error=str(e)[:50])
        return {"total": 0, "error": str(e)[:50]}


def format_activity_display(activities: List[Dict]) -> str:
    """Format recent activities for Telegram display."""
    if not activities:
        return "<i>No recent activity.</i>"

    lines = ["<b>Recent Activity</b>\n"]

    for a in activities[:MAX_ACTIVITIES_DISPLAY]:
        action = a.get("action_type", "?")
        skill = a.get("skill")
        summary = a.get("summary", "")[:50]

        icon = {
            "chat": "💬",
            "skill_invoke": "🔧",
            "macro": "⚡",
            "command": "⌨️"
        }.get(action, "•")

        if skill:
            lines.append(f"{icon} <b>{skill}</b>: {summary}")
        else:
            lines.append(f"{icon} {summary}")

    return "\n".join(lines)


def format_stats_display(stats: Dict) -> str:
    """Format activity stats for Telegram display."""
    lines = ["<b>Activity Stats</b>\n"]

    lines.append(f"📊 <b>Total activities:</b> {stats.get('total', 0)}")
    lines.append(f"🔧 <b>Skill invocations:</b> {stats.get('skill_invocations', 0)}")

    top_skills = stats.get("top_skills", [])
    if top_skills:
        lines.append("\n<b>Top Skills:</b>")
        for skill, count in top_skills:
            lines.append(f"  • {skill}: {count}")

    return "\n".join(lines)
```

### 2. `src/core/suggestions.py`

Proactive suggestion engine.

```python
"""Suggestion engine - Proactive suggestions based on patterns."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from src.services.activity import get_skill_sequence, get_time_patterns
from src.services.firebase import get_user_reminders
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
    """Check for due or upcoming reminders."""
    try:
        reminders = await get_user_reminders(user_id, limit=1)
        if reminders:
            reminder = reminders[0]
            message = reminder.get("message", "Reminder")[:100]
            return f"⏰ <b>Reminder:</b> {message}"
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
            if context.last_active.replace(tzinfo=timezone.utc) < inactive_threshold:
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
```

### 3. `src/services/data_deletion.py`

GDPR-compliant data deletion.

```python
"""Data deletion service - GDPR compliance."""
from src.services.firebase import get_db
from src.services.qdrant import get_client
from src.core.state import get_state_manager
from src.utils.logging import get_logger

logger = get_logger()


async def delete_all_user_data(user_id: int) -> dict:
    """Delete all personal data for a user.

    Implements /forget command for GDPR compliance.

    Args:
        user_id: Telegram user ID

    Returns:
        Dict with deletion status per collection
    """
    results = {}

    # 1. Delete profile
    try:
        from src.services.user_profile import delete_profile
        await delete_profile(user_id)
        results["profile"] = "deleted"
    except Exception as e:
        results["profile"] = f"error: {str(e)[:30]}"

    # 2. Delete context
    try:
        db = get_db()
        db.collection("user_contexts").document(str(user_id)).delete()
        results["context"] = "deleted"
    except Exception as e:
        results["context"] = f"error: {str(e)[:30]}"

    # 3. Delete macros
    try:
        db = get_db()
        macros_ref = db.collection("user_macros").document(str(user_id))
        # Delete subcollection
        for doc in macros_ref.collection("macros").get():
            doc.reference.delete()
        macros_ref.delete()
        results["macros"] = "deleted"
    except Exception as e:
        results["macros"] = f"error: {str(e)[:30]}"

    # 4. Delete activities (Firebase)
    try:
        db = get_db()
        activities_ref = db.collection("user_activities").document(str(user_id))
        for doc in activities_ref.collection("logs").limit(500).get():
            doc.reference.delete()
        activities_ref.delete()
        results["activities"] = "deleted"
    except Exception as e:
        results["activities"] = f"error: {str(e)[:30]}"

    # 5. Delete from Qdrant (conversations and activities)
    try:
        client = get_client()
        if client:
            from qdrant_client.http import models

            # Delete from conversations collection
            client.delete(
                collection_name="conversations",
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="user_id",
                                match=models.MatchValue(value=str(user_id))
                            )
                        ]
                    )
                )
            )

            # Delete from user_activities collection
            client.delete(
                collection_name="user_activities",
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="user_id",
                                match=models.MatchValue(value=user_id)
                            )
                        ]
                    )
                )
            )

            results["qdrant"] = "deleted"
    except Exception as e:
        results["qdrant"] = f"error: {str(e)[:30]}"

    # 6. Invalidate all caches
    try:
        state = get_state_manager()
        await state.invalidate("user_profiles", str(user_id))
        await state.invalidate("user_contexts", str(user_id))
        await state.invalidate("user_tiers", str(user_id))
        results["cache"] = "invalidated"
    except Exception as e:
        results["cache"] = f"error: {str(e)[:30]}"

    logger.info("user_data_deleted", user_id=user_id, results=results)
    return results


def format_deletion_result(results: dict) -> str:
    """Format deletion results for Telegram."""
    lines = ["<b>Data Deletion Complete</b>\n"]

    for key, status in results.items():
        icon = "✅" if status == "deleted" or status == "invalidated" else "❌"
        lines.append(f"{icon} <b>{key}:</b> {status}")

    lines.append("\n<i>Your personal data has been removed from our systems.</i>")

    return "\n".join(lines)
```

### 4. Update `main.py` - Add Commands

Add /activity, /suggest, and /forget commands.

```python
# Add to handle_command():

    if cmd == "/activity":
        return await handle_activity_command(args, user)

    if cmd == "/suggest":
        return await handle_suggest_command(user)

    if cmd == "/forget":
        return await handle_forget_command(user, chat_id)


# Add command handlers:

async def handle_activity_command(args: str, user: dict) -> str:
    """Handle /activity command."""
    from src.services.activity import (
        get_recent_activities, get_activity_stats,
        format_activity_display, format_stats_display
    )

    user_id = user.get("id")
    args_lower = args.lower().strip()

    if args_lower == "stats":
        stats = await get_activity_stats(user_id)
        return format_stats_display(stats)

    # Default: show recent activity
    activities = await get_recent_activities(user_id)
    return format_activity_display(activities)


async def handle_suggest_command(user: dict) -> str:
    """Handle /suggest command."""
    from src.core.suggestions import get_suggestions_list, format_suggestions_display

    suggestions = await get_suggestions_list(user.get("id"))
    return format_suggestions_display(suggestions)


async def handle_forget_command(user: dict, chat_id: int) -> str:
    """Handle /forget command - delete all personal data."""
    from src.services.data_deletion import delete_all_user_data, format_deletion_result

    # Send confirmation keyboard
    keyboard = [
        [
            {"text": "✅ Yes, delete everything", "callback_data": f"forget_confirm:{user.get('id')}"},
            {"text": "❌ Cancel", "callback_data": "forget_cancel"}
        ]
    ]

    await send_telegram_message_with_keyboard(
        chat_id,
        "⚠️ <b>Delete All Personal Data?</b>\n\nThis will permanently delete:\n• Your profile and preferences\n• Work context\n• All macros\n• Activity history\n• Conversation memory\n\n<b>This cannot be undone.</b>",
        keyboard
    )

    return None  # Message sent with keyboard


# Add callback handler for forget confirmation:

async def handle_forget_callback(callback_data: str, user: dict) -> str:
    """Handle forget confirmation callback."""
    from src.services.data_deletion import delete_all_user_data, format_deletion_result

    if callback_data.startswith("forget_confirm:"):
        results = await delete_all_user_data(user.get("id"))
        return format_deletion_result(results)

    if callback_data == "forget_cancel":
        return "Data deletion cancelled. Your data is safe."

    return "Unknown action."
```

### 5. Update `main.py:process_message()` - Integrate Activity Logging

Add activity logging after message processing.

```python
# At the end of process_message(), before return:

    # Log activity (async, non-blocking)
    import asyncio
    try:
        from src.services.activity import log_activity

        # Determine action type and skill
        action_type = "chat"
        skill_used = None

        # Check what was routed to
        if pending_skill:
            action_type = "skill_invoke"
            skill_used = pending_skill
        elif mode == "routed" and hasattr(response, 'skill'):
            action_type = "skill_invoke"
            skill_used = response.skill

        # Fire and forget - don't block on logging
        asyncio.create_task(
            log_activity(
                user_id=user_id,
                action_type=action_type,
                summary=text[:100],
                skill=skill_used,
                duration_ms=int((time.time() - start) * 1000) if 'start' in locals() else 0
            )
        )
    except Exception as e:
        logger.warning("activity_log_failed", error=str(e)[:50])
```

## Tasks

- [ ] Create `src/services/activity.py`
- [ ] Create `src/core/suggestions.py`
- [ ] Create `src/services/data_deletion.py`
- [ ] Add `/activity` command handler
- [ ] Add `/suggest` command handler
- [ ] Add `/forget` command with confirmation keyboard
- [ ] Add callback handler for forget confirmation
- [ ] Integrate activity logging in process_message()
- [ ] Add unit tests for activity logging
- [ ] Add unit tests for suggestions
- [ ] Test full data deletion flow

## Validation Criteria

1. `/activity` shows recent user activities
2. `/activity stats` shows aggregated statistics
3. `/suggest` shows personalized suggestions
4. Suggestions include skill sequence predictions
5. `/forget` shows confirmation keyboard
6. Confirming deletion removes all personal data
7. Activity is logged after each message (non-blocking)
8. Qdrant data is deleted on /forget

## Notes

- Activity logging is fire-and-forget (non-blocking)
- Suggestions prioritize: reminders > context > sequences > time patterns
- Data deletion follows GDPR right to erasure
- Deletion confirmation prevents accidental data loss
- Firebase subcollection deletion has 500 item limit per batch
