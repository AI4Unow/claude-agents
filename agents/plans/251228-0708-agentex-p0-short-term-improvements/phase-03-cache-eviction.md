# Phase 03: Cache Eviction

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Issue:** Code review #9 - cleanup_expired() never runs automatically
- **Related:** `src/core/state.py:184-193`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Priority | MEDIUM |
| Effort | 1h |
| Implementation | pending |
| Review | pending |

## Problem

`StateManager.cleanup_expired()` exists but is never called automatically. L1 cache grows unbounded, causing memory leak over time.

## Solution

Add periodic background task to run cleanup every 5 minutes:

```python
async def _periodic_cleanup(self):
    """Background task to cleanup expired entries."""
    while True:
        await asyncio.sleep(300)  # 5 minutes
        try:
            self.cleanup_expired()
        except Exception as e:
            self.logger.error("cleanup_failed", error=str(e))
```

## Related Files

| File | Lines | Action |
|------|-------|--------|
| `src/core/state.py` | 45-60 | Add cleanup task in __init__ or warm() |

## Implementation Steps

1. Add `_cleanup_task: Optional[asyncio.Task]` attribute
2. Create `_periodic_cleanup()` coroutine
3. Start cleanup task in `warm()` method (called by @enter hook)
4. Add task cancellation in case of cleanup (optional)

## Code Changes

### src/core/state.py

```python
import asyncio
from typing import Optional

class StateManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._l1_cache: Dict[str, CacheEntry] = {}
        self._db = None
        self._cleanup_task: Optional[asyncio.Task] = None  # NEW
        self.logger = logger.bind(component="StateManager")
        self._initialized = True

    async def warm(self):
        """Warm cache with frequently accessed data."""
        # ... existing warm logic ...

        # Start periodic cleanup if not already running
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self.logger.info("cleanup_task_started")

    async def _periodic_cleanup(self):
        """Background task to cleanup expired L1 cache entries."""
        while True:
            await asyncio.sleep(300)  # 5 minutes
            try:
                count = self.cleanup_expired()
                if count > 0:
                    self.logger.info("cache_cleanup", expired_count=count)
            except Exception as e:
                self.logger.error("cleanup_failed", error=str(e))

    def cleanup_expired(self) -> int:
        """Remove expired entries from L1 cache. Returns count removed."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._l1_cache.items()
            if entry.expires_at and entry.expires_at < now
        ]
        for key in expired_keys:
            del self._l1_cache[key]

        return len(expired_keys)
```

## Considerations

### Modal Container Lifecycle

- @enter hook calls `warm()` when container starts
- Cleanup task runs for container lifetime
- No explicit shutdown needed (task dies with container)

### Memory Impact

- 5-minute interval balances cleanup overhead vs memory usage
- Expected: dozens of expired entries per cleanup (minimal CPU)
- L1 cache entries: ~1KB each, max ~10k entries = ~10MB

## Success Criteria

- [ ] `_periodic_cleanup()` runs every 5 minutes
- [ ] Expired entries removed from L1 cache
- [ ] Cleanup errors logged but don't crash
- [ ] Test: entries with expired TTL are removed

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Task blocks event loop | LOW | Only dict iteration, O(n) with small n |
| Task fails silently | LOW | Error logging added |
| Multiple cleanup tasks | LOW | Check task.done() before starting |

## Next Steps

After this phase, proceed to [Phase 04](./phase-04-admin-authentication.md).
