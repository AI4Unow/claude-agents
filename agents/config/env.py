"""Environment configuration and admin validation.

Security:
- Centralized admin ID validation
- Fail-closed by default
- Thread-safe caching via lru_cache
"""
import os
from functools import lru_cache


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


@lru_cache(maxsize=1)
def get_admin_telegram_id() -> int:
    """Get admin Telegram ID from environment (cached).

    Returns:
        Admin Telegram user ID

    Raises:
        ConfigurationError: If ADMIN_TELEGRAM_ID not set or invalid

    Security:
        - Cached for performance (single read from env)
        - Validates integer format
        - Fails fast on misconfiguration
    """
    admin_str = os.environ.get("ADMIN_TELEGRAM_ID")
    if not admin_str:
        raise ConfigurationError("ADMIN_TELEGRAM_ID not set")

    try:
        return int(admin_str)
    except ValueError:
        raise ConfigurationError(f"Invalid ADMIN_TELEGRAM_ID: {admin_str}")


def is_admin(user_id: int) -> bool:
    """Check if user is admin.

    Args:
        user_id: Telegram user ID to check

    Returns:
        True if user is admin, False otherwise

    Security:
        - Defaults to False on configuration errors
        - Uses cached admin ID lookup
    """
    try:
        return user_id == get_admin_telegram_id()
    except ConfigurationError:
        return False


def require_admin(user_id: int) -> None:
    """Require admin access, raise if not admin.

    Args:
        user_id: Telegram user ID to check

    Raises:
        PermissionError: If user is not admin

    Security:
        - Fail-closed: denies on configuration errors
        - Clear error message for access denial
    """
    if not is_admin(user_id):
        raise PermissionError("Admin access required")
