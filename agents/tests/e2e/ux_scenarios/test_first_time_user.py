# agents/tests/e2e/ux_scenarios/test_first_time_user.py
"""E2E tests for first-time user experience."""
import pytest
import asyncio
from ..conftest import send_and_wait, execute_skill


class TestFirstTimeUser:
    """Tests simulating new user onboarding journey."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_welcome_experience(self, telegram_client, bot_username):
        """New user receives welcoming, informative first response."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/start",
            timeout=45
        )

        assert response is not None, "No welcome response"
        text_lower = (response.text or "").lower()

        # Should feel welcoming
        welcome_words = ["hello", "welcome", "hi", "hey", "glad", "back"]
        assert any(word in text_lower for word in welcome_words), \
            f"Welcome not friendly enough: {response.text[:200]}"

        # Should hint at capabilities
        capability_hints = ["help", "skill", "can", "try", "command", "feature"]
        assert any(hint in text_lower for hint in capability_hints), \
            f"No capability hints in welcome: {response.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_help_discovery(self, telegram_client, bot_username):
        """User naturally discovers help command."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/help",
            timeout=30
        )

        assert response is not None, "No help response"
        text = response.text or ""

        # Help should list available commands
        assert "/" in text, "Help should show commands with /"
        assert len(text) > 100, "Help response too brief"

        # Should mention key commands
        key_commands = ["/skills", "/start", "/help"]
        mentioned = sum(1 for cmd in key_commands if cmd in text)
        assert mentioned >= 2, f"Help missing key commands: {text[:300]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_discovery_journey(self, telegram_client, bot_username):
        """User browses skills and understands categories."""
        # Step 1: View skills
        skills_response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skills",
            timeout=20
        )

        assert skills_response is not None, "No skills response"

        # Should show skills or categories
        has_content = len(skills_response.text or "") > 20 or skills_response.buttons
        assert has_content, "Skills view empty"

        await asyncio.sleep(2)

        # Step 2: Ask about a specific skill
        info_response = await send_and_wait(
            telegram_client,
            bot_username,
            "What can the planning skill do?",
            timeout=30
        )

        assert info_response is not None, "No skill info response"
        assert len(info_response.text or "") > 30, "Skill info too brief"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_first_skill_execution(self, telegram_client, bot_username):
        """User successfully executes their first skill."""
        # Use a simple, fast skill
        result = await execute_skill(
            telegram_client,
            bot_username,
            "problem-solving",
            "What is 2 + 2?",
            timeout=45
        )

        assert result.success, "First skill execution failed"
        assert result.text is not None, "Empty skill response"
        assert len(result.text) > 20, "Response too short"

        # Should not show error
        assert "error" not in result.text.lower() or "fix" in result.text.lower(), \
            f"First skill showed error: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tier_explanation(self, telegram_client, bot_username):
        """User understands their tier and limitations."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/tier",
            timeout=20
        )

        assert response is not None, "No tier response"
        text_lower = (response.text or "").lower()

        # Should explain tier concept
        tier_words = ["tier", "guest", "user", "developer", "admin", "level", "access"]
        assert any(word in text_lower for word in tier_words), \
            f"Tier not explained: {response.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_onboarding_journey(self, telegram_client, bot_username):
        """Complete onboarding: /start → /help → /skills → first skill."""
        # Step 1: Start
        start = await send_and_wait(telegram_client, bot_username, "/start", timeout=30)
        assert start is not None, "Onboarding: /start failed"
        await asyncio.sleep(2)

        # Step 2: Help
        help_resp = await send_and_wait(telegram_client, bot_username, "/help", timeout=20)
        assert help_resp is not None, "Onboarding: /help failed"
        await asyncio.sleep(2)

        # Step 3: Skills
        skills = await send_and_wait(telegram_client, bot_username, "/skills", timeout=20)
        assert skills is not None, "Onboarding: /skills failed"
        await asyncio.sleep(2)

        # Step 4: First skill
        result = await execute_skill(
            telegram_client,
            bot_username,
            "planning",
            "What is agile?",
            timeout=45
        )
        assert result.success, "Onboarding: first skill failed"

        # All steps completed successfully
        assert True, "Complete onboarding journey passed"
