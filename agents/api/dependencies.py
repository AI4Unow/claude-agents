"""FastAPI dependencies for webhook verification and authentication.

Security:
- GitHub webhook HMAC-SHA256 verification
- Telegram webhook verification
- Admin token authentication
- Timing-safe signature comparison
- Fail-closed by default
"""
import hashlib
import hmac
import json
import os
from typing import Tuple
from fastapi import Request, HTTPException, Header


async def verify_github_webhook(request: Request) -> Tuple[str, dict]:
    """Verify GitHub webhook signature using HMAC-SHA256.

    Security:
    - Uses timing-safe comparison (hmac.compare_digest)
    - Fail-closed: rejects if secret not configured
    - Returns parsed JSON payload on success

    Args:
        request: FastAPI Request object

    Returns:
        Tuple of (event_type, parsed_payload)

    Raises:
        HTTPException: 500 if secret not configured, 401 if signature invalid
    """
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="GitHub webhook secret not configured"
        )

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=401,
            detail="Invalid signature format"
        )

    # Get event type
    event_type = request.headers.get("X-GitHub-Event", "push")

    # Get raw body
    body = await request.body()

    # Compute expected signature
    computed = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    # Timing-safe comparison
    provided = signature_header[7:]  # Remove "sha256=" prefix
    if not hmac.compare_digest(computed, provided):
        raise HTTPException(
            status_code=401,
            detail="Invalid signature"
        )

    # Parse and return event type + payload
    return event_type, json.loads(body)


async def verify_telegram_webhook(request: Request) -> bool:
    """Verify Telegram webhook using secret token (timing-safe comparison).

    SECURITY: If secret not configured, verification is skipped (permissive).
    Set TELEGRAM_WEBHOOK_SECRET to enable strict verification.

    Args:
        request: FastAPI Request object

    Returns:
        True if verification succeeds or is disabled
    """
    import structlog

    secret_token = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not secret_token:
        # Not configured - allow but log warning
        structlog.get_logger().debug("telegram_webhook_secret_not_configured")
        return True

    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hmac.compare_digest(secret_token, header_token)


async def verify_admin_token(x_admin_token: str = Header(None)):
    """Verify admin token from X-Admin-Token header.

    Args:
        x_admin_token: Token from request header

    Returns:
        True if token is valid

    Raises:
        HTTPException: 500 if token not configured, 401 if invalid
    """
    expected_token = os.environ.get("ADMIN_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")
    return True
