# agents/tests/e2e/integration/test_multi_turn.py
"""E2E tests for multi-turn conversation handling."""
import pytest
import asyncio
from ..conftest import send_and_wait


class TestMultiTurn:
    """Tests for conversation continuity across messages."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_basic_multi_turn(self, telegram_client, bot_username):
        """Basic multi-turn conversation works."""
        # Turn 1: Establish topic
        turn1 = await send_and_wait(
            telegram_client,
            bot_username,
            "I want to learn about Python decorators",
            timeout=45
        )

        assert turn1 is not None, "No response to turn 1"
        await asyncio.sleep(2)

        # Turn 2: Follow up
        turn2 = await send_and_wait(
            telegram_client,
            bot_username,
            "Can you give me a simple example?",
            timeout=45
        )

        assert turn2 is not None, "No response to turn 2"
        text_lower = (turn2.text or "").lower()

        # Should provide example related to decorators
        example_words = ["def", "example", "@", "decorator", "function", "code"]
        has_example = any(word in text_lower for word in example_words)
        assert has_example, f"Follow-up not contextual: {turn2.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_context_across_skill_changes(self, telegram_client, bot_username):
        """Context maintained when switching skills."""
        from ..conftest import execute_skill

        # Use research skill
        research = await execute_skill(
            telegram_client,
            bot_username,
            "research",
            "What are the benefits of TypeScript?",
            timeout=45
        )

        assert research.success, "Research failed"
        await asyncio.sleep(2)

        # Use planning skill referencing research
        planning = await execute_skill(
            telegram_client,
            bot_username,
            "planning",
            "Now plan how to migrate our JS project to TypeScript",
            timeout=45
        )

        assert planning.success, "Planning failed"
        text_lower = (planning.text or "").lower()

        # Should reference TypeScript
        ts_words = ["typescript", "migrate", "js", "javascript", "type", "plan"]
        has_ts = any(word in text_lower for word in ts_words)
        assert has_ts, f"Context lost: {planning.text[:200]}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_long_conversation_chain(self, telegram_client, bot_username):
        """Multi-turn with 5+ messages maintains coherence."""
        messages = [
            "Let's design a REST API for a todo app",
            "What endpoints should we have?",
            "How about authentication?",
            "What about pagination?",
            "Can you summarize what we've discussed?",
        ]

        last_response = None
        for msg in messages:
            response = await send_and_wait(
                telegram_client,
                bot_username,
                msg,
                timeout=45
            )
            assert response is not None, f"No response to: {msg}"
            last_response = response
            await asyncio.sleep(2)

        # Final summary should reference earlier topics
        text_lower = (last_response.text or "").lower()
        summary_refs = ["todo", "endpoint", "api", "authentication", "pagination", "rest"]
        refs_found = sum(1 for word in summary_refs if word in text_lower)
        assert refs_found >= 2, f"Summary missing context: {last_response.text[:300]}"
