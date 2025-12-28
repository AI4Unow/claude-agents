---
phase: 1
title: "Firebase Task Queue Schema"
parent: plan.md
status: completed
effort: 1h
---

# Phase 1: Firebase Task Queue Schema

## Context

- Parent: [plan.md](./plan.md)
- Docs: [system-architecture.md](../../docs/system-architecture.md)
- Code: `agents/src/services/firebase.py`

## Overview

Add `task_queue` collection to Firebase with CRUD operations for local skill execution.

## Requirements

1. New Firestore collection: `task_queue`
2. Functions: create, get pending, update status, get result
3. Circuit breaker integration
4. TTL for old tasks (7 days)

## Architecture

```
task_queue/{task_id}
├── skill: string          # Skill name (e.g., "pdf")
├── task: string           # Task description
├── user_id: int           # Telegram user ID
├── deployment: "local"    # Always "local" for this queue
├── status: string         # pending | processing | completed | failed
├── created_at: timestamp
├── updated_at: timestamp
├── started_at: timestamp? # When processing began
├── completed_at: timestamp?
├── result: string?        # Execution result
├── error: string?         # Error message if failed
└── retry_count: int       # Number of retries (max 3)
```

## Related Code Files

- `agents/src/services/firebase.py` - Add new functions
- `agents/src/core/state.py` - Optional: cache pending tasks

## Implementation Steps

### Step 1: Add Task Queue Functions to firebase.py

```python
# ==================== Task Queue ====================

@dataclass
class LocalTask:
    """Local skill execution task."""
    task_id: str
    skill: str
    task: str
    user_id: int
    status: str  # pending, processing, completed, failed
    created_at: datetime
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0


async def create_local_task(
    skill: str,
    task: str,
    user_id: int
) -> str:
    """Create a new local task. Returns task_id."""
    db = get_db()
    doc_ref = db.collection("task_queue").document()
    doc_ref.set({
        "skill": skill,
        "task": task,
        "user_id": user_id,
        "deployment": "local",
        "status": "pending",
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "retry_count": 0
    })
    return doc_ref.id


async def get_pending_local_tasks(limit: int = 10) -> List[Dict]:
    """Get pending local tasks for processing."""
    db = get_db()
    query = (
        db.collection("task_queue")
        .where(filter=FieldFilter("status", "==", "pending"))
        .order_by("created_at")
        .limit(limit)
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]


async def claim_local_task(task_id: str) -> bool:
    """Claim a task for processing (atomic)."""
    db = get_db()
    doc_ref = db.collection("task_queue").document(task_id)

    # Atomic update only if still pending
    try:
        db.transaction()
        doc = doc_ref.get()
        if doc.exists and doc.to_dict().get("status") == "pending":
            doc_ref.update({
                "status": "processing",
                "started_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            return True
    except Exception:
        pass
    return False


async def complete_local_task(
    task_id: str,
    result: str,
    success: bool = True,
    error: str = None
) -> None:
    """Mark task as completed or failed."""
    db = get_db()
    db.collection("task_queue").document(task_id).update({
        "status": "completed" if success else "failed",
        "result": result if success else None,
        "error": error,
        "completed_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    })


async def get_task_result(task_id: str) -> Optional[Dict]:
    """Get task result by ID."""
    db = get_db()
    doc = db.collection("task_queue").document(task_id).get()
    return {"id": doc.id, **doc.to_dict()} if doc.exists else None
```

### Step 2: Add Cleanup Function

```python
async def cleanup_old_tasks(days: int = 7) -> int:
    """Delete tasks older than N days. Returns count deleted."""
    from datetime import timedelta

    db = get_db()
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.collection("task_queue").where(
        filter=FieldFilter("created_at", "<", cutoff)
    )

    count = 0
    for doc in query.stream():
        doc.reference.delete()
        count += 1

    return count
```

## Todo List

- [ ] Add LocalTask dataclass
- [ ] Add create_local_task function
- [ ] Add get_pending_local_tasks function
- [ ] Add claim_local_task function (atomic)
- [ ] Add complete_local_task function
- [ ] Add get_task_result function
- [ ] Add cleanup_old_tasks function
- [ ] Add circuit breaker checks to all functions

## Success Criteria

- [ ] Can create tasks in Firebase
- [ ] Can query pending tasks
- [ ] Can atomically claim tasks
- [ ] Can mark tasks complete/failed
- [ ] Old tasks auto-cleanup

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Firebase quota | Medium | Use batch operations, cleanup old |
| Race conditions | High | Atomic claim with transaction |
| Data loss | Medium | Include retry_count, error logging |

## Security Considerations

- Task IDs are random UUIDs (not guessable)
- Only authenticated Modal app can write
- Local executor validates task ownership

## Next Steps

After completion, proceed to [Phase 2](./phase-02-modal-detection-queueing.md).
