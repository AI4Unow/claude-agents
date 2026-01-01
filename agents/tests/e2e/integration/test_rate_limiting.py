# agents/tests/e2e/integration/test_rate_limiting.py
"""E2E tests for rate limiting behavior."""
import pytest
import asyncio
from ..conftest import send_and_wait


class TestRateLimiting:
    """Tests for rate limit and throttling behavior."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.flaky
    async def test_rapid_messages_handled(self, telegram_client, bot_username):
        """Bot handles rapid message burst."""
        # Send 10 messages quickly
        sent_ids = []
        for i in range(10):
            msg = await telegram_client.send_message(
                bot_username,
                f"Rapid message {i+1}"
            )
            sent_ids.append(msg.id)

        # Wait for responses
        await asyncio.sleep(20)

        # Get all recent messages
        messages = await telegram_client.get_messages(bot_username, limit=30)
        bot_responses = [m for m in messages if not m.out]

        # Should have gotten at least some responses
        assert len(bot_responses) >= 1, "No responses to rapid messages"

        # Should not have errors about rate limiting exposed
        for resp in bot_responses:
            text_lower = (resp.text or "").lower()
            assert "rate limit" not in text_lower or "please slow down" in text_lower, \
                f"Raw rate limit error: {resp.text[:100]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.flaky
    async def test_normal_pace_not_limited(self, telegram_client, bot_username):
        """Normal message pace isn't rate limited."""
        messages = [
            "First normal message",
            "Second normal message",
            "Third normal message",
        ]

        for msg_text in messages:
            response = await send_and_wait(
                telegram_client,
                bot_username,
                msg_text,
                timeout=30
            )

            assert response is not None, f"No response to: {msg_text}"
            text_lower = (response.text or "").lower()
            assert "rate" not in text_lower or "limit" not in text_lower, \
                f"Normal pace rate limited: {response.text[:100]}"

            await asyncio.sleep(3)  # Normal pace between messages
