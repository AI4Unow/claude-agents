# Phase 3: ImprovementService Core

## Context

- Plan: `./plan.md`
- Depends on: Phase 1, 2 complete (or can run in parallel)

## Overview

- **Priority:** P1
- **Status:** Pending
- **Effort:** 4h

Create ImprovementService for LLM-based error reflection and proposal generation.

## Key Insights

- SkillRegistry already has update_memory() and add_error() methods
- TraceContext in agentic.py captures tool errors
- Need LLM call to analyze error and suggest improvement
- Store proposals in Firebase for admin review
- Rate limiting needed to prevent spam

## Requirements

### Functional
- Analyze errors and generate improvement proposals
- Store proposals in Firebase (skill_improvements collection)
- Rate limit: max 3 proposals per skill per hour
- Deduplicate similar errors (fuzzy matching)
- Return proposal ID for later approval/rejection

### Non-Functional
- Async operations for non-blocking
- Structured logging throughout
- Graceful degradation if Firebase unavailable

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ImprovementService                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  analyze_error(skill_name, error, context)                           │
│       │                                                              │
│       ├── Check rate limit (max 3/hour/skill)                        │
│       ├── Check deduplication (skip if same error in 24h)            │
│       ├── Load current skill info.md                                 │
│       ├── Call LLM with reflection prompt                            │
│       └── Return ImprovementProposal                                 │
│                                                                      │
│  store_proposal(proposal) -> proposal_id                             │
│       │                                                              │
│       └── Write to Firebase: skill_improvements/{proposal_id}        │
│                                                                      │
│  apply_proposal(proposal_id) -> bool                                 │
│       │                                                              │
│       ├── Load proposal from Firebase                                │
│       ├── Update skill info.md (Memory + Error History)              │
│       ├── Commit to Modal Volume                                     │
│       └── Mark proposal as approved in Firebase                      │
│                                                                      │
│  reject_proposal(proposal_id, reason) -> bool                        │
│       │                                                              │
│       └── Mark proposal as rejected in Firebase                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Firebase Schema

```javascript
// skill_improvements/{proposal_id}
{
  id: "uuid",
  skill_name: "telegram-chat",
  error_summary: "Tool web_search failed: API timeout",
  error_full: "...",
  proposed_memory_addition: "When web search times out, retry once before failing.",
  proposed_error_entry: "2025-12-28: web_search timeout - added retry guidance",
  current_memory: "...",
  current_error_history: "...",
  status: "pending",  // pending | approved | rejected
  created_at: timestamp,
  updated_at: timestamp,
  admin_id: null,  // Set when approved/rejected
  rejection_reason: null
}
```

## Related Code Files

### Create
- `agents/src/core/improvement.py` - ImprovementService class

### Modify
- `agents/requirements.txt` - Add any new deps if needed

## Implementation Steps

1. Create ImprovementProposal dataclass
2. Implement ImprovementService class:
   - `__init__` with LLM client, Firebase client
   - `_check_rate_limit(skill_name)` - max 3/hour
   - `_is_duplicate(skill_name, error)` - fuzzy match in 24h
   - `_generate_reflection(skill_name, error, context)` - LLM call
   - `analyze_error()` - main entry point
   - `store_proposal()` - Firebase write
   - `apply_proposal()` - Update info.md
   - `reject_proposal()` - Mark rejected
3. Add reflection prompt template
4. Add singleton accessor function

## Code Skeleton

```python
# agents/src/core/improvement.py

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import uuid

from src.utils.logging import get_logger
from src.services.llm import get_llm_client
from src.skills.registry import get_registry

logger = get_logger()


@dataclass
class ImprovementProposal:
    """Proposal for skill improvement."""
    id: str
    skill_name: str
    error_summary: str
    error_full: str
    proposed_memory_addition: str
    proposed_error_entry: str
    current_memory: str
    current_error_history: str
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    admin_id: Optional[int] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "error_summary": self.error_summary,
            "error_full": self.error_full,
            "proposed_memory_addition": self.proposed_memory_addition,
            "proposed_error_entry": self.proposed_error_entry,
            "current_memory": self.current_memory,
            "current_error_history": self.current_error_history,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "admin_id": self.admin_id,
            "rejection_reason": self.rejection_reason,
        }


class ImprovementService:
    """Service for skill self-improvement with human-in-the-loop."""

    COLLECTION = "skill_improvements"
    RATE_LIMIT_HOUR = 3
    DEDUP_HOURS = 24

    def __init__(self):
        self._db = None
        self._llm = None
        self.logger = logger.bind(component="ImprovementService")

    def _get_db(self):
        if self._db is None:
            from src.services.firebase import get_db
            self._db = get_db()
        return self._db

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    async def _check_rate_limit(self, skill_name: str) -> bool:
        """Check if under rate limit (max 3/hour/skill)."""
        import asyncio
        db = self._get_db()
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        docs = await asyncio.to_thread(
            lambda: db.collection(self.COLLECTION)
                .where("skill_name", "==", skill_name)
                .where("created_at", ">=", one_hour_ago.isoformat())
                .get()
        )
        return len(list(docs)) < self.RATE_LIMIT_HOUR

    async def _is_duplicate(self, skill_name: str, error: str) -> bool:
        """Check if similar error already proposed in last 24h."""
        import asyncio
        db = self._get_db()
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=self.DEDUP_HOURS)

        docs = await asyncio.to_thread(
            lambda: db.collection(self.COLLECTION)
                .where("skill_name", "==", skill_name)
                .where("created_at", ">=", one_day_ago.isoformat())
                .get()
        )

        error_lower = error.lower()[:100]
        for doc in docs:
            existing = doc.to_dict().get("error_summary", "").lower()[:100]
            # Simple substring match for deduplication
            if error_lower in existing or existing in error_lower:
                return True
        return False

    async def analyze_error(
        self,
        skill_name: str,
        error: str,
        context: Optional[Dict] = None
    ) -> Optional[ImprovementProposal]:
        """Analyze error and generate improvement proposal."""
        self.logger.info("analyzing_error", skill=skill_name, error=error[:100])

        # Rate limit check
        if not await self._check_rate_limit(skill_name):
            self.logger.warning("rate_limited", skill=skill_name)
            return None

        # Deduplication check
        if await self._is_duplicate(skill_name, error):
            self.logger.info("duplicate_error", skill=skill_name)
            return None

        # Load current skill
        registry = get_registry()
        skill = registry.get_full(skill_name)
        if not skill:
            self.logger.warning("skill_not_found", skill=skill_name)
            return None

        # Generate reflection via LLM
        proposal = await self._generate_reflection(skill, error, context)
        return proposal

    async def _generate_reflection(
        self,
        skill,
        error: str,
        context: Optional[Dict]
    ) -> ImprovementProposal:
        """Use LLM to reflect on error and propose improvement."""
        llm = self._get_llm()

        prompt = f"""You are analyzing an error that occurred while using a skill.

SKILL NAME: {skill.name}
SKILL DESCRIPTION: {skill.description}

CURRENT MEMORY:
{skill.memory or "(empty)"}

CURRENT ERROR HISTORY:
{skill.error_history or "(none)"}

ERROR THAT OCCURRED:
{error}

CONTEXT:
{context or "(none)"}

Based on this error, provide:
1. A brief learning to add to the Memory section (1-2 sentences)
2. An error history entry (format: "error description - fix/learning")

Respond in this exact JSON format:
{{
  "memory_addition": "What I learned from this error...",
  "error_entry": "Error description - how to prevent/handle"
}}

Be concise and actionable. Focus on preventing this error in the future."""

        try:
            response = llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )

            import json
            # Parse JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            if response.endswith("```"):
                response = response[:-3]

            data = json.loads(response.strip())

            proposal_id = str(uuid.uuid4())
            date_str = datetime.now().strftime('%Y-%m-%d')

            return ImprovementProposal(
                id=proposal_id,
                skill_name=skill.name,
                error_summary=error[:200],
                error_full=error,
                proposed_memory_addition=data.get("memory_addition", ""),
                proposed_error_entry=f"{date_str}: {data.get('error_entry', error[:50])}",
                current_memory=skill.memory,
                current_error_history=skill.error_history,
            )

        except Exception as e:
            self.logger.error("reflection_failed", error=str(e))
            # Fallback proposal
            proposal_id = str(uuid.uuid4())
            date_str = datetime.now().strftime('%Y-%m-%d')

            return ImprovementProposal(
                id=proposal_id,
                skill_name=skill.name,
                error_summary=error[:200],
                error_full=error,
                proposed_memory_addition=f"Error occurred: {error[:100]}",
                proposed_error_entry=f"{date_str}: {error[:100]} - review needed",
                current_memory=skill.memory,
                current_error_history=skill.error_history,
            )

    async def store_proposal(self, proposal: ImprovementProposal) -> str:
        """Store proposal in Firebase."""
        import asyncio
        db = self._get_db()

        await asyncio.to_thread(
            lambda: db.collection(self.COLLECTION).document(proposal.id).set(proposal.to_dict())
        )

        self.logger.info("proposal_stored", id=proposal.id, skill=proposal.skill_name)
        return proposal.id

    async def apply_proposal(self, proposal_id: str, admin_id: int) -> bool:
        """Apply approved proposal to skill info.md."""
        import asyncio
        db = self._get_db()

        # Load proposal
        doc = await asyncio.to_thread(
            lambda: db.collection(self.COLLECTION).document(proposal_id).get()
        )
        if not doc.exists:
            self.logger.warning("proposal_not_found", id=proposal_id)
            return False

        data = doc.to_dict()
        skill_name = data["skill_name"]

        # Update skill
        registry = get_registry()

        # Add to memory
        new_memory = data["current_memory"]
        if new_memory:
            new_memory += "\n"
        new_memory += data["proposed_memory_addition"]
        registry.update_memory(skill_name, new_memory)

        # Add to error history
        registry.add_error(
            skill_name,
            data["error_summary"][:50],
            data["proposed_memory_addition"][:50]
        )

        # Update proposal status
        await asyncio.to_thread(
            lambda: db.collection(self.COLLECTION).document(proposal_id).update({
                "status": "approved",
                "admin_id": admin_id,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
        )

        self.logger.info("proposal_applied", id=proposal_id, skill=skill_name, admin=admin_id)
        return True

    async def reject_proposal(self, proposal_id: str, admin_id: int, reason: str = "") -> bool:
        """Reject a proposal."""
        import asyncio
        db = self._get_db()

        await asyncio.to_thread(
            lambda: db.collection(self.COLLECTION).document(proposal_id).update({
                "status": "rejected",
                "admin_id": admin_id,
                "rejection_reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
        )

        self.logger.info("proposal_rejected", id=proposal_id, admin=admin_id)
        return True

    async def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """Get proposal by ID."""
        import asyncio
        db = self._get_db()

        doc = await asyncio.to_thread(
            lambda: db.collection(self.COLLECTION).document(proposal_id).get()
        )
        return doc.to_dict() if doc.exists else None


# Singleton
_improvement_service: Optional[ImprovementService] = None


def get_improvement_service() -> ImprovementService:
    """Get singleton ImprovementService."""
    global _improvement_service
    if _improvement_service is None:
        _improvement_service = ImprovementService()
    return _improvement_service
```

## Todo List

- [ ] Create ImprovementProposal dataclass
- [ ] Implement ImprovementService class
- [ ] Add rate limiting logic
- [ ] Add deduplication logic
- [ ] Implement LLM reflection prompt
- [ ] Implement store_proposal()
- [ ] Implement apply_proposal()
- [ ] Implement reject_proposal()
- [ ] Add singleton accessor
- [ ] Test with sample error

## Success Criteria

- analyze_error() returns valid proposal
- Rate limiting works (max 3/hour/skill)
- Deduplication prevents spam
- Firebase writes succeed
- apply_proposal() updates info.md

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM reflection fails | Medium | Fallback proposal with raw error |
| Firebase unavailable | High | Log and skip, don't crash |
| Malformed LLM response | Medium | JSON parsing with fallback |

## Next Steps

After this phase, proceed to Phase 4: Telegram Admin Notifications
