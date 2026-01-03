"""Task management service.

Task queue operations for agent task distribution.
"""
from typing import Optional, Dict, Any, List

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()


async def create_task(
    task_type: str,
    payload: Dict,
    created_by: str,
    priority: int = 5
) -> str:
    """Create a new task and return task ID."""
    db = get_db()
    doc_ref = db.collection(Collections.TASKS).add({
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


@with_firebase_circuit(open_return=None)
async def claim_task(task_type: str, agent_id: str) -> Optional[Dict]:
    """Claim a pending task for processing."""
    db = get_db()
    tasks = db.collection(Collections.TASKS)\
        .where(filter=FieldFilter("type", "==", task_type))\
        .where(filter=FieldFilter("status", "==", "pending"))\
        .order_by("priority", direction=firestore.Query.DESCENDING)\
        .order_by("createdAt")\
        .limit(1)\
        .get()

    if not tasks:
        return None

    task_doc = tasks[0]
    task_ref = db.collection(Collections.TASKS).document(task_doc.id)

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
    return result


@with_firebase_circuit(open_return=None)
async def complete_task(task_id: str, result: Dict) -> bool:
    """Mark task as completed with result."""
    db = get_db()
    task_ref = db.collection(Collections.TASKS).document(task_id)

    @firestore.transactional
    def complete_in_transaction(transaction, task_ref):
        snapshot = task_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False
        if snapshot.get("status") != "processing":
            logger.warning("task_completion_invalid_status", task_id=task_id, current_status=snapshot.get("status"))
            return False
        transaction.update(task_ref, {
            "status": "done",
            "result": result,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        return True

    transaction = db.transaction()
    return complete_in_transaction(transaction, task_ref)


@with_firebase_circuit(open_return=None)
async def fail_task(task_id: str, error: str) -> bool:
    """Mark task as failed with error."""
    db = get_db()
    task_ref = db.collection(Collections.TASKS).document(task_id)

    @firestore.transactional
    def fail_in_transaction(transaction, task_ref):
        snapshot = task_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False
        if snapshot.get("status") != "processing":
            logger.warning("task_failure_invalid_status", task_id=task_id, current_status=snapshot.get("status"))
            return False
        transaction.update(task_ref, {
            "status": "failed",
            "error": error,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        return True

    transaction = db.transaction()
    return fail_in_transaction(transaction, task_ref)
