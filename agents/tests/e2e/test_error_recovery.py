"""E2E tests for error handling and recovery."""
import pytest
import asyncio
from .conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_empty_command_handling(telegram_client, bot_username):
    """Test bot handles empty input gracefully."""
    response = await send_and_wait(telegram_client, bot_username, "/skill")

    assert response is not None, "No response to empty skill"
    # Should show usage or help
    text = response.text.lower()
    assert any(word in text for word in ["usage", "help", "specify", "name"]), \
        "Expected usage hint"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_invalid_command_handling(telegram_client, bot_username):
    """Test unknown command is handled."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/unknowncommandxyz123"
    )

    # Should get some response (error or default)
    assert response is not None, "No response to invalid command"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_rate_limit_behavior(telegram_client, bot_username):
    """Test rapid messages don't break the bot."""
    # Send 5 messages rapidly
    for i in range(5):
        await telegram_client.send_message(bot_username, f"/status {i}")

    # Wait for responses
    await asyncio.sleep(10)

    messages = await telegram_client.get_messages(bot_username, limit=15)
    bot_responses = [m for m in messages if not m.out]

    # Should get at least some responses
    assert len(bot_responses) >= 1, "No responses to rapid messages"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_long_input_handling(telegram_client, bot_username):
    """Test very long input is handled."""
    long_input = "x" * 500  # Long but not too long

    response = await send_and_wait(
        telegram_client,
        bot_username,
        f"Summarize this: {long_input}",
        timeout=45
    )

    # Should respond (either process or error gracefully)
    assert response is not None, "No response to long input"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_special_characters(telegram_client, bot_username):
    """Test special characters don't break parsing."""
    special = 'Hello with "quotes" and <brackets>'

    response = await send_and_wait(
        telegram_client,
        bot_username,
        special,
        timeout=45
    )

    assert response is not None, "No response with special chars"
