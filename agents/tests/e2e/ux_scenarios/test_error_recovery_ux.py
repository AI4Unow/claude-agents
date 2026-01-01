# agents/tests/e2e/ux_scenarios/test_error_recovery_ux.py
"""E2E tests for error recovery user experience."""
import pytest
import asyncio
from ..conftest import send_and_wait, execute_skill


class TestErrorRecoveryUX:
    """Tests for graceful error handling from user perspective."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_typo_suggestions(self, telegram_client, bot_username):
        """Typo in skill name gets suggestions."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "planing",  # Typo: should be "planning"
            "Create a plan",
            timeout=30
        )

        assert result.success, "No response to typo"
        text_lower = (result.text or "").lower()

        # Should suggest correct skill or show similar
        assert any(word in text_lower for word in ["planning", "suggest", "mean", "similar", "not found"]), \
            f"No helpful response to typo: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_missing_arguments_prompt(self, telegram_client, bot_username):
        """Missing required args prompts user."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "gemini-deep-research",
            "",  # Missing required topic
            timeout=30
        )

        assert result.success, "No response to missing args"
        text_lower = (result.text or "").lower()

        # Should ask for input
        assert any(word in text_lower for word in ["provide", "specify", "need", "topic", "what"]), \
            f"No prompt for missing args: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_permission_denied_message(self, telegram_client, bot_username):
        """Guest accessing admin feature gets clear message."""
        # Try admin-only command (might not be denied, depends on test user tier)
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/admin",  # Or other admin command
            timeout=20
        )

        # Either succeeds (if admin) or shows clear denial
        if response:
            text_lower = (response.text or "").lower()
            # If denied, should be clear
            if "permission" in text_lower or "denied" in text_lower or "admin" in text_lower:
                assert "error" not in text_lower or "permission" in text_lower, \
                    "Permission denial not user-friendly"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_timeout_graceful_message(self, telegram_client, bot_username):
        """Long-running request shows appropriate status."""
        # This test verifies the bot acknowledges long requests
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "Analyze a very complex multi-step problem with many considerations",
            timeout=45
        )

        assert response is not None, "No response to complex request"
        # Should either complete or show processing
        assert len(response.text or "") > 10, "Response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_malformed_input_handled(self, telegram_client, bot_username):
        """Weird unicode and special chars handled safely."""
        weird_input = "Test with émojis 🎉 and «special» chars: <script>alert(1)</script>"

        response = await send_and_wait(
            telegram_client,
            bot_username,
            weird_input,
            timeout=30
        )

        assert response is not None, "No response to special chars"
        # Should not crash or show raw error
        text_lower = (response.text or "").lower()
        assert "exception" not in text_lower, f"Raw exception shown: {response.text[:200]}"
        assert "traceback" not in text_lower, f"Traceback exposed: {response.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_recovery_after_error(self, telegram_client, bot_username):
        """Bot recovers gracefully after error."""
        # Cause an error with invalid input
        error_response = await execute_skill(
            telegram_client,
            bot_username,
            "nonexistent-skill-xyz",
            "test",
            timeout=20
        )

        await asyncio.sleep(2)

        # Normal command should still work
        recovery = await send_and_wait(
            telegram_client,
            bot_username,
            "/status",
            timeout=20
        )

        assert recovery is not None, "Bot didn't recover after error"
        assert len(recovery.text or "") > 10, "Recovery response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, telegram_client, bot_username):
        """Multiple rapid requests handled gracefully."""
        # Send 5 messages quickly
        messages = [
            "First message",
            "Second message",
            "Third message",
            "/status",
            "/help",
        ]

        for msg in messages:
            await telegram_client.send_message(bot_username, msg)

        # Wait for responses
        await asyncio.sleep(10)

        # Get recent messages
        recent = await telegram_client.get_messages(bot_username, limit=15)
        bot_responses = [m for m in recent if not m.out]

        # Should have gotten at least some responses
        assert len(bot_responses) >= 1, "No responses to rapid requests"
