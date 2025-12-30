"""User tier management service.

Access tier system for Telegram bot parity.
"""
from typing import Literal

from firebase_admin import firestore

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()

TierType = Literal["guest", "user", "developer", "admin"]
TIER_HIERARCHY = {"guest": 0, "user": 1, "developer": 2, "admin": 3}

# Rate limits per tier (requests per minute)
TIER_RATE_LIMITS = {
    "guest": 5,
    "user": 20,
    "developer": 50,
    "admin": 1000  # effectively unlimited
}


@with_firebase_circuit(open_return="guest")
async def get_user_tier(telegram_id: int) -> TierType:
    """Get user's tier. Returns 'guest' if not in allowlist."""
    db = get_db()
    doc = db.collection(Collections.USER_TIERS).document(str(telegram_id)).get()

    if doc.exists:
        return doc.to_dict().get("tier", "guest")

    return "guest"


@with_firebase_circuit(open_return=False)
async def set_user_tier(telegram_id: int, tier: TierType, granted_by: int) -> bool:
    """Add/update user tier in allowlist.

    Args:
        telegram_id: User's Telegram ID
        tier: Access tier to grant
        granted_by: Admin Telegram ID

    Returns:
        True if successful
    """
    db = get_db()
    db.collection(Collections.USER_TIERS).document(str(telegram_id)).set({
        "tier": tier,
        "granted_by": granted_by,
        "granted_at": firestore.SERVER_TIMESTAMP,
        "last_active": firestore.SERVER_TIMESTAMP
    })

    logger.info("user_tier_set", tier=tier, user=telegram_id, by=granted_by)
    return True


@with_firebase_circuit(open_return=False)
async def remove_user_tier(telegram_id: int) -> bool:
    """Remove user from allowlist (revoke access)."""
    db = get_db()
    db.collection(Collections.USER_TIERS).document(str(telegram_id)).delete()
    logger.info("user_tier_removed", user=telegram_id)
    return True


def has_permission(user_tier: TierType, required_tier: TierType) -> bool:
    """Check if user tier meets required tier."""
    return TIER_HIERARCHY.get(user_tier, 0) >= TIER_HIERARCHY.get(required_tier, 0)


def get_rate_limit(tier: TierType) -> int:
    """Get rate limit (req/min) for tier."""
    return TIER_RATE_LIMITS.get(tier, 5)
