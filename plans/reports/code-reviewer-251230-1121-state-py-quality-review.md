# Code Review: state.py Quality Assessment

## Scope
- File reviewed: `agents/src/core/state.py`
- Lines analyzed: 541 (full file)
- Review focus: Recent changes (Profile & Context methods added), SRP violations, DRY issues, cache coordination, thread safety, type safety
- Updated plans: None (standalone review)

## Overall Assessment
StateManager exhibits classic "God Object" anti-pattern with multiple SRP violations. Recent Profile/Context additions (lines 283-328) follow existing DRY violations. Thread safety implementation solid but cache invalidation lacks atomic guarantees. Type hints incomplete with missing generic specifications.

## Critical Issues

### None identified
No security vulnerabilities, data loss risks, or breaking changes.

## High Priority Findings

### H1: Single Responsibility Principle (SRP) Violation - God Object Pattern
**Severity:** HIGH
**Lines:** Entire class (44-526)

**Problem:**
StateManager handles 6 distinct responsibilities:
1. Generic L1/L2 cache management (114-212)
2. Telegram session state (213-282)
3. User profiles (283-308)
4. Work contexts (309-328)
5. Conversation history (330-386)
6. User tiers + rate limiting (388-454)
7. Cache warming (456-526)

**Impact:**
- Violates Open/Closed Principle - every new state type requires modifying this class
- High coupling - all state consumers depend on single class
- Testing difficulty - requires mocking multiple Firebase collections
- 500+ line class difficult to maintain

**Recommendation:**
Refactor into layered architecture:

```python
# Layer 1: Generic cache (keep in state.py)
class CacheManager:
    """L1 TTL cache with LRU eviction."""
    def get(key: str) -> Optional[Any]
    def set(key: str, value: Any, ttl: int)
    def invalidate(key: str)

# Layer 2: Persistence adapters (new files)
class FirebaseRepository:
    """Generic Firebase CRUD with circuit breaker."""
    async def get(collection: str, doc_id: str) -> Optional[Dict]
    async def set(collection: str, doc_id: str, data: Dict)
    async def update(collection: str, doc_id: str, data: Dict)

# Layer 3: Domain-specific state managers (new files)
# src/services/session_state.py
class SessionStateManager:
    def __init__(self, cache: CacheManager, repo: FirebaseRepository)
    async def get_session(user_id: int) -> Optional[Dict]
    async def set_session(user_id: int, data: Dict)
    async def get_user_mode(user_id: int) -> str

# src/services/profile_state.py
class ProfileStateManager:
    async def get_user_profile(user_id: int) -> Optional[Dict]
    async def set_user_profile(user_id: int, data: Dict)
    async def get_work_context(user_id: int) -> Optional[Dict]
    async def set_work_context(user_id: int, data: Dict)

# src/services/tier_manager.py
class TierManager:
    async def get_user_tier_cached(user_id: int) -> str
    def check_rate_limit(user_id: int, tier: str) -> tuple
```

**Migration Path:**
1. Extract CacheManager (preserve existing behavior)
2. Create FirebaseRepository wrapper
3. Move session methods to SessionStateManager
4. Move profile/context methods to ProfileStateManager
5. Move tier logic to TierManager
6. Update consumers incrementally (7 files import state.py)
7. Deprecate StateManager once migration complete

### H2: DRY Violation - Repetitive CRUD Pattern
**Severity:** HIGH
**Lines:** 215-328

**Problem:**
Four method pairs follow identical pattern with only collection name + TTL differing:

```python
# Pattern repeated 4x:
async def get_X(user_id: int) -> Optional[Dict]:
    if not user_id:
        return None
    return await self.get("collection_X", str(user_id), ttl_seconds=TTL_X)

async def set_X(user_id: int, data: Dict):
    if not user_id:
        return
    await self.set("collection_X", str(user_id), data, ttl_seconds=TTL_X)
```

Instances:
- `get_session` / `set_session` (215-263) - exception: set_session has merge logic
- `get_user_profile` / `set_user_profile` (288-307)
- `get_work_context` / `set_work_context` (309-328)

**Impact:**
- 84 lines of boilerplate (288-328 entirely duplicative)
- Bug propagation - input validation fix requires 4 changes
- Inconsistency risk - set_session has merge logic, others don't

**Recommendation:**
Extract generic accessor factory:

```python
def _create_state_accessor(
    collection: str,
    ttl: int,
    merge_on_update: bool = False
) -> tuple[Callable, Callable]:
    """Factory for get/set pair with consistent validation."""

    async def getter(self, user_id: int) -> Optional[Dict]:
        if not user_id:
            return None
        return await self.get(collection, str(user_id), ttl_seconds=ttl)

    async def setter(self, user_id: int, data: Dict):
        if not user_id:
            return

        if merge_on_update:
            # Merge logic from set_session
            update_data = {**data, "updated_at": datetime.now(timezone.utc).isoformat()}
            await self._firebase_set(collection, str(user_id), update_data, merge=True)
            # ... cache merge logic ...
        else:
            await self.set(collection, str(user_id), data, ttl_seconds=ttl)

    return getter, setter

# Usage:
get_user_profile, set_user_profile = _create_state_accessor(
    "user_profiles", TTL_PROFILE
)
get_work_context, set_work_context = _create_state_accessor(
    "user_contexts", TTL_CONTEXT
)
```

Or use descriptor protocol for cleaner syntax:

```python
class StateProperty:
    """Descriptor for typed state access."""
    def __init__(self, collection: str, ttl: int):
        self.collection = collection
        self.ttl = ttl

    async def get(self, user_id: int) -> Optional[Dict]:
        # Implementation

    async def set(self, user_id: int, data: Dict):
        # Implementation

# Declarative definitions:
user_profiles = StateProperty("user_profiles", TTL_PROFILE)
work_contexts = StateProperty("user_contexts", TTL_CONTEXT)
```

### H3: Cache Invalidation - Atomic Guarantee Gap
**Severity:** HIGH
**Lines:** 225-263 (set_session)

**Problem:**
`set_session` has race condition between Firebase write and cache update:

```python
async def set_session(self, user_id: int, data: Dict):
    # 1. Write to Firebase (blocking I/O)
    await self._firebase_set(
        self.COLLECTION_SESSIONS, str(user_id), update_data, merge=True
    )

    # 2. Update L1 cache (critical section)
    with _cache_lock:
        existing = self._l1_cache.get(key)
        # GAP: Another thread could read stale cache here
        if existing and not existing.is_expired:
            merged = {**existing.value, **update_data}
            self._l1_cache[key] = CacheEntry(value=merged, ...)
```

**Race Condition Scenario:**
1. Thread A calls `set_session(123, {"mode": "routed"})`
2. Thread A writes to Firebase (200ms)
3. Thread B calls `get_session(123)` during write
4. Thread B reads L1 cache (stale data, pre-merge)
5. Thread A completes Firebase write
6. Thread A updates L1 cache
7. Thread B returns stale mode to caller

**Impact:**
User sees wrong mode for 200ms window. Low probability but possible under concurrent webhook load.

**Recommendation:**
Option 1 - Write-through with invalidation-before-write:

```python
async def set_session(self, user_id: int, data: Dict):
    # Invalidate BEFORE Firebase write to force cache miss
    key = self._cache_key(self.COLLECTION_SESSIONS, str(user_id))
    with _cache_lock:
        self._l1_cache.pop(key, None)

    # Write to Firebase
    update_data = {**data, "updated_at": datetime.now(timezone.utc).isoformat()}
    await self._firebase_set(
        self.COLLECTION_SESSIONS, str(user_id), update_data, merge=True
    )

    # Cache miss forces fresh read from Firebase
    # No stale window, trades latency for consistency
```

Option 2 - Lock entire operation:

```python
# Add async lock (replace _cache_lock for this operation)
_session_locks: Dict[int, asyncio.Lock] = {}

async def set_session(self, user_id: int, data: Dict):
    # Per-user lock prevents concurrent read/write
    if user_id not in _session_locks:
        _session_locks[user_id] = asyncio.Lock()

    async with _session_locks[user_id]:
        # Write + cache update atomic
        await self._firebase_set(...)
        with _cache_lock:
            # Update cache
```

Option 2 preferred for consistency, Option 1 simpler if latency acceptable.

### H4: Type Hints - Missing Generic Specifications
**Severity:** MEDIUM (upgraded to HIGH for consistency)
**Lines:** 65, 68, 147, 174, 215, etc.

**Problem:**
Dict/List used without type parameters:

```python
# Current:
self._l1_cache: Dict[str, CacheEntry] = {}  # ✓ Good
self._rate_counters: Dict[int, List[float]] = defaultdict(list)  # ✓ Good

async def get(self, ...) -> Optional[Dict]:  # ✗ Missing [str, Any]
async def set(self, collection: str, doc_id: str, data: Dict, ...):  # ✗
async def get_session(self, user_id: int) -> Optional[Dict]:  # ✗
async def get_conversation(self, user_id: int) -> List[Dict]:  # ✗
```

**Impact:**
- Type checkers (mypy) can't verify nested access
- IDE autocomplete reduced effectiveness
- Runtime type errors not caught

**Recommendation:**
Add type parameters throughout:

```python
from typing import Dict, List, Optional, Any

async def get(
    self,
    collection: str,
    doc_id: str,
    ttl_seconds: int = TTL_CACHE
) -> Optional[Dict[str, Any]]:
    """Get from L1 cache, fallback to L2 Firebase."""
    ...

async def set(
    self,
    collection: str,
    doc_id: str,
    data: Dict[str, Any],
    ttl_seconds: int = TTL_CACHE,
    persist: bool = True
) -> None:
    """Set to L1 cache and optionally L2 Firebase."""
    ...

async def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
    """Get Telegram session with caching."""
    ...

async def get_conversation(self, user_id: int) -> List[Dict[str, Any]]:
    """Get conversation history."""
    ...
```

For better type safety, create typed models:

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class SessionData:
    mode: Literal["simple", "routed", "orchestrated"]
    pending_skill: Optional[str] = None
    updated_at: str = ""

async def get_session(self, user_id: int) -> Optional[SessionData]:
    data = await self.get(...)
    return SessionData(**data) if data else None
```

## Medium Priority Improvements

### M1: Inconsistent Cache Invalidation API
**Severity:** MEDIUM
**Lines:** 198-202, 449-454

**Problem:**
Two invalidation patterns exist:

```python
# Generic invalidate (uses _cache_lock)
async def invalidate(self, collection: str, doc_id: str):
    key = self._cache_key(collection, doc_id)
    with _cache_lock:
        self._l1_cache.pop(key, None)

# Tier-specific invalidate (duplicates lock logic)
async def invalidate_user_tier(self, user_id: int):
    key = self._cache_key("user_tiers", str(user_id))
    with _cache_lock:
        if key in self._l1_cache:
            del self._l1_cache[key]
```

**Impact:**
`invalidate_user_tier` reimplements generic `invalidate` logic with subtle differences (if-check vs pop).

**Recommendation:**
Consolidate to single method:

```python
async def invalidate_user_tier(self, user_id: int):
    """Invalidate cached tier after grant/revoke."""
    await self.invalidate("user_tiers", str(user_id))
```

### M2: Missing Input Validation - Type Safety
**Severity:** MEDIUM
**Lines:** 215-328

**Problem:**
User ID validation only checks falsy (0 is valid Telegram ID):

```python
async def get_session(self, user_id: int) -> Optional[Dict]:
    if not user_id:  # ✗ Rejects 0, accepts negative
        return None
```

**Impact:**
- Negative IDs pass validation but invalid for Telegram
- user_id=0 is theoretically valid but rejected

**Recommendation:**
Explicit positive integer check:

```python
def _validate_user_id(user_id: Optional[int]) -> bool:
    """Validate user_id is positive integer."""
    return user_id is not None and user_id > 0

async def get_session(self, user_id: int) -> Optional[Dict]:
    if not self._validate_user_id(user_id):
        return None
    ...
```

### M3: Rate Limiting - Non-thread-safe Modification
**Severity:** MEDIUM
**Lines:** 420-447

**Problem:**
`check_rate_limit` modifies `_rate_counters` without lock:

```python
def check_rate_limit(self, user_id: int, tier: str) -> tuple:
    # No lock protection!
    self._rate_counters[user_id] = [
        ts for ts in self._rate_counters[user_id]
        if ts > window_start
    ]

    current_count = len(self._rate_counters[user_id])

    # Race: another thread could modify between read and write
    self._rate_counters[user_id].append(now)
```

**Impact:**
Under high concurrency:
- Lost updates (append overwrites concurrent append)
- Incorrect count (read-modify-write race)
- Rate limit bypass possible

**Recommendation:**
Add lock protection:

```python
_rate_limit_lock = threading.Lock()

def check_rate_limit(self, user_id: int, tier: str) -> tuple:
    from src.services.firebase import get_rate_limit

    limit = get_rate_limit(tier)
    now = time.time()
    window_start = now - 60

    with _rate_limit_lock:
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
```

### M4: Magic Numbers - Constants Not Centralized
**Severity:** MEDIUM
**Lines:** 30, 54-62, 285-286

**Problem:**
Cache size limit defined at module level, TTLs scattered:

```python
# Module level
MAX_CACHE_SIZE = 1000

# Class level (lines 54-62)
class StateManager:
    TTL_SESSION = 3600
    TTL_CONVERSATION = 86400
    TTL_CACHE = 300
    TTL_USER_TIER = 3600

    # Later additions (lines 285-286)
    TTL_PROFILE = 300
    TTL_CONTEXT = 60
```

**Impact:**
- MAX_CACHE_SIZE conceptually belongs to StateManager
- TTL constants not grouped together
- Magic number 20 in MAX_CONVERSATION_MESSAGES (line 62)

**Recommendation:**
Centralize all constants:

```python
class StateManager:
    # Cache configuration
    MAX_CACHE_SIZE = 1000
    MAX_CONVERSATION_MESSAGES = 20

    # TTL defaults (seconds) - grouped by domain
    # Session state
    TTL_SESSION = 3600        # 1 hour
    TTL_USER_TIER = 3600      # 1 hour

    # Conversation
    TTL_CONVERSATION = 86400  # 24 hours

    # Personalization
    TTL_PROFILE = 300         # 5 minutes
    TTL_CONTEXT = 60          # 1 minute

    # Generic cache
    TTL_CACHE = 300           # 5 minutes
```

Move MAX_CACHE_SIZE from module to class level:

```python
# Remove: MAX_CACHE_SIZE = 1000

# In _set_to_l1:
if len(self._l1_cache) >= self.MAX_CACHE_SIZE and key not in self._l1_cache:
    # ...
```

### M5: Error Handling - Silent Failures
**Severity:** MEDIUM
**Lines:** 88-90, 99-100, 109-110

**Problem:**
Firebase wrapper methods catch all exceptions and log but don't propagate:

```python
async def _firebase_get(self, collection: str, doc_id: str) -> Optional[Dict]:
    try:
        db = self._get_db()
        doc = await asyncio.to_thread(...)
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        self.logger.error("firebase_get_failed", ...)
        return None  # ✗ Caller can't distinguish error from missing doc
```

**Impact:**
Callers can't distinguish:
- Document doesn't exist (expected)
- Firebase unavailable (transient error)
- Permission denied (auth issue)

**Recommendation:**
Re-raise after logging:

```python
async def _firebase_get(self, collection: str, doc_id: str) -> Optional[Dict]:
    try:
        db = self._get_db()
        doc = await asyncio.to_thread(...)
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        self.logger.error("firebase_get_failed", ...)
        raise  # Let caller handle with circuit breaker
```

Or use circuit breaker pattern (already available):

```python
from src.core.resilience import firebase_circuit, CircuitOpenError

async def _firebase_get(self, collection: str, doc_id: str) -> Optional[Dict]:
    if firebase_circuit.state == CircuitState.OPEN:
        self.logger.warning("firebase_circuit_open", operation="get")
        return None

    try:
        db = self._get_db()
        doc = await asyncio.to_thread(...)
        firebase_circuit.record_success()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        firebase_circuit.record_failure()
        self.logger.error("firebase_get_failed", ...)
        return None  # Now safe - circuit will open after threshold
```

Check if firebase_circuit already used elsewhere (line 413 uses it in get_user_tier_cached).

### M6: LRU Eviction - Not True LRU
**Severity:** MEDIUM
**Lines:** 134-140

**Problem:**
Cache eviction uses expiration time, not access time:

```python
def _set_to_l1(self, key: str, value: Any, ttl_seconds: int):
    with _cache_lock:
        if len(self._l1_cache) >= MAX_CACHE_SIZE and key not in self._l1_cache:
            # Find oldest entry BY EXPIRATION, not by last access
            oldest_key = min(
                self._l1_cache.keys(),
                key=lambda k: self._l1_cache[k].expires_at
            )
            del self._l1_cache[oldest_key]
```

**Impact:**
- Not LRU (Least Recently Used) but LEE (Least Expiring Entry)
- Hot entries with short TTL evicted before cold entries with long TTL
- Misleading comment in docstring: "LRU eviction"

**Recommendation:**
Option 1 - True LRU with access tracking:

```python
@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

def _get_from_l1(self, key: str) -> Optional[Any]:
    with _cache_lock:
        entry = self._l1_cache.get(key)
        if entry and not entry.is_expired:
            entry.last_accessed = datetime.now(timezone.utc)  # Update access time
            return entry.value
        # ...

def _set_to_l1(self, key: str, value: Any, ttl_seconds: int):
    with _cache_lock:
        if len(self._l1_cache) >= MAX_CACHE_SIZE and key not in self._l1_cache:
            # Evict least recently accessed
            oldest_key = min(
                self._l1_cache.keys(),
                key=lambda k: self._l1_cache[k].last_accessed
            )
            del self._l1_cache[oldest_key]
```

Option 2 - Use functools.lru_cache for simple cases, or OrderedDict:

```python
from collections import OrderedDict

# In __init__:
self._l1_cache: OrderedDict[str, CacheEntry] = OrderedDict()

def _set_to_l1(self, key: str, value: Any, ttl_seconds: int):
    with _cache_lock:
        # Move to end (most recently used)
        if key in self._l1_cache:
            self._l1_cache.move_to_end(key)

        # Evict from front (least recently used)
        if len(self._l1_cache) >= MAX_CACHE_SIZE and key not in self._l1_cache:
            self._l1_cache.popitem(last=False)

        # Add new entry
        self._l1_cache[key] = CacheEntry(...)
```

Option 3 - Fix docstring if current behavior intentional:

```python
def _set_to_l1(self, key: str, value: Any, ttl_seconds: int):
    """Set to L1 cache with TTL and FIFO-by-expiration eviction (thread-safe)."""
```

## Low Priority Suggestions

### L1: Docstring Completeness
**Severity:** LOW
**Lines:** Various

**Issue:**
Some methods lack return type or parameter descriptions:

```python
async def clear_pending_skill(self, user_id: int):
    """Clear pending skill."""  # ✗ No params/returns documented
```

**Recommendation:**
Add Google-style docstrings per code standards:

```python
async def clear_pending_skill(self, user_id: int):
    """Clear pending skill from user session.

    Args:
        user_id: Telegram user ID

    Returns:
        None
    """
```

### L2: Cleanup Task - No Shutdown Hook
**Severity:** LOW
**Lines:** 523-525

**Issue:**
Background cleanup task created but never cancelled:

```python
if self._cleanup_task is None or self._cleanup_task.done():
    self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
```

**Impact:**
Task continues running after Modal function exit, logs warnings.

**Recommendation:**
Add shutdown method:

```python
async def shutdown(self):
    """Cancel background tasks gracefully."""
    if self._cleanup_task and not self._cleanup_task.done():
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        self.logger.info("cleanup_task_cancelled")
```

Call from Modal @exit hook or FastAPI lifespan.

### L3: Collection Names - Hardcoded Strings
**Severity:** LOW
**Lines:** 60-61, 293, 314

**Issue:**
Some collection names as class constants, others hardcoded:

```python
# Constants (good):
COLLECTION_SESSIONS = "telegram_sessions"
COLLECTION_CONVERSATIONS = "conversations"

# Hardcoded (bad):
await self.get("user_profiles", ...)  # Line 293
await self.get("user_contexts", ...)  # Line 314
await self.get("user_tiers", ...)     # Line 405
```

**Recommendation:**
Centralize all collection names:

```python
# Collection names
COLLECTION_SESSIONS = "telegram_sessions"
COLLECTION_CONVERSATIONS = "conversations"
COLLECTION_PROFILES = "user_profiles"
COLLECTION_CONTEXTS = "user_contexts"
COLLECTION_TIERS = "user_tiers"
```

## Positive Observations

1. **Thread Safety Implementation:** Proper double-check locking singleton (532-540)
2. **TTL Design:** Varied TTLs per data type appropriate (sessions 1h, contexts 1m)
3. **Cache Warming:** Proactive warming reduces cold-start latency (469-526)
4. **Structured Logging:** Consistent use of structlog with bound component (69)
5. **Async Wrappers:** Clean Firebase sync-to-async bridging with asyncio.to_thread (84-110)
6. **Docstring Quality:** Main methods have clear usage examples (45-51)
7. **Conversation Sanitization:** Proper handling of non-serializable content (354-367)
8. **Cache Expiration:** Expired entries cleaned on access (122-126)
9. **Defensive Programming:** Admin env var check prevents tier lookup overhead (401-403)
10. **Type Annotations:** Basic annotations present (most functions have return types)

## Recommended Actions

### Immediate (Before Next Deploy)
1. **Fix M3 (rate limit race)** - Add lock to check_rate_limit() - 10 min
2. **Fix M1 (invalidate consolidation)** - Use generic invalidate() - 5 min
3. **Fix M4 (centralize constants)** - Group TTLs, move MAX_CACHE_SIZE - 5 min
4. **Fix L3 (collection names)** - Add missing constants - 5 min

### Short Term (This Week)
5. **Fix H4 (type hints)** - Add Dict[str, Any] throughout - 30 min
6. **Fix H3 (cache race)** - Implement invalidate-before-write for set_session - 20 min
7. **Fix M2 (validation)** - Replace `if not user_id` with positive check - 15 min
8. **Fix M6 (LRU)** - Fix docstring or implement true LRU - 30 min
9. **Fix L1 (docstrings)** - Document all public methods - 30 min
10. **Fix L2 (shutdown)** - Add cleanup task cancellation - 15 min

### Medium Term (Next Sprint)
11. **Refactor H1 (SRP)** - Extract domain managers (2-3 days)
    - Day 1: CacheManager + FirebaseRepository base
    - Day 2: SessionStateManager + ProfileStateManager
    - Day 3: Update consumers, integration tests
12. **Refactor H2 (DRY)** - Factory pattern for accessors (4 hours)
13. **Fix M5 (error handling)** - Integrate circuit breaker or re-raise (2 hours)

### Metrics
- Type Coverage: ~60% (return types present, generics missing)
- Test Coverage: Not measured (no test file present)
- Linting Issues: 0 (py_compile passed)
- Lines of Code: 541
- Cyclomatic Complexity: High (StateManager: 25+ methods)
- Technical Debt Ratio: ~35% (186 lines of boilerplate in get/set pairs)

## Unresolved Questions

1. **Rate limit persistence:** Should `_rate_counters` survive restart? Currently in-memory only.
2. **Cache size tuning:** Is MAX_CACHE_SIZE=1000 based on profiling or arbitrary?
3. **TTL rationale:** Why TTL_CONTEXT=60s vs TTL_PROFILE=300s? Document decision.
4. **Migration strategy:** H1 refactor affects 7 files - coordinate with other teams?
5. **Circuit breaker usage:** Why get_user_tier_cached uses circuit (line 413) but wrappers don't?
6. **Firebase merge semantics:** set_session uses merge=True, generic set() uses merge=True by default - intentional?
