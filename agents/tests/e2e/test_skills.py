"""E2E tests for skill execution."""
import pytest
from .conftest import send_and_wait

pytestmark = pytest.mark.no_llm  # Infrastructure tests (skill routing, not execution)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_list(telegram_client, bot_username):
    """Test /skill without args shows skill list or usage."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill",
        timeout=30
    )

    assert response is not None, "No response to /skill"
    text = response.text.lower()

    # Should show usage or skill list
    assert any(word in text for word in ["usage", "skill", "name", "help"]), \
        f"Expected usage info: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_not_found(telegram_client, bot_username):
    """Test non-existent skill handling."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill nonexistent-skill-xyz Do something",
        timeout=30
    )

    assert response is not None, "No response"
    text = response.text.lower()

    # Should indicate skill not found
    assert any(word in text for word in ["not found", "unknown", "error", "doesn't exist", "available"]), \
        f"Expected not found message: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_command(telegram_client, bot_username):
    """Test /skill with a skill name shows info."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill planning",
        timeout=30
    )

    # May succeed or show usage - either is valid
    assert response is not None, "No response to /skill planning"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_natural_chat(telegram_client, bot_username):
    """Test natural language chat."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "Hello, how are you today?",
        timeout=60
    )

    assert response is not None, "No response to greeting"
    # Should get some response
    assert len(response.text) > 10, "Response too short"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_categories(telegram_client, bot_username):
    """Test /skills shows categories."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skills",
        timeout=30
    )

    assert response is not None, "No response to /skills"
    # Should have either buttons or text with categories
    has_buttons = response.buttons is not None
    has_text = len(response.text or "") > 10

    assert has_buttons or has_text, "Expected skill categories"
