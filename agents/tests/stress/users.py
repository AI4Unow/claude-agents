"""Synthetic user pool management for stress tests."""

import random
from typing import Literal, Tuple
from .config import config

Tier = Literal["guest", "user", "developer", "admin"]


class UserPool:
    """Manages synthetic user allocation by tier."""

    # Tier distribution weights (must sum to 100)
    DISTRIBUTION = {
        "guest": 80,      # 80% of traffic
        "user": 15,       # 15% of traffic
        "developer": 4,   # 4% of traffic
        "admin": 1,       # 1% of traffic
    }

    def __init__(self):
        """Initialize user pool with config ranges."""
        self._pools = {
            "guest": list(range(config.guest_start, config.guest_end)),
            "user": list(range(config.user_start, config.user_end)),
            "developer": list(range(config.developer_start, config.developer_end)),
            "admin": [config.admin_id],
        }

    def get_user(self, tier: Tier) -> int:
        """Get random user ID from tier pool."""
        return random.choice(self._pools[tier])

    def get_weighted_user(self) -> Tuple[int, Tier]:
        """Get user with realistic tier distribution."""
        roll = random.randint(1, 100)
        cumulative = 0

        for tier, weight in self.DISTRIBUTION.items():
            cumulative += weight
            if roll <= cumulative:
                return self.get_user(tier), tier

        # Fallback to guest
        return self.get_user("guest"), "guest"

    def get_user_name(self, user_id: int) -> str:
        """Generate consistent username for user ID."""
        return f"StressUser{user_id}"

    @property
    def pool_sizes(self) -> dict:
        """Return size of each pool."""
        return {tier: len(pool) for tier, pool in self._pools.items()}


# Commands available per tier
TIER_COMMANDS = {
    "guest": ["/start", "/help", "/status", "/skills", "/mode", "/cancel", "/clear"],
    "user": ["/skill", "/translate", "/summarize", "/rewrite", "/remind", "/reminders", "/task"],
    "developer": ["/traces", "/trace", "/circuits", "/tier"],
    "admin": ["/grant", "/revoke", "/admin"],
}


def get_commands_for_tier(tier: Tier) -> list:
    """Get all commands accessible to a tier (including lower tiers)."""
    tier_order = ["guest", "user", "developer", "admin"]
    tier_idx = tier_order.index(tier)
    commands = []
    for i in range(tier_idx + 1):
        commands.extend(TIER_COMMANDS[tier_order[i]])
    return commands


# Global user pool instance
user_pool = UserPool()
