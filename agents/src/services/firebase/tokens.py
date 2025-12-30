"""OAuth token management service.

Storage and retrieval of OAuth tokens for external services.
"""
from datetime import datetime
from typing import Optional, Dict

from firebase_admin import firestore

from ._client import get_db, Collections


async def get_token(service: str) -> Optional[Dict]:
    """Get OAuth token for service."""
    db = get_db()
    doc = db.collection(Collections.TOKENS).document(service).get()
    return doc.to_dict() if doc.exists else None


async def save_token(
    service: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime
) -> None:
    """Save OAuth token."""
    db = get_db()
    db.collection(Collections.TOKENS).document(service).set({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresAt": expires_at,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })
