"""OAuth token storage for calendar services.

Secure storage and retrieval of OAuth tokens for Google Calendar, Google Tasks,
and Apple CalDAV credentials in Firebase.
"""
from datetime import datetime
from typing import Optional, Dict

from firebase_admin import firestore
from google.oauth2.credentials import Credentials

from ._client import get_db
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()


@with_firebase_circuit(open_return=None)
async def store_google_tokens(
    user_id: int,
    access_token: str,
    refresh_token: str,
    expiry: datetime,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None
) -> None:
    """Store Google OAuth tokens for calendar/tasks access.

    Args:
        user_id: User ID
        access_token: Google OAuth access token
        refresh_token: Google OAuth refresh token
        expiry: Token expiry datetime
        client_id: Optional OAuth client ID
        client_secret: Optional OAuth client secret
    """
    db = get_db()

    token_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expiry": expiry,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    if client_id:
        token_data["client_id"] = client_id
    if client_secret:
        token_data["client_secret"] = client_secret

    db.collection("users").document(str(user_id)).collection("calendar_tokens").document("google").set(
        token_data,
        merge=True
    )

    logger.info("google_tokens_stored", user_id=user_id, expiry=expiry.isoformat())


@with_firebase_circuit(open_return=None)
async def get_google_credentials(user_id: int) -> Optional[Credentials]:
    """Get Google OAuth credentials for calendar/tasks access.

    Args:
        user_id: User ID

    Returns:
        Google Credentials object or None if not found
    """
    db = get_db()

    doc = db.collection("users").document(str(user_id)).collection("calendar_tokens").document("google").get()

    if not doc.exists:
        logger.debug("google_credentials_not_found", user_id=user_id)
        return None

    data = doc.to_dict()

    # Build Credentials object
    creds = Credentials(
        token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret")
    )

    # Set expiry if available
    if data.get("expiry"):
        creds.expiry = data["expiry"]

    logger.debug("google_credentials_retrieved", user_id=user_id)
    return creds


@with_firebase_circuit(open_return=None)
async def get_google_tokens_dict(user_id: int) -> Optional[Dict]:
    """Get Google OAuth tokens as dict (for CalendarSyncManager).

    Args:
        user_id: User ID

    Returns:
        Dict with token fields or None
    """
    db = get_db()

    doc = db.collection("users").document(str(user_id)).collection("calendar_tokens").document("google").get()

    if not doc.exists:
        return None

    return doc.to_dict()


@with_firebase_circuit(open_return=None)
async def store_apple_credentials(
    user_id: int,
    apple_id: str,
    app_password: str
) -> None:
    """Store Apple CalDAV credentials (app-specific password).

    Args:
        user_id: User ID
        apple_id: Apple ID email (e.g., user@icloud.com)
        app_password: App-specific password from appleid.apple.com
    """
    db = get_db()

    # Note: In production, encrypt app_password before storage
    db.collection("users").document(str(user_id)).collection("calendar_tokens").document("apple").set(
        {
            "apple_id": apple_id,
            "app_password": app_password,  # TODO: Encrypt in production
            "updated_at": firestore.SERVER_TIMESTAMP
        },
        merge=True
    )

    logger.info("apple_credentials_stored", user_id=user_id, apple_id=apple_id)


@with_firebase_circuit(open_return=None)
async def get_apple_credentials(user_id: int) -> Optional[Dict]:
    """Get Apple CalDAV credentials.

    Args:
        user_id: User ID

    Returns:
        Dict with apple_id and app_password or None
    """
    db = get_db()

    doc = db.collection("users").document(str(user_id)).collection("calendar_tokens").document("apple").get()

    if not doc.exists:
        logger.debug("apple_credentials_not_found", user_id=user_id)
        return None

    data = doc.to_dict()

    # TODO: Decrypt app_password in production
    return {
        "apple_id": data.get("apple_id"),
        "app_password": data.get("app_password")
    }


@with_firebase_circuit(open_return=None)
async def delete_calendar_tokens(user_id: int, service: str) -> bool:
    """Delete calendar tokens for a service.

    Args:
        user_id: User ID
        service: Service name ("google" or "apple")

    Returns:
        True if deleted
    """
    db = get_db()

    db.collection("users").document(str(user_id)).collection("calendar_tokens").document(service).delete()

    logger.info("calendar_tokens_deleted", user_id=user_id, service=service)
    return True


@with_firebase_circuit(open_return={})
async def get_all_credentials(user_id: int) -> Dict:
    """Get all calendar credentials for a user.

    Args:
        user_id: User ID

    Returns:
        Dict with google_calendar, google_tasks, apple_caldav keys
    """
    result = {}

    # Google (same tokens for Calendar and Tasks)
    google_tokens = await get_google_tokens_dict(user_id)
    if google_tokens:
        result["google_calendar"] = google_tokens
        result["google_tasks"] = google_tokens

    # Apple CalDAV
    apple_creds = await get_apple_credentials(user_id)
    if apple_creds:
        result["apple_caldav"] = apple_creds

    return result


@with_firebase_circuit(open_return=None)
async def store_event_etag(user_id: int, event_id: str, etag: str) -> None:
    """Store ETag for Google Calendar event (for conflict detection).

    Args:
        user_id: User ID
        event_id: Google Calendar event ID
        etag: ETag value from Google API
    """
    db = get_db()

    db.collection("users").document(str(user_id)).collection("event_etags").document(event_id).set({
        "etag": etag,
        "updated_at": firestore.SERVER_TIMESTAMP
    })


@with_firebase_circuit(open_return=None)
async def get_event_etag(user_id: int, event_id: str) -> Optional[str]:
    """Get stored ETag for Google Calendar event.

    Args:
        user_id: User ID
        event_id: Google Calendar event ID

    Returns:
        ETag string or None
    """
    db = get_db()

    doc = db.collection("users").document(str(user_id)).collection("event_etags").document(event_id).get()

    if not doc.exists:
        return None

    return doc.to_dict().get("etag")


@with_firebase_circuit(open_return=None)
async def store_sync_token(user_id: int, service: str, sync_token: str) -> None:
    """Store sync token for incremental sync.

    Args:
        user_id: User ID
        service: Service name (e.g., "google_calendar")
        sync_token: Sync token from API
    """
    db = get_db()

    db.collection("users").document(str(user_id)).collection("sync_tokens").document(service).set({
        "token": sync_token,
        "updated_at": firestore.SERVER_TIMESTAMP
    })


@with_firebase_circuit(open_return=None)
async def get_sync_token(user_id: int, service: str) -> Optional[str]:
    """Get sync token for incremental sync.

    Args:
        user_id: User ID
        service: Service name (e.g., "google_calendar")

    Returns:
        Sync token or None
    """
    db = get_db()

    doc = db.collection("users").document(str(user_id)).collection("sync_tokens").document(service).get()

    if not doc.exists:
        return None

    return doc.to_dict().get("token")
