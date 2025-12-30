"""User macros service - CRUD and NLU detection."""
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict
import uuid

from src.models.personalization import Macro, MacroActionType
from src.services.firebase import get_db, firestore
from src.services.embeddings import get_embedding
from src.utils.logging import get_logger

logger = get_logger()

# Semantic similarity threshold
SIMILARITY_THRESHOLD = float(os.environ.get("MACRO_SIMILARITY_THRESHOLD", "0.85"))
MAX_MACROS_PER_USER = 20
MAX_TRIGGERS_PER_MACRO = 10
MAX_TRIGGER_LENGTH = 100
MAX_ACTION_LENGTH = 1000


async def get_macros(user_id: int) -> List[Macro]:
    """Get all macros for user."""
    try:
        db = get_db()
        docs = db.collection("user_macros").document(str(user_id)) \
            .collection("macros").limit(MAX_MACROS_PER_USER).get()

        return [Macro.from_dict({**doc.to_dict(), "macro_id": doc.id})
                for doc in docs]
    except Exception as e:
        logger.error("get_macros_error", user_id=user_id, error=str(e)[:50])
        return []


async def get_macro(user_id: int, macro_id: str) -> Optional[Macro]:
    """Get specific macro by ID."""
    try:
        db = get_db()
        doc = db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).get()

        if doc.exists:
            return Macro.from_dict({**doc.to_dict(), "macro_id": doc.id})
        return None
    except Exception as e:
        logger.error("get_macro_error", error=str(e)[:50])
        return None


async def create_macro(
    user_id: int,
    trigger_phrases: List[str],
    action_type: MacroActionType,
    action: str,
    description: Optional[str] = None
) -> Optional[Macro]:
    """Create a new macro.

    Args:
        user_id: Telegram user ID
        trigger_phrases: List of phrases that trigger this macro
        action_type: command, skill, or sequence
        action: The action to execute
        description: Optional description

    Returns:
        Created Macro or None if limit reached or validation failed
    """
    # Input validation
    if not trigger_phrases:
        logger.warning("macro_no_triggers", user_id=user_id)
        return None

    if len(trigger_phrases) > MAX_TRIGGERS_PER_MACRO:
        logger.warning("macro_too_many_triggers", user_id=user_id, count=len(trigger_phrases))
        return None

    for t in trigger_phrases:
        if len(t) > MAX_TRIGGER_LENGTH:
            logger.warning("macro_trigger_too_long", user_id=user_id, length=len(t))
            return None

    if len(action) > MAX_ACTION_LENGTH:
        logger.warning("macro_action_too_long", user_id=user_id, length=len(action))
        return None

    # Check limit
    existing = await get_macros(user_id)
    if len(existing) >= MAX_MACROS_PER_USER:
        logger.warning("macro_limit_reached", user_id=user_id)
        return None

    # Check for duplicate triggers
    existing_triggers = set()
    for m in existing:
        existing_triggers.update(t.lower() for t in m.trigger_phrases)

    for phrase in trigger_phrases:
        if phrase.lower() in existing_triggers:
            logger.warning("duplicate_trigger", user_id=user_id, phrase=phrase)
            return None

    macro_id = str(uuid.uuid4())[:8]
    macro = Macro(
        macro_id=macro_id,
        user_id=user_id,
        trigger_phrases=[t.strip().lower() for t in trigger_phrases],
        action_type=action_type,
        action=action,
        description=description,
        created_at=datetime.now(timezone.utc),
        use_count=0
    )

    try:
        db = get_db()
        db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).set(macro.to_dict())

        logger.info("macro_created", user_id=user_id, macro_id=macro_id)
        return macro
    except Exception as e:
        logger.error("create_macro_error", error=str(e)[:50])
        return None


async def delete_macro(user_id: int, macro_id: str) -> bool:
    """Delete a macro."""
    try:
        db = get_db()
        db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).delete()

        logger.info("macro_deleted", user_id=user_id, macro_id=macro_id)
        return True
    except Exception as e:
        logger.error("delete_macro_error", error=str(e)[:50])
        return False


async def increment_use_count(user_id: int, macro_id: str) -> None:
    """Increment macro use count."""
    try:
        db = get_db()
        db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).update({
                "use_count": firestore.Increment(1)
            })
    except Exception as e:
        logger.error("increment_use_count_error", error=str(e)[:50])


async def detect_macro(user_id: int, message: str) -> Optional[Macro]:
    """Detect if message triggers a personal macro.

    Uses two-phase matching:
    1. Exact match (fast)
    2. Semantic similarity (if no exact match)

    Args:
        user_id: Telegram user ID
        message: User's message text

    Returns:
        Matched Macro or None
    """
    macros = await get_macros(user_id)
    if not macros:
        return None

    message_lower = message.lower().strip()

    # Phase 1: Exact match
    for macro in macros:
        for trigger in macro.trigger_phrases:
            if message_lower == trigger.lower():
                logger.info("macro_exact_match", user_id=user_id, trigger=trigger)
                return macro

    # Phase 2: Semantic similarity (only for short messages)
    if len(message_lower.split()) <= 5:
        return await _semantic_match(message_lower, macros)

    return None


async def _semantic_match(message: str, macros: List[Macro]) -> Optional[Macro]:
    """Find macro via semantic similarity."""
    try:
        message_embedding = get_embedding(message)

        best_match = None
        best_score = 0.0

        for macro in macros:
            for trigger in macro.trigger_phrases:
                trigger_embedding = get_embedding(trigger)
                score = _cosine_similarity(message_embedding, trigger_embedding)

                if score > best_score:
                    best_score = score
                    best_match = macro

        if best_score >= SIMILARITY_THRESHOLD:
            logger.info("macro_semantic_match", score=best_score, trigger=best_match.trigger_phrases[0])
            return best_match

        return None

    except Exception as e:
        logger.error("semantic_match_error", error=str(e)[:50])
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def format_macro_display(macro: Macro) -> str:
    """Format macro for Telegram display."""
    triggers = ", ".join(f'"{t}"' for t in macro.trigger_phrases)
    return f"""<b>Macro:</b> {macro.macro_id}
<b>Triggers:</b> {triggers}
<b>Type:</b> {macro.action_type}
<b>Action:</b> <code>{macro.action}</code>
<b>Uses:</b> {macro.use_count}"""


def format_macros_list(macros: List[Macro]) -> str:
    """Format macro list for Telegram display."""
    if not macros:
        return "<i>No macros defined. Use /macro add to create one.</i>"

    lines = ["<b>Your Macros</b>\n"]

    for m in macros:
        triggers = ", ".join(f'"{t}"' for t in m.trigger_phrases[:2])
        if len(m.trigger_phrases) > 2:
            triggers += f" (+{len(m.trigger_phrases) - 2})"
        lines.append(f"• <code>{m.macro_id}</code>: {triggers} → {m.action_type}")

    lines.append(f"\n<i>Use /macro show <id> for details</i>")
    return "\n".join(lines)
