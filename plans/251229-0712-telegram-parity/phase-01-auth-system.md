# Phase 1: Auth System (REVISED)

**Status:** pending
**Effort:** 1-2 days

## Context

- [plan.md](plan.md) - Overview
- [brainstorm](../reports/brainstorm-251229-0712-telegram-parity-architecture.md)

## Overview

Implement **Telegram ID allowlist** for tier-based access control. Admin adds user IDs to Firebase with assigned tiers. Simpler than token-based approach.

**Validation Changes:**
- ~~Token-based auth~~ → Telegram ID allowlist
- Guest tier has rate-limited access (5 req/min) instead of no access

## Key Insights

1. Allowlist is simpler than token generation/redemption
2. Admin adds users via `/grant <telegram_id> <tier>` command
3. Admin auto-assigned via `ADMIN_TELEGRAM_ID` env
4. Tier hierarchy: guest (rate-limited) < user < developer < admin
5. Guest can use skills but with lower rate limits

## Requirements

- [ ] Firebase `user_tiers/{telegram_id}` collection
- [ ] `get_user_tier()` helper with caching
- [ ] `/grant <telegram_id> <tier>` admin command
- [ ] `/tier` command to check own tier
- [ ] Rate limiting per tier (guest: 5/min, user: 20/min, developer: 50/min)
- [ ] Tier-based command filtering decorator

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ALLOWLIST AUTH FLOW                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ADMIN                                                                   │
│    │                                                                     │
│    │ /grant 123456789 developer                                          │
│    │                                                                     │
│    ▼                                                                     │
│  ┌──────────────────┐                                                    │
│  │ Store in Firebase│                                                    │
│  │ user_tiers/      │                                                    │
│  │ 123456789: {     │                                                    │
│  │   tier: developer│                                                    │
│  │   granted_by: X  │                                                    │
│  │ }                │                                                    │
│  └──────────────────┘                                                    │
│                                                                          │
│  USER MESSAGE                                                            │
│    │                                                                     │
│    ▼                                                                     │
│  ┌──────────────────┐     ┌──────────────────┐                          │
│  │ get_user_tier()  │────▶│ Check rate limit │                          │
│  │ (cached)         │     │ per tier         │                          │
│  └──────────────────┘     └────────┬─────────┘                          │
│                                    │                                     │
│                           ┌────────┴────────┐                            │
│                           ▼                 ▼                            │
│                      ALLOWED           RATE LIMITED                      │
│                        │                    │                            │
│                        ▼                    ▼                            │
│                   Process             "Rate limited.                     │
│                   request              Try later."                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| File | Purpose | Changes |
|------|---------|---------|
| `agents/main.py:596-778` | `handle_command()` | Add `/grant`, `/tier` commands |
| `agents/src/services/firebase.py` | Firebase client | Add tier functions |
| `agents/src/core/state.py` | State manager | Add tier caching + rate limiting |

## Implementation Steps

### Step 1: Firebase Schema (firebase.py)

Add tier storage and rate limiting functions:

```python
# agents/src/services/firebase.py

from typing import Literal

TierType = Literal["guest", "user", "developer", "admin"]
TIER_HIERARCHY = {"guest": 0, "user": 1, "developer": 2, "admin": 3}

# Rate limits per tier (requests per minute)
TIER_RATE_LIMITS = {
    "guest": 5,
    "user": 20,
    "developer": 50,
    "admin": 1000  # effectively unlimited
}


async def set_user_tier(telegram_id: int, tier: TierType, granted_by: int) -> bool:
    """Add/update user tier in allowlist.

    Args:
        telegram_id: User's Telegram ID
        tier: Access tier to grant
        granted_by: Admin Telegram ID

    Returns:
        True if successful
    """
    if firebase_circuit.state == CircuitState.OPEN:
        return False

    try:
        db = get_db()
        db.collection("user_tiers").document(str(telegram_id)).set({
            "tier": tier,
            "granted_by": granted_by,
            "granted_at": firestore.SERVER_TIMESTAMP,
            "last_active": firestore.SERVER_TIMESTAMP
        })

        firebase_circuit._record_success()
        logger.info("user_tier_set", tier=tier, user=telegram_id, by=granted_by)
        return True

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("set_user_tier_error", error=str(e)[:100])
        return False


async def get_user_tier(telegram_id: int) -> TierType:
    """Get user's tier. Returns 'guest' if not in allowlist."""
    if firebase_circuit.state == CircuitState.OPEN:
        return "guest"

    try:
        db = get_db()
        doc = db.collection("user_tiers").document(str(telegram_id)).get()

        if doc.exists:
            firebase_circuit._record_success()
            return doc.to_dict().get("tier", "guest")

        firebase_circuit._record_success()
        return "guest"

    except Exception as e:
        firebase_circuit._record_failure(e)
        return "guest"


async def remove_user_tier(telegram_id: int) -> bool:
    """Remove user from allowlist (revoke access)."""
    if firebase_circuit.state == CircuitState.OPEN:
        return False

    try:
        db = get_db()
        db.collection("user_tiers").document(str(telegram_id)).delete()
        firebase_circuit._record_success()
        logger.info("user_tier_removed", user=telegram_id)
        return True

    except Exception as e:
        firebase_circuit._record_failure(e)
        return False


def has_permission(user_tier: TierType, required_tier: TierType) -> bool:
    """Check if user tier meets required tier."""
    return TIER_HIERARCHY.get(user_tier, 0) >= TIER_HIERARCHY.get(required_tier, 0)


def get_rate_limit(tier: TierType) -> int:
    """Get rate limit (req/min) for tier."""
    return TIER_RATE_LIMITS.get(tier, 5)
```

### Step 2: Rate Limiting (state.py)

Add per-user rate limiting with tier awareness:

```python
# agents/src/core/state.py

from collections import defaultdict
import time

# Add to StateManager class
TTL_USER_TIER = 3600  # 1 hour
_rate_counters: Dict[int, List[float]] = defaultdict(list)  # user_id -> list of timestamps

async def get_user_tier_cached(self, user_id: int) -> str:
    """Get user tier with L1 cache."""
    if not user_id:
        return "guest"

    # Check admin env var first
    import os
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user_id) == str(admin_id):
        return "admin"

    key = self._cache_key("user_tiers", str(user_id))

    # L1 hit
    cached = self._get_from_l1(key)
    if cached is not None:
        return cached.get("tier", "guest")

    # L2 fallback
    from src.services.firebase import get_user_tier
    tier = await get_user_tier(user_id)

    # Cache the result
    self._set_to_l1(key, {"tier": tier}, self.TTL_USER_TIER)
    return tier


def check_rate_limit(self, user_id: int, tier: str) -> tuple[bool, int]:
    """Check if user is within rate limit.

    Returns:
        (is_allowed, seconds_until_reset)
    """
    from src.services.firebase import get_rate_limit

    limit = get_rate_limit(tier)
    now = time.time()
    window_start = now - 60  # 1 minute window

    # Clean old entries
    self._rate_counters[user_id] = [
        ts for ts in self._rate_counters[user_id]
        if ts > window_start
    ]

    current_count = len(self._rate_counters[user_id])

    if current_count >= limit:
        oldest = min(self._rate_counters[user_id]) if self._rate_counters[user_id] else now
        reset_in = int(oldest + 60 - now)
        return False, max(1, reset_in)

    # Record this request
    self._rate_counters[user_id].append(now)
    return True, 0


async def invalidate_user_tier(self, user_id: int):
    """Invalidate cached tier after grant/revoke."""
    key = self._cache_key("user_tiers", str(user_id))
    with _cache_lock:
        if key in self._l1_cache:
            del self._l1_cache[key]
```

### Step 3: Command Handler (main.py)

Add `/grant`, `/revoke`, `/tier` commands:

```python
# agents/main.py

from src.services.firebase import (
    set_user_tier, get_user_tier, remove_user_tier,
    has_permission, TierType, TIER_HIERARCHY
)

# Add in handle_command():

elif cmd == "/grant":
    # Admin only
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != str(admin_id):
        return "Admin only command."

    parts = args.split()
    if len(parts) != 2:
        return "Usage: /grant <telegram_id> <user|developer>"

    try:
        target_id = int(parts[0])
    except ValueError:
        return "Invalid Telegram ID. Must be a number."

    tier = parts[1].lower()
    if tier not in ["user", "developer"]:
        return "Tier must be 'user' or 'developer'."

    success = await set_user_tier(target_id, tier, user.get("id"))

    if success:
        # Invalidate cache
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.invalidate_user_tier(target_id)
        return f"Granted <b>{tier}</b> tier to user {target_id}"
    else:
        return "Failed to grant tier. Check logs."


elif cmd == "/revoke":
    # Admin only
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != str(admin_id):
        return "Admin only command."

    if not args:
        return "Usage: /revoke <telegram_id>"

    try:
        target_id = int(args.strip())
    except ValueError:
        return "Invalid Telegram ID."

    success = await remove_user_tier(target_id)

    if success:
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.invalidate_user_tier(target_id)
        return f"Revoked access for user {target_id}. Now guest tier."
    else:
        return "Failed to revoke tier."


elif cmd == "/tier":
    from src.core.state import get_state_manager
    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))

    from src.services.firebase import get_rate_limit
    limit = get_rate_limit(tier)

    return f"Your tier: <b>{tier}</b>\nRate limit: {limit} requests/min"
```

### Step 4: Rate Limit Check in process_message()

```python
# agents/main.py - in process_message()

async def process_message(message: str, user: dict, chat_id: int) -> str:
    """Process incoming message with rate limiting."""
    from src.core.state import get_state_manager

    state = get_state_manager()
    user_id = user.get("id")

    # Get tier and check rate limit
    tier = await state.get_user_tier_cached(user_id)
    allowed, reset_in = state.check_rate_limit(user_id, tier)

    if not allowed:
        return f"Rate limited. Try again in {reset_in}s.\n\nUpgrade tier for higher limits."

    # ... rest of message processing
```

## Todo List

- [ ] Add Firebase functions (`set_user_tier`, `get_user_tier`, `remove_user_tier`)
- [ ] Add `TIER_RATE_LIMITS` constant
- [ ] Add state manager tier caching + rate limiting
- [ ] Add `/grant` admin command
- [ ] Add `/revoke` admin command
- [ ] Add `/tier` self-check command
- [ ] Add rate limit check in `process_message()`
- [ ] Update `/help` with new commands
- [ ] Test grant/revoke flow
- [ ] Test rate limiting per tier

## Success Criteria

1. Admin can grant tiers via `/grant <id> <tier>`
2. Admin can revoke access via `/revoke <id>`
3. Users can check their tier via `/tier`
4. Guest users are rate-limited (5 req/min)
5. Higher tiers have higher limits
6. Rate limits reset after 60 seconds

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Admin grants wrong tier | Low | Medium | Revoke command available |
| Rate limit too strict | Medium | Low | Can adjust constants easily |
| Cache stale after grant | Low | Low | Explicit invalidation on grant/revoke |

## Security Considerations

1. **Admin verification** - ADMIN_TELEGRAM_ID env var
2. **No tokens to leak** - Just Telegram IDs
3. **Rate limiting** - Protects against abuse
4. **Firebase rules** - Should restrict user_tiers writes to admin

## Next Steps

After completing this phase:
1. Proceed to [Phase 2: Admin Commands](phase-02-admin-commands.md)
2. Use `require_tier` decorator for admin commands
