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
from datetime import datetime
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

