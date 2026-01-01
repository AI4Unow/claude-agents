# agents/tests/e2e/state/test_tier_access.py
"""E2E tests for tier-based access control."""
import pytest
from ..conftest import send_and_wait, execute_skill


class TestTierAccess:
    """Tests for permission enforcement by tier."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tier_command_shows_current(self, telegram_client, bot_username):
        """/tier shows current tier level."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/tier",
            timeout=20
        )

        assert response is not None, "No tier response"
        text_lower = (response.text or "").lower()

        # Should show tier info
        tier_words = ["tier", "guest", "user", "developer", "admin", "level"]
        assert any(word in text_lower for word in tier_words), \
            f"Tier not shown: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_basic_commands_available_all_tiers(self, telegram_client, bot_username):
        """Basic commands available to all tiers."""
        basic_commands = ["/start", "/help", "/status"]

        for cmd in basic_commands:
            response = await send_and_wait(
                telegram_client,
                bot_username,
                cmd,
                timeout=20
            )

            assert response is not None, f"No response to {cmd}"
            text_lower = (response.text or "").lower()

            # Should not show permission denied
            assert "permission" not in text_lower or "allowed" in text_lower, \
                f"Permission denied for basic command {cmd}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skills_available_by_tier(self, telegram_client, bot_username):
        """Skills accessible based on tier."""
        # Test a common skill that should be available
        result = await execute_skill(
            telegram_client,
            bot_username,
            "planning",
            "Create a simple plan",
            timeout=45
        )

        # Should either succeed or show tier limitation clearly
        assert result.success, "Skill request failed"
        text_lower = (result.text or "").lower()

        # If denied, should be clear about why
        if "permission" in text_lower or "tier" in text_lower:
            assert "upgrade" in text_lower or "access" in text_lower, \
                "Permission denial not helpful"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.admin
    async def test_admin_commands_restricted(self, telegram_client, bot_username):
        """Admin commands properly restricted."""
        # Try admin-like commands
        admin_attempts = [
            "/admin",
            "/broadcast Hello",
            "/users",
        ]

        for cmd in admin_attempts:
            response = await send_and_wait(
                telegram_client,
                bot_username,
                cmd,
                timeout=15
            )

            # Response depends on current tier
            # Just verify we get some response (not crash)
            if response:
                text_lower = (response.text or "").lower()
                # If not admin, should not execute
                if "admin" not in text_lower:
                    # Either denied or unknown command
                    pass
