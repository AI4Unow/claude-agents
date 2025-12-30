"""Temporal entities and II Framework services.

Temporal entities (facts with validity periods), decisions, observations, skills.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db, Collections


# ==================== Skills (II Framework) ====================

async def get_skill(skill_id: str) -> Optional[Dict]:
    """Get skill config and stats."""
    db = get_db()
    doc = db.collection(Collections.SKILLS).document(skill_id).get()
    return doc.to_dict() if doc.exists else None


async def update_skill_stats(
    skill_id: str,
    run_count: int,
    success_rate: float,
    duration_ms: int
) -> None:
    """Update skill execution statistics."""
    db = get_db()
    db.collection(Collections.SKILLS).document(skill_id).set({
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
    db.collection(Collections.SKILLS).document(skill_id).set({
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
    existing = db.collection(Collections.ENTITIES) \
        .where(filter=FieldFilter("type", "==", entity_type)) \
        .where(filter=FieldFilter("key", "==", key)) \
        .where(filter=FieldFilter("valid_until", "==", None)) \
        .limit(1) \
        .get()

    now = datetime.utcnow()

    for doc in existing:
        db.collection(Collections.ENTITIES).document(doc.id).update({
            "valid_until": now
        })

    # Create new version
    doc_ref = db.collection(Collections.ENTITIES).add({
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
    query = db.collection(Collections.ENTITIES) \
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
    query = db.collection(Collections.ENTITIES) \
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

    doc_ref = db.collection(Collections.DECISIONS).add({
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
    query = db.collection(Collections.DECISIONS) \
        .where(filter=FieldFilter("valid_until", "==", None)) \
        .where(filter=FieldFilter("confidence", ">=", min_confidence))

    if skill:
        query = query.where(filter=FieldFilter("learned_from", "==", skill))

    docs = query.get()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


async def invalidate_decision(decision_id: str) -> None:
    """Invalidate a decision rule."""
    db = get_db()
    db.collection(Collections.DECISIONS).document(decision_id).update({
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
    doc_ref = db.collection(Collections.OBSERVATIONS).add({
        "content": content,
        "summary": summary,
        "skill_id": skill_id,
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    return doc_ref[1].id


async def get_observation(obs_id: str) -> Optional[Dict]:
    """Retrieve a stored observation by ID."""
    db = get_db()
    doc = db.collection(Collections.OBSERVATIONS).document(obs_id).get()
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
    doc_ref = db.collection(Collections.LOGS).add({
        "skill_id": skill_id,
        "action": action,
        "result": result,
        "duration_ms": duration_ms,
        "observation_ref": observation_ref,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

    return doc_ref[1].id


async def log_activity(
    agent: str,
    action: str,
    details: Dict,
    level: str = "info"
) -> None:
    """Log agent activity."""
    db = get_db()
    db.collection(Collections.LOGS).add({
        "agent": agent,
        "action": action,
        "level": level,
        "details": details,
        "timestamp": firestore.SERVER_TIMESTAMP
    })


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
