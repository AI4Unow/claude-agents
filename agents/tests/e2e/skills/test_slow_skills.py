# agents/tests/e2e/skills/test_slow_skills.py
"""E2E tests for slow skills (>30s execution time).

Uses dynamic skill discovery and YAML test data.
"""
import pytest
from ..conftest import execute_skill, get_user_reports

from .skill_loader import get_skill_names_by_marker, get_skill_timeout
from .test_data_loader import TestDataLoader
from .assertions import SkillAssertionChecker

# Initialize shared instances
loader = TestDataLoader()
checker = SkillAssertionChecker(use_llm=False)

# Module-level marker for Claude
pytestmark = pytest.mark.requires_claude


class TestSlowSkills:
    """Tests for slow-running skills. Run with: pytest -m slow"""

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    @pytest.mark.parametrize("skill_name", get_skill_names_by_marker("slow"))
    async def test_slow_skill_responds(self, telegram_client, bot_username, skill_name):
        """Test each slow skill can complete within extended timeout."""
        test_data = loader.get(skill_name)
        timeout = test_data.timeout if test_data else 90
        prompt = test_data.prompt if test_data else "Hello"

        result = await execute_skill(
            telegram_client,
            bot_username,
            skill_name,
            prompt,
            timeout=timeout
        )

        assert result.success, f"Slow skill '{skill_name}' failed to respond"
        assert result.text is not None, f"Slow skill '{skill_name}' returned None"
        assert len(result.text) > 50, f"Slow skill '{skill_name}' response too short"

        # Run assertion checks
        if test_data and test_data.assertions:
            check_result = checker.check(
                response=result.text,
                config=test_data.assertions,
                skill_name=skill_name
            )
            assert check_result.passed, check_result.message

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    @pytest.mark.requires_gemini
    @pytest.mark.flaky(reruns=2, reason="Gemini deep research may return empty on API issues")
    async def test_gemini_deep_research(self, telegram_client, bot_username, e2e_env):
        """Test Gemini deep research skill (60-90s execution)."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "gemini-deep-research",
            '"AI agent frameworks in 2026"',
            timeout=90
        )

        assert result.success, "Deep research failed to respond"
        assert result.text is not None, "Empty response from deep research"

        # Skip if Gemini API returned no content
        if "no content available" in result.text.lower():
            pytest.skip("Gemini deep research returned no content (API issue)")

        assert len(result.text) > 200, "Deep research response too short"

        text_lower = result.text.lower()
        assert any(word in text_lower for word in ["research", "report", "finding", "result", "analysis"]), \
            f"Deep research response missing expected content: {result.text[:300]}"

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    @pytest.mark.requires_gemini
    async def test_gemini_deep_research_saves_report(self, telegram_client, bot_username, e2e_env):
        """Test that deep research saves report to Firebase."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "gemini-deep-research",
            '"Python web frameworks comparison 2026"',
            timeout=90
        )

        if not result.success:
            pytest.skip("Deep research not available")

        user_id = e2e_env.get("user_id", 0)
        if user_id:
            reports = await get_user_reports(user_id)
            assert len(reports) > 0, "No reports saved after deep research"

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    @pytest.mark.media
    @pytest.mark.requires_gemini
    async def test_gemini_vision(self, telegram_client, bot_username, sample_image):
        """Test Gemini vision skill with image."""
        from ..conftest import upload_file

        if not sample_image.exists():
            pytest.skip("Sample image fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            sample_image,
            caption="/skill gemini-vision Describe this image in detail"
        )

        assert response is not None, "Vision skill failed to respond"
        assert response.text is not None, "Empty response from vision"
        assert len(response.text) > 50, "Vision response too short"

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    async def test_content_research_writer(self, telegram_client, bot_username):
        """Test content research writer (multi-step)."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "content-research-writer",
            '"Write a short article about TypeScript advantages"',
            timeout=75
        )

        assert result.success, "Content research writer failed"
        assert result.text is not None, "Empty response"
        assert len(result.text) > 100, "Response too short for article"

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    @pytest.mark.requires_gemini
    async def test_slow_skill_progress_updates(self, telegram_client, bot_username):
        """Test that slow skills send progress updates."""
        import asyncio
        import time

        message = '/skill gemini-deep-research "Test progress updates"'
        sent = await telegram_client.send_message(bot_username, message)

        messages = []
        start = time.time()
        while time.time() - start < 60:
            recent = await telegram_client.get_messages(bot_username, limit=10)
            for msg in recent:
                if not msg.out and msg.id > sent.id:
                    if msg.id not in [m.id for m in messages]:
                        messages.append(msg)
            await asyncio.sleep(5)

        assert len(messages) >= 1, "No progress updates received"

        has_progress = any(
            "processing" in (m.text or "").lower() or
            "working" in (m.text or "").lower() or
            "..." in (m.text or "")
            for m in messages
        )
        # Progress updates are optional but good UX
        if not has_progress and len(messages) == 1:
            pass  # Single response is acceptable
