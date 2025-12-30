"""FAQ entry management service.

Smart FAQ system with hybrid keyword + semantic matching.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()


@dataclass
class FAQEntry:
    """FAQ entry for smart FAQ system."""
    id: str
    patterns: List[str]
    answer: str
    category: str
    enabled: bool
    embedding: Optional[List[float]] = None
    updated_at: Optional[datetime] = None


@with_firebase_circuit(open_return=[])
async def get_faq_entries(enabled_only: bool = True) -> List[FAQEntry]:
    """Get all FAQ entries from Firestore."""
    db = get_db()
    query = db.collection(Collections.FAQ_ENTRIES)

    if enabled_only:
        query = query.where(filter=FieldFilter("enabled", "==", True))

    docs = query.stream()
    entries = []

    for doc in docs:
        data = doc.to_dict()
        entries.append(FAQEntry(
            id=doc.id,
            patterns=data.get("patterns", []),
            answer=data.get("answer", ""),
            category=data.get("category", "general"),
            enabled=data.get("enabled", True),
            embedding=data.get("embedding"),
            updated_at=data.get("updated_at")
        ))

    logger.info("faq_entries_fetched", count=len(entries))
    return entries


@with_firebase_circuit(open_return=False)
async def create_faq_entry(entry: FAQEntry) -> bool:
    """Create new FAQ entry in Firestore."""
    db = get_db()
    doc_ref = db.collection(Collections.FAQ_ENTRIES).document(entry.id)

    doc_ref.set({
        "patterns": entry.patterns,
        "answer": entry.answer,
        "category": entry.category,
        "enabled": entry.enabled,
        "embedding": entry.embedding,
        "updated_at": datetime.utcnow()
    })

    logger.info("faq_entry_created", faq_id=entry.id)
    return True


@with_firebase_circuit(open_return=False)
async def update_faq_entry(faq_id: str, updates: dict) -> bool:
    """Update FAQ entry fields."""
    db = get_db()
    doc_ref = db.collection(Collections.FAQ_ENTRIES).document(faq_id)

    # Check exists
    if not doc_ref.get().exists:
        return False

    updates["updated_at"] = datetime.utcnow()
    doc_ref.update(updates)

    logger.info("faq_entry_updated", faq_id=faq_id)
    return True


async def delete_faq_entry(faq_id: str) -> bool:
    """Soft delete FAQ entry (set enabled=False)."""
    return await update_faq_entry(faq_id, {"enabled": False})
