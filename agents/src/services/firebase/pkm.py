"""PKM item CRUD operations.

Personal Knowledge Management system for capturing notes, tasks, ideas, links, and quotes.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Literal
import uuid

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()

ItemType = Literal["note", "task", "idea", "link", "quote"]
ItemStatus = Literal["inbox", "active", "done", "archived"]


@dataclass
class PKMItem:
    """PKM item with PARA-style organization."""
    id: str
    user_id: int
    content: str
    type: ItemType
    status: ItemStatus
    tags: List[str] = field(default_factory=list)
    project: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    outcome: Optional[str] = None
    source: str = "telegram"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


def _item_to_dict(item: PKMItem, for_create: bool = False) -> dict:
    """Convert PKMItem to Firebase dict.

    Args:
        item: PKMItem instance
        for_create: If True, use SERVER_TIMESTAMP for timestamps

    Returns:
        Dict suitable for Firebase storage
    """
    data = {
        "user_id": item.user_id,
        "content": item.content,
        "type": item.type,
        "status": item.status,
        "tags": item.tags,
        "project": item.project,
        "priority": item.priority,
        "source": item.source,
    }

    # Handle datetime fields
    if for_create:
        data["created_at"] = firestore.SERVER_TIMESTAMP
        data["updated_at"] = firestore.SERVER_TIMESTAMP
    else:
        data["updated_at"] = firestore.SERVER_TIMESTAMP
        if item.created_at:
            data["created_at"] = item.created_at

    # Optional datetime fields
    if item.due_date:
        data["due_date"] = item.due_date
    if item.completed_at:
        data["completed_at"] = item.completed_at
    if item.outcome:
        data["outcome"] = item.outcome

    return data


def _dict_to_item(doc_id: str, data: dict) -> PKMItem:
    """Convert Firebase dict to PKMItem.

    Args:
        doc_id: Document ID
        data: Firebase document data

    Returns:
        PKMItem instance
    """
    return PKMItem(
        id=doc_id,
        user_id=data.get("user_id"),
        content=data.get("content", ""),
        type=data.get("type", "note"),
        status=data.get("status", "inbox"),
        tags=data.get("tags", []),
        project=data.get("project"),
        priority=data.get("priority"),
        due_date=data.get("due_date"),
        outcome=data.get("outcome"),
        source=data.get("source", "telegram"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        completed_at=data.get("completed_at"),
    )


@with_firebase_circuit(raise_on_open=True)
async def create_item(
    user_id: int,
    content: str,
    item_type: ItemType = "note",
    **kwargs
) -> PKMItem:
    """Create new PKM item.

    Args:
        user_id: Telegram user ID
        content: Item content/text
        item_type: Type of item (note, task, idea, link, quote)
        **kwargs: Optional fields (tags, project, priority, due_date, status, source)

    Returns:
        Created PKMItem with ID

    Raises:
        CircuitOpenError: If Firebase circuit is open
    """
    db = get_db()

    # Build item
    item_id = str(uuid.uuid4())
    item = PKMItem(
        id=item_id,
        user_id=user_id,
        content=content,
        type=item_type,
        status=kwargs.get("status", "inbox"),
        tags=kwargs.get("tags", []),
        project=kwargs.get("project"),
        priority=kwargs.get("priority"),
        due_date=kwargs.get("due_date"),
        source=kwargs.get("source", "telegram"),
    )

    # Save to Firebase
    doc_ref = db.collection("pkm_items").document(str(user_id)).collection("items").document(item_id)
    doc_ref.set(_item_to_dict(item, for_create=True))

    logger.info("pkm_item_created", user_id=user_id, item_id=item_id, type=item_type)

    # Fetch to get server timestamps
    created_doc = doc_ref.get()
    return _dict_to_item(item_id, created_doc.to_dict())


@with_firebase_circuit(open_return=None)
async def get_item(user_id: int, item_id: str) -> Optional[PKMItem]:
    """Get item by ID.

    Args:
        user_id: Telegram user ID
        item_id: Item ID

    Returns:
        PKMItem if found, None otherwise
    """
    db = get_db()
    doc = db.collection("pkm_items").document(str(user_id)).collection("items").document(item_id).get()

    if not doc.exists:
        return None

    return _dict_to_item(item_id, doc.to_dict())


@with_firebase_circuit(open_return=None)
async def update_item(user_id: int, item_id: str, **updates) -> Optional[PKMItem]:
    """Update item fields.

    Args:
        user_id: Telegram user ID
        item_id: Item ID
        **updates: Fields to update (content, status, tags, project, priority, due_date, outcome)

    Returns:
        Updated PKMItem if found, None otherwise

    Raises:
        CircuitOpenError: If Firebase circuit is open
    """
    db = get_db()
    doc_ref = db.collection("pkm_items").document(str(user_id)).collection("items").document(item_id)

    # Check if exists
    doc = doc_ref.get()
    if not doc.exists:
        logger.warning("pkm_item_not_found", user_id=user_id, item_id=item_id)
        return None

    # Build update dict
    update_data = {"updated_at": firestore.SERVER_TIMESTAMP}

    # Allow updating specific fields
    allowed_fields = ["content", "status", "tags", "project", "priority", "due_date", "outcome", "type"]
    for field in allowed_fields:
        if field in updates:
            update_data[field] = updates[field]

    # Auto-set completed_at when status changes to done
    if updates.get("status") == "done" and doc.get("status") != "done":
        update_data["completed_at"] = firestore.SERVER_TIMESTAMP

    doc_ref.update(update_data)
    logger.info("pkm_item_updated", user_id=user_id, item_id=item_id, fields=list(update_data.keys()))

    # Fetch updated doc
    updated_doc = doc_ref.get()
    return _dict_to_item(item_id, updated_doc.to_dict())


@with_firebase_circuit(open_return=False)
async def delete_item(user_id: int, item_id: str) -> bool:
    """Delete item.

    Args:
        user_id: Telegram user ID
        item_id: Item ID

    Returns:
        True if deleted, False if not found
    """
    db = get_db()
    doc_ref = db.collection("pkm_items").document(str(user_id)).collection("items").document(item_id)

    # Check if exists
    doc = doc_ref.get()
    if not doc.exists:
        return False

    doc_ref.delete()
    logger.info("pkm_item_deleted", user_id=user_id, item_id=item_id)
    return True


@with_firebase_circuit(open_return=[])
async def list_items(
    user_id: int,
    status: Optional[ItemStatus] = None,
    item_type: Optional[ItemType] = None,
    limit: int = 20
) -> List[PKMItem]:
    """List items with optional filters.

    Args:
        user_id: Telegram user ID
        status: Filter by status (inbox, active, done, archived)
        item_type: Filter by type (note, task, idea, link, quote)
        limit: Maximum number of items

    Returns:
        List of PKMItem instances
    """
    db = get_db()
    query = db.collection("pkm_items").document(str(user_id)).collection("items")

    # Apply filters
    if status:
        query = query.where(filter=FieldFilter("status", "==", status))
    if item_type:
        query = query.where(filter=FieldFilter("type", "==", item_type))

    # Order by created_at desc, limit
    query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)

    results = []
    for doc in query.stream():
        results.append(_dict_to_item(doc.id, doc.to_dict()))

    return results


@with_firebase_circuit(open_return=[])
async def get_inbox(user_id: int, limit: int = 10) -> List[PKMItem]:
    """Get inbox items (status=inbox).

    Args:
        user_id: Telegram user ID
        limit: Maximum number of items

    Returns:
        List of inbox PKMItem instances
    """
    return await list_items(user_id, status="inbox", limit=limit)


@with_firebase_circuit(open_return=[])
async def get_tasks(user_id: int, include_done: bool = False) -> List[PKMItem]:
    """Get task items.

    Args:
        user_id: Telegram user ID
        include_done: Include completed tasks

    Returns:
        List of task PKMItem instances
    """
    db = get_db()
    query = db.collection("pkm_items").document(str(user_id)).collection("items")
    query = query.where(filter=FieldFilter("type", "==", "task"))

    if not include_done:
        query = query.where(filter=FieldFilter("status", "!=", "done"))

    query = query.order_by("status").order_by("created_at", direction=firestore.Query.DESCENDING)

    results = []
    for doc in query.stream():
        results.append(_dict_to_item(doc.id, doc.to_dict()))

    return results
