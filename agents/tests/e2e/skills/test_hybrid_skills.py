# agents/tests/e2e/skills/test_hybrid_skills.py
"""E2E tests for hybrid skills (both remote and local capabilities)."""
import pytest
from ..conftest import execute_skill

# Hybrid skills that need longer timeout
SLOW_HYBRID_SKILLS = {"sequential-thinking", "mcp-builder", "better-auth"}

HYBRID_SKILLS = {
    "better-auth": {
        "remote_prompt": "What is Better Auth?",
        "local_prompt": "Generate auth code for my app",
        "remote_keywords": ["auth", "authentication", "library"],
        "local_keywords": ["code", "generate", "implement"],
    },
    "chrome-devtools": {
        "remote_prompt": "How to use Chrome DevTools?",
        "local_prompt": "Open DevTools and inspect this page",
        "remote_keywords": ["devtools", "chrome", "inspect", "debug"],
        "local_keywords": ["browser", "automation", "open"],
    },
    "mcp-builder": {
        "remote_prompt": "What is MCP protocol?",
        "local_prompt": "Create an MCP server for my tool",
        "remote_keywords": ["mcp", "protocol", "server"],
        "local_keywords": ["create", "build", "server"],
    },
    "repomix": {
        "remote_prompt": "How does Repomix work?",
        "local_prompt": "Bundle this repository with Repomix",
        "remote_keywords": ["repomix", "bundle", "repository"],
        "local_keywords": ["bundle", "file", "output"],
    },
    "sequential-thinking": {
        "remote_prompt": "Think through the Fibonacci sequence",
        "local_prompt": "Use sequential thinking to solve this complex problem",
        "remote_keywords": ["think", "step", "reason", "sequence"],
        "local_keywords": ["analyze", "step", "solution"],
    },
    "web-frameworks": {
        "remote_prompt": "Compare React vs Vue frameworks",
        "local_prompt": "Generate React component code",
        "remote_keywords": ["react", "vue", "framework", "compare"],
        "local_keywords": ["code", "component", "generate"],
    },
    "webapp-testing": {
        "remote_prompt": "What are best practices for web app testing?",
        "local_prompt": "Run tests on this web application",
        "remote_keywords": ["test", "testing", "practice", "strategy"],
        "local_keywords": ["run", "execute", "test"],
    },
}


class TestHybridSkills:
    """Tests for hybrid skills with both remote and local capabilities."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name", list(HYBRID_SKILLS.keys()))
    async def test_hybrid_remote_mode(self, telegram_client, bot_username, skill_name):
        """Test hybrid skill in remote mode (info/docs queries)."""
        config = HYBRID_SKILLS[skill_name]
        timeout = 90 if skill_name in SLOW_HYBRID_SKILLS else 60

        result = await execute_skill(
            telegram_client,
            bot_username,
            skill_name,
            config["remote_prompt"],
            timeout=timeout
        )

        assert result.success, f"Hybrid skill '{skill_name}' remote mode failed"
        assert result.text is not None, f"Empty response from '{skill_name}'"

        text_lower = result.text.lower()
        keywords = config["remote_keywords"]

        # At least one keyword should match
        matched = any(kw in text_lower for kw in keywords)
        assert matched, \
            f"Hybrid skill '{skill_name}' remote response missing expected keywords. " \
            f"Expected: {keywords}, got: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name", list(HYBRID_SKILLS.keys()))
    @pytest.mark.xfail(reason="Hybrid local-mode routing requires intent detection (future feature)")
    async def test_hybrid_local_mode(self, telegram_client, bot_username, skill_name):
        """Test hybrid skill in local mode (action queries).

        Note: Currently hybrid skills always execute remotely.
        Intent-based routing to detect local vs remote actions is planned.
        """
        config = HYBRID_SKILLS[skill_name]
        timeout = 90 if skill_name in SLOW_HYBRID_SKILLS else 60

        result = await execute_skill(
            telegram_client,
            bot_username,
            skill_name,
            config["local_prompt"],
            timeout=timeout
        )

        assert result.success, f"Hybrid skill '{skill_name}' local mode failed"
        assert result.text is not None, f"Empty response from '{skill_name}'"

        text_lower = result.text.lower()

        # For local actions, might get queue notification or action response
        keywords = config["local_keywords"] + ["queue", "task", "local", "execute"]
        matched = any(kw in text_lower for kw in keywords)

        assert matched, \
            f"Hybrid skill '{skill_name}' local response unexpected. " \
            f"Expected one of: {keywords}, got: {result.text[:200]}"
