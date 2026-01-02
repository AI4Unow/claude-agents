"""
Telegram authentication endpoint for dashboard.

Verifies Telegram Login Widget hash and returns Firebase custom token.
"""
import os
import hmac
import hashlib
import time
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import firebase_admin
from firebase_admin import auth as firebase_auth

from src.services.firebase._client import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    auth_date: int
    hash: str
    username: str | None = None
    photo_url: str | None = None


@router.post("/telegram")
async def telegram_auth(data: TelegramAuthData) -> Dict[str, str]:
    """
    Verify Telegram login and return Firebase custom token.

    Algorithm per https://core.telegram.org/widgets/login#checking-authorization
    """
    # Get bot token from environment
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise HTTPException(500, "Bot token not configured")

    # Create secret key from bot token
    secret = hashlib.sha256(bot_token.encode()).digest()

    # Build check string from all fields except hash
    check_dict = data.model_dump(exclude={"hash"}, exclude_none=True)
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_dict.items()))

    # Calculate expected hash
    expected_hash = hmac.new(
        secret, check_string.encode(), hashlib.sha256
    ).hexdigest()

    # Verify hash
    if data.hash != expected_hash:
        raise HTTPException(401, "Invalid hash")

    # Check auth_date is recent (within 24 hours)
    if time.time() - data.auth_date > 86400:
        raise HTTPException(401, "Auth expired")

    # Ensure Firebase is initialized (get_db() triggers initialization)
    get_db()

    # Create Firebase custom token
    try:
        custom_token = firebase_auth.create_custom_token(str(data.id))
        return {"customToken": custom_token.decode()}
    except Exception as e:
        raise HTTPException(500, f"Failed to create token: {str(e)}")
