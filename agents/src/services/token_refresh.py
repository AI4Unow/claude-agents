"""Token refresh service for OAuth tokens."""
from datetime import datetime
from src.services.firebase import get_token, save_token
import os


async def refresh_github_token() -> str:
    """Refresh GitHub access token if expired.

    For GitHub Apps, tokens need periodic refresh.
    For personal access tokens, no refresh needed.
    """
    token_data = await get_token("github")

    if token_data and token_data["expiresAt"] > datetime.utcnow():
        return token_data["accessToken"]

    # Personal access tokens don't expire - return from env
    return os.environ.get("GITHUB_TOKEN", "")


async def get_valid_token(service: str) -> str:
    """Get a valid token for the specified service."""
    if service == "github":
        return await refresh_github_token()

    # Add other services as needed
    token_data = await get_token(service)
    if token_data:
        return token_data.get("accessToken", "")
    return ""
