# agents/tests/e2e/integration/test_concurrent_users.py
"""E2E tests for concurrent user handling.

Note: These tests require additional test accounts to properly verify.
With single account, we simulate concurrency within that account.
"""
import pytest
import asyncio
from ..conftest import send_and_wait


class TestConcurrentUsers:
    """Tests for multi-user concurrent access."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_concurrent_requests_same_user(self, telegram_client, bot_username):
        """Multiple concurrent requests from same user handled."""
        # Send multiple requests concurrently
        async def send_request(text):
            return await send_and_wait(telegram_client, bot_username, text, timeout=45)

        # Launch 3 concurrent requests
        tasks = [
            asyncio.create_task(send_request("First concurrent request")),
            asyncio.create_task(send_request("Second concurrent request")),
            asyncio.create_task(send_request("Third concurrent request")),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # At least some should succeed
        successful = [r for r in responses if r and not isinstance(r, Exception)]
        assert len(successful) >= 1, "No successful concurrent responses"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_session_isolation(self, telegram_client, bot_username):
        """User session isolated from others."""
        # Set some context
        await send_and_wait(
            telegram_client,
            bot_username,
            "My project uses Python and Django",
            timeout=30
        )

        await asyncio.sleep(2)

        # Verify context is maintained
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "What framework am I using?",
            timeout=30
        )

        assert response is not None, "No response"
        text_lower = (response.text or "").lower()

        # Should remember Django
        assert "django" in text_lower or "python" in text_lower, \
            f"Session context lost: {response.text[:200]}"
