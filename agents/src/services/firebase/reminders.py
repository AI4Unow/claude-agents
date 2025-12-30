"""Reminder system service.

Schedule and manage time-based reminders.
"""
from datetime import datetime, timezone
from typing import List, Dict

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()


@with_firebase_circuit(raise_on_open=True)
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
    db = get_db()
    doc_ref = db.collection(Collections.REMINDERS).document()
    doc_ref.set({
        "user_id": user_id,
        "chat_id": chat_id,
        "message": message,
        "due_at": due_at,
        "sent": False,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    logger.info("reminder_created", id=doc_ref.id, due_at=due_at.isoformat())
    return doc_ref.id


@with_firebase_circuit(open_return=[])
async def get_due_reminders(limit: int = 50) -> List[Dict]:
    """Get reminders that are due and not sent.

    Args:
        limit: Maximum reminders to return

    Returns:
        List of reminder dicts with 'id' field
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    query = (
        db.collection(Collections.REMINDERS)
        .where(filter=FieldFilter("sent", "==", False))
        .where(filter=FieldFilter("due_at", "<=", now))
        .limit(limit)
    )

    results = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
    return results


@with_firebase_circuit(open_return=None)
async def mark_reminder_sent(reminder_id: str) -> None:
    """Mark reminder as sent.

    Args:
        reminder_id: Firebase document ID
    """
    db = get_db()
    db.collection(Collections.REMINDERS).document(reminder_id).update({
        "sent": True,
        "sent_at": firestore.SERVER_TIMESTAMP
    })


@with_firebase_circuit(open_return=[])
async def get_user_reminders(user_id: int, limit: int = 10) -> List[Dict]:
    """Get pending reminders for a user.

    Args:
        user_id: Telegram user ID
        limit: Maximum reminders to return

    Returns:
        List of reminder dicts with 'id' field
    """
    db = get_db()
    query = (
        db.collection(Collections.REMINDERS)
        .where(filter=FieldFilter("user_id", "==", user_id))
        .where(filter=FieldFilter("sent", "==", False))
        .order_by("due_at")
        .limit(limit)
    )

    results = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
    return results


@with_firebase_circuit(open_return=False)
async def delete_reminder(reminder_id: str, user_id: int) -> bool:
    """Delete a reminder (admin only).

    Args:
        reminder_id: Firebase document ID
        user_id: User ID (for verification)

    Returns:
        True if deleted, False otherwise
    """
    db = get_db()
    doc_ref = db.collection(Collections.REMINDERS).document(reminder_id)
    doc = doc_ref.get()

    if not doc.exists:
        return False

    data = doc.to_dict()
    if data.get("user_id") != user_id:
        return False

    doc_ref.delete()
    logger.info("reminder_deleted", id=reminder_id)
    return True
