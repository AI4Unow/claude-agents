# agents/tests/e2e/skills/test_smoke.py
"""Smoke tests for all skills - basic invocation check.

Runs against ALL discovered skills to ensure basic functionality.
Uses dynamic discovery from SkillRegistry.
"""
import pytest
from ..conftest import execute_skill

from .skill_loader import get_skill_names, is_local_skill, get_skill_timeout
from .test_data_loader import TestDataLoader
from .assertions import SkillAssertionChecker

# Initialize shared instances
loader = TestDataLoader()
checker = SkillAssertionChecker(use_llm=False)


class TestSkillSmoke:
    """Basic invocation tests for all skills."""

    @pytest.mark.e2e
    @pytest.mark.smoke
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name", get_skill_names())
    async def test_skill_responds(self, telegram_client, bot_username, skill_name):
        """Every skill should respond without error."""
        test_data = loader.get(skill_name)
        timeout = test_data.timeout if test_data else get_skill_timeout(skill_name)
        prompt = test_data.prompt if test_data else "Hello"

        # Apply slow marker dynamically
        if timeout > 60:
            pytest.mark.slow(self)

        result = await execute_skill(
            telegram_client,
            bot_username,
            skill_name,
            prompt,
            timeout=timeout
        )

        # Basic assertions
        assert result.success, f"Skill '{skill_name}' failed to respond"
        assert result.text is not None, f"Skill '{skill_name}' returned None"

        # Local skills return queue confirmation
        if is_local_skill(skill_name):
            text_lower = result.text.lower()
            is_queued = "queue" in text_lower or "task" in text_lower or "pending" in text_lower
            assert is_queued or len(result.text) > 20, \
                f"Local skill '{skill_name}' unexpected response: {result.text[:200]}"
            return

        # Remote skills should have substantive response
        assert len(result.text) > 20, f"Skill '{skill_name}' response too short: {result.text[:100]}"

    @pytest.mark.e2e
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_skill_discovery_count(self, all_skill_summaries):
        """Verify skill discovery finds expected number of skills."""
        # Should find at least 50 skills (we have 102 total)
        assert len(all_skill_summaries) >= 50, \
            f"Expected at least 50 skills, found {len(all_skill_summaries)}"

    @pytest.mark.e2e
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_local_skills_detected(self, local_skill_names):
        """Verify local skills are properly detected."""
        expected_local = {"pdf", "docx", "xlsx", "pptx", "canvas-design",
                         "media-processing", "image-enhancer", "video-downloader"}
        detected = set(local_skill_names)
        missing = expected_local - detected
        assert not missing, f"Missing local skills: {missing}"

    @pytest.mark.e2e
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_slow_skills_detected(self, slow_skill_names):
        """Verify slow skills are properly detected."""
        expected_slow = {"planning", "research", "gemini-deep-research", "ui-ux-pro-max"}
        detected = set(slow_skill_names)
        missing = expected_slow - detected
        assert not missing, f"Missing slow skills: {missing}"
