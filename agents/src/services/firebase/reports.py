"""Report and content file storage service.

Firebase Storage for research reports and generated content with Firestore metadata.
"""
from datetime import timedelta, datetime, timezone
from typing import Optional, Dict, Any, List

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db, get_bucket, Collections
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()

# Content file settings
CONTENT_LINK_EXPIRY_HOURS = 24
CONTENT_RETENTION_DAYS = 7

# MIME type to extension mapping
MIME_TO_EXT = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "text/markdown": "md",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}


@with_firebase_circuit(raise_on_open=True)
async def save_report(
    user_id: int,
    report_id: str,
    content: str,
    metadata: Dict = None,
) -> str:
    """Save report to Firebase Storage.

    Args:
        user_id: User ID who generated the report
        report_id: Unique report ID
        content: Report content (markdown)
        metadata: Optional metadata (title, query, duration, etc.)

    Returns:
        Signed download URL
    """
    bucket = get_bucket()
    blob_path = f"reports/{user_id}/{report_id}.md"
    blob = bucket.blob(blob_path)

    # Upload content
    blob.upload_from_string(content, content_type="text/markdown")

    # Generate signed URL (7 days)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(days=7),
        method="GET"
    )

    # Save metadata to Firestore for listing
    db = get_db()
    db.collection(Collections.REPORTS).document(report_id).set({
        "user_id": user_id,
        "report_id": report_id,
        "blob_path": blob_path,
        "title": metadata.get("title", "Untitled Report") if metadata else "Untitled Report",
        "query": metadata.get("query", "") if metadata else "",
        "duration_seconds": metadata.get("duration_seconds", "0") if metadata else "0",
        "query_count": metadata.get("query_count", "0") if metadata else "0",
        "created_at": firestore.SERVER_TIMESTAMP,
    })

    logger.info("report_saved", user_id=user_id, report_id=report_id)

    return url


@with_firebase_circuit(raise_on_open=True)
async def save_file(
    user_id: int,
    file_id: str,
    content: bytes | str,
    content_type: str,
    metadata: Dict = None,
) -> str:
    """Save file to Firebase Storage with download link.

    Args:
        user_id: Owner user ID
        file_id: Unique file ID (e.g., "design-abc123")
        content: File content (bytes or str)
        content_type: MIME type (e.g., "application/pdf", "image/png")
        metadata: Optional metadata dict (title, skill)

    Returns:
        Signed download URL (24h expiry)
    """
    bucket = get_bucket()
    ext = MIME_TO_EXT.get(content_type, "bin")
    blob_path = f"content/{user_id}/{file_id}.{ext}"
    blob = bucket.blob(blob_path)

    # Upload content
    if isinstance(content, str):
        blob.upload_from_string(content.encode("utf-8"), content_type=content_type)
    else:
        blob.upload_from_string(content, content_type=content_type)

    # Generate signed URL (24h)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=CONTENT_LINK_EXPIRY_HOURS),
        method="GET"
    )

    # Save metadata to Firestore
    db = get_db()
    db.collection(Collections.CONTENT_FILES).document(file_id).set({
        "user_id": user_id,
        "file_id": file_id,
        "blob_path": blob_path,
        "content_type": content_type,
        "title": metadata.get("title", "Untitled") if metadata else "Untitled",
        "skill": metadata.get("skill", "") if metadata else "",
        "created_at": firestore.SERVER_TIMESTAMP,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=CONTENT_RETENTION_DAYS),
    })

    logger.info("content_file_saved", user_id=user_id, file_id=file_id, skill=metadata.get("skill") if metadata else None)

    return url


@with_firebase_circuit(open_return=[])
async def list_user_reports(user_id: int, limit: int = 20) -> List[Dict]:
    """List reports for a user.

    Args:
        user_id: User ID
        limit: Max reports to return

    Returns:
        List of report metadata dicts
    """
    db = get_db()
    docs = (
        db.collection(Collections.REPORTS)
        .where(filter=FieldFilter("user_id", "==", user_id))
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    reports = []
    for doc in docs:
        data = doc.to_dict()
        reports.append({
            "report_id": data.get("report_id"),
            "title": data.get("title"),
            "query": data.get("query"),
            "created_at": data.get("created_at"),
        })

    return reports


@with_firebase_circuit(open_return=None)
async def get_report_url(user_id: int, report_id: str) -> Optional[str]:
    """Get download URL for a report.

    Args:
        user_id: User ID (for auth check)
        report_id: Report ID

    Returns:
        Signed download URL or None if not found/unauthorized
    """
    # Check ownership in Firestore
    db = get_db()
    doc = db.collection(Collections.REPORTS).document(report_id).get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    if data.get("user_id") != user_id:
        logger.warning("report_access_denied", user_id=user_id, report_id=report_id)
        return None

    # Generate signed URL
    bucket = get_bucket()
    blob = bucket.blob(data.get("blob_path"))

    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=1),
        method="GET"
    )

    return url


@with_firebase_circuit(open_return=None)
async def get_report_content(user_id: int, report_id: str) -> Optional[str]:
    """Get report content directly from Firebase Storage.

    Args:
        user_id: User ID (for auth check)
        report_id: Report ID

    Returns:
        Report content or None if not found/unauthorized
    """
    # Check ownership in Firestore
    db = get_db()
    doc = db.collection(Collections.REPORTS).document(report_id).get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    if data.get("user_id") != user_id:
        logger.warning("report_access_denied", user_id=user_id, report_id=report_id)
        return None

    # Download content from Storage
    bucket = get_bucket()
    blob = bucket.blob(data.get("blob_path"))
    content = blob.download_as_text()

    return content


@with_firebase_circuit(open_return=0)
async def cleanup_expired_content(days: int = CONTENT_RETENTION_DAYS) -> int:
    """Delete content files older than retention period.

    Args:
        days: Retention period in days (default: 7)

    Returns:
        Number of files deleted
    """
    db = get_db()
    bucket = get_bucket()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = db.collection(Collections.CONTENT_FILES).where(
        filter=FieldFilter("created_at", "<", cutoff)
    )

    count = 0
    for doc in query.stream():
        data = doc.to_dict()
        # Delete from Storage
        try:
            blob = bucket.blob(data.get("blob_path"))
            blob.delete()
        except Exception:
            pass  # File may already be deleted
        # Delete from Firestore
        doc.reference.delete()
        count += 1

    logger.info("content_cleanup", deleted=count, days=days)
    return count
