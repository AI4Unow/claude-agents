"""E2E tests for new user onboarding flow."""
import pytest
import asyncio
from .conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_start_command(telegram_client, bot_username):
    """Test /start returns welcome message."""
    # Longer timeout for cold-start scenarios
    response = await send_and_wait(telegram_client, bot_username, "/start", timeout=60)

    assert response is not None, "No response to /start"
    text = response.text.lower()

    # Skip file error messages (flaky Telethon issue)
    if "octet-stream" in text or "can't process" in text:
        # Retry once
        await asyncio.sleep(2)
        response = await send_and_wait(telegram_client, bot_username, "/start", timeout=30)
        assert response is not None, "No response to /start on retry"
        text = response.text.lower()

    assert any(word in text for word in ["hello", "welcome", "hi", "tips", "back"]), \
        f"Unexpected /start response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_help_command(telegram_client, bot_username):
    """Test /help shows available commands."""
    response = await send_and_wait(telegram_client, bot_username, "/help", timeout=30)

    assert response is not None, "No response to /help"
    text = response.text

    # Should contain command references
    assert "/start" in text or "commands" in text.lower(), "Missing command references in help"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_status_command(telegram_client, bot_username):
    """Test /status shows agent status."""
    response = await send_and_wait(telegram_client, bot_username, "/status", timeout=30)

    assert response is not None, "No response to /status"
    text = response.text.lower()

    # Should indicate some status
    assert any(word in text for word in ["status", "running", "online", "tier", "mode"]), \
        f"Unexpected /status response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_onboarding_flow(telegram_client, bot_username):
    """Test complete onboarding: /start -> /help -> /status."""
    # Step 1: Start
    start_resp = await send_and_wait(telegram_client, bot_username, "/start", timeout=30)
    assert start_resp is not None, "No /start response"

    # Longer delay between commands to avoid message overlap
    await asyncio.sleep(3)

    # Step 2: Help
    help_resp = await send_and_wait(telegram_client, bot_username, "/help", timeout=30)
    assert help_resp is not None, "No /help response"

    await asyncio.sleep(3)

    # Step 3: Status
    status_resp = await send_and_wait(telegram_client, bot_username, "/status", timeout=30)
    assert status_resp is not None, "No /status response"

    # All three should have meaningful content
    assert len(start_resp.text) > 20, "Start response too short"
    assert len(help_resp.text) > 50, "Help response too short"
    assert len(status_resp.text) > 20, "Status response too short"
