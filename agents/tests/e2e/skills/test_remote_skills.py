# agents/tests/e2e/skills/test_remote_skills.py
"""E2E tests for remote skills (executed on Modal).

Uses dynamic skill discovery from SkillRegistry.
"""
import pytest
from ..conftest import execute_skill

from .skill_loader import (
    get_skill_names,
    is_local_skill,
    is_slow_skill,
    get_skill_timeout,
)
from .test_data_loader import TestDataLoader

# Module-level marker
pytestmark = pytest.mark.requires_claude

# Initialize test data loader
loader = TestDataLoader()


class TestRemoteSkills:
    """Tests for remotely executed skills."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name", get_skill_names("remote"))
    async def test_skill_invocation(self, telegram_client, bot_username, skill_name):
        """Test each remote skill can be invoked and responds."""
        # Get test data (prompt, timeout, assertions)
        test_data = loader.get(skill_name)
        timeout = test_data.timeout if test_data else get_skill_timeout(skill_name)
        prompt = test_data.prompt if test_data else "Hello"

        result = await execute_skill(
            telegram_client,
            bot_username,
            skill_name,
            prompt,
            timeout=timeout
        )

        # Basic assertions
        assert result.success, f"Skill '{skill_name}' failed to respond"
        assert result.text is not None, f"Skill '{skill_name}' returned empty response"

        text_lower = result.text.lower()

        # Handle local skills (queued to Firebase)
        if is_local_skill(skill_name):
            is_queued = "queue" in text_lower or "task" in text_lower
            assert is_queued or len(result.text) > 20, \
                f"Local skill '{skill_name}' not queued: {result.text[:200]}"
            return

        assert len(result.text) > 20, f"Skill '{skill_name}' response too short"

        # Check for error indicators (exclude skills that discuss errors)
        error_discussing_skills = {"debugging", "code-review", "problem-solving"}
        if skill_name not in error_discussing_skills:
            is_actual_error = (
                text_lower.startswith("❌") or
                text_lower.startswith("error:") or
                (text_lower.startswith("error") and ":" in text_lower[:15])
            )
            assert not is_actual_error, \
                f"Skill '{skill_name}' returned error: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name", get_skill_names("remote"))
    async def test_skill_response_content(self, telegram_client, bot_username, skill_name):
        """Test skill responses contain expected content patterns."""
        # Skip local skills
        if is_local_skill(skill_name):
            pytest.skip(f"Skill '{skill_name}' is local (queued)")

        test_data = loader.get(skill_name)
        timeout = test_data.timeout if test_data else get_skill_timeout(skill_name)
        prompt = test_data.prompt if test_data else "Hello"

        result = await execute_skill(
            telegram_client,
            bot_username,
            skill_name,
            prompt,
            timeout=timeout
        )

        if not result.success:
            pytest.skip(f"Skill '{skill_name}' not available")

        text_lower = result.text.lower()

        # Handle queued response
        if "queue" in text_lower and "task" in text_lower:
            pytest.skip(f"Skill '{skill_name}' queued for local execution")

        # Skip if circuit breaker is open
        if "circuit" in text_lower and "opened" in text_lower:
            pytest.skip(f"Skill '{skill_name}' circuit breaker open")

        # Check expected patterns if test data has assertions
        if test_data and test_data.assertions:
            patterns = test_data.assertions.get("patterns", [])
            if patterns:
                matched = any(p.lower() in text_lower for p in patterns)
                assert matched, \
                    f"Skill '{skill_name}' response missing expected content. " \
                    f"Expected one of: {patterns}. Got: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_skill_without_prompt(self, telegram_client, bot_username):
        """Test skill invocation without prompt shows usage."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "planning",
            "",  # Empty prompt
            timeout=30
        )

        assert result.success, "No response to empty skill invocation"
        text_lower = result.text.lower()
        assert any(word in text_lower for word in ["usage", "help", "provide", "specify", "what"]), \
            f"Expected usage hint, got: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_unknown_skill(self, telegram_client, bot_username):
        """Test unknown skill returns helpful error."""
        result = await execute_skill(
            telegram_client,
            bot_username,
            "nonexistent-skill-xyz-123",
            "test",
            timeout=30
        )

        assert result.success, "No response to unknown skill"
        text_lower = result.text.lower()
        assert any(word in text_lower for word in ["not found", "unknown", "available", "error"]), \
            f"Expected 'not found' message, got: {result.text[:200]}"
