# Code Review: Service Layer

**Reviewer:** code-reviewer
**Date:** 2025-12-28
**Scope:** `/agents/src/services/` layer review

---

## Summary

Reviewed service layer implementation (774 lines changed across 5 files). Services provide database clients, LLM wrappers, and agentic execution. Code quality generally good with several critical issues requiring immediate attention.

---

## Critical Issues

### 1. **Missing Circuit Breaker Integration** [CRITICAL]

**Location:** `agentic.py`, `llm.py`, `firebase.py`, `qdrant.py`, `embeddings.py`

**Problem:** None of services use circuit breaker from `resilience.py` despite explicit requirement. Circuit breakers exist (`exa_circuit`, `firebase_circuit`, `qdrant_circuit`, `claude_circuit`) but are unused.

**Impact:**
- Cascading failures when external APIs fail
- No protection against service degradation
- Rate limit exhaustion
- Poor user experience during outages

**Fix:**
```python
# llm.py - Add circuit breaker
from src.core.resilience import claude_circuit

def chat(self, messages, system=None, max_tokens=2048, ...):
    # Wrap API call in circuit breaker
    return await claude_circuit.call(
        self._chat_internal,
        messages=messages,
        system=system,
        max_tokens=max_tokens,
        timeout=30.0
    )

async def _chat_internal(self, messages, system, max_tokens, ...):
    # Existing implementation
    response = self.client.messages.create(...)
    return response
```

Apply same pattern to:
- `firebase.py` - wrap Firestore calls with `firebase_circuit`
- `qdrant.py` - wrap Qdrant calls with `qdrant_circuit`
- `embeddings.py` - needs own circuit for Z.AI API

---

### 2. **Unsafe Singleton Pattern** [CRITICAL]

**Location:** `llm.py:73-78`, `firebase.py:27-43`

**Problem:** Global singletons not thread-safe. Missing lock protection during initialization.

**Current Code:**
```python
# llm.py - UNSAFE
_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    global _client
    if _client is None:  # ← Race condition
        _client = LLMClient()
    return _client
```

**Impact:** Multiple concurrent requests create duplicate clients, wasting resources and causing initialization race conditions.

**Fix:**
```python
# Use double-checked locking like state.py does
import threading

_client: Optional[LLMClient] = None
_client_lock = threading.Lock()

def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # Double-check
                _client = LLMClient()
    return _client
```

Apply to:
- `llm.py:73-78`
- `firebase.py:27-43`
- `qdrant.py:38-55`
- `embeddings.py:38-45`

---

### 3. **Unhandled Firebase Exceptions** [HIGH]

**Location:** `firebase.py` - all async functions

**Problem:** Firebase SDK throws sync exceptions but wrappers don't catch them. State manager catches generically but service layer doesn't.

**Current:**
```python
async def get_user(user_id: str) -> Optional[Dict]:
    db = get_db()
    doc = db.collection("users").document(user_id).get()  # ← Can throw
    return doc.to_dict() if doc.exists else None
```

**Impact:** Unhandled `FirebaseError`, `NetworkError`, `PermissionDenied` crash entire request.

**Fix:**
```python
from google.cloud.exceptions import GoogleCloudError

async def get_user(user_id: str) -> Optional[Dict]:
    try:
        db = get_db()
        doc = await asyncio.to_thread(
            lambda: db.collection("users").document(user_id).get()
        )
        return doc.to_dict() if doc.exists else None
    except GoogleCloudError as e:
        logger.error("firebase_get_user_failed", user_id=user_id, error=str(e))
        return None
```

Apply to all Firebase functions: `get_user`, `create_or_update_user`, `get_agent`, `update_agent_status`, `claim_task`, etc.

---

### 4. **Missing Input Validation** [HIGH]

**Location:** `firebase.py`, `qdrant.py`

**Problem:** No validation on user-provided IDs and data before database operations.

**Examples:**
```python
# firebase.py:56 - No validation
async def get_user(user_id: str) -> Optional[Dict]:
    db = get_db()
    doc = db.collection("users").document(user_id).get()  # ← What if user_id is ""?
```

**Impact:**
- Empty string IDs cause confusing errors
- Special characters in IDs might break queries
- Large payloads bypass size limits

**Fix:**
```python
async def get_user(user_id: str) -> Optional[Dict]:
    if not user_id or not user_id.strip():
        logger.warning("invalid_user_id", user_id=user_id)
        return None

    user_id = user_id.strip()
    if len(user_id) > 128:  # Reasonable limit
        logger.error("user_id_too_long", length=len(user_id))
        return None

    # ... rest of implementation
```

Add validation to all public functions accepting IDs, queries, payloads.

---

### 5. **Async Blocking Operations** [HIGH]

**Location:** `firebase.py` - most functions

**Problem:** Firebase SDK is synchronous but functions not wrapped in `asyncio.to_thread`. Blocks event loop.

**Current (BAD):**
```python
async def get_user(user_id: str) -> Optional[Dict]:
    db = get_db()
    doc = db.collection("users").document(user_id).get()  # ← Blocking I/O
    return doc.to_dict() if doc.exists else None
```

**Impact:** Single slow Firebase call blocks all concurrent requests in Modal function.

**Fix:** Already done correctly in `state.py:72-82`, apply same pattern everywhere:
```python
async def get_user(user_id: str) -> Optional[Dict]:
    try:
        db = get_db()
        doc = await asyncio.to_thread(
            lambda: db.collection("users").document(user_id).get()
        )
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error("get_user_failed", error=str(e))
        return None
```

Apply to all Firebase operations in `firebase.py`.

---

## High Priority Findings

### 6. **Improvement Proposal Circular Import** [HIGH]

**Location:** `agentic.py:194-203`

**Problem:** Lazy import of `main.send_improvement_notification` inside function creates tight coupling and import fragility.

**Current:**
```python
try:
    from main import send_improvement_notification  # ← Modal-specific
    await send_improvement_notification(proposal.to_dict())
except ImportError:
    logger.debug("skipping_notification_outside_modal")
```

**Impact:** Hard to test, tight coupling to Modal deployment, fragile error handling.

**Fix:** Use dependency injection or event bus pattern:
```python
# In improvement.py
class ImprovementService:
    def __init__(self, notification_callback: Optional[Callable] = None):
        self._notify = notification_callback

    async def store_proposal(self, proposal):
        # ... store logic ...
        if self._notify:
            await self._notify(proposal.to_dict())

# In main.py
service = get_improvement_service()
service._notify = send_improvement_notification
```

---

### 7. **Missing Timeouts on External Calls** [HIGH]

**Location:** `llm.py:60`, `embeddings.py:62-66`

**Problem:** No timeout on Anthropic/Z.AI API calls. Can hang indefinitely.

**Current:**
```python
response = self.client.messages.create(**kwargs)  # ← No timeout
```

**Impact:** Stuck requests consume Modal function slots, eventual resource exhaustion.

**Fix:** Add timeout to all HTTP clients:
```python
# llm.py
import anthropic

self._client = anthropic.Anthropic(
    api_key=self.api_key,
    base_url=self.base_url,
    default_headers={"x-api-key": self.api_key},
    timeout=30.0,  # ← Add this
)
```

Also add to Z.AI client in `embeddings.py`.

---

### 8. **Unbounded Embedding Batch Size** [MEDIUM]

**Location:** `embeddings.py:69-84`

**Problem:** `get_embeddings_batch` accepts unlimited list size. Z.AI API likely has limits.

**Current:**
```python
def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    client = get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,  # ← Could be 10,000 items
    )
    return [item.embedding for item in response.data]
```

**Impact:** Large batches fail with API errors or timeouts.

**Fix:**
```python
def get_embeddings_batch(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    if not texts:
        return []

    if len(texts) > 1000:
        logger.warning("embedding_batch_too_large", size=len(texts))
        texts = texts[:1000]

    # Process in chunks
    results = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=chunk)
        results.extend([item.embedding for item in response.data])

    return results
```

---

### 9. **State Manager Cache Race Condition** [MEDIUM]

**Location:** `state.py:217-226`

**Problem:** `set_session` invalidates L1 cache after Firebase write. Small window where stale data could be cached by concurrent read.

**Timeline:**
```
T1: set_session starts
T2: set_session writes to Firebase
T3: get_session reads (gets new data)
T4: get_session caches new data in L1
T5: set_session invalidates L1 ← Too late, T4 already cached
```

**Impact:** Rare race where session updates get lost briefly (until TTL expires).

**Fix:** Invalidate BEFORE write:
```python
async def set_session(self, user_id: int, data: Dict):
    if not user_id:
        return

    # Invalidate cache BEFORE write to prevent race
    await self.invalidate(self.COLLECTION_SESSIONS, str(user_id))

    update_data = {**data, "updated_at": datetime.now(timezone.utc).isoformat()}

    await self._firebase_set(
        self.COLLECTION_SESSIONS,
        str(user_id),
        update_data,
        merge=True
    )
```

---

## Medium Priority Improvements

### 10. **Hardcoded Magic Numbers** [MEDIUM]

**Location:** Multiple files

- `agentic.py:13` - `MAX_ITERATIONS = 5` (no comment why 5)
- `qdrant.py:21` - `VECTOR_DIM = 1024` (embedding-2, not embedding-3)
- `state.py:48-50` - TTL values uncommented
- `agentic.py:86` - `max_tokens=4096` (why 4096?)

**Fix:** Document rationale or make configurable:
```python
# Constants with rationale
MAX_ITERATIONS = 5  # Prevent runaway loops; typical tasks need 2-3
MAX_TOKENS = 4096   # Claude Opus context window optimization
VECTOR_DIM = 1024   # Z.AI embedding-2 output dimension
```

---

### 11. **Poor Error Messages** [MEDIUM]

**Location:** `embeddings.py:29-35`

**Problem:** `is_available()` test call produces cryptic errors.

**Current:**
```python
def is_available() -> bool:
    try:
        embedding = get_embedding("test")  # ← Generic error
        _available = len(embedding) > 0
    except Exception as e:
        logger.warning("embedding_service_unavailable", error=str(e))
        _available = False
```

**Fix:** Improve error context:
```python
def is_available() -> bool:
    global _available
    if _available is not None:
        return _available

    try:
        embedding = get_embedding("availability check")
        if not embedding or len(embedding) != VECTOR_DIM:
            logger.error("embedding_invalid_response", dim=len(embedding) if embedding else 0)
            _available = False
        else:
            _available = True
    except Exception as e:
        logger.warning(
            "embedding_service_unavailable",
            error=type(e).__name__,
            message=str(e)[:100],
            model=EMBEDDING_MODEL
        )
        _available = False

    return _available
```

---

### 12. **Missing Observability** [MEDIUM]

**Location:** All services

**Problem:** Limited metrics on performance, success rates, error patterns.

**Add:**
```python
# In llm.py
def chat(self, messages, ...):
    start = time.monotonic()
    try:
        response = self.client.messages.create(**kwargs)
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "llm_success",
            model=self.model,
            duration_ms=duration_ms,
            tokens_in=len(str(messages)),
            tokens_out=response.usage.output_tokens if hasattr(response, 'usage') else 0
        )
        return response
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error("llm_failed", duration_ms=duration_ms, error=str(e)[:100])
        raise
```

---

## Low Priority Suggestions

### 13. **Inconsistent Naming** [LOW]

- `firebase.py:get_db()` vs `qdrant.py:get_client()` - both are clients
- `embeddings.py:get_client()` vs `llm.py:get_llm_client()` - inconsistent naming
- `state.py:get_state_manager()` vs `agentic.py:get_registry()` - different patterns

**Suggestion:** Standardize on `get_X_client()` or `get_X_service()`.

---

### 14. **Type Hints Missing** [LOW]

**Location:** `agentic.py:170-213`, `firebase.py` several functions

Missing return type hints for:
```python
async def _trigger_improvement_proposal(...) -> None:  # ← Add
async def create_task(...) -> str:  # ← Already has
async def log_activity(...) -> None:  # ← Add
```

---

### 15. **Docstring Completeness** [LOW]

**Location:** `qdrant.py`, `firebase.py`

Many functions missing Args/Returns/Raises sections.

**Example:**
```python
async def store_conversation(
    user_id: str,
    agent: str,
    role: str,
    content: str,
    embedding: List[float]
) -> Optional[str]:
    """Store a conversation message with embedding.

    Args:
        user_id: Telegram user ID
        agent: Agent name handling conversation
        role: Message role (user/assistant)
        content: Message content text
        embedding: Pre-computed embedding vector (1024-dim)

    Returns:
        Point ID if stored successfully, None if Qdrant disabled

    Raises:
        QdrantException: If storage fails
    """
```

---

## Positive Observations

1. **Excellent resilience patterns** in `resilience.py` - circuit breaker implementation is production-ready
2. **Smart caching strategy** in `state.py` - L1/L2 pattern well-designed
3. **Proper thread safety** in `state.py` - double-checked locking, lock-protected cache operations
4. **Good separation of concerns** - services don't leak abstractions
5. **Async-first design** - proper use of `asyncio.to_thread` in `state.py`
6. **Comprehensive temporal data model** in `firebase.py` - entities/decisions with validity periods
7. **Fallback mechanisms** - Qdrant → Firebase keyword search is solid
8. **Structured logging** throughout - enables debugging

---

## Recommended Actions

**Immediate (Fix before production):**

1. Add circuit breakers to all external service calls (llm, firebase, qdrant, embeddings)
2. Fix singleton thread safety in `llm.py`, `firebase.py`, `qdrant.py`, `embeddings.py`
3. Wrap all Firebase sync calls in `asyncio.to_thread`
4. Add exception handling to all Firebase functions
5. Add input validation to database operation functions

**Short-term (Next sprint):**

6. Add timeouts to all HTTP client initializations
7. Fix improvement notification coupling (use dependency injection)
8. Add batch size limits to `get_embeddings_batch`
9. Fix cache invalidation race in `state.py:set_session`
10. Add comprehensive metrics/observability

**Long-term (Tech debt):**

11. Standardize naming conventions across services
12. Complete type hints and docstrings
13. Add integration tests for all service layer functions
14. Consider retry logic for transient failures (use `@with_retry` decorator)

---

## Metrics

**Files Reviewed:** 6 (agentic.py, llm.py, firebase.py, qdrant.py, embeddings.py, telegram.py)
**Lines Changed:** 774 additions
**Critical Issues:** 5
**High Priority:** 4
**Medium Priority:** 5
**Low Priority:** 3

**Estimated Remediation Time:**
- Critical fixes: 4-6 hours
- High priority: 3-4 hours
- Medium priority: 2-3 hours

---

## Unresolved Questions

1. **Z.AI API limits** - What are actual rate limits and batch sizes for embedding-2?
2. **Firebase quota** - What happens when Firestore read/write quota exhausted?
3. **Modal concurrency** - What's max concurrent requests per function? Need to validate connection pooling.
4. **Qdrant failover** - Should we implement automatic collection rebuild on corruption?
5. **LLM retry strategy** - Should we retry on rate limits (429) vs server errors (500)?
6. **Session TTL tuning** - Are 1hr/24hr TTLs optimal for actual usage patterns?
