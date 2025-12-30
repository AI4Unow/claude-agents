# Phase 1: Core Infrastructure

**Duration:** 3-4 days
**Dependencies:** None
**Output:** Core personalization module, data models, context loader

## Objectives

1. Create data models for personalization entities
2. Implement PersonalContextLoader with parallel fetching
3. Implement PromptBuilder for system prompt injection
4. Add new Qdrant collection for user activities
5. Update StateManager with profile/context caching

## Files to Create

### 1. `src/models/personalization.py`

Data classes for personalization entities.

```python
"""Personalization data models."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Literal

ToneType = Literal["concise", "detailed", "casual", "formal"]
ResponseLength = Literal["short", "medium", "long"]
MacroActionType = Literal["command", "skill", "sequence"]


@dataclass
class CommunicationPrefs:
    """User communication preferences."""
    use_emoji: bool = False
    markdown_preference: bool = True
    response_length: ResponseLength = "short"


@dataclass
class UserProfile:
    """User profile for personalization."""
    user_id: int
    name: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    tone: ToneType = "concise"
    domain: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    communication: CommunicationPrefs = field(default_factory=CommunicationPrefs)
    onboarded: bool = False
    onboarded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "timezone": self.timezone,
            "language": self.language,
            "tone": self.tone,
            "domain": self.domain,
            "tech_stack": self.tech_stack,
            "communication": {
                "use_emoji": self.communication.use_emoji,
                "markdown_preference": self.communication.markdown_preference,
                "response_length": self.communication.response_length,
            },
            "onboarded": self.onboarded,
            "onboarded_at": self.onboarded_at.isoformat() if self.onboarded_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        comm = data.get("communication", {})
        return cls(
            user_id=data.get("user_id", 0),
            name=data.get("name"),
            timezone=data.get("timezone", "UTC"),
            language=data.get("language", "en"),
            tone=data.get("tone", "concise"),
            domain=data.get("domain", []),
            tech_stack=data.get("tech_stack", []),
            communication=CommunicationPrefs(
                use_emoji=comm.get("use_emoji", False),
                markdown_preference=comm.get("markdown_preference", True),
                response_length=comm.get("response_length", "short"),
            ),
            onboarded=data.get("onboarded", False),
            onboarded_at=datetime.fromisoformat(data["onboarded_at"]) if data.get("onboarded_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )


@dataclass
class WorkContext:
    """Current work context for user."""
    user_id: int
    current_project: Optional[str] = None
    current_task: Optional[str] = None
    active_branch: Optional[str] = None
    recent_skills: List[str] = field(default_factory=list)
    session_facts: List[str] = field(default_factory=list)
    last_active: Optional[datetime] = None
    session_start: Optional[datetime] = None

    MAX_RECENT_SKILLS = 5
    MAX_SESSION_FACTS = 10

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "current_project": self.current_project,
            "current_task": self.current_task,
            "active_branch": self.active_branch,
            "recent_skills": self.recent_skills[-self.MAX_RECENT_SKILLS:],
            "session_facts": self.session_facts[-self.MAX_SESSION_FACTS:],
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "session_start": self.session_start.isoformat() if self.session_start else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkContext":
        return cls(
            user_id=data.get("user_id", 0),
            current_project=data.get("current_project"),
            current_task=data.get("current_task"),
            active_branch=data.get("active_branch"),
            recent_skills=data.get("recent_skills", []),
            session_facts=data.get("session_facts", []),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else None,
            session_start=datetime.fromisoformat(data["session_start"]) if data.get("session_start") else None,
        )


@dataclass
class Macro:
    """Personal macro for shortcuts."""
    macro_id: str
    user_id: int
    trigger_phrases: List[str]
    action_type: MacroActionType
    action: str  # command string, skill name, or sequence JSON
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    use_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "macro_id": self.macro_id,
            "user_id": self.user_id,
            "trigger_phrases": self.trigger_phrases,
            "action_type": self.action_type,
            "action": self.action,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "use_count": self.use_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Macro":
        return cls(
            macro_id=data.get("macro_id", ""),
            user_id=data.get("user_id", 0),
            trigger_phrases=data.get("trigger_phrases", []),
            action_type=data.get("action_type", "command"),
            action=data.get("action", ""),
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            use_count=data.get("use_count", 0),
        )


@dataclass
class PersonalContext:
    """Aggregated personalization context."""
    profile: Optional[UserProfile] = None
    work_context: Optional[WorkContext] = None
    macros: List[Macro] = field(default_factory=list)
    memories: List[Dict] = field(default_factory=list)

    @property
    def is_onboarded(self) -> bool:
        return self.profile is not None and self.profile.onboarded

    @property
    def has_macros(self) -> bool:
        return len(self.macros) > 0
```

### 2. `src/services/personalization.py`

Core personalization loader and prompt builder.

```python
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
        if context.last_active < timeout_threshold:
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
        docs = db.collection("user_macros").document(str(user_id)) \
            .collection("macros").limit(20).get()

        return [Macro.from_dict({**doc.to_dict(), "macro_id": doc.id})
                for doc in docs]
    except Exception as e:
        logger.error("get_user_macros_error", error=str(e)[:50])
        return []


async def _get_relevant_memories(user_id: int, limit: int = 3) -> List[Dict]:
    """Get relevant memories from Qdrant conversations collection."""
    # This will be enhanced in Phase 4 to use semantic search
    # For now, just get recent conversations
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
```

### 3. Updates to `src/services/qdrant.py`

Add user_activities collection.

```python
# Add to COLLECTIONS dict (line 25-31):
COLLECTIONS = {
    "skills": "Semantic skill matching for routing",
    "knowledge": "Cross-skill insights and learnings",
    "conversations": "Chat history for context",
    "errors": "Error pattern matching",
    "tasks": "Task context for similar task lookup",
    "user_activities": "User activity patterns for learning",  # NEW
}

# Add to init_collections() (line 67):
collections = ["conversations", "knowledge", "tasks", "user_activities"]

# Add new functions after line 405:

# ==================== User Activities ====================

async def store_user_activity(
    user_id: int,
    action_type: str,
    summary: str,
    embedding: List[float],
    skill: Optional[str] = None,
    duration_ms: int = 0
) -> Optional[str]:
    """Store user activity for pattern learning."""
    client = get_client()
    if not client:
        return None

    from qdrant_client.http import models

    point_id = f"{user_id}_{datetime.utcnow().timestamp()}"

    client.upsert(
        collection_name="user_activities",
        points=[
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "user_id": user_id,
                    "action_type": action_type,
                    "skill": skill,
                    "summary": summary,
                    "timestamp": datetime.utcnow().isoformat(),
                    "hour_of_day": datetime.utcnow().hour,
                    "day_of_week": datetime.utcnow().weekday(),
                    "duration_ms": duration_ms
                }
            )
        ]
    )

    return point_id


async def search_user_activities(
    user_id: int,
    embedding: List[float],
    limit: int = 5
) -> List[Dict]:
    """Search user's past activities."""
    client = get_client()
    if not client:
        return []

    from qdrant_client.http import models

    filter_conditions = models.Filter(
        must=[
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id)
            )
        ]
    )

    results = client.search(
        collection_name="user_activities",
        query_vector=embedding,
        query_filter=filter_conditions,
        limit=limit
    )

    return [
        {
            "id": r.id,
            "score": r.score,
            **r.payload
        }
        for r in results
    ]
```

### 4. Updates to `src/core/state.py`

Add profile/context caching methods.

```python
# Add after line 282 (after set_user_mode):

# ==================== Profile & Context Methods ====================

TTL_PROFILE = 300   # 5 minutes
TTL_CONTEXT = 60    # 1 minute

async def get_user_profile(self, user_id: int) -> Optional[Dict]:
    """Get user profile with caching."""
    if not user_id:
        return None
    return await self.get(
        "user_profiles",
        str(user_id),
        ttl_seconds=self.TTL_PROFILE
    )

async def set_user_profile(self, user_id: int, data: Dict):
    """Update user profile."""
    if not user_id:
        return
    await self.set(
        "user_profiles",
        str(user_id),
        data,
        ttl_seconds=self.TTL_PROFILE
    )

async def get_work_context(self, user_id: int) -> Optional[Dict]:
    """Get work context with short TTL caching."""
    if not user_id:
        return None
    return await self.get(
        "user_contexts",
        str(user_id),
        ttl_seconds=self.TTL_CONTEXT
    )

async def set_work_context(self, user_id: int, data: Dict):
    """Update work context."""
    if not user_id:
        return
    await self.set(
        "user_contexts",
        str(user_id),
        data,
        ttl_seconds=self.TTL_CONTEXT
    )
```

## Tasks

- [ ] Create `src/models/__init__.py`
- [ ] Create `src/models/personalization.py` with data classes
- [ ] Create `src/services/personalization.py` with loader + builder
- [ ] Update `src/services/qdrant.py` with user_activities collection
- [ ] Update `src/core/state.py` with profile/context methods
- [ ] Add unit tests for PersonalContext loading
- [ ] Add unit tests for prompt building
- [ ] Test parallel fetch performance (< 50ms target)

## Validation Criteria

1. `load_personal_context()` completes in < 50ms (parallel fetch)
2. `build_personalized_prompt()` adds < 500 tokens to system prompt
3. New Qdrant collection `user_activities` created on deploy
4. L1 cache hit rate > 80% for profile data

## Notes

- Profile caching uses 5-min TTL (user rarely changes preferences)
- Context caching uses 1-min TTL (more dynamic)
- Macros are fetched fresh each time (low cost, high importance)
- Memories are fetched from Qdrant with fallback to empty list
