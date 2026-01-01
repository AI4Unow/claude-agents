# agents/tests/e2e/skills/test_skill_discovery.py
"""E2E tests for skill discovery and listing."""
import pytest
from ..conftest import send_and_wait, execute_skill


class TestSkillDiscovery:
    """Tests for skill listing, search, and category browsing."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skills_command_returns_list(self, telegram_client, bot_username):
        """Test /skills returns skill list or categories."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skills",
            timeout=30
        )

        assert response is not None, "No response to /skills"

        # Should have text or buttons with skill info
        has_content = (response.text and len(response.text) > 10) or response.buttons
        assert has_content, "Expected skill list or category info"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skills_shows_categories(self, telegram_client, bot_username):
        """Test /skills shows skill categories or skill names."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skills",
            timeout=30
        )

        assert response is not None, "No response to /skills"
        text_lower = (response.text or "").lower()

        # Should mention categories OR skill names OR total count
        expected_terms = [
            "research", "development", "design", "ai", "content", "devops",  # categories
            "skill", "total", "available",  # meta terms
            "planning", "debugging", "code-review"  # common skill names
        ]
        has_term = any(term in text_lower for term in expected_terms)

        # Or has buttons with skill/category info
        if response.buttons:
            button_texts = " ".join(btn.text.lower() for row in response.buttons for btn in row)
            has_term = has_term or len(button_texts) > 10

        assert has_term, f"Expected skill info: {response.text[:200] if response.text else 'buttons only'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_command_shows_usage(self, telegram_client, bot_username):
        """Test /skill without args shows usage."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skill",
            timeout=30
        )

        assert response is not None, "No response to /skill"
        text_lower = (response.text or "").lower()

        # Should show usage/help OR skill list
        assert any(word in text_lower for word in ["usage", "skill", "name", "help", "specify", "example", "list"]), \
            f"Expected usage info: {response.text[:200] if response.text else '(no text)'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_info_lookup(self, telegram_client, bot_username):
        """Test /skill <name> shows skill info or executes."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skill debugging",  # Use a fast skill
            timeout=45
        )

        assert response is not None, "No response to skill lookup"
        # Should show skill info or execution result
        assert response.text and len(response.text) > 10, "Response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_search(self, telegram_client, bot_username):
        """Test searching for skills by keyword."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "What skills can help me with debugging?",
            timeout=45
        )

        assert response is not None, "No response to skill search"
        # Bot should respond with something (even if just a general response)
        assert response.text and len(response.text) > 10, "Response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_category_navigation(self, telegram_client, bot_username):
        """Test navigating skill categories via buttons."""
        from ..conftest import click_button

        # Get skills list
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/skills",
            timeout=30
        )

        if not response or not response.buttons:
            pytest.skip("No category buttons available")

        # Try to click first button
        first_button = response.buttons[0][0]
        updated = await click_button(telegram_client, response, first_button.text)

        if updated:
            # Should show skills in category
            assert len(updated.text or "") > 10, "Category view too short"
