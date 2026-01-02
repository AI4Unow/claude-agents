# agents/tests/e2e/ux_scenarios/test_power_user.py
"""E2E tests for power user patterns."""
import pytest
import asyncio
from ..conftest import send_and_wait, execute_skill


class TestPowerUser:
    """Tests for advanced user interaction patterns."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_rapid_skill_switching(self, telegram_client, bot_username):
        """Power user switches between skills rapidly."""
        skills_sequence = [
            ("planning", "Plan a login feature"),
            ("debugging", "Debug null reference"),
            ("research", "Research JWT tokens"),
        ]

        for skill_name, prompt in skills_sequence:
            result = await execute_skill(
                telegram_client,
                bot_username,
                skill_name,
                prompt,
                timeout=45
            )

            assert result.success, f"Skill '{skill_name}' failed in rapid sequence"
            assert result.text is not None, f"Empty response from '{skill_name}'"

            await asyncio.sleep(1)  # Brief pause between skills

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_context_persistence(self, telegram_client, bot_username):
        """Context maintained across multi-turn conversation."""
        # Initial context
        response1 = await send_and_wait(
            telegram_client,
            bot_username,
            "I'm working on a React e-commerce app",
            timeout=30
        )
        assert response1 is not None, "No response to context setting"

        await asyncio.sleep(2)

        # Follow-up referencing context
        response2 = await send_and_wait(
            telegram_client,
            bot_username,
            "What components should I build for it?",
            timeout=45
        )

        assert response2 is not None, "No follow-up response"
        text_lower = (response2.text or "").lower()

        # Should reference React or e-commerce from context
        context_refs = ["react", "component", "cart", "product", "checkout", "store"]
        has_context = any(ref in text_lower for ref in context_refs)
        assert has_context, f"Context not maintained: {response2.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_chaining(self, telegram_client, bot_username):
        """Output from one skill feeds another."""
        # Step 1: Research skill generates info
        research = await execute_skill(
            telegram_client,
            bot_username,
            "research",
            "What are the key features of a todo app?",
            timeout=60
        )

        assert research.success, "Research step failed"
        await asyncio.sleep(2)

        # Step 2: Planning skill builds on research
        planning = await execute_skill(
            telegram_client,
            bot_username,
            "planning",
            "Now plan the implementation based on those features",
            timeout=60
        )

        assert planning.success, "Planning step failed"
        text_lower = (planning.text or "").lower()

        # Should reference todo app concepts OR show planning output
        todo_refs = ["task", "todo", "list", "feature", "implement", "plan", "step"]
        has_chaining = any(ref in text_lower for ref in todo_refs)
        assert has_chaining, f"Skill chaining failed: {planning.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mode_switching(self, telegram_client, bot_username):
        """Power user switches between execution modes."""
        # Check current mode
        mode_check = await send_and_wait(
            telegram_client,
            bot_username,
            "/mode",
            timeout=20
        )

        assert mode_check is not None, "No mode response"
        text_lower = (mode_check.text or "").lower()

        # Should show mode options
        mode_words = ["mode", "simple", "routed", "auto", "current"]
        assert any(word in text_lower for word in mode_words), \
            f"Mode info not shown: {mode_check.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_profile_customization(self, telegram_client, bot_username):
        """Power user views and updates profile."""
        # View profile
        profile = await send_and_wait(
            telegram_client,
            bot_username,
            "/profile",
            timeout=20
        )

        assert profile is not None, "No profile response"
        text_lower = (profile.text or "").lower()

        # Should show profile info
        profile_words = ["profile", "preference", "name", "language", "setting"]
        assert any(word in text_lower for word in profile_words), \
            f"Profile not shown: {profile.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_clear_conversation(self, telegram_client, bot_username):
        """Power user clears conversation context."""
        # Set some context
        await send_and_wait(
            telegram_client,
            bot_username,
            "Remember that I prefer Python",
            timeout=30
        )

        await asyncio.sleep(1)

        # Clear conversation
        clear = await send_and_wait(
            telegram_client,
            bot_username,
            "/clear",
            timeout=20
        )

        assert clear is not None, "No clear response"
        text_lower = (clear.text or "").lower()

        # Should confirm clear
        assert any(word in text_lower for word in ["clear", "reset", "fresh", "conversation"]), \
            f"Clear not confirmed: {clear.text[:200]}"
