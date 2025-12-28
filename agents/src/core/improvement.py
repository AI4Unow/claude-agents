"""Self-improvement service for II Framework skills.

AgentEx Pattern: Human-in-the-loop improvement proposals.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import uuid

from src.utils.logging import get_logger

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

    @classmethod
    def from_dict(cls, data: Dict) -> "ImprovementProposal":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            created_at = datetime.now(timezone.utc)

        return cls(
            id=data["id"],
            skill_name=data["skill_name"],
            error_summary=data.get("error_summary", ""),
            error_full=data.get("error_full", ""),
            proposed_memory_addition=data.get("proposed_memory_addition", ""),
            proposed_error_entry=data.get("proposed_error_entry", ""),
            current_memory=data.get("current_memory", ""),
            current_error_history=data.get("current_error_history", ""),
            status=data.get("status", "pending"),
            created_at=created_at,
            admin_id=data.get("admin_id"),
            rejection_reason=data.get("rejection_reason"),
        )


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
            from src.services.firebase import init_firebase
            self._db = init_firebase()
        return self._db

    def _get_llm(self):
        if self._llm is None:
            from src.services.llm import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    async def _check_rate_limit(self, skill_name: str) -> bool:
        """Check if under rate limit (max 3/hour/skill)."""
        import asyncio
        try:
            db = self._get_db()
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

            docs = await asyncio.to_thread(
                lambda: list(db.collection(self.COLLECTION)
                    .where("skill_name", "==", skill_name)
                    .where("created_at", ">=", one_hour_ago.isoformat())
                    .limit(self.RATE_LIMIT_HOUR + 1)
                    .get())
            )
            return len(docs) < self.RATE_LIMIT_HOUR
        except Exception as e:
            self.logger.error("rate_limit_check_failed", error=str(e))
            return True  # Allow on error

    async def _is_duplicate(self, skill_name: str, error: str) -> bool:
        """Check if similar error already proposed in last 24h."""
        import asyncio
        try:
            db = self._get_db()
            one_day_ago = datetime.now(timezone.utc) - timedelta(hours=self.DEDUP_HOURS)

            docs = await asyncio.to_thread(
                lambda: list(db.collection(self.COLLECTION)
                    .where("skill_name", "==", skill_name)
                    .where("created_at", ">=", one_day_ago.isoformat())
                    .limit(20)
                    .get())
            )

            error_lower = error.lower()[:100]
            for doc in docs:
                existing = doc.to_dict().get("error_summary", "").lower()[:100]
                if error_lower in existing or existing in error_lower:
                    return True
            return False
        except Exception as e:
            self.logger.error("dedup_check_failed", error=str(e))
            return False  # Allow on error

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
        from src.skills.registry import get_registry
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
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            if response.endswith("```"):
                response = response[:-3]

            data = json.loads(response.strip())

            proposal_id = str(uuid.uuid4())[:8]
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
            proposal_id = str(uuid.uuid4())[:8]
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
        try:
            db = self._get_db()
            await asyncio.to_thread(
                lambda: db.collection(self.COLLECTION).document(proposal.id).set(proposal.to_dict())
            )
            self.logger.info("proposal_stored", id=proposal.id, skill=proposal.skill_name)
            return proposal.id
        except Exception as e:
            self.logger.error("proposal_store_failed", error=str(e))
            return proposal.id

    async def approve_proposal(self, proposal_id: str, admin_id: int) -> bool:
        """Mark proposal as approved (for local application later).

        Local-First Flow: Admin approves → marked in Firebase →
        local script pulls and applies to agents/skills/ → commit → deploy.
        """
        import asyncio

        try:
            db = self._get_db()

            doc = await asyncio.to_thread(
                lambda: db.collection(self.COLLECTION).document(proposal_id).get()
            )
            if not doc.exists:
                self.logger.warning("proposal_not_found", id=proposal_id)
                return False

            data = doc.to_dict()
            skill_name = data["skill_name"]

            # Mark as approved (NOT applied yet - local script will apply)
            await asyncio.to_thread(
                lambda: db.collection(self.COLLECTION).document(proposal_id).update({
                    "status": "approved",
                    "admin_id": admin_id,
                    "approved_at": datetime.now(timezone.utc).isoformat()
                })
            )

            self.logger.info("proposal_approved", id=proposal_id, skill=skill_name, admin=admin_id)
            return True
        except Exception as e:
            self.logger.error("approve_proposal_failed", error=str(e))
            return False

    async def get_approved_proposals(self, limit: int = 50) -> list:
        """Get approved (not yet applied) proposals for local application."""
        import asyncio
        try:
            db = self._get_db()
            docs = await asyncio.to_thread(
                lambda: list(db.collection(self.COLLECTION)
                    .where("status", "==", "approved")
                    .order_by("approved_at")
                    .limit(limit)
                    .get())
            )
            return [ImprovementProposal.from_dict(doc.to_dict()) for doc in docs]
        except Exception as e:
            self.logger.error("get_approved_failed", error=str(e))
            return []

    async def mark_applied(self, proposal_id: str) -> bool:
        """Mark proposal as applied (after local script applies it)."""
        import asyncio
        try:
            db = self._get_db()
            await asyncio.to_thread(
                lambda: db.collection(self.COLLECTION).document(proposal_id).update({
                    "status": "applied",
                    "applied_at": datetime.now(timezone.utc).isoformat()
                })
            )
            self.logger.info("proposal_marked_applied", id=proposal_id)
            return True
        except Exception as e:
            self.logger.error("mark_applied_failed", error=str(e))
            return False

    # Keep legacy method for backwards compatibility
    async def apply_proposal(self, proposal_id: str, admin_id: int) -> bool:
        """Legacy: Approve proposal (renamed for clarity).

        Note: This now only marks as approved. Use pull-improvements.py
        to apply locally and commit to git.
        """
        return await self.approve_proposal(proposal_id, admin_id)

    async def reject_proposal(self, proposal_id: str, admin_id: int, reason: str = "") -> bool:
        """Reject a proposal."""
        import asyncio
        try:
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
        except Exception as e:
            self.logger.error("reject_proposal_failed", error=str(e))
            return False

    async def get_proposal(self, proposal_id: str) -> Optional[ImprovementProposal]:
        """Get proposal by ID."""
        import asyncio
        try:
            db = self._get_db()
            doc = await asyncio.to_thread(
                lambda: db.collection(self.COLLECTION).document(proposal_id).get()
            )
            if doc.exists:
                return ImprovementProposal.from_dict(doc.to_dict())
            return None
        except Exception as e:
            self.logger.error("get_proposal_failed", error=str(e))
            return None

    async def get_pending_proposals(self, limit: int = 10) -> list:
        """Get pending proposals for admin review."""
        import asyncio
        try:
            db = self._get_db()
            docs = await asyncio.to_thread(
                lambda: list(db.collection(self.COLLECTION)
                    .where("status", "==", "pending")
                    .order_by("created_at", direction="DESCENDING")
                    .limit(limit)
                    .get())
            )
            return [ImprovementProposal.from_dict(doc.to_dict()) for doc in docs]
        except Exception as e:
            self.logger.error("get_pending_failed", error=str(e))
            return []


# Singleton
_improvement_service: Optional[ImprovementService] = None


def get_improvement_service() -> ImprovementService:
    """Get singleton ImprovementService."""
    global _improvement_service
    if _improvement_service is None:
        _improvement_service = ImprovementService()
    return _improvement_service
