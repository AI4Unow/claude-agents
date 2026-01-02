"""E2E tests for all major commands."""
import pytest
from .conftest import send_and_wait

pytestmark = pytest.mark.no_llm  # Infrastructure tests, no LLM required


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
async def test_profile_command(telegram_client, bot_username):
    """Test /profile shows user profile."""
    response = await send_and_wait(telegram_client, bot_username, "/profile", timeout=30)

    assert response is not None, "No response to /profile"
    text = response.text.lower()

    # Should contain profile info
    assert any(word in text for word in ["profile", "preference", "language", "name"]), \
        f"Profile info not found: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_context_command(telegram_client, bot_username):
    """Test /context shows personalization context."""
    response = await send_and_wait(telegram_client, bot_username, "/context", timeout=30)

    assert response is not None, "No response to /context"
    # Should have some content
    assert len(response.text) > 10, "Context response too short"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_clear_command(telegram_client, bot_username):
    """Test /clear resets conversation."""
    response = await send_and_wait(telegram_client, bot_username, "/clear")

    assert response is not None, "No response to /clear"
    text = response.text.lower()

    assert any(word in text for word in ["clear", "reset", "conversation"]), \
        f"Clear confirmation not found: {text[:100]}"
