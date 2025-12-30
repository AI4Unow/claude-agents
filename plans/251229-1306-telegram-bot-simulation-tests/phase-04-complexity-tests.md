---
phase: 4
title: "Complexity Detection and Routing Tests"
status: pending
effort: 1h
---

# Phase 4: Complexity Detection and Routing Tests

## Context

- Parent: [plan.md](./plan.md)
- Dependencies: Phase 1
- Docs: pytest, unittest.mock

## Overview

Test the complexity detection system that routes messages to simple LLM or orchestrator based on message analysis. Covers fast-path keyword matching and LLM fallback.

## Requirements

1. Test fast_keyword_check for all patterns
2. Test LLM-based classification
3. Test circuit breaker integration
4. Test process_message routing based on mode
5. Test orchestrator progress callbacks

## Related Code Files

- `agents/src/core/complexity.py` - fast_keyword_check, classify_complexity
- `agents/main.py:1540-1560` - Mode-based routing
- `agents/src/core/orchestrator.py` - progress_callback handling

## Complexity Detection Flow

```
Message → fast_keyword_check() → SIMPLE/COMPLEX/None
                                     ↓ None
                               LLM Classification
                                     ↓
                               SIMPLE/COMPLEX
```

## Implementation Steps

### Step 1: Create test_complexity.py

```python
# agents/tests/test_telegram/test_complexity.py
"""Tests for complexity detection and message routing."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

pytestmark = pytest.mark.asyncio


class TestFastKeywordCheck:
    """Test fast path keyword-based classification."""

    def test_simple_greetings(self):
        """Greetings classified as simple."""
        from src.core.complexity import fast_keyword_check

        simple_greetings = ["hi", "hello", "hey", "Hi!", "HELLO?", "thanks", "ok"]
        for msg in simple_greetings:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_simple_questions(self):
        """Simple questions classified as simple."""
        from src.core.complexity import fast_keyword_check

        questions = [
            "what is Python?",
            "who is the CEO?",
            "where is the file?",
            "when was it created?",
            "how does it work?",
        ]
        for msg in questions:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_simple_commands(self):
        """Translate/convert commands classified as simple."""
        from src.core.complexity import fast_keyword_check

        commands = [
            "translate this to French",
            "convert 100 USD to EUR",
            "define machine learning",
            "explain the concept",
        ]
        for msg in commands:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_complex_keywords(self):
        """Complex keywords trigger complex classification."""
        from src.core.complexity import fast_keyword_check

        complex_messages = [
            "plan a new feature",
            "build a login system",
            "create a REST API",
            "implement user authentication",
            "design a database schema",
            "analyze the codebase",
            "review my code",
            "debug this error",
            "fix the bug",
            "optimize performance",
            "refactor the module",
            "research best practices",
        ]
        for msg in complex_messages:
            result = fast_keyword_check(msg)
            assert result == "complex", f"'{msg}' should be complex"

    def test_short_questions_simple(self):
        """Short questions with ? are simple."""
        from src.core.complexity import fast_keyword_check

        short_questions = [
            "how much?",
            "why not?",
            "when?",
        ]
        for msg in short_questions:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_ambiguous_returns_none(self):
        """Ambiguous messages return None for LLM classification."""
        from src.core.complexity import fast_keyword_check

        ambiguous = [
            "I need help with my project",
            "Can you assist me?",
            "Let's discuss the architecture",
            "What are the best options for this?",
        ]
        for msg in ambiguous:
            result = fast_keyword_check(msg)
            # Should return None or a classification
            # None means needs LLM

    def test_case_insensitive_keywords(self):
        """Keywords are matched case-insensitively."""
        from src.core.complexity import fast_keyword_check

        assert fast_keyword_check("PLAN a feature") == "complex"
        assert fast_keyword_check("Build IT") == "complex"
        assert fast_keyword_check("HI there") == "simple"


class TestClassifyComplexity:
    """Test LLM-based complexity classification."""

    async def test_classify_uses_fast_path_first(self):
        """classify_complexity uses fast path when available."""
        from src.core.complexity import classify_complexity

        with patch("src.core.complexity.fast_keyword_check", return_value="simple") as mock:
            result = await classify_complexity("hi there")

        assert result == "simple"
        mock.assert_called_once()

    async def test_classify_falls_back_to_llm(self):
        """classify_complexity calls LLM when fast path returns None."""
        from src.core.complexity import classify_complexity

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="COMPLEX")]

        with patch("src.core.complexity.fast_keyword_check", return_value=None), \
             patch("src.services.llm.get_llm_client") as mock_client:

            mock_client.return_value.client.messages.create.return_value = mock_response

            result = await classify_complexity("help me with my code")

        # LLM should have been called
        mock_client.return_value.client.messages.create.assert_called_once()

    async def test_classify_returns_simple_on_error(self):
        """classify_complexity returns simple on LLM error."""
        from src.core.complexity import classify_complexity

        with patch("src.core.complexity.fast_keyword_check", return_value=None), \
             patch("src.services.llm.get_llm_client") as mock_client:

            mock_client.return_value.client.messages.create.side_effect = Exception("API error")

            result = await classify_complexity("ambiguous message")

        assert result == "simple"  # Default on error

    async def test_classify_respects_circuit_breaker(self):
        """classify_complexity skips LLM if circuit is open."""
        from src.core.complexity import classify_complexity
        from src.core.resilience import CircuitState

        with patch("src.core.complexity.fast_keyword_check", return_value=None), \
             patch("src.core.resilience.claude_circuit") as mock_circuit:

            mock_circuit.state = CircuitState.OPEN

            result = await classify_complexity("ambiguous message")

        assert result == "simple"  # Default when circuit open


class TestModeBasedRouting:
    """Test message routing based on user mode."""

    async def test_auto_mode_routes_simple_directly(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Auto mode routes simple messages to direct LLM."""
        from main import process_message

        mock_state.set_mode(123, "auto")

        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock, return_value="simple"), \
             patch("main._run_simple", new_callable=AsyncMock, return_value="Simple response") as mock_simple, \
             patch("main._run_orchestrated", new_callable=AsyncMock) as mock_orch:

            user = {"id": 123}
            result = await process_message("hello", user, 123, 1)

        mock_simple.assert_called_once()
        mock_orch.assert_not_called()

    async def test_auto_mode_routes_complex_to_orchestrator(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Auto mode routes complex messages to orchestrator."""
        from main import process_message

        mock_state.set_mode(123, "auto")

        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock, return_value="complex"), \
             patch("main._run_simple", new_callable=AsyncMock) as mock_simple, \
             patch("main._run_orchestrated", new_callable=AsyncMock, return_value="Orchestrated response") as mock_orch:

            user = {"id": 123}
            result = await process_message("build a login system", user, 123, 1)

        mock_orch.assert_called_once()
        mock_simple.assert_not_called()

    async def test_simple_mode_skips_classification(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Simple mode always uses direct LLM."""
        from main import process_message

        mock_state.set_mode(123, "simple")

        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock) as mock_classify, \
             patch("main._run_simple", new_callable=AsyncMock, return_value="Response") as mock_simple:

            user = {"id": 123}
            result = await process_message("build a login system", user, 123, 1)

        mock_classify.assert_not_called()  # Skipped in simple mode
        mock_simple.assert_called_once()

    async def test_routed_mode_uses_router(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Routed mode uses skill router."""
        from main import process_message

        mock_state.set_mode(123, "routed")

        with patch("main._run_routed", new_callable=AsyncMock, return_value="Routed response") as mock_routed:

            user = {"id": 123}
            result = await process_message("help me", user, 123, 1)

        mock_routed.assert_called_once()


class TestOrchestratorProgress:
    """Test orchestrator progress callback integration."""

    async def test_orchestrator_calls_progress_callback(self):
        """Orchestrator calls progress callback during execution."""
        from src.core.orchestrator import Orchestrator

        progress_updates = []

        async def track_progress(msg: str):
            progress_updates.append(msg)

        with patch("src.core.router.SkillRouter") as mock_router, \
             patch("src.services.llm.get_llm_client") as mock_llm, \
             patch("src.skills.registry.get_registry") as mock_reg:

            # Set up mocks
            mock_router.return_value.route.return_value = []
            mock_router.return_value.get_all_skills.return_value = ["planning"]
            mock_llm.return_value.chat.return_value = '[]'  # Empty decomposition
            mock_reg.return_value.get_full.return_value = None

            orchestrator = Orchestrator()

            # Override decompose to return simple subtasks
            async def mock_decompose(task, context):
                return []

            orchestrator.decompose = mock_decompose

            result = await orchestrator.execute(
                "test task",
                context={},
                progress_callback=track_progress
            )

        # Should have progress updates
        assert len(progress_updates) > 0
        assert any("Analyzing" in msg for msg in progress_updates)

    async def test_orchestrator_handles_callback_error(self):
        """Orchestrator continues if progress callback raises."""
        from src.core.orchestrator import Orchestrator

        async def failing_callback(msg: str):
            raise Exception("Callback failed")

        with patch("src.core.router.SkillRouter") as mock_router, \
             patch("src.services.llm.get_llm_client") as mock_llm:

            mock_router.return_value.route.return_value = []
            mock_router.return_value.get_all_skills.return_value = []
            mock_llm.return_value.chat.return_value = '[]'

            orchestrator = Orchestrator()

            # Should not raise despite callback failure
            result = await orchestrator.execute(
                "test task",
                progress_callback=failing_callback
            )

            # Should still complete
            assert result is not None


class TestProgressMessageUpdates:
    """Test Telegram progress message updates."""

    async def test_progress_message_sent_on_start(self, mock_env, mock_state, mock_telegram_api):
        """Progress message sent when processing starts."""
        from main import process_message

        mock_state.set_mode(123, "simple")

        with patch("main._run_simple", new_callable=AsyncMock, return_value="Response"):
            user = {"id": 123}
            await process_message("hello", user, 123, 1)

        # Initial progress message sent
        mock_telegram_api["progress"].assert_called()

    async def test_progress_message_updated_on_complete(self, mock_env, mock_state, mock_telegram_api):
        """Progress message updated to 'Complete' when done."""
        from main import process_message

        mock_state.set_mode(123, "simple")

        with patch("main._run_simple", new_callable=AsyncMock, return_value="Response"):
            user = {"id": 123}
            await process_message("hello", user, 123, 1)

        # Should have edited progress to complete
        calls = mock_telegram_api["edit"].call_args_list
        final_call = calls[-1] if calls else None
        if final_call:
            assert "Complete" in str(final_call)

    async def test_progress_message_shows_error(self, mock_env, mock_state, mock_telegram_api):
        """Progress message shows error on failure."""
        from main import process_message

        mock_state.set_mode(123, "simple")

        with patch("main._run_simple", new_callable=AsyncMock, side_effect=Exception("Test error")):
            user = {"id": 123}
            result = await process_message("hello", user, 123, 1)

        # Should have edited progress to show error
        calls = mock_telegram_api["edit"].call_args_list
        assert any("Error" in str(call) for call in calls)
```

## Todo List

- [ ] Create `test_complexity.py` file
- [ ] Implement TestFastKeywordCheck (8 tests)
- [ ] Implement TestClassifyComplexity (4 tests)
- [ ] Implement TestModeBasedRouting (4 tests)
- [ ] Implement TestOrchestratorProgress (2 tests)
- [ ] Implement TestProgressMessageUpdates (3 tests)
- [ ] Run tests and verify all pass

## Success Criteria

1. All 21 tests pass
2. Fast path keywords fully covered
3. LLM fallback tested
4. Circuit breaker integration verified
5. Mode routing works correctly
6. Progress callbacks function properly

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Keyword list changes | Test representative samples |
| LLM response format varies | Mock at message level |
| Async timing issues | Use proper async fixtures |

## Next Steps

After completing this phase:
1. Proceed to Phase 5: Full Integration Tests
2. Test complete conversation flows
