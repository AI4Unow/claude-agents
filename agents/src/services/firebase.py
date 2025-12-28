"""Firebase Firestore service for state management, task queues, and logging.

II Framework Temporal Schema:
- skills/{id}: Skill config, stats, memory backup
- entities/{id}: Facts with valid_from/valid_until (temporal)
- decisions/{id}: Learned rules with temporal validity
- logs/{id}: Execution logs with observation refs
- observations/{id}: Masked verbose outputs
"""
import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter

from src.utils.logging import get_logger
from src.core.resilience import firebase_circuit, CircuitOpenError, CircuitState

logger = get_logger()

# Initialize Firebase
_app = None
_db = None


def init_firebase():
    """Initialize Firebase with credentials from Modal secret."""
    global _app, _db

    if _app is not None:
        return _db

    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not cred_json:
        raise ValueError("FIREBASE_CREDENTIALS not set")

    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    _app = firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("firebase_initialized", project=cred_dict.get("project_id"))
    return _db


def get_db():
    """Get Firestore client, initializing if needed."""
    global _db
    if _db is None:
        init_firebase()
    return _db


# ==================== Users ====================

async def get_user(user_id: str) -> Optional[Dict]:
    """Get user by Telegram user ID."""
    # Check circuit state
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="get_user")
        return None

    try:
        db = get_db()
        doc = db.collection("users").document(user_id).get()
        firebase_circuit._record_success()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("firebase_get_user_error", error=str(e)[:50])
        return None


async def create_or_update_user(user_id: str, data: Dict) -> None:
    """Create or update user."""
    # Check circuit state
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="create_or_update_user")
        raise CircuitOpenError("firebase", firebase_circuit._cooldown_remaining())

    try:
        db = get_db()
        db.collection("users").document(user_id).set({
            **data,
            "updatedAt": firestore.SERVER_TIMESTAMP
        }, merge=True)
        firebase_circuit._record_success()
    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("firebase_update_user_error", error=str(e)[:50])
        raise


# ==================== Agents ====================

async def update_agent_status(agent_id: str, status: str) -> None:
    """Update agent status."""
    db = get_db()
    db.collection("agents").document(agent_id).set({
        "status": status,
        "lastRun": firestore.SERVER_TIMESTAMP
    }, merge=True)


async def get_agent(agent_id: str) -> Optional[Dict]:
    """Get agent by ID."""
    db = get_db()
    doc = db.collection("agents").document(agent_id).get()
    return doc.to_dict() if doc.exists else None


# ==================== Tasks ====================

async def create_task(
    task_type: str,
    payload: Dict,
    created_by: str,
    priority: int = 5
) -> str:
    """Create a new task and return task ID."""
    db = get_db()
    doc_ref = db.collection("tasks").add({
        "type": task_type,
        "status": "pending",
        "priority": priority,
        "createdBy": created_by,
        "assignedTo": None,
        "payload": payload,
        "result": None,
        "error": None,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })
    return doc_ref[1].id


async def claim_task(task_type: str, agent_id: str) -> Optional[Dict]:
    """Claim a pending task for processing."""
    # Check circuit state
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="claim_task")
        return None

    try:
        db = get_db()
        tasks = db.collection("tasks")\
            .where(filter=FieldFilter("type", "==", task_type))\
            .where(filter=FieldFilter("status", "==", "pending"))\
            .order_by("priority", direction=firestore.Query.DESCENDING)\
            .order_by("createdAt")\
            .limit(1)\
            .get()

        if not tasks:
            firebase_circuit._record_success()
            return None

        task_doc = tasks[0]
        task_ref = db.collection("tasks").document(task_doc.id)

        # Atomic claim with transaction
        @firestore.transactional
        def claim_in_transaction(transaction, task_ref):
            snapshot = task_ref.get(transaction=transaction)
            if snapshot.get("status") != "pending":
                return None
            transaction.update(task_ref, {
                "status": "processing",
                "assignedTo": agent_id,
                "updatedAt": firestore.SERVER_TIMESTAMP
            })
            return {**snapshot.to_dict(), "id": snapshot.id}

        transaction = db.transaction()
        result = claim_in_transaction(transaction, task_ref)
        firebase_circuit._record_success()
        return result

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("firebase_claim_task_error", error=str(e)[:50])
        return None


async def complete_task(task_id: str, result: Dict) -> None:
    """Mark task as completed with result."""
    db = get_db()
    db.collection("tasks").document(task_id).update({
        "status": "done",
        "result": result,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })


async def fail_task(task_id: str, error: str) -> None:
    """Mark task as failed with error."""
    db = get_db()
    db.collection("tasks").document(task_id).update({
        "status": "failed",
        "error": error,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })


# ==================== Tokens ====================

async def get_token(service: str) -> Optional[Dict]:
    """Get OAuth token for service."""
    db = get_db()
    doc = db.collection("tokens").document(service).get()
    return doc.to_dict() if doc.exists else None


async def save_token(
    service: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime
) -> None:
    """Save OAuth token."""
    db = get_db()
    db.collection("tokens").document(service).set({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresAt": expires_at,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })


# ==================== Logs ====================

async def log_activity(
    agent: str,
    action: str,
    details: Dict,
    level: str = "info"
) -> None:
    """Log agent activity."""
    db = get_db()
    db.collection("logs").add({
        "agent": agent,
        "action": action,
        "level": level,
        "details": details,
        "timestamp": firestore.SERVER_TIMESTAMP
    })


# ==================== Skills (II Framework) ====================

async def get_skill(skill_id: str) -> Optional[Dict]:
    """Get skill config and stats."""
    db = get_db()
    doc = db.collection("skills").document(skill_id).get()
    return doc.to_dict() if doc.exists else None


async def update_skill_stats(
    skill_id: str,
    run_count: int,
    success_rate: float,
    duration_ms: int
) -> None:
    """Update skill execution statistics."""
    db = get_db()
    db.collection("skills").document(skill_id).set({
        "stats": {
            "runCount": run_count,
            "successRate": success_rate,
            "lastRun": firestore.SERVER_TIMESTAMP,
            "avgDurationMs": duration_ms
        },
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)


async def backup_skill_memory(skill_id: str, memory_content: str) -> None:
    """Backup skill memory to Firebase."""
    db = get_db()
    db.collection("skills").document(skill_id).set({
        "memoryBackup": memory_content,
        "memoryBackedUpAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)


# ==================== Entities (Temporal) ====================

async def create_entity(
    entity_type: str,
    key: str,
    value: Any,
    source_skill: str
) -> str:
    """Create a temporal entity (fact with validity period).

    Returns:
        Entity ID
    """
    db = get_db()

    # Invalidate previous version if exists
    existing = db.collection("entities") \
        .where(filter=FieldFilter("type", "==", entity_type)) \
        .where(filter=FieldFilter("key", "==", key)) \
        .where(filter=FieldFilter("valid_until", "==", None)) \
        .limit(1) \
        .get()

    now = datetime.utcnow()

    for doc in existing:
        db.collection("entities").document(doc.id).update({
            "valid_until": now
        })

    # Create new version
    doc_ref = db.collection("entities").add({
        "type": entity_type,
        "key": key,
        "value": value,
        "source_skill": source_skill,
        "valid_from": now,
        "valid_until": None,  # Current version
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    return doc_ref[1].id


async def get_entity(
    entity_type: str,
    key: str,
    at_time: Optional[datetime] = None
) -> Optional[Dict]:
    """Get entity value, optionally at a specific time (time-travel).

    Args:
        entity_type: Type of entity (e.g., 'user_preference')
        key: Entity key
        at_time: Query time (None = current)

    Returns:
        Entity dict or None
    """
    db = get_db()
    query = db.collection("entities") \
        .where(filter=FieldFilter("type", "==", entity_type)) \
        .where(filter=FieldFilter("key", "==", key))

    if at_time is None:
        # Current value
        query = query.where(filter=FieldFilter("valid_until", "==", None))
    else:
        # Historical value at specific time
        query = query.where(filter=FieldFilter("valid_from", "<=", at_time))

    docs = query.limit(10).get()

    if at_time is None:
        return docs[0].to_dict() if docs else None

    # For historical queries, filter valid_until in memory
    for doc in docs:
        data = doc.to_dict()
        valid_until = data.get("valid_until")
        if valid_until is None or valid_until > at_time:
            return data

    return None


async def get_entities_by_type(
    entity_type: str,
    source_skill: Optional[str] = None
) -> List[Dict]:
    """Get all current entities of a type."""
    db = get_db()
    query = db.collection("entities") \
        .where(filter=FieldFilter("type", "==", entity_type)) \
        .where(filter=FieldFilter("valid_until", "==", None))

    if source_skill:
        query = query.where(
            filter=FieldFilter("source_skill", "==", source_skill)
        )

    docs = query.get()
    return [doc.to_dict() for doc in docs]


# ==================== Decisions (Learned Rules) ====================

async def create_decision(
    condition: str,
    action: str,
    confidence: float,
    learned_from: str
) -> str:
    """Create a learned decision rule with temporal validity.

    Returns:
        Decision ID
    """
    db = get_db()
    now = datetime.utcnow()

    doc_ref = db.collection("decisions").add({
        "condition": condition,
        "action": action,
        "confidence": confidence,
        "learned_from": learned_from,
        "valid_from": now,
        "valid_until": None,
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    return doc_ref[1].id


async def get_decisions(
    skill: Optional[str] = None,
    min_confidence: float = 0.7
) -> List[Dict]:
    """Get current decision rules."""
    db = get_db()
    query = db.collection("decisions") \
        .where(filter=FieldFilter("valid_until", "==", None)) \
        .where(filter=FieldFilter("confidence", ">=", min_confidence))

    if skill:
        query = query.where(filter=FieldFilter("learned_from", "==", skill))

    docs = query.get()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


async def invalidate_decision(decision_id: str) -> None:
    """Invalidate a decision rule."""
    db = get_db()
    db.collection("decisions").document(decision_id).update({
        "valid_until": datetime.utcnow()
    })


# ==================== Observations (Masked Outputs) ====================

async def store_observation(
    content: str,
    summary: str,
    skill_id: str
) -> str:
    """Store verbose output for observation masking.

    Returns:
        Observation ID for reference
    """
    db = get_db()
    doc_ref = db.collection("observations").add({
        "content": content,
        "summary": summary,
        "skill_id": skill_id,
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    return doc_ref[1].id


async def get_observation(obs_id: str) -> Optional[Dict]:
    """Retrieve a stored observation by ID."""
    db = get_db()
    doc = db.collection("observations").document(obs_id).get()
    return doc.to_dict() if doc.exists else None


# ==================== Logs with Observation Refs ====================

async def log_execution(
    skill_id: str,
    action: str,
    result: str,
    duration_ms: int,
    observation_ref: Optional[str] = None
) -> str:
    """Log skill execution with optional observation reference.

    Returns:
        Log ID
    """
    db = get_db()
    doc_ref = db.collection("logs").add({
        "skill_id": skill_id,
        "action": action,
        "result": result,
        "duration_ms": duration_ms,
        "observation_ref": observation_ref,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

    return doc_ref[1].id


# ==================== Keyword Search Fallback ====================

async def keyword_search(
    collection: str,
    keywords: List[str],
    limit: int = 10
) -> List[Dict]:
    """Simple keyword search fallback when Qdrant unavailable.

    Note: This is a basic implementation. For production,
    consider using Firebase full-text search extensions.
    """
    db = get_db()

    # Get recent documents
    docs = db.collection(collection) \
        .order_by("createdAt", direction=firestore.Query.DESCENDING) \
        .limit(limit * 3) \
        .get()

    results = []
    for doc in docs:
        data = doc.to_dict()
        text_fields = []

        # Extract text from common fields
        for field in ["content", "condition", "action", "summary", "key"]:
            if field in data and isinstance(data[field], str):
                text_fields.append(data[field].lower())

        text = " ".join(text_fields)

        # Simple keyword matching
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            results.append({"id": doc.id, "score": score, **data})

    # Sort by score and limit
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


# ==================== Local Task Queue ====================

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
    """Create a new local task. Returns task_id.

    Args:
        skill: Local skill name (e.g., 'pdf', 'docx')
        task: Task description/prompt
        user_id: Telegram user ID for notifications

    Returns:
        Task ID (Firebase document ID)
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="create_local_task")
        raise CircuitOpenError("firebase", firebase_circuit._cooldown_remaining())

    try:
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
        firebase_circuit._record_success()
        logger.info("local_task_created", task_id=doc_ref.id, skill=skill)
        return doc_ref.id

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("create_local_task_error", error=str(e)[:100])
        raise


async def get_pending_local_tasks(limit: int = 10) -> List[Dict]:
    """Get pending local tasks for processing.

    Args:
        limit: Maximum number of tasks to return

    Returns:
        List of task dicts with 'id' field
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="get_pending_local_tasks")
        return []

    try:
        db = get_db()
        query = (
            db.collection("task_queue")
            .where(filter=FieldFilter("status", "==", "pending"))
            .order_by("created_at")
            .limit(limit)
        )
        results = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
        firebase_circuit._record_success()
        return results

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("get_pending_local_tasks_error", error=str(e)[:100])
        return []


async def claim_local_task(task_id: str) -> bool:
    """Claim a task for processing (atomic).

    Uses transaction to ensure only one executor claims the task.

    Args:
        task_id: Firebase document ID

    Returns:
        True if claimed successfully, False otherwise
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="claim_local_task")
        return False

    try:
        db = get_db()
        doc_ref = db.collection("task_queue").document(task_id)

        @firestore.transactional
        def claim_in_transaction(transaction, doc_ref):
            snapshot = doc_ref.get(transaction=transaction)
            if not snapshot.exists:
                return False
            if snapshot.get("status") != "pending":
                return False
            transaction.update(doc_ref, {
                "status": "processing",
                "started_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            return True

        transaction = db.transaction()
        result = claim_in_transaction(transaction, doc_ref)
        firebase_circuit._record_success()

        if result:
            logger.info("local_task_claimed", task_id=task_id)
        return result

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("claim_local_task_error", task_id=task_id, error=str(e)[:100])
        return False


async def complete_local_task(
    task_id: str,
    result: str,
    success: bool = True,
    error: str = None
) -> None:
    """Mark task as completed or failed.

    Args:
        task_id: Firebase document ID
        result: Execution result (if success)
        success: True for completed, False for failed
        error: Error message (if failed)
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="complete_local_task")
        raise CircuitOpenError("firebase", firebase_circuit._cooldown_remaining())

    try:
        db = get_db()
        update_data = {
            "status": "completed" if success else "failed",
            "completed_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        if success:
            update_data["result"] = result
        else:
            update_data["error"] = error

        db.collection("task_queue").document(task_id).update(update_data)
        firebase_circuit._record_success()

        logger.info(
            "local_task_completed" if success else "local_task_failed",
            task_id=task_id
        )

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("complete_local_task_error", task_id=task_id, error=str(e)[:100])
        raise


async def increment_retry_count(task_id: str) -> int:
    """Increment retry count and reset to pending for retry.

    Args:
        task_id: Firebase document ID

    Returns:
        New retry count
    """
    db = get_db()
    doc_ref = db.collection("task_queue").document(task_id)
    doc = doc_ref.get()

    if not doc.exists:
        return -1

    current_count = doc.to_dict().get("retry_count", 0)
    new_count = current_count + 1

    if new_count <= 3:  # Max 3 retries
        doc_ref.update({
            "retry_count": new_count,
            "status": "pending",
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        logger.info("local_task_retry", task_id=task_id, retry_count=new_count)
    else:
        doc_ref.update({
            "status": "failed",
            "error": "Max retries exceeded",
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        logger.warning("local_task_max_retries", task_id=task_id)

    return new_count


async def get_task_result(task_id: str) -> Optional[Dict]:
    """Get task result by ID.

    Args:
        task_id: Firebase document ID

    Returns:
        Task dict with 'id' field, or None if not found
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="get_task_result")
        return None

    try:
        db = get_db()
        doc = db.collection("task_queue").document(task_id).get()
        firebase_circuit._record_success()

        if doc.exists:
            return {"id": doc.id, **doc.to_dict()}
        return None

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("get_task_result_error", task_id=task_id, error=str(e)[:100])
        return None


async def cleanup_old_tasks(days: int = 7) -> int:
    """Delete tasks older than N days.

    Args:
        days: Age threshold in days (default 7)

    Returns:
        Number of tasks deleted
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="cleanup_old_tasks")
        return 0

    try:
        db = get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = db.collection("task_queue").where(
            filter=FieldFilter("created_at", "<", cutoff)
        )

        count = 0
        for doc in query.stream():
            doc.reference.delete()
            count += 1

        firebase_circuit._record_success()
        logger.info("old_tasks_cleaned", count=count, days=days)
        return count

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("cleanup_old_tasks_error", error=str(e)[:100])
        return 0


# ==================== Reminders ====================

async def create_reminder(
    user_id: int,
    chat_id: int,
    message: str,
    due_at: datetime
) -> str:
    """Create a reminder. Returns reminder ID.

    Args:
        user_id: Telegram user ID
        chat_id: Chat ID to send reminder to
        message: Reminder message
        due_at: When to send the reminder (UTC)

    Returns:
        Reminder ID
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="create_reminder")
        raise CircuitOpenError("firebase", firebase_circuit._cooldown_remaining())

    try:
        db = get_db()
        doc_ref = db.collection("reminders").document()
        doc_ref.set({
            "user_id": user_id,
            "chat_id": chat_id,
            "message": message,
            "due_at": due_at,
            "sent": False,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        firebase_circuit._record_success()
        logger.info("reminder_created", id=doc_ref.id, due_at=due_at.isoformat())
        return doc_ref.id

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("create_reminder_error", error=str(e)[:100])
        raise


async def get_due_reminders(limit: int = 50) -> List[Dict]:
    """Get reminders that are due and not sent.

    Args:
        limit: Maximum reminders to return

    Returns:
        List of reminder dicts with 'id' field
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="get_due_reminders")
        return []

    try:
        from datetime import timezone
        db = get_db()
        now = datetime.now(timezone.utc)

        query = (
            db.collection("reminders")
            .where(filter=FieldFilter("sent", "==", False))
            .where(filter=FieldFilter("due_at", "<=", now))
            .limit(limit)
        )

        results = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
        firebase_circuit._record_success()
        return results

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("get_due_reminders_error", error=str(e)[:100])
        return []


async def mark_reminder_sent(reminder_id: str) -> None:
    """Mark reminder as sent.

    Args:
        reminder_id: Firebase document ID
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="mark_reminder_sent")
        return

    try:
        db = get_db()
        db.collection("reminders").document(reminder_id).update({
            "sent": True,
            "sent_at": firestore.SERVER_TIMESTAMP
        })
        firebase_circuit._record_success()

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("mark_reminder_sent_error", error=str(e)[:100])


async def get_user_reminders(user_id: int, limit: int = 10) -> List[Dict]:
    """Get pending reminders for a user.

    Args:
        user_id: Telegram user ID
        limit: Maximum reminders to return

    Returns:
        List of reminder dicts with 'id' field
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="get_user_reminders")
        return []

    try:
        db = get_db()
        query = (
            db.collection("reminders")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("sent", "==", False))
            .order_by("due_at")
            .limit(limit)
        )

        results = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
        firebase_circuit._record_success()
        return results

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("get_user_reminders_error", error=str(e)[:100])
        return []


async def delete_reminder(reminder_id: str, user_id: int) -> bool:
    """Delete a reminder (admin only).

    Args:
        reminder_id: Firebase document ID
        user_id: User ID (for verification)

    Returns:
        True if deleted, False otherwise
    """
    if firebase_circuit.state == CircuitState.OPEN:
        logger.warning("firebase_circuit_open", operation="delete_reminder")
        return False

    try:
        db = get_db()
        doc_ref = db.collection("reminders").document(reminder_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        data = doc.to_dict()
        if data.get("user_id") != user_id:
            return False

        doc_ref.delete()
        firebase_circuit._record_success()
        logger.info("reminder_deleted", id=reminder_id)
        return True

    except Exception as e:
        firebase_circuit._record_failure(e)
        logger.error("delete_reminder_error", error=str(e)[:100])
        return False

