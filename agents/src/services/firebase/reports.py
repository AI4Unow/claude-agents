"""Report storage service.

Firebase Storage for research reports with Firestore metadata.
"""
from datetime import timedelta, datetime
from typing import Optional, Dict, Any, List

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from ._client import get_db, get_bucket, Collections
from ._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()


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
