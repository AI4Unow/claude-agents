"""Stress test configuration."""

from dataclasses import dataclass, field
from typing import List
import os


@dataclass
class StressConfig:
    """Configuration for stress tests."""

    # Webhook endpoint
    webhook_url: str = field(
        default_factory=lambda: os.getenv(
            "STRESS_WEBHOOK_URL",
            "https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/webhook/telegram"
        )
    )
    webhook_secret: str = field(default_factory=lambda: os.getenv("TELEGRAM_WEBHOOK_SECRET", ""))

    # User pool ranges (non-overlapping with real users)
    guest_start: int = 1_000_000
    guest_end: int = 1_001_000  # 1000 guests
    user_start: int = 2_000_000
    user_end: int = 2_000_100  # 100 users
    developer_start: int = 3_000_000
    developer_end: int = 3_000_010  # 10 developers
    admin_id: int = 999999999  # Matches ADMIN_TELEGRAM_ID

    # Performance thresholds
    p50_target_ms: int = 500
    p95_target_ms: int = 2000
    p99_target_ms: int = 5000
    error_rate_threshold: float = 0.05  # 5%
    min_throughput_rps: float = 50.0

    # Timeouts
    request_timeout: float = 30.0
    connect_timeout: float = 5.0

    # Test profiles
    @staticmethod
    def get_profile(name: str) -> dict:
        """Get test profile by name."""
        profiles = {
            "ramp_up": {
                "users": 1000,
                "spawn_rate": 10,  # 10 users/sec → 100s to full load
                "run_time": "5m",
            },
            "sustained": {
                "users": 1000,
                "spawn_rate": 50,
                "run_time": "10m",
            },
            "spike": {
                "users": 2000,
                "spawn_rate": 100,
                "run_time": "3m",
            },
            "soak": {
                "users": 200,
                "spawn_rate": 20,
                "run_time": "1h",
            },
            "quick": {
                "users": 50,
                "spawn_rate": 10,
                "run_time": "1m",
            },
        }
        return profiles.get(name, profiles["quick"])


# Global config instance
config = StressConfig()
