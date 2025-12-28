# Phase 01: StateManager Core + TTL Cache

## Objective

Create `src/core/state.py` with unified state management and TTL-based caching.

## Files to Create

### `src/core/state.py`

```python
"""Unified state management with L1 cache + L2 Firebase persistence.

TTL Defaults:
- Sessions: 1 hour
- Conversations: 24 hours
- Generic cache: 5 minutes
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from src.utils.logging import get_logger

logger = get_logger()

@dataclass
class CacheEntry:
    """Cache entry with expiration."""
    value: Any
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class StateManager:
    """Unified state manager with L1 cache + L2 Firebase.

    Usage:
        state = get_state_manager()
        await state.set("key", value, ttl_seconds=300)
        value = await state.get("key")
    """

    # TTL defaults (seconds)
    TTL_SESSION = 3600      # 1 hour
    TTL_CONVERSATION = 86400  # 24 hours
    TTL_CACHE = 300         # 5 minutes

    def __init__(self):
        self._l1_cache: Dict[str, CacheEntry] = {}
        self._db = None
        self._initialized = False
        self.logger = logger.bind(component="StateManager")

    def _get_db(self):
        """Get Firestore client (lazy init)."""
        if self._db is None:
            from src.services.firebase import get_db
            self._db = get_db()
        return self._db

    async def _firebase_get(self, collection: str, doc_id: str) -> Optional[Dict]:
        """Async wrapper for Firebase get."""
        db = self._get_db()
        doc = await asyncio.to_thread(
            lambda: db.collection(collection).document(doc_id).get()
        )
        return doc.to_dict() if doc.exists else None

    async def _firebase_set(self, collection: str, doc_id: str, data: Dict, merge: bool = True):
        """Async wrapper for Firebase set."""
        db = self._get_db()
        await asyncio.to_thread(
            lambda: db.collection(collection).document(doc_id).set(data, merge=merge)
        )

    async def _firebase_update(self, collection: str, doc_id: str, data: Dict):
        """Async wrapper for Firebase update."""
        db = self._get_db()
        await asyncio.to_thread(
            lambda: db.collection(collection).document(doc_id).update(data)
        )

    # ==================== Generic Cache ====================

    def _cache_key(self, collection: str, doc_id: str) -> str:
        """Generate cache key."""
        return f"{collection}:{doc_id}"

    def _get_from_l1(self, key: str) -> Optional[Any]:
        """Get from L1 cache if not expired."""
        entry = self._l1_cache.get(key)
        if entry and not entry.is_expired:
            return entry.value
        if entry:
            del self._l1_cache[key]  # Cleanup expired
        return None

    def _set_to_l1(self, key: str, value: Any, ttl_seconds: int):
        """Set to L1 cache with TTL."""
        self._l1_cache[key] = CacheEntry(
            value=value,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds)
        )

    async def get(self, collection: str, doc_id: str, ttl_seconds: int = TTL_CACHE) -> Optional[Dict]:
        """Get from L1 cache, fallback to L2 Firebase.

        Args:
            collection: Firestore collection name
            doc_id: Document ID
            ttl_seconds: TTL for L1 cache on miss

        Returns:
            Document dict or None
        """
        key = self._cache_key(collection, doc_id)

        # L1 hit
        cached = self._get_from_l1(key)
        if cached is not None:
            self.logger.debug("l1_hit", key=key)
            return cached

        # L2 fallback
        data = await self._firebase_get(collection, doc_id)
        if data:
            self._set_to_l1(key, data, ttl_seconds)
            self.logger.debug("l2_hit", key=key)

        return data

    async def set(
        self,
        collection: str,
        doc_id: str,
        data: Dict,
        ttl_seconds: int = TTL_CACHE,
        persist: bool = True
    ):
        """Set to L1 cache and optionally L2 Firebase.

        Args:
            collection: Firestore collection name
            doc_id: Document ID
            data: Data to store
            ttl_seconds: TTL for L1 cache
            persist: Whether to write to Firebase
        """
        key = self._cache_key(collection, doc_id)
        self._set_to_l1(key, data, ttl_seconds)

        if persist:
            await self._firebase_set(collection, doc_id, data)
            self.logger.debug("persisted", key=key)

    async def invalidate(self, collection: str, doc_id: str):
        """Remove from L1 cache."""
        key = self._cache_key(collection, doc_id)
        self._l1_cache.pop(key, None)

    def cleanup_expired(self):
        """Remove all expired L1 entries."""
        now = datetime.utcnow()
        expired = [k for k, v in self._l1_cache.items() if v.expires_at < now]
        for k in expired:
            del self._l1_cache[k]
        if expired:
            self.logger.info("cache_cleanup", removed=len(expired))


# Singleton
_state_manager: Optional[StateManager] = None

def get_state_manager() -> StateManager:
    """Get or create singleton StateManager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
```

## Tests

```python
# tests/test_state_manager.py
import pytest
from datetime import datetime, timedelta
from src.core.state import CacheEntry, StateManager

def test_cache_entry_expiration():
    # Not expired
    entry = CacheEntry(value="test", expires_at=datetime.utcnow() + timedelta(seconds=10))
    assert not entry.is_expired

    # Expired
    entry = CacheEntry(value="test", expires_at=datetime.utcnow() - timedelta(seconds=1))
    assert entry.is_expired

def test_l1_cache_hit():
    sm = StateManager()
    sm._set_to_l1("test:1", {"foo": "bar"}, ttl_seconds=60)

    result = sm._get_from_l1("test:1")
    assert result == {"foo": "bar"}

def test_l1_cache_miss_expired():
    sm = StateManager()
    sm._l1_cache["test:1"] = CacheEntry(
        value={"foo": "bar"},
        expires_at=datetime.utcnow() - timedelta(seconds=1)
    )

    result = sm._get_from_l1("test:1")
    assert result is None
    assert "test:1" not in sm._l1_cache  # Cleaned up
```

## Verification

```bash
# Run tests
pytest tests/test_state_manager.py -v

# Check import works
python3 -c "from src.core.state import get_state_manager; print('OK')"
```

## Acceptance Criteria

- [ ] `StateManager` class created with L1 TTL cache
- [ ] Async wrappers for Firebase ops (`asyncio.to_thread`)
- [ ] Unit tests pass
- [ ] No breaking changes to existing code
