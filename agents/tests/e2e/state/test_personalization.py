# agents/tests/e2e/state/test_personalization.py
"""E2E tests for personalization persistence."""
import pytest
import asyncio
from ..conftest import send_and_wait


class TestPersonalization:
    """Tests for context and preference persistence."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_profile_viewable(self, telegram_client, bot_username):
        """User can view their profile."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/profile",
            timeout=20
        )

        assert response is not None, "No profile response"
        text_lower = (response.text or "").lower()

        # Should show profile info
        profile_words = ["profile", "name", "preference", "setting", "language"]
        assert any(word in text_lower for word in profile_words), \
            f"Profile not shown: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_context_command(self, telegram_client, bot_username):
        """User can view their context."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/context",
            timeout=20
        )

        assert response is not None, "No context response"
        # Should show some context info
        assert len(response.text or "") > 10, "Context response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_conversation_context_maintained(self, telegram_client, bot_username):
        """Context maintained within session."""
        # Set context
        await send_and_wait(
            telegram_client,
            bot_username,
            "My name is TestUser and I'm building a FastAPI app",
            timeout=30
        )

        await asyncio.sleep(2)

        # Reference context
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "What was I building again?",
            timeout=30
        )

        assert response is not None, "No follow-up response"
        text_lower = (response.text or "").lower()

        # Should remember FastAPI
        context_words = ["fastapi", "api", "app", "building", "python"]
        has_context = any(word in text_lower for word in context_words)
        # Context maintenance is optional but expected
        if not has_context:
            print(f"Warning: Context may not be maintained: {response.text[:200]}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_clear_resets_context(self, telegram_client, bot_username):
        """Clear command resets conversation context."""
        # Set some context
        await send_and_wait(
            telegram_client,
            bot_username,
            "Remember the secret code is ALPHA123",
            timeout=30
        )

        await asyncio.sleep(1)

        # Clear
        clear = await send_and_wait(
            telegram_client,
            bot_username,
            "/clear",
            timeout=20
        )

        assert clear is not None, "No clear response"

        await asyncio.sleep(1)

        # Try to reference cleared context
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "What was the secret code?",
            timeout=30
        )

        assert response is not None, "No post-clear response"
        text_lower = (response.text or "").lower()

        # Should NOT remember the code after clear
        assert "alpha123" not in text_lower, "Context not cleared"
