"""Firebase/StateManager mocks for testing."""
from typing import Dict, Any, Optional, List, Tuple
import time


# Tier level mapping
TIER_LEVELS = {"guest": 0, "user": 1, "developer": 2, "admin": 3}
RATE_LIMITS = {"guest": 10, "user": 30, "developer": 100, "admin": 1000}


class MockStateManager:
    """Mock StateManager for testing without Firebase."""

    def __init__(self):
        self._tiers: Dict[int, str] = {}
        self._modes: Dict[int, str] = {}
        self._pending_skills: Dict[int, str] = {}
        self._l1_cache: Dict[str, Any] = {}
        self._rate_counters: Dict[int, List[float]] = {}

    async def get_user_tier_cached(self, user_id: int) -> str:
        return self._tiers.get(user_id, "guest")

    async def get_user_mode(self, user_id: int) -> str:
        return self._modes.get(user_id, "simple")

    async def set_user_mode(self, user_id: int, mode: str):
        self._modes[user_id] = mode

    async def get_pending_skill(self, user_id: int) -> Optional[str]:
        return self._pending_skills.get(user_id)

    async def clear_pending_skill(self, user_id: int):
        self._pending_skills.pop(user_id, None)

    async def clear_conversation(self, user_id: int):
        pass

    async def invalidate_user_tier(self, user_id: int):
        self._tiers.pop(user_id, None)

    def check_rate_limit(self, user_id: int, tier: str) -> Tuple[bool, int]:
        """Check rate limit - always allow in mock unless explicitly set."""
        now = time.time()
        limit = RATE_LIMITS.get(tier, 10)

        # Clean old entries
        if user_id in self._rate_counters:
            self._rate_counters[user_id] = [
                t for t in self._rate_counters[user_id] if now - t < 60
            ]
        else:
            self._rate_counters[user_id] = []

        if len(self._rate_counters[user_id]) >= limit:
            return (False, 60)

        self._rate_counters[user_id].append(now)
        return (True, 0)

    # Test helpers
    def set_tier(self, user_id: int, tier: str):
        self._tiers[user_id] = tier

    def set_mode(self, user_id: int, mode: str):
        self._modes[user_id] = mode

    def set_pending_skill(self, user_id: int, skill: str):
        self._pending_skills[user_id] = skill


def mock_has_permission(tier: str, required: str) -> bool:
    """Check if tier has required permission level."""
    return TIER_LEVELS.get(tier, 0) >= TIER_LEVELS.get(required, 0)


def mock_get_rate_limit(tier: str) -> int:
    """Get rate limit for tier."""
    return RATE_LIMITS.get(tier, 10)
