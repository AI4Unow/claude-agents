# Phase 3: Services Resilience

## Files
- `agents/src/services/llm.py`
- `agents/src/services/firebase.py`
- `agents/src/services/qdrant.py`

## Issues

### 1. LLM Missing Circuit Breaker + Timeout (HIGH)
**File:** llm.py
**Fix:** Wrap API calls in circuit breaker

```python
from src.core.resilience import claude_circuit, CircuitOpenError

def chat(
    self,
    messages: List[Dict],
    system: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    tools: Optional[List[dict]] = None,
    timeout: float = 60.0,
):
    kwargs = {
        "model": self.model,
        "max_tokens": max_tokens,
        "system": system or "You are a helpful assistant.",
        "messages": messages,
        "timeout": timeout,
    }
    if tools:
        kwargs["tools"] = tools

    try:
        # Synchronous call - wrap in sync circuit check
        if claude_circuit.state.value == "open":
            raise CircuitOpenError("claude_api", claude_circuit._cooldown_remaining())

        response = self.client.messages.create(**kwargs)
        claude_circuit._record_success()

    except Exception as e:
        claude_circuit._record_failure(e)
        raise
```

### 2. Firebase Missing Circuit Breaker (HIGH)
**File:** firebase.py
**Fix:** Wrap Firestore operations

```python
from src.core.resilience import firebase_circuit

def get_document(self, collection: str, doc_id: str) -> Optional[Dict]:
    try:
        if firebase_circuit.state.value == "open":
            self.logger.warning("firebase_circuit_open")
            return None

        doc = self.db.collection(collection).document(doc_id).get()
        firebase_circuit._record_success()
        return doc.to_dict() if doc.exists else None

    except Exception as e:
        firebase_circuit._record_failure(e)
        self.logger.error("firebase_get_error", error=str(e)[:50])
        return None
```

### 3. Qdrant Missing Circuit Breaker (HIGH)
**File:** qdrant.py
**Fix:** Protect search operations

```python
from src.core.resilience import qdrant_circuit

async def search(self, collection: str, vector: List[float], limit: int = 5):
    try:
        result = await qdrant_circuit.call(
            self._search_internal,
            collection,
            vector,
            limit,
            timeout=15.0
        )
        return result
    except CircuitOpenError:
        self.logger.warning("qdrant_circuit_open")
        return []
```

## Success Criteria
- [x] All external calls protected by circuit breakers
- [x] Timeouts on all API calls
- [x] Graceful degradation when circuits open

## Implementation Status: COMPLETED

### Files Modified
1. `agents/src/services/llm.py` - Added circuit breaker + timeout (60s default)
2. `agents/src/services/firebase.py` - Added circuit breaker to critical operations
3. `agents/src/services/qdrant.py` - Added circuit breaker with async pattern

### Changes Summary
- **LLM**: Sync circuit pattern, timeout parameter, error handling
- **Firebase**: Protected get_user, create_or_update_user, claim_task
- **Qdrant**: Async circuit pattern on search_conversations, search_knowledge
