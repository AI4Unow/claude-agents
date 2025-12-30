"""User management service.

CRUD operations for user profiles.
"""
from typing import Optional, Dict, Any

from firebase_admin import firestore

from ._client import get_db, Collections
from ._circuit import with_firebase_circuit


@with_firebase_circuit(open_return=None)
async def get_user(user_id: str) -> Optional[Dict]:
    """Get user by Telegram user ID."""
    db = get_db()
    doc = db.collection(Collections.USERS).document(user_id).get()
    return doc.to_dict() if doc.exists else None


@with_firebase_circuit(raise_on_open=True)
async def create_or_update_user(user_id: str, data: Dict) -> None:
    """Create or update user."""
    db = get_db()
    db.collection(Collections.USERS).document(user_id).set({
        **data,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)


# ==================== Agents ====================

async def update_agent_status(agent_id: str, status: str) -> None:
    """Update agent status."""
    db = get_db()
    db.collection(Collections.AGENTS).document(agent_id).set({
        "status": status,
        "lastRun": firestore.SERVER_TIMESTAMP
    }, merge=True)


async def get_agent(agent_id: str) -> Optional[Dict]:
    """Get agent by ID."""
    db = get_db()
    doc = db.collection(Collections.AGENTS).document(agent_id).get()
    return doc.to_dict() if doc.exists else None
