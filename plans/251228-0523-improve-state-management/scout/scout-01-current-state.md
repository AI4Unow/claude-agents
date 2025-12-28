# Scout Report: Current State Management

## Summary

Analyzed state management across the codebase. Found 3 separate patterns with inconsistencies.

## 1. Telegram Session State (main.py:695-784)

**Location:** `main.py` - Session state functions

**Pattern:** Direct Firebase per-request

```python
async def store_pending_skill(user_id: int, skill_name: str):
    db = init_firebase()
    db.collection("telegram_sessions").document(str(user_id)).set({...}, merge=True)
```

**Issues:**
- No caching - every request hits Firebase
- No TTL - orphaned sessions persist forever
- Synchronous Firebase ops in async functions
- Each function calls `init_firebase()` separately

**Fields Stored:**
- `pending_skill`: str | None
- `mode`: "simple" | "routed" | "evaluated"
- `timestamp`, `mode_updated`: datetime

## 2. Skill Registry Cache (src/skills/registry.py:86-87, 100-101)

**Location:** `SkillRegistry` class

**Pattern:** In-memory dict cache

```python
self._summaries_cache: Dict[str, SkillSummary] = {}
self._full_cache: Dict[str, Skill] = {}
```

**Issues:**
- No TTL/expiration
- Lost on container restart
- No cross-container sync
- No Firebase backup integration

## 3. Web Search Cache (src/tools/web_search.py:12, 68-81)

**Pattern:** Module-level dict with 15min TTL

```python
_cache: Dict[str, tuple] = {}
CACHE_TTL = 900  # 15 min
```

**Good:** Has TTL
**Bad:** Module-level global, lost on restart

## 4. Firebase Service (src/services/firebase.py)

**Collections:**
- `telegram_sessions/{user_id}` - NEW (from today's impl)
- `users/{user_id}` - User data
- `skills/{skill_id}` - Skill stats, memory backup
- `entities/{id}` - Temporal facts
- `decisions/{id}` - Learned rules
- `observations/{id}` - Masked outputs
- `logs/{id}` - Execution logs
- `tasks/{id}` - Task queue

**Patterns Used:**
- Singleton init (`_app`, `_db` globals)
- Transaction for atomic task claiming
- Temporal validity (`valid_from`, `valid_until`)
- SERVER_TIMESTAMP for timing

## 5. Agentic Loop State (src/services/agentic.py:33-41)

**Pattern:** In-function local state

```python
messages = []  # conversation context
accumulated_text = []  # response accumulator
```

**Issue:** No conversation persistence across requests

## Identified Problems

| Problem | Location | Impact |
|---------|----------|--------|
| No caching layer | main.py session funcs | Firebase latency per request |
| No TTL on sessions | telegram_sessions | Data accumulation |
| Cache lost on restart | registry, web_search | Cold start penalty |
| No conversation memory | agentic.py | No multi-turn context |
| Inconsistent async | firebase.py | Mixing sync/async |
| No cross-container sync | Modal containers | Stale cache |

## Recommended Improvements

1. **Session Manager Class** - Centralize session state with in-memory + Firebase layers
2. **TTL on all caches** - Auto-expire old data
3. **Conversation store** - Persist agentic loop messages
4. **Firebase async wrapper** - Use `asyncio.to_thread()` for sync ops
5. **Cache warming on startup** - Preload hot skills
