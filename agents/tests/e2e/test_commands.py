"""E2E tests for all major commands."""
import pytest
from .conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skills_command(telegram_client, bot_username):
    """Test /skills shows skill list."""
    response = await send_and_wait(telegram_client, bot_username, "/skills", timeout=20)

    assert response is not None, "No response to /skills"

    # May have inline keyboard or text list
    text = response.text.lower() if response.text else ""
    has_keyboard = response.buttons is not None

    assert has_keyboard or "skill" in text, \
        "Expected skill list or inline keyboard"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_tier_command(telegram_client, bot_username):
    """Test /tier shows user tier."""
    response = await send_and_wait(telegram_client, bot_username, "/tier")

    assert response is not None, "No response to /tier"
    text = response.text.lower()

    # Should mention tier level
    assert any(tier in text for tier in ["guest", "user", "developer", "admin", "tier"]), \
        f"No tier info in response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mode_command(telegram_client, bot_username):
    """Test /mode shows or sets execution mode."""
    response = await send_and_wait(telegram_client, bot_username, "/mode")

    assert response is not None, "No response to /mode"
    text = response.text.lower()

    # Should mention mode options
    assert any(mode in text for mode in ["simple", "routed", "auto", "mode"]), \
        f"No mode info in response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_translate_command(telegram_client, bot_username):
    """Test /translate works."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/translate Bonjour le monde",
        timeout=30
    )

    assert response is not None, "No response to /translate"

    # Should contain English translation
    text = response.text.lower()
    assert any(word in text for word in ["hello", "world", "greet"]), \
        f"Translation not recognized: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_summarize_command(telegram_client, bot_username):
    """Test /summarize works."""
    long_text = (
        "This is a test paragraph that contains multiple sentences. "
        "It discusses various topics including testing, automation, and bots. "
        "The purpose is to verify that the summarization feature works correctly. "
        "We expect a shorter version of this text."
    )

    response = await send_and_wait(
        telegram_client,
        bot_username,
        f"/summarize {long_text}",
        timeout=30
    )

    assert response is not None, "No response to /summarize"
    assert len(response.text) > 20, "Summary too short"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_clear_command(telegram_client, bot_username):
    """Test /clear resets conversation."""
    response = await send_and_wait(telegram_client, bot_username, "/clear")

    assert response is not None, "No response to /clear"
    text = response.text.lower()

    assert any(word in text for word in ["clear", "reset", "conversation"]), \
        f"Clear confirmation not found: {text[:100]}"
