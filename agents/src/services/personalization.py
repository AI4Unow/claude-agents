"""Personalization service - Context loading and prompt building."""
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta

from src.models.personalization import (
    PersonalContext, UserProfile, WorkContext, Macro
)
from src.core.state import get_state_manager
from src.utils.logging import get_logger

logger = get_logger()

# Token budgets per section
TOKEN_BUDGET_PROFILE = 100
TOKEN_BUDGET_CONTEXT = 150
TOKEN_BUDGET_MEMORIES = 200

# Session timeout (2 hours)
SESSION_TIMEOUT_HOURS = 2


async def load_personal_context(user_id: int) -> PersonalContext:
    """Load all personalization data in parallel.

    Args:
        user_id: Telegram user ID

    Returns:
        PersonalContext with all available data
    """
    if not user_id:
        return PersonalContext()

    # Parallel fetch all personalization data
    profile_task = _get_user_profile(user_id)
    context_task = _get_work_context(user_id)
    macros_task = _get_user_macros(user_id)
    memories_task = _get_relevant_memories(user_id)

    profile, context, macros, memories = await asyncio.gather(
        profile_task,
        context_task,
        macros_task,
        memories_task,
        return_exceptions=True
    )

    # Handle exceptions gracefully
    if isinstance(profile, Exception):
        logger.warning("profile_load_failed", error=str(profile)[:50])
        profile = None
    if isinstance(context, Exception):
        logger.warning("context_load_failed", error=str(context)[:50])
        context = None
    if isinstance(macros, Exception):
        logger.warning("macros_load_failed", error=str(macros)[:50])
        macros = []
    if isinstance(memories, Exception):
        logger.warning("memories_load_failed", error=str(memories)[:50])
        memories = []

    # Check session timeout
    if context and context.last_active:
        timeout_threshold = datetime.now(timezone.utc) - timedelta(hours=SESSION_TIMEOUT_HOURS)
        # Handle timezone-naive datetimes
        last_active = context.last_active
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        if last_active < timeout_threshold:
            logger.info("session_timeout", user_id=user_id)
            context = WorkContext(user_id=user_id)  # Reset context

    return PersonalContext(
        profile=profile,
        work_context=context,
        macros=macros or [],
        memories=memories or []
    )


async def _get_user_profile(user_id: int) -> Optional[UserProfile]:
    """Get user profile from Firebase with caching."""
    state = get_state_manager()
    data = await state.get("user_profiles", str(user_id), ttl_seconds=300)
    if data:
        return UserProfile.from_dict(data)
    return None


async def _get_work_context(user_id: int) -> Optional[WorkContext]:
    """Get work context from Firebase with caching."""
    state = get_state_manager()
    data = await state.get("user_contexts", str(user_id), ttl_seconds=60)
    if data:
        return WorkContext.from_dict(data)
    return None


async def _get_user_macros(user_id: int) -> List[Macro]:
    """Get user macros from Firebase."""
    from src.services.firebase import get_db

    try:
        db = get_db()
        if not db:
            return []
        docs = db.collection("user_macros").document(str(user_id)) \
            .collection("macros").limit(20).get()

        return [Macro.from_dict({**doc.to_dict(), "macro_id": doc.id})
                for doc in docs]
    except Exception as e:
        logger.error("get_user_macros_error", error=str(e)[:50])
        return []


async def _get_relevant_memories(user_id: int, limit: int = 3) -> List[Dict]:
    """Get relevant memories from Qdrant conversations collection."""
    from src.services.qdrant import search_conversations
    from src.services.embeddings import get_embedding

    try:
        # Use a generic query to get recent context
        embedding = get_embedding("recent conversation context")
        results = await search_conversations(
            embedding=embedding,
            user_id=str(user_id),
            limit=limit
        )
        return results
    except Exception as e:
        logger.error("get_memories_error", error=str(e)[:50])
        return []


def build_personalized_prompt(
    base_prompt: str,
    personal_ctx: PersonalContext
) -> str:
    """Build personalized system prompt.

    Args:
        base_prompt: Base system prompt
        personal_ctx: User's personal context

    Returns:
        Personalized system prompt
    """
    sections = [base_prompt]

    # Add profile context
    if personal_ctx.profile:
        profile_section = _format_profile_section(personal_ctx.profile)
        if profile_section:
            sections.append(profile_section)

    # Add work context
    if personal_ctx.work_context:
        context_section = _format_context_section(personal_ctx.work_context)
        if context_section:
            sections.append(context_section)

    # Add relevant memories
    if personal_ctx.memories:
        memory_section = _format_memory_section(personal_ctx.memories)
        if memory_section:
            sections.append(memory_section)

    return "\n\n".join(sections)


def _format_profile_section(profile: UserProfile) -> str:
    """Format profile for system prompt injection."""
    lines = ["## User Preferences"]

    if profile.name:
        lines.append(f"- Name: {profile.name}")
    if profile.tone:
        lines.append(f"- Communication style: {profile.tone}")
    if profile.domain:
        lines.append(f"- Domain expertise: {', '.join(profile.domain[:3])}")
    if profile.tech_stack:
        lines.append(f"- Tech stack: {', '.join(profile.tech_stack[:5])}")
    if profile.communication:
        if not profile.communication.use_emoji:
            lines.append("- Do NOT use emojis in responses")
        lines.append(f"- Response length: {profile.communication.response_length}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _format_context_section(context: WorkContext) -> str:
    """Format work context for system prompt injection."""
    lines = ["## Current Context"]

    if context.current_project:
        lines.append(f"- Working on project: {context.current_project}")
    if context.current_task:
        lines.append(f"- Current task: {context.current_task}")
    if context.active_branch:
        lines.append(f"- Git branch: {context.active_branch}")
    if context.session_facts:
        facts = context.session_facts[-3:]  # Last 3 facts
        lines.append(f"- Session facts: {'; '.join(facts)}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _format_memory_section(memories: List[Dict]) -> str:
    """Format memories for system prompt injection."""
    if not memories:
        return ""

    lines = ["## Relevant Past Context"]

    for mem in memories[:3]:
        content = mem.get("content", "")[:100]
        if content:
            lines.append(f"- {content}")

    return "\n".join(lines) if len(lines) > 1 else ""
