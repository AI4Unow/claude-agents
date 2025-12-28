# Phase 02: Migrate Telegram Session Functions

## Objective

Replace direct Firebase calls in `main.py` session functions with StateManager.

## Current State (main.py:695-785)

```python
# Current: Direct Firebase, sync ops
async def store_pending_skill(user_id: int, skill_name: str):
    db = init_firebase()
    db.collection("telegram_sessions").document(str(user_id)).set({...}, merge=True)
```

## Target State

```python
# Target: StateManager with caching
async def store_pending_skill(user_id: int, skill_name: str):
    state = get_state_manager()
    await state.set_session(user_id, {"pending_skill": skill_name})
```

## Changes to `src/core/state.py`

Add session-specific methods:

```python
# Add to StateManager class

COLLECTION_SESSIONS = "telegram_sessions"

async def get_session(self, user_id: int) -> Optional[Dict]:
    """Get Telegram session with caching."""
    if not user_id:
        return None
    return await self.get(
        self.COLLECTION_SESSIONS,
        str(user_id),
        ttl_seconds=self.TTL_SESSION
    )

async def set_session(self, user_id: int, data: Dict):
    """Update Telegram session."""
    if not user_id:
        return

    # Merge with existing
    existing = await self.get_session(user_id) or {}
    merged = {**existing, **data, "updated_at": datetime.utcnow().isoformat()}

    await self.set(
        self.COLLECTION_SESSIONS,
        str(user_id),
        merged,
        ttl_seconds=self.TTL_SESSION
    )

async def get_pending_skill(self, user_id: int) -> Optional[str]:
    """Get pending skill from session."""
    session = await self.get_session(user_id)
    return session.get("pending_skill") if session else None

async def clear_pending_skill(self, user_id: int):
    """Clear pending skill."""
    await self.set_session(user_id, {"pending_skill": None})

async def get_user_mode(self, user_id: int) -> str:
    """Get user's execution mode."""
    session = await self.get_session(user_id)
    return session.get("mode", "simple") if session else "simple"

async def set_user_mode(self, user_id: int, mode: str):
    """Set user's execution mode."""
    await self.set_session(user_id, {"mode": mode})
```

## Changes to `main.py`

Replace functions at lines 695-785:

```python
# At top of file, add import
from src.core.state import get_state_manager

# Remove these functions (lines 695-785):
# - store_pending_skill()
# - get_pending_skill()
# - clear_pending_skill()
# - store_user_mode()
# - get_user_mode()

# Update call sites to use StateManager:

# Before (line ~424):
pending_skill = await get_pending_skill(user.get("id"))

# After:
state = get_state_manager()
pending_skill = await state.get_pending_skill(user.get("id"))

# Before (line ~428):
await clear_pending_skill(user.get("id"))

# After:
await state.clear_pending_skill(user.get("id"))

# Before (line ~366):
mode = await get_user_mode(user.get("id")) or "simple"

# After:
mode = await state.get_user_mode(user.get("id"))

# Before (line ~382):
await store_user_mode(user.get("id"), args)

# After:
await state.set_user_mode(user.get("id"), args)

# Before (line ~386):
await clear_pending_skill(user.get("id"))

# After:
await state.clear_pending_skill(user.get("id"))

# Before (line ~623):
await store_user_mode(user.get("id"), value)

# After:
await state.set_user_mode(user.get("id"), value)

# Before (line ~682):
await store_pending_skill(user.get("id"), skill_name)

# After:
await state.set_session(user.get("id"), {"pending_skill": skill_name})
```

## Verification

```bash
# Deploy and test
modal serve main.py

# Test via curl
curl -X POST https://...modal.run/webhook/telegram \
  -H "Content-Type: application/json" \
  -d '{"message":{"chat":{"id":123},"text":"/skills","from":{"id":456}}}'

# Check logs for cache hits
modal app logs claude-agents | grep "l1_hit"
```

## Acceptance Criteria

- [ ] All session functions migrated to StateManager
- [ ] Session reads hit L1 cache on repeat calls
- [ ] All Firebase ops wrapped with `asyncio.to_thread()`
- [ ] Existing functionality unchanged
- [ ] No direct `init_firebase()` calls in session code
