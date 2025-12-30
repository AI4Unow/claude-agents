# Phase 4: Refactor Services

## Context

- [firebase.py Review](../reports/code-reviewer-251230-1121-firebase-service-review.md)
- [state.py Review](../reports/code-reviewer-251230-1121-state-py-quality-review.md)
- [Comprehensive Analysis - Phase 4](../reports/codebase-review-251230-1119-comprehensive-analysis.md#phase-4-refactor-services-week-3-4---24-hrs)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P1 - High |
| Status | pending |
| Effort | 24 hours |
| Risk | HIGH (core services) |
| Depends On | Phase 1 |

## Key Insights

1. **firebase.py is 1413 lines handling 10+ domains** - God Object anti-pattern
2. **Circuit breaker pattern duplicated 24 times** - ~100 lines of boilerplate
3. **Inconsistent circuit handling** - returns None, [], False, or raises
4. **state.py has SRP violations** - 6 distinct responsibilities in one class
5. **Missing transaction for entity versioning** - race condition possible

## Requirements

- [ ] Split firebase.py into domain-specific services
- [ ] Create circuit breaker decorator for DRY
- [ ] Standardize circuit handling (return sentinel or raise)
- [ ] Split StateManager into focused managers
- [ ] Add Firestore transactions for entity versioning

## Architecture Decisions

1. **Domain Split**: firebase.py -> users.py, tasks.py, reminders.py, reports.py, tiers.py, faq.py
2. **Circuit Pattern**: Decorator with configurable open_return/raise_on_open
3. **Shared Client**: _client.py for Firebase/Storage initialization
4. **State Split**: CacheManager + SessionState + ProfileState + TierManager

## Target Structure

```
agents/src/services/firebase/
├── __init__.py (re-exports public API)
├── _client.py (shared db/bucket init)
├── _circuit.py (circuit breaker decorator)
├── _validation.py (input sanitization)
├── users.py (user CRUD)
├── tasks.py (task management)
├── local_tasks.py (local task queue)
├── reminders.py (reminder system)
├── reports.py (reports + storage)
├── tiers.py (user tier system)
├── faq.py (FAQ entries)
├── entities.py (temporal entities)
└── skills.py (skill learnings)
```

## Related Code Files

| File | Lines | Domains |
|------|-------|---------|
| `agents/src/services/firebase.py` | 72-108 | Users |
| `agents/src/services/firebase.py` | 112-126 | Agents |
| `agents/src/services/firebase.py` | 130-219 | Tasks |
| `agents/src/services/firebase.py` | 563-841 | Local Task Queue |
| `agents/src/services/firebase.py` | 845-1014 | Reminders |
| `agents/src/services/firebase.py` | 1018-1220 | Reports/Storage |
| `agents/src/services/firebase.py` | 1224-1303 | User Tiers |
| `agents/src/services/firebase.py` | 1307-1413 | FAQ System |
| `agents/src/core/state.py` | 44-526 | StateManager |

## Implementation Steps

### 1. Create Circuit Breaker Decorator (3h)

Create `agents/src/services/firebase/_circuit.py`:

```python
from functools import wraps
from typing import TypeVar, Callable, Any, Optional
import structlog

from src.core.resilience import firebase_circuit, CircuitState, CircuitOpenError

logger = structlog.get_logger()
T = TypeVar('T')

# Sentinel for circuit open state
CIRCUIT_OPEN = object()

def with_firebase_circuit(
    operation: str = None,
    open_return: Any = None,
    raise_on_open: bool = False
):
    """Decorator for Firebase operations with circuit breaker.

    Args:
        operation: Operation name for logging (auto-detected from func name)
        open_return: Value to return when circuit open (None, [], False, CIRCUIT_OPEN)
        raise_on_open: Raise CircuitOpenError instead of returning
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            op_name = operation or func.__name__

            # Check circuit state
            if firebase_circuit.state == CircuitState.OPEN:
                logger.warning("firebase_circuit_open", operation=op_name)
                if raise_on_open:
                    raise CircuitOpenError("firebase", firebase_circuit.cooldown_remaining)
                return open_return

            # Execute with circuit tracking
            try:
                result = await func(*args, **kwargs)
                firebase_circuit.record_success()
                return result
            except Exception as e:
                firebase_circuit.record_failure(e)
                logger.error(
                    f"firebase_{op_name}_error",
                    error=str(e)[:100],
                    error_type=type(e).__name__
                )
                raise

        return wrapper
    return decorator
```

### 2. Create Shared Client (2h)

Create `agents/src/services/firebase/_client.py`:

```python
from functools import lru_cache
import os
import json
import structlog

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import storage

logger = structlog.get_logger()

@lru_cache(maxsize=1)
def _init_firebase_once():
    """Initialize Firebase once (thread-safe via lru_cache)."""
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not cred_json:
        raise ValueError("FIREBASE_CREDENTIALS_JSON not set")

    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    app = firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("firebase_initialized", project=cred_dict.get("project_id"))
    return db

def get_db():
    """Get Firestore client (singleton)."""
    return _init_firebase_once()

@lru_cache(maxsize=1)
def _init_storage_once():
    """Initialize Cloud Storage once."""
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET")
    if not bucket_name:
        raise ValueError("FIREBASE_STORAGE_BUCKET not set")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    logger.info("storage_initialized", bucket=bucket_name)
    return bucket

def get_bucket():
    """Get Storage bucket (singleton)."""
    return _init_storage_once()

# Collection name constants
class Collections:
    USERS = "users"
    AGENTS = "agents"
    TASKS = "tasks"
    TOKENS = "tokens"
    LOGS = "logs"
    SKILLS = "skills"
    ENTITIES = "entities"
    DECISIONS = "decisions"
    OBSERVATIONS = "observations"
    TASK_QUEUE = "task_queue"
    REMINDERS = "reminders"
    REPORTS = "reports"
    USER_TIERS = "user_tiers"
    FAQ_ENTRIES = "faq_entries"
```

### 3. Create Input Validation (1h)

Create `agents/src/services/firebase/_validation.py`:

```python
import re
from typing import Union

VALID_DOC_ID = re.compile(r'^[a-zA-Z0-9_-]{1,1500}$')
PROTECTED_FIELDS = {"createdAt", "updatedAt", "id"}

def sanitize_doc_id(doc_id: Union[str, int]) -> str:
    """Sanitize Firestore document ID."""
    doc_id = str(doc_id)
    if not VALID_DOC_ID.match(doc_id):
        raise ValueError(f"Invalid document ID: {doc_id}")
    return doc_id

def sanitize_user_data(data: dict) -> dict:
    """Remove protected fields from user data."""
    return {k: v for k, v in data.items() if k not in PROTECTED_FIELDS}

def sanitize_path(user_id: Union[str, int], filename: str) -> str:
    """Sanitize storage path to prevent traversal."""
    user_id = sanitize_doc_id(user_id)
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    filename = filename.lstrip('.')
    return f"reports/{user_id}/{filename}"
```

### 4. Split Users Service (2h)

Create `agents/src/services/firebase/users.py`:

```python
from typing import Optional, Dict, Any
from google.cloud.firestore_v1 import FieldFilter
from firebase_admin import firestore

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit
from ._validation import sanitize_doc_id, sanitize_user_data

@with_firebase_circuit(open_return=None)
async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by Telegram user ID."""
    doc_id = sanitize_doc_id(user_id)
    db = get_db()
    doc = db.collection(Collections.USERS).document(doc_id).get()
    return doc.to_dict() if doc.exists else None

@with_firebase_circuit(raise_on_open=True)
async def create_or_update_user(user_id: int, data: Dict[str, Any]) -> None:
    """Create or update user."""
    doc_id = sanitize_doc_id(user_id)
    data = sanitize_user_data(data)
    db = get_db()
    db.collection(Collections.USERS).document(doc_id).set({
        **data,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)

@with_firebase_circuit(open_return=False)
async def delete_user(user_id: int) -> bool:
    """Delete user data (GDPR forget)."""
    doc_id = sanitize_doc_id(user_id)
    db = get_db()
    db.collection(Collections.USERS).document(doc_id).delete()
    return True
```

### 5. Split Tiers Service (2h)

Create `agents/src/services/firebase/tiers.py`:

```python
from typing import Optional
from firebase_admin import firestore

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit
from ._validation import sanitize_doc_id

# Rate limits by tier
RATE_LIMITS = {
    "guest": 10,
    "user": 30,
    "developer": 100,
    "admin": 1000
}

@with_firebase_circuit(open_return="guest")
async def get_user_tier(telegram_id: int) -> str:
    """Get user tier (defaults to 'guest' on error)."""
    doc_id = sanitize_doc_id(telegram_id)
    db = get_db()
    doc = db.collection(Collections.USER_TIERS).document(doc_id).get()

    if doc.exists:
        data = doc.to_dict()
        return data.get("tier", "guest")
    return "guest"

@with_firebase_circuit(open_return=False)
async def set_user_tier(telegram_id: int, tier: str) -> bool:
    """Set user tier."""
    if tier not in RATE_LIMITS:
        raise ValueError(f"Invalid tier: {tier}")

    doc_id = sanitize_doc_id(telegram_id)
    db = get_db()
    db.collection(Collections.USER_TIERS).document(doc_id).set({
        "tier": tier,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)
    return True

def get_rate_limit(tier: str) -> int:
    """Get rate limit for tier."""
    return RATE_LIMITS.get(tier, RATE_LIMITS["guest"])
```

### 6. Split Reports Service (3h)

Create `agents/src/services/firebase/reports.py`:

```python
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from firebase_admin import firestore

from ._client import get_db, get_bucket, Collections
from ._circuit import with_firebase_circuit
from ._validation import sanitize_doc_id, sanitize_path
import structlog

logger = structlog.get_logger()

@with_firebase_circuit(raise_on_open=True)
async def save_report(
    user_id: int,
    report_id: str,
    content: str,
    title: str,
    query: str,
    duration: float
) -> str:
    """Save research report to Storage and metadata to Firestore."""
    # Upload to Storage
    blob_path = sanitize_path(user_id, f"{report_id}.md")
    bucket = get_bucket()
    blob = bucket.blob(blob_path)
    blob.upload_from_string(content, content_type="text/markdown")
    logger.info("report_uploaded", path=blob_path)

    # Save metadata to Firestore
    db = get_db()
    doc_id = sanitize_doc_id(report_id)
    db.collection(Collections.REPORTS).document(doc_id).set({
        "user_id": user_id,
        "title": title,
        "query": query,
        "blob_path": blob_path,
        "duration": str(duration),
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    return report_id

@with_firebase_circuit(open_return=[])
async def list_user_reports(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """List user's research reports."""
    db = get_db()
    docs = (
        db.collection(Collections.REPORTS)
        .where(filter=FieldFilter("user_id", "==", user_id))
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

@with_firebase_circuit(open_return=None)
async def get_report_url(report_id: str, user_id: int) -> Optional[str]:
    """Get signed download URL for report."""
    db = get_db()
    doc = db.collection(Collections.REPORTS).document(report_id).get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    if data.get("user_id") != user_id:
        return None  # Access denied

    bucket = get_bucket()
    blob = bucket.blob(data["blob_path"])
    url = blob.generate_signed_url(expiration=timedelta(hours=1))
    return url
```

### 7. Split FAQ Service (2h)

Create `agents/src/services/firebase/faq.py` following same pattern.

### 8. Split Local Tasks Service (3h)

Create `agents/src/services/firebase/local_tasks.py` following same pattern.

### 9. Split Reminders Service (2h)

Create `agents/src/services/firebase/reminders.py` following same pattern.

### 10. Create Re-exports (1h)

Create `agents/src/services/firebase/__init__.py`:

```python
# Re-export public API for backward compatibility
from .users import get_user, create_or_update_user, delete_user
from .tiers import get_user_tier, set_user_tier, get_rate_limit
from .reports import save_report, list_user_reports, get_report_url
from .faq import get_faq_entries, create_faq_entry, update_faq_entry, delete_faq_entry
from .local_tasks import create_local_task, claim_local_task, complete_local_task
from .reminders import create_reminder, get_due_reminders, complete_reminder

__all__ = [
    # Users
    "get_user", "create_or_update_user", "delete_user",
    # Tiers
    "get_user_tier", "set_user_tier", "get_rate_limit",
    # Reports
    "save_report", "list_user_reports", "get_report_url",
    # FAQ
    "get_faq_entries", "create_faq_entry", "update_faq_entry", "delete_faq_entry",
    # Local Tasks
    "create_local_task", "claim_local_task", "complete_local_task",
    # Reminders
    "create_reminder", "get_due_reminders", "complete_reminder",
]
```

### 11. Refactor StateManager (3h)

Split `agents/src/core/state.py` into:

- `agents/src/core/cache.py` - CacheManager (generic L1 cache)
- `agents/src/core/session_state.py` - SessionStateManager
- `agents/src/core/profile_state.py` - ProfileStateManager
- `agents/src/core/tier_manager.py` - TierManager

Keep `state.py` as facade that re-exports for backward compatibility.

## Todo List

- [ ] Create firebase/_circuit.py with decorator
- [ ] Create firebase/_client.py with singletons
- [ ] Create firebase/_validation.py with sanitization
- [ ] Split users.py from firebase.py
- [ ] Split tiers.py from firebase.py
- [ ] Split reports.py from firebase.py
- [ ] Split faq.py from firebase.py
- [ ] Split local_tasks.py from firebase.py
- [ ] Split reminders.py from firebase.py
- [ ] Create firebase/__init__.py with re-exports
- [ ] Split CacheManager from state.py
- [ ] Split SessionStateManager from state.py
- [ ] Split ProfileStateManager from state.py
- [ ] Update all imports in consumers
- [ ] Run tests to verify no regressions

## Success Criteria

- [ ] firebase.py replaced with 10+ domain services
- [ ] Circuit breaker decorator used instead of 24 inline checks
- [ ] Each domain service < 200 lines
- [ ] StateManager split into 4 focused managers
- [ ] All existing tests pass
- [ ] No behavior changes from consumer perspective

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Import cycles | HIGH | MEDIUM | Careful dependency order |
| Breaking changes | HIGH | MEDIUM | Keep __init__.py re-exports |
| Circuit behavior changes | MEDIUM | LOW | Test each operation |
| Transaction errors | MEDIUM | LOW | Test entity versioning |

## Security Considerations

- Input sanitization must be applied consistently
- Document IDs must be validated before use
- Storage paths must prevent traversal attacks
- Protected fields must not be overwritable

## Next Steps

After Phase 4 completion:
1. Verify all Firebase operations work correctly
2. Check circuit breaker behavior under load
3. Begin [Phase 5: Testing and Docs](./phase-05-testing-docs.md)
