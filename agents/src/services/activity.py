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
        if db:
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
        if not db:
            return []

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
        if not db:
            return []

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
        if not db:
            return {"morning": [], "afternoon": [], "evening": []}

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
        if not db:
            return {"total": 0}

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
            "action_types": dict(Counter(a.get("action_type", "unknown") for a in activities))
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
