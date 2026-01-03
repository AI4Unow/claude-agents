"""Local task queue service.

Queue for local skill execution (browser automation, consumer IP required).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()


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


@with_firebase_circuit(raise_on_open=True)
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
    db = get_db()
    doc_ref = db.collection(Collections.TASK_QUEUE).document()
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
    logger.info("local_task_created", task_id=doc_ref.id, skill=skill)
    return doc_ref.id


@with_firebase_circuit(open_return=[])
async def get_pending_local_tasks(limit: int = 10) -> List[Dict]:
    """Get pending local tasks for processing.

    Also cleans up stale tasks:
    - pending > 1 hour -> failed
    - processing > 15 minutes -> failed

    Args:
        limit: Maximum number of tasks to return

    Returns:
        List of task dicts with 'id' field
    """
    db = get_db()
    now = datetime.utcnow()

    # 1. Cleanup stale tasks
    # Pending > 1 hour
    stale_pending_cutoff = now - timedelta(hours=1)
    stale_pending = (
        db.collection(Collections.TASK_QUEUE)
        .where(filter=FieldFilter("status", "==", "pending"))
        .where(filter=FieldFilter("created_at", "<", stale_pending_cutoff))
        .limit(10)
        .stream()
    )
    for doc in stale_pending:
        doc.reference.update({
            "status": "failed",
            "error": "Task timed out in pending status (>1h)",
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        logger.warning("local_task_stale_pending_failed", task_id=doc.id)

    # Processing > 15 minutes
    stale_processing_cutoff = now - timedelta(minutes=15)
    stale_processing = (
        db.collection(Collections.TASK_QUEUE)
        .where(filter=FieldFilter("status", "==", "processing"))
        .where(filter=FieldFilter("updated_at", "<", stale_processing_cutoff))
        .limit(10)
        .stream()
    )
    for doc in stale_processing:
        doc.reference.update({
            "status": "failed",
            "error": "Task timed out in processing status (>15m)",
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        logger.warning("local_task_stale_processing_failed", task_id=doc.id)

    # 2. Get pending tasks
    query = (
        db.collection(Collections.TASK_QUEUE)
        .where(filter=FieldFilter("status", "==", "pending"))
        .order_by("created_at")
        .limit(limit)
    )
    results = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
    return results


@with_firebase_circuit(open_return=False)
async def claim_local_task(task_id: str) -> bool:
    """Claim a task for processing (atomic).

    Uses transaction to ensure only one executor claims the task.

    Args:
        task_id: Firebase document ID

    Returns:
        True if claimed successfully, False otherwise
    """
    db = get_db()
    doc_ref = db.collection(Collections.TASK_QUEUE).document(task_id)

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

    if result:
        logger.info("local_task_claimed", task_id=task_id)
    return result


@with_firebase_circuit(raise_on_open=True)
async def complete_local_task(
    task_id: str,
    result: str,
    success: bool = True,
    error: str = None
) -> bool:
    """Mark task as completed or failed.

    Args:
        task_id: Firebase document ID
        result: Execution result (if success)
        success: True for completed, False for failed
        error: Error message (if failed)

    Returns:
        True if updated successfully, False if status was not processing
    """
    db = get_db()
    task_ref = db.collection(Collections.TASK_QUEUE).document(task_id)

    @firestore.transactional
    def complete_in_transaction(transaction, task_ref):
        snapshot = task_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False
        if snapshot.get("status") != "processing":
            logger.warning("local_task_completion_invalid_status", task_id=task_id, current_status=snapshot.get("status"))
            return False

        update_data = {
            "status": "completed" if success else "failed",
            "completed_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        if success:
            update_data["result"] = result
        else:
            update_data["error"] = error

        transaction.update(task_ref, update_data)
        return True

    transaction = db.transaction()
    updated = complete_in_transaction(transaction, task_ref)

    if updated:
        logger.info(
            "local_task_completed" if success else "local_task_failed",
            task_id=task_id
        )
    return updated


async def increment_retry_count(task_id: str) -> int:
    """Increment retry count and reset to pending for retry.

    Args:
        task_id: Firebase document ID

    Returns:
        New retry count
    """
    db = get_db()
    doc_ref = db.collection(Collections.TASK_QUEUE).document(task_id)
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


@with_firebase_circuit(open_return=None)
async def get_task_result(task_id: str) -> Optional[Dict]:
    """Get task result by ID.

    Args:
        task_id: Firebase document ID

    Returns:
        Task dict with 'id' field, or None if not found
    """
    db = get_db()
    doc = db.collection(Collections.TASK_QUEUE).document(task_id).get()

    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


@with_firebase_circuit(open_return=0)
async def cleanup_old_tasks(days: int = 7) -> int:
    """Delete tasks older than N days.

    Args:
        days: Age threshold in days (default 7)

    Returns:
        Number of tasks deleted
    """
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.collection(Collections.TASK_QUEUE).where(
        filter=FieldFilter("created_at", "<", cutoff)
    )

    count = 0
    for doc in query.stream():
        doc.reference.delete()
        count += 1

    logger.info("old_tasks_cleaned", count=count, days=days)
    return count
