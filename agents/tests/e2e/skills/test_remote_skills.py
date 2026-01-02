# agents/tests/e2e/skills/test_remote_skills.py
"""E2E tests for remote skills (executed on Modal)."""
import pytest
from ..conftest import execute_skill, send_and_wait

pytestmark = pytest.mark.requires_claude  # All tests in this module require Claude API

# Skills that need longer timeout (90s instead of 45s)
SLOW_SKILLS = {
    "planning", "research", "ai-multimodal", "content", "github",
    "telegram-chat", "devops", "firebase-automation", "problem-solving",
    "sequential-thinking", "skill-creator", "mcp-management",
    "internal-comms", "worktree-manager", "gemini-deep-research",
    "content-research-writer"
}

# Skill categories with expected response patterns
SKILL_ASSERTIONS = {
    # Research skills - expect report/analysis structure
    "planning": {"contains": ["plan", "step", "implement"]},
    "debugging": {"contains": ["debug", "issue", "fix"]},
    "research": {"contains": ["research", "find", "result"]},
    "code-review": {"contains": ["review", "code", "suggest"]},

    # Development skills - expect code/technical output
    "backend-development": {"contains": ["api", "endpoint", "database"]},
    "frontend-development": {"contains": ["component", "ui", "react"]},
    "mobile-development": {"contains": ["app", "mobile", "screen"]},

    # Design skills - expect design artifacts
    "ui-ux-pro-max": {"contains": ["design", "ui", "component"]},
    "ui-styling": {"contains": ["style", "css", "color"]},
    "frontend-design-pro": {"contains": ["design", "layout", "interface"]},

    # AI skills - expect AI-generated content
    "ai-multimodal": {"contains": ["image", "vision", "analyze"]},
    "ai-artist": {"contains": ["create", "generate", "art"]},
    "gemini-grounding": {"contains": ["search", "ground", "fact"]},
    "gemini-thinking": {"contains": ["think", "reason", "analyze"]},

    # Content skills - expect content output
    "content": {"contains": ["content", "write", "create"]},
    "content-research-writer": {"contains": ["research", "write", "article"]},

    # Data skills - expect data handling
    "data": {"contains": ["data", "analyze", "report"]},
    "databases": {"contains": ["database", "query", "schema"]},

    # Integration skills - expect integration info
    "github": {"contains": ["github", "repo", "issue"]},
    "telegram-chat": {"contains": ["telegram", "chat", "message"]},
    "shopify": {"contains": ["shopify", "store", "product"]},
    "payment-integration": {"contains": ["payment", "stripe", "checkout"]},

    # DevOps skills - expect infra commands
    "devops": {"contains": ["deploy", "docker", "cloud"]},
    "firebase-automation": {"contains": ["firebase", "firestore", "auth"]},

    # Cognitive skills - expect structured thinking
    "problem-solving": {"contains": ["problem", "solution", "approach"]},
    "sequential-thinking": {"contains": ["step", "think", "reason"]},

    # Meta skills
    "skill-creator": {"contains": ["skill", "create", "template"]},
    "mcp-management": {"contains": ["mcp", "server", "tool"]},
    "internal-comms": {"contains": ["communication", "update", "report"]},
    "worktree-manager": {"contains": ["worktree", "branch", "git"]},
}

# Default test prompts per skill
SKILL_PROMPTS = {
    "planning": "Create a simple hello world feature",
    "debugging": "Debug a null pointer exception",
    "research": "Research Python async best practices",
    "code-review": "Review this code: def foo(): pass",
    "backend-development": "Create a simple REST endpoint",
    "frontend-development": "Create a button component",
    "mobile-development": "Create a login screen",
    "ui-ux-pro-max": "Design a login form",
    "ui-styling": "Create a modern button style",
    "frontend-design-pro": "Design a dashboard layout",
    "ai-multimodal": "Describe what AI can do",
    "ai-artist": "Create a concept for a landscape",
    "gemini-grounding": "What is the current weather API?",
    "gemini-thinking": "Think through a sorting algorithm",
    "content": "Write a short product description",
    "content-research-writer": "Research and write about AI trends",
    "data": "Analyze sales data patterns",
    "databases": "Design a user table schema",
    "github": "List common GitHub actions",
    "telegram-chat": "What are Telegram bot capabilities?",
    "shopify": "How to create a Shopify product?",
    "payment-integration": "Explain Stripe checkout flow",
    "devops": "How to deploy a Python app?",
    "firebase-automation": "How to setup Firestore rules?",
    "problem-solving": "Solve the FizzBuzz problem",
    "sequential-thinking": "Think through a maze algorithm",
    "skill-creator": "How to create a new skill?",
    "mcp-management": "List available MCP servers",
    "internal-comms": "Write a project status update",
    "worktree-manager": "How to create a git worktree?",
}


class TestRemoteSkills:
    """Tests for remotely executed skills."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name", list(SKILL_PROMPTS.keys()))
    async def test_skill_invocation(self, telegram_client, bot_username, skill_name):
        """Test each remote skill can be invoked."""
        prompt = SKILL_PROMPTS.get(skill_name, "Hello")
        timeout = 90 if skill_name in SLOW_SKILLS else 45

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
        assert len(result.text) > 20, f"Skill '{skill_name}' response too short"

        # Check for error indicators - only fail on actual error responses
        # not on skill responses that discuss errors (like debugging skill)
        text_lower = result.text.lower()
        is_actual_error = (
            text_lower.startswith("❌") or
            text_lower.startswith("error:") or
            "error:" in text_lower[:50]  # Error indicator at start
        )
        assert not is_actual_error, \
            f"Skill '{skill_name}' returned error: {result.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_name", list(SKILL_ASSERTIONS.keys()))
    async def test_skill_response_content(self, telegram_client, bot_username, skill_name):
        """Test skill responses contain expected content."""
        prompt = SKILL_PROMPTS.get(skill_name, "Hello")
        assertions = SKILL_ASSERTIONS.get(skill_name, {"contains": []})
        timeout = 90 if skill_name in SLOW_SKILLS else 45

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

        # Check expected keywords (at least one must match)
        expected = assertions.get("contains", [])
        if expected:
            matched = any(word in text_lower for word in expected)
            assert matched, \
                f"Skill '{skill_name}' response missing expected content. " \
                f"Expected one of: {expected}. Got: {result.text[:200]}"

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
        # Should show usage hint or ask for input
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
