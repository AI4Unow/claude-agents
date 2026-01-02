"""SDK configuration for tiers and permissions."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TierLimits:
    max_iterations: int
    max_tools_per_turn: int

    @classmethod
    def for_tier(cls, tier: str) -> "TierLimits":
        limits = {
            "guest": cls(max_iterations=3, max_tools_per_turn=2),
            "user": cls(max_iterations=10, max_tools_per_turn=5),
            "developer": cls(max_iterations=25, max_tools_per_turn=10),
            "admin": cls(max_iterations=50, max_tools_per_turn=20),
        }
        return limits.get(tier, limits["user"])


@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-20250514"
    checkpoint_enabled: bool = True

    @classmethod
    def for_tier(cls, tier: str) -> "AgentConfig":
        return cls()  # Same config, different limits via TierLimits
