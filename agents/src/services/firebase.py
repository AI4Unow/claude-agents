"""Firebase Firestore service for state management, task queues, and logging."""
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter
import structlog

logger = structlog.get_logger()

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
    db = get_db()
    doc = db.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else None


async def create_or_update_user(user_id: str, data: Dict) -> None:
    """Create or update user."""
    db = get_db()
    db.collection("users").document(user_id).set({
        **data,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)


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
    db = get_db()
    tasks = db.collection("tasks")\
        .where(filter=FieldFilter("type", "==", task_type))\
        .where(filter=FieldFilter("status", "==", "pending"))\
        .order_by("priority", direction=firestore.Query.DESCENDING)\
        .order_by("createdAt")\
        .limit(1)\
        .get()

    if not tasks:
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
    return claim_in_transaction(transaction, task_ref)


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
