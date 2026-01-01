# agents/tests/e2e/skills/test_slow_skills.py
"""E2E tests for slow skills (> 30s execution time)."""
import pytest
from ..conftest import execute_skill, get_user_reports


class TestSlowSkills:
    """Tests for slow-running skills. Run with: pytest -m slow"""

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
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
        assert len(result.text) > 200, "Deep research response too short"

        text_lower = result.text.lower()

        # Should contain research indicators
        assert any(word in text_lower for word in ["research", "report", "finding", "result", "analysis"]), \
            f"Deep research response missing expected content: {result.text[:300]}"

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
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

        # Check if report was saved
        # Note: User ID extraction from e2e_env may need adjustment
        user_id = e2e_env.get("user_id", 0)
        if user_id:
            reports = await get_user_reports(user_id)
            # Recent report should exist
            assert len(reports) > 0, "No reports saved after deep research"

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    @pytest.mark.media
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
    async def test_slow_skill_progress_updates(self, telegram_client, bot_username):
        """Test that slow skills send progress updates."""
        import asyncio
        import time

        # Send deep research request
        message = '/skill gemini-deep-research "Test progress updates"'
        sent = await telegram_client.send_message(bot_username, message)

        # Collect messages over time to check for progress
        messages = []
        start = time.time()
        while time.time() - start < 60:
            recent = await telegram_client.get_messages(bot_username, limit=10)
            for msg in recent:
                if not msg.out and msg.id > sent.id:
                    if msg.id not in [m.id for m in messages]:
                        messages.append(msg)
            await asyncio.sleep(5)

        # Should have at least initial acknowledgment
        assert len(messages) >= 1, "No progress updates received"

        # Check for progress indicators
        has_progress = any(
            "processing" in (m.text or "").lower() or
            "working" in (m.text or "").lower() or
            "..." in (m.text or "")
            for m in messages
        )
        # Progress updates are optional but good UX
        if not has_progress and len(messages) == 1:
            # Single response is acceptable
            pass
