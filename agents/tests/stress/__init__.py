"""Stress test package for Telegram bot."""

from .config import config, StressConfig
from .users import user_pool, UserPool, get_commands_for_tier, TIER_COMMANDS
from .payloads import (
    text_message,
    voice_message,
    image_message,
    document_message,
    callback_query,
    category_callback,
    skill_callback,
    malformed_json,
    empty_payload,
    missing_message,
    huge_payload,
)
from .metrics import MetricsCollector, collector, check_thresholds
from .chaos import ChaosRunner, run_chaos_tests

__all__ = [
    # Config
    "config",
    "StressConfig",
    # Users
    "user_pool",
    "UserPool",
    "get_commands_for_tier",
    "TIER_COMMANDS",
    # Payloads
    "text_message",
    "voice_message",
    "image_message",
    "document_message",
    "callback_query",
    "category_callback",
    "skill_callback",
    "malformed_json",
    "empty_payload",
    "missing_message",
    "huge_payload",
    # Metrics
    "MetricsCollector",
    "collector",
    "check_thresholds",
    # Chaos
    "ChaosRunner",
    "run_chaos_tests",
]
