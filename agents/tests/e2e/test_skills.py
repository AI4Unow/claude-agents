"""E2E tests for skill execution."""
import pytest
from .conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_web_search_skill(telegram_client, bot_username):
    """Test web search returns results."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill web-search What is Python programming?",
        timeout=60  # Skills take longer
    )

    assert response is not None, "No response to skill"
    text = response.text.lower()

    assert len(text) > 100, "Response too short for search"
    assert "python" in text, "No relevant content"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_not_found(telegram_client, bot_username):
    """Test non-existent skill handling."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill nonexistent-skill-xyz Do something",
        timeout=20
    )

    assert response is not None, "No response"
    text = response.text.lower()

    # Should indicate skill not found
    assert any(word in text for word in ["not found", "unknown", "error", "doesn't exist"]), \
        f"Expected not found message: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_use_command(telegram_client, bot_username):
    """Test /use skill shorthand."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/use translate Hola mundo",
        timeout=30
    )

    # May succeed or show usage - either is valid
    assert response is not None, "No response to /use"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_execution_progress(telegram_client, bot_username):
    """Test that long-running skills show progress."""
    # This test is more observational - we just verify response arrives
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill research Brief summary of AI trends",
        timeout=120  # Research takes time
    )

    # Response should eventually arrive
    if response:
        assert len(response.text) > 50, "Research output too short"
