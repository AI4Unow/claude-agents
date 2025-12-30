"""Reports API endpoints.

Provides access to user research reports stored in Firebase.
"""
from fastapi import APIRouter
import structlog


router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = structlog.get_logger()


@router.get("")
async def list_reports(user_id: int):
    """List reports for a user.

    Args:
        user_id: User's Telegram ID

    Returns:
        List of reports metadata
    """
    from src.services.firebase import list_user_reports

    if not user_id:
        return {"ok": False, "error": "user_id required"}

    reports = await list_user_reports(user_id)
    return {
        "ok": True,
        "reports": reports,
        "count": len(reports)
    }


@router.get("/{report_id}")
async def get_report(report_id: str, user_id: int):
    """Get report download URL.

    Args:
        report_id: Report identifier
        user_id: User's Telegram ID

    Returns:
        Signed download URL for the report
    """
    from src.services.firebase import get_report_url

    if not user_id:
        return {"ok": False, "error": "user_id required"}

    url = await get_report_url(user_id, report_id)
    if not url:
        return {"ok": False, "error": "Report not found or access denied"}

    return {
        "ok": True,
        "report_id": report_id,
        "download_url": url
    }


@router.get("/{report_id}/content")
async def get_report_content_api(report_id: str, user_id: int):
    """Get report content directly.

    Args:
        report_id: Report identifier
        user_id: User's Telegram ID

    Returns:
        Report content as text
    """
    from src.services.firebase import get_report_content

    if not user_id:
        return {"ok": False, "error": "user_id required"}

    content = await get_report_content(user_id, report_id)
    if not content:
        return {"ok": False, "error": "Report not found or access denied"}

    return {
        "ok": True,
        "report_id": report_id,
        "content": content
    }
