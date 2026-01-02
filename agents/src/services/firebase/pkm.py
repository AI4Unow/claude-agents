"""PKM item CRUD operations.

Personal Knowledge Management system for capturing notes, tasks, ideas, links, and quotes.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, time
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
Priority = Literal["p1", "p2", "p3", "p4"]
EnergyLevel = Literal["high", "medium", "low"]


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


@dataclass
class SmartTask:
    """Enhanced task model with time-based and smart features.

    Extends PKMItem with reminder capabilities, calendar sync, and agent metadata.
    """
    id: str
    user_id: int
    content: str
    type: ItemType = "task"
    status: ItemStatus = "inbox"
    tags: List[str] = field(default_factory=list)
    project: Optional[str] = None
    priority: Optional[Priority] = None

    # Time fields (from reminders)
    due_date: Optional[datetime] = None
    due_time: Optional[time] = None
    reminder_offset: Optional[int] = None  # Minutes before due
    recurrence: Optional[str] = None  # RRULE format

    # Smart fields
    estimated_duration: Optional[int] = None  # Minutes
    energy_level: Optional[EnergyLevel] = None
    context: Optional[str] = None  # @home, @work, @errands
    blocked_by: List[str] = field(default_factory=list)

    # Calendar sync
    google_event_id: Optional[str] = None
    google_task_id: Optional[str] = None
    apple_uid: Optional[str] = None

    # Agent metadata
    auto_created: bool = False
    source_message_id: Optional[int] = None
    confidence_score: Optional[float] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Legacy fields for backward compat
    outcome: Optional[str] = None
    source: str = "telegram"


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


# ============================================================================
# SmartTask CRUD Operations
# ============================================================================


def _smart_task_to_dict(task: SmartTask, for_create: bool = False) -> dict:
    """Convert SmartTask to Firebase dict.

    Args:
        task: SmartTask instance
        for_create: If True, use SERVER_TIMESTAMP for timestamps

    Returns:
        Dict suitable for Firebase storage
    """
    data = {
        "user_id": task.user_id,
        "content": task.content,
        "type": task.type,
        "status": task.status,
        "tags": task.tags,
        "project": task.project,
        "priority": task.priority,
        "source": task.source,
        "blocked_by": task.blocked_by,
        "auto_created": task.auto_created,
    }

    # Handle datetime fields
    if for_create:
        data["created_at"] = firestore.SERVER_TIMESTAMP
        data["updated_at"] = firestore.SERVER_TIMESTAMP
    else:
        data["updated_at"] = firestore.SERVER_TIMESTAMP
        if task.created_at:
            data["created_at"] = task.created_at

    # Time fields
    if task.due_date:
        data["due_date"] = task.due_date
    if task.due_time:
        # Store time as string (HH:MM:SS format)
        data["due_time"] = task.due_time.isoformat()
    if task.reminder_offset is not None:
        data["reminder_offset"] = task.reminder_offset
    if task.recurrence:
        data["recurrence"] = task.recurrence

    # Smart fields
    if task.estimated_duration is not None:
        data["estimated_duration"] = task.estimated_duration
    if task.energy_level:
        data["energy_level"] = task.energy_level
    if task.context:
        data["context"] = task.context

    # Calendar sync
    if task.google_event_id:
        data["google_event_id"] = task.google_event_id
    if task.google_task_id:
        data["google_task_id"] = task.google_task_id
    if task.apple_uid:
        data["apple_uid"] = task.apple_uid

    # Agent metadata
    if task.source_message_id is not None:
        data["source_message_id"] = task.source_message_id
    if task.confidence_score is not None:
        data["confidence_score"] = task.confidence_score

    # Optional fields
    if task.completed_at:
        data["completed_at"] = task.completed_at
    if task.outcome:
        data["outcome"] = task.outcome

    return data


def _dict_to_smart_task(doc_id: str, data: dict) -> SmartTask:
    """Convert Firebase dict to SmartTask.

    Args:
        doc_id: Document ID
        data: Firebase document data

    Returns:
        SmartTask instance
    """
    # Parse time string back to time object
    due_time = None
    if data.get("due_time"):
        try:
            time_parts = data["due_time"].split(":")
            due_time = time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0)
        except (ValueError, IndexError):
            logger.warning("invalid_due_time_format", task_id=doc_id, due_time=data["due_time"])

    return SmartTask(
        id=doc_id,
        user_id=data.get("user_id"),
        content=data.get("content", ""),
        type=data.get("type", "task"),
        status=data.get("status", "inbox"),
        tags=data.get("tags", []),
        project=data.get("project"),
        priority=data.get("priority"),
        due_date=data.get("due_date"),
        due_time=due_time,
        reminder_offset=data.get("reminder_offset"),
        recurrence=data.get("recurrence"),
        estimated_duration=data.get("estimated_duration"),
        energy_level=data.get("energy_level"),
        context=data.get("context"),
        blocked_by=data.get("blocked_by", []),
        google_event_id=data.get("google_event_id"),
        google_task_id=data.get("google_task_id"),
        apple_uid=data.get("apple_uid"),
        auto_created=data.get("auto_created", False),
        source_message_id=data.get("source_message_id"),
        confidence_score=data.get("confidence_score"),
        outcome=data.get("outcome"),
        source=data.get("source", "telegram"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        completed_at=data.get("completed_at"),
    )


@with_firebase_circuit(raise_on_open=True)
async def create_smart_task(
    user_id: int,
    content: str,
    **kwargs
) -> SmartTask:
    """Create new SmartTask.

    Args:
        user_id: Telegram user ID
        content: Task content/text
        **kwargs: Optional fields (all SmartTask fields supported)

    Returns:
        Created SmartTask with ID

    Raises:
        CircuitOpenError: If Firebase circuit is open
    """
    db = get_db()

    # Build task
    task_id = str(uuid.uuid4())
    task = SmartTask(
        id=task_id,
        user_id=user_id,
        content=content,
        type=kwargs.get("type", "task"),
        status=kwargs.get("status", "inbox"),
        tags=kwargs.get("tags", []),
        project=kwargs.get("project"),
        priority=kwargs.get("priority"),
        due_date=kwargs.get("due_date"),
        due_time=kwargs.get("due_time"),
        reminder_offset=kwargs.get("reminder_offset"),
        recurrence=kwargs.get("recurrence"),
        estimated_duration=kwargs.get("estimated_duration"),
        energy_level=kwargs.get("energy_level"),
        context=kwargs.get("context"),
        blocked_by=kwargs.get("blocked_by", []),
        google_event_id=kwargs.get("google_event_id"),
        google_task_id=kwargs.get("google_task_id"),
        apple_uid=kwargs.get("apple_uid"),
        auto_created=kwargs.get("auto_created", False),
        source_message_id=kwargs.get("source_message_id"),
        confidence_score=kwargs.get("confidence_score"),
        source=kwargs.get("source", "telegram"),
    )

    # Save to Firebase (using same collection as PKMItem)
    doc_ref = db.collection("pkm_items").document(str(user_id)).collection("items").document(task_id)
    doc_ref.set(_smart_task_to_dict(task, for_create=True))

    logger.info("smart_task_created", user_id=user_id, task_id=task_id)

    # Fetch to get server timestamps
    created_doc = doc_ref.get()
    return _dict_to_smart_task(task_id, created_doc.to_dict())


@with_firebase_circuit(open_return=None)
async def get_smart_task(user_id: int, task_id: str) -> Optional[SmartTask]:
    """Get SmartTask by ID.

    Args:
        user_id: Telegram user ID
        task_id: Task ID

    Returns:
        SmartTask if found, None otherwise
    """
    db = get_db()
    doc = db.collection("pkm_items").document(str(user_id)).collection("items").document(task_id).get()

    if not doc.exists:
        return None

    return _dict_to_smart_task(task_id, doc.to_dict())


@with_firebase_circuit(open_return=None)
async def update_smart_task(user_id: int, task_id: str, **updates) -> Optional[SmartTask]:
    """Update SmartTask fields.

    Args:
        user_id: Telegram user ID
        task_id: Task ID
        **updates: Fields to update (any SmartTask field)

    Returns:
        Updated SmartTask if found, None otherwise

    Raises:
        CircuitOpenError: If Firebase circuit is open
    """
    db = get_db()
    doc_ref = db.collection("pkm_items").document(str(user_id)).collection("items").document(task_id)

    # Check if exists
    doc = doc_ref.get()
    if not doc.exists:
        logger.warning("smart_task_not_found", user_id=user_id, task_id=task_id)
        return None

    # Build update dict
    update_data = {"updated_at": firestore.SERVER_TIMESTAMP}

    # Allow updating specific fields
    allowed_fields = [
        "content", "status", "tags", "project", "priority", "due_date", "due_time",
        "reminder_offset", "recurrence", "estimated_duration", "energy_level",
        "context", "blocked_by", "google_event_id", "google_task_id", "apple_uid",
        "outcome", "type", "source_message_id", "confidence_score"
    ]

    for field in allowed_fields:
        if field in updates:
            value = updates[field]
            # Convert time object to string for storage
            if field == "due_time" and isinstance(value, time):
                update_data[field] = value.isoformat()
            else:
                update_data[field] = value

    # Auto-set completed_at when status changes to done
    if updates.get("status") == "done" and doc.get("status") != "done":
        update_data["completed_at"] = firestore.SERVER_TIMESTAMP

    doc_ref.update(update_data)
    logger.info("smart_task_updated", user_id=user_id, task_id=task_id, fields=list(update_data.keys()))

    # Fetch updated doc
    updated_doc = doc_ref.get()
    return _dict_to_smart_task(task_id, updated_doc.to_dict())


@with_firebase_circuit(open_return=False)
async def delete_smart_task(user_id: int, task_id: str) -> bool:
    """Delete SmartTask.

    Args:
        user_id: Telegram user ID
        task_id: Task ID

    Returns:
        True if deleted, False if not found
    """
    db = get_db()
    doc_ref = db.collection("pkm_items").document(str(user_id)).collection("items").document(task_id)

    # Check if exists
    doc = doc_ref.get()
    if not doc.exists:
        return False

    doc_ref.delete()
    logger.info("smart_task_deleted", user_id=user_id, task_id=task_id)
    return True


@with_firebase_circuit(open_return=[])
async def list_smart_tasks(
    user_id: int,
    status: Optional[ItemStatus] = None,
    limit: int = 20
) -> List[SmartTask]:
    """List SmartTasks with optional filters.

    Args:
        user_id: Telegram user ID
        status: Filter by status (inbox, active, done, archived)
        limit: Maximum number of tasks

    Returns:
        List of SmartTask instances
    """
    db = get_db()
    query = db.collection("pkm_items").document(str(user_id)).collection("items")
    query = query.where(filter=FieldFilter("type", "==", "task"))

    # Apply filters
    if status:
        query = query.where(filter=FieldFilter("status", "==", status))

    # Order by created_at desc, limit
    query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)

    results = []
    for doc in query.stream():
        results.append(_dict_to_smart_task(doc.id, doc.to_dict()))

    return results


@with_firebase_circuit(open_return=[])
async def get_due_tasks(user_id: int = None, limit: int = 50) -> List[SmartTask]:
    """Get tasks that are due and not completed.

    Args:
        user_id: Telegram user ID (if None, get for all users - admin only)
        limit: Maximum tasks to return

    Returns:
        List of SmartTask instances with due_date <= now
    """
    db = get_db()
    now = datetime.now()

    # Query all users or specific user
    if user_id:
        query = db.collection("pkm_items").document(str(user_id)).collection("items")
    else:
        # For admin/system use - query across all users
        query = db.collection_group("items")

    query = (
        query.where(filter=FieldFilter("type", "==", "task"))
        .where(filter=FieldFilter("status", "!=", "done"))
        .where(filter=FieldFilter("due_date", "<=", now))
        .limit(limit)
    )

    results = []
    for doc in query.stream():
        results.append(_dict_to_smart_task(doc.id, doc.to_dict()))

    return results
