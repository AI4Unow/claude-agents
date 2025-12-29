"""Tests for complexity detection and message routing."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

pytestmark = pytest.mark.asyncio


class TestFastKeywordCheck:
    """Test fast path keyword-based classification."""

    def test_simple_greetings(self):
        """Greetings classified as simple."""
        from src.core.complexity import fast_keyword_check

        greetings = ["hi", "hello", "hey", "Hi!", "thanks", "ok"]
        for msg in greetings:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_simple_questions(self):
        """Simple questions classified as simple."""
        from src.core.complexity import fast_keyword_check

        questions = [
            "what is Python?",
            "who is the CEO?",
            "where is the file?",
        ]
        for msg in questions:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_simple_commands(self):
        """Translate/convert commands classified as simple."""
        from src.core.complexity import fast_keyword_check

        commands = ["translate this to French", "define machine learning"]
        for msg in commands:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_complex_keywords(self):
        """Complex keywords trigger complex classification."""
        from src.core.complexity import fast_keyword_check

        messages = [
            "plan a new feature",
            "build a login system",
            "create a REST API",
            "analyze the codebase",
            "review my code",
            "debug this error",
        ]
        for msg in messages:
            result = fast_keyword_check(msg)
            assert result == "complex", f"'{msg}' should be complex"

    def test_short_questions_simple(self):
        """Short questions with ? are simple."""
        from src.core.complexity import fast_keyword_check

        short = ["how much?", "why not?"]
        for msg in short:
            result = fast_keyword_check(msg)
            assert result == "simple", f"'{msg}' should be simple"

    def test_case_insensitive(self):
        """Keywords matched case-insensitively."""
        from src.core.complexity import fast_keyword_check

        assert fast_keyword_check("PLAN a feature") == "complex"
        assert fast_keyword_check("Build IT") == "complex"


class TestClassifyComplexity:
    """Test LLM-based complexity classification."""

    async def test_uses_fast_path_first(self):
        """classify_complexity uses fast path when available."""
        from src.core.complexity import classify_complexity

        with patch("src.core.complexity.fast_keyword_check", return_value="simple") as mock:
            result = await classify_complexity("hi there")

        assert result == "simple"
        mock.assert_called_once()

    async def test_returns_simple_on_error(self):
        """Returns simple on LLM error."""
        from src.core.complexity import classify_complexity

        with patch("src.core.complexity.fast_keyword_check", return_value=None), \
             patch("src.services.llm.get_llm_client") as mock_client:

            mock_client.return_value.client.messages.create.side_effect = Exception("API error")
            result = await classify_complexity("ambiguous message")

        assert result == "simple"

    async def test_respects_circuit_breaker(self):
        """Skips LLM if circuit is open."""
        from src.core.complexity import classify_complexity
        from src.core.resilience import CircuitState

        with patch("src.core.complexity.fast_keyword_check", return_value=None), \
             patch("src.core.resilience.claude_circuit") as mock_circuit:

            mock_circuit.state = CircuitState.OPEN
            result = await classify_complexity("ambiguous message")

        assert result == "simple"


class TestModeBasedRouting:
    """Test message routing based on user mode."""

    async def test_auto_mode_routes_simple(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Auto mode routes simple messages directly."""
        from main import process_message

        mock_state.set_mode(123, "auto")
        mock_state.set_tier(123, "user")

        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock, return_value="simple"), \
             patch("main._run_simple", new_callable=AsyncMock, return_value="Simple response") as mock_simple, \
             patch("main._run_orchestrated", new_callable=AsyncMock) as mock_orch:

            user = {"id": 123}
            result = await process_message("hello", user, 123, 1)

        mock_simple.assert_called_once()
        mock_orch.assert_not_called()

    async def test_auto_mode_routes_complex(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Auto mode routes complex to orchestrator."""
        from main import process_message

        mock_state.set_mode(123, "auto")
        mock_state.set_tier(123, "user")

        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock, return_value="complex"), \
             patch("main._run_simple", new_callable=AsyncMock) as mock_simple, \
             patch("main._run_orchestrated", new_callable=AsyncMock, return_value="Orchestrated") as mock_orch:

            user = {"id": 123}
            result = await process_message("build a login system", user, 123, 1)

        mock_orch.assert_called_once()
        mock_simple.assert_not_called()

    async def test_simple_mode_skips_classification(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Simple mode always uses direct LLM."""
        from main import process_message

        mock_state.set_mode(123, "simple")
        mock_state.set_tier(123, "user")

        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock) as mock_classify, \
             patch("main._run_simple", new_callable=AsyncMock, return_value="Response"):

            user = {"id": 123}
            result = await process_message("build a login", user, 123, 1)

        mock_classify.assert_not_called()

    async def test_routed_mode_uses_router(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Routed mode uses skill router."""
        from main import process_message

        mock_state.set_mode(123, "routed")
        mock_state.set_tier(123, "user")

        with patch("main._run_routed", new_callable=AsyncMock, return_value="Routed") as mock_routed:
            user = {"id": 123}
            result = await process_message("help me", user, 123, 1)

        mock_routed.assert_called_once()


class TestOrchestratorProgress:
    """Test orchestrator progress callback."""

    async def test_orchestrator_calls_callback(self):
        """Orchestrator calls progress callback."""
        from src.core.orchestrator import Orchestrator

        updates = []

        async def track(msg: str):
            updates.append(msg)

        with patch("src.core.router.SkillRouter") as mock_router, \
             patch("src.services.llm.get_llm_client") as mock_llm:

            mock_router.return_value.route.return_value = []
            mock_router.return_value.get_all_skills.return_value = []
            mock_llm.return_value.chat.return_value = '[]'

            orch = Orchestrator()

            async def mock_decompose(task, ctx):
                return []

            orch.decompose = mock_decompose
            result = await orch.execute("test", progress_callback=track)

        assert len(updates) > 0

    async def test_orchestrator_handles_callback_error(self):
        """Continues if callback raises."""
        from src.core.orchestrator import Orchestrator

        async def failing(msg: str):
            raise Exception("Fail")

        with patch("src.core.router.SkillRouter") as mock_router, \
             patch("src.services.llm.get_llm_client") as mock_llm:

            mock_router.return_value.route.return_value = []
            mock_router.return_value.get_all_skills.return_value = []
            mock_llm.return_value.chat.return_value = '[]'

            orch = Orchestrator()
            result = await orch.execute("test", progress_callback=failing)

            assert result is not None


class TestProgressMessages:
    """Test Telegram progress message updates."""

    async def test_progress_sent_on_start(self, mock_env, mock_state, mock_telegram_api):
        """Progress message sent when processing starts."""
        from main import process_message

        mock_state.set_mode(123, "simple")
        mock_state.set_tier(123, "user")

        with patch("main._run_simple", new_callable=AsyncMock, return_value="Response"):
            user = {"id": 123}
            await process_message("hello", user, 123, 1)

        mock_telegram_api["progress"].assert_called()

    async def test_progress_shows_error(self, mock_env, mock_state, mock_telegram_api):
        """Progress shows error on failure."""
        from main import process_message

        mock_state.set_mode(123, "simple")
        mock_state.set_tier(123, "user")

        with patch("main._run_simple", new_callable=AsyncMock, side_effect=Exception("Test error")):
            user = {"id": 123}
            result = await process_message("hello", user, 123, 1)

        calls = mock_telegram_api["edit"].call_args_list
        assert any("Error" in str(c) for c in calls)
