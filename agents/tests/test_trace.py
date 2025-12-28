"""Unit tests for src/core/trace.py - Execution Tracing.

Target: 100% coverage
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import re

from src.core.trace import (
    ToolTrace,
    ExecutionTrace,
    TraceContext,
    get_current_trace,
    get_trace,
    list_traces,
    _sanitize_input,
    MAX_TOOL_TRACES,
    SENSITIVE_KEYS,
    VALID_STATUSES,
)


class TestSanitizeInput:
    """Test input sanitization."""

    def test_sanitizes_api_key(self):
        """api_key is redacted."""
        result = _sanitize_input({"api_key": "sk-secret-123"})
        assert result["api_key"] == "***REDACTED***"

    def test_sanitizes_token(self):
        """token is redacted."""
        result = _sanitize_input({"auth_token": "bearer-xyz"})
        assert result["auth_token"] == "***REDACTED***"

    def test_sanitizes_password(self):
        """password is redacted."""
        result = _sanitize_input({"password": "secret123"})
        assert result["password"] == "***REDACTED***"

    def test_sanitizes_secret(self):
        """secret is redacted."""
        result = _sanitize_input({"client_secret": "abcdef"})
        assert result["client_secret"] == "***REDACTED***"

    def test_sanitizes_authorization(self):
        """authorization is redacted."""
        result = _sanitize_input({"Authorization": "Bearer xyz"})
        assert result["Authorization"] == "***REDACTED***"

    def test_preserves_normal_keys(self):
        """Normal keys are preserved."""
        result = _sanitize_input({"query": "test search", "limit": 10})
        assert result["query"] == "test search"
        assert result["limit"] == "10"

    def test_truncates_long_values(self):
        """Values are truncated to 100 chars."""
        long_value = "x" * 200
        result = _sanitize_input({"data": long_value})
        assert len(result["data"]) == 100

    def test_case_insensitive_matching(self):
        """Sensitive key matching is case-insensitive."""
        result = _sanitize_input({
            "API_KEY": "secret1",
            "Api_Key": "secret2",
            "api_key": "secret3",
        })
        assert all(v == "***REDACTED***" for v in result.values())


class TestToolTrace:
    """Test ToolTrace dataclass."""

    def test_tool_trace_truncates_output(self):
        """Output truncated to 500 chars."""
        long_output = "y" * 1000
        trace = ToolTrace.create(
            name="test_tool",
            input_params={"query": "test"},
            output=long_output,
            duration_ms=100,
        )
        assert len(trace.output) <= 503  # 500 + "..."

    def test_tool_trace_sanitizes_input(self):
        """Sensitive keys in input are redacted."""
        trace = ToolTrace.create(
            name="web_search",
            input_params={"query": "test", "api_key": "secret"},
            output="results",
            duration_ms=50,
        )
        assert trace.input["api_key"] == "***REDACTED***"
        assert trace.input["query"] == "test"

    def test_tool_trace_sets_timestamp(self):
        """Timestamp is set on creation."""
        trace = ToolTrace.create(
            name="test",
            input_params={},
            output="result",
            duration_ms=10,
        )
        assert trace.timestamp is not None
        # Validate ISO format
        datetime.fromisoformat(trace.timestamp.replace("Z", "+00:00"))

    def test_tool_trace_is_error_default_false(self):
        """is_error defaults to False."""
        trace = ToolTrace.create(
            name="test",
            input_params={},
            output="result",
            duration_ms=10,
        )
        assert trace.is_error is False

    def test_tool_trace_is_error_can_be_set(self):
        """is_error can be set to True."""
        trace = ToolTrace.create(
            name="test",
            input_params={},
            output="Error: failed",
            duration_ms=10,
            is_error=True,
        )
        assert trace.is_error is True


class TestExecutionTrace:
    """Test ExecutionTrace dataclass."""

    def test_to_dict_converts_correctly(self):
        """to_dict produces Firebase-compatible dict."""
        tool_trace = ToolTrace.create(
            name="test",
            input_params={"q": "test"},
            output="result",
            duration_ms=100,
        )
        trace = ExecutionTrace(
            trace_id="abc123",
            user_id=42,
            skill="planning",
            started_at="2025-12-28T12:00:00+00:00",
            ended_at="2025-12-28T12:00:05+00:00",
            iterations=2,
            tool_traces=[tool_trace],
            final_output="Final result",
            status="success",
            metadata={"extra": "data"},
        )

        d = trace.to_dict()

        assert d["trace_id"] == "abc123"
        assert d["user_id"] == 42
        assert d["skill"] == "planning"
        assert d["iterations"] == 2
        assert len(d["tool_traces"]) == 1
        assert d["status"] == "success"

    def test_to_dict_truncates_final_output(self):
        """Final output truncated to 1000 chars."""
        long_output = "z" * 2000
        trace = ExecutionTrace(
            trace_id="abc",
            user_id=None,
            skill=None,
            started_at="2025-12-28T12:00:00+00:00",
            ended_at=None,
            iterations=1,
            tool_traces=[],
            final_output=long_output,
            status="success",
            metadata={},
        )

        d = trace.to_dict()
        assert len(d["final_output"]) == 1000

    def test_from_dict_creates_trace(self):
        """from_dict creates ExecutionTrace from dict."""
        data = {
            "trace_id": "xyz789",
            "user_id": 123,
            "skill": "research",
            "started_at": "2025-12-28T12:00:00+00:00",
            "ended_at": "2025-12-28T12:01:00+00:00",
            "iterations": 3,
            "tool_traces": [
                {
                    "name": "web_search",
                    "input": {"query": "test"},
                    "output": "results",
                    "duration_ms": 200,
                    "is_error": False,
                    "timestamp": "2025-12-28T12:00:30+00:00",
                }
            ],
            "final_output": "Done",
            "status": "success",
            "metadata": {"key": "value"},
        }

        trace = ExecutionTrace.from_dict(data)

        assert trace.trace_id == "xyz789"
        assert trace.user_id == 123
        assert trace.skill == "research"
        assert trace.iterations == 3
        assert len(trace.tool_traces) == 1
        assert trace.tool_traces[0].name == "web_search"


class TestTraceContext:
    """Test TraceContext async context manager."""

    @pytest.mark.asyncio
    async def test_trace_context_sets_status_success(self):
        """Normal exit sets status to success."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext(user_id=1, skill="test") as ctx:
                ctx.set_output("result")

            assert ctx.status == "success"

    @pytest.mark.asyncio
    async def test_trace_context_sets_status_error_on_exception(self):
        """Exception sets status to error."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            with pytest.raises(ValueError):
                async with TraceContext(user_id=1) as ctx:
                    raise ValueError("Test error")

            assert ctx.status == "error"
            assert "Test error" in ctx.metadata.get("error", "")

    @pytest.mark.asyncio
    async def test_trace_context_cleanup_on_save_failure(self):
        """Context restored even if _save_trace fails."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock(side_effect=Exception("Save failed"))
            mock.return_value = manager

            # Should not raise despite save failure
            async with TraceContext(user_id=1) as ctx:
                ctx.status = "error"  # Force save (errors always saved)
                ctx.set_output("result")

            # Context should still be cleaned up
            assert get_current_trace() is None

    @pytest.mark.asyncio
    async def test_trace_sampling_errors_always_saved(self):
        """Error traces always saved (100%)."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext(user_id=1) as ctx:
                ctx.set_status("error")

            # Verify save was called
            manager.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_tool_traces_limit(self):
        """Exceeding MAX_TOOL_TRACES stops adding."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext(user_id=1) as ctx:
                # Add more than MAX_TOOL_TRACES
                for i in range(MAX_TOOL_TRACES + 10):
                    trace = ToolTrace.create(
                        name=f"tool_{i}",
                        input_params={},
                        output="result",
                        duration_ms=10,
                    )
                    ctx.add_tool_trace(trace)

                # Should be capped at MAX_TOOL_TRACES
                assert len(ctx.tool_traces) == MAX_TOOL_TRACES

    @pytest.mark.asyncio
    async def test_trace_context_increments_iteration(self):
        """increment_iteration increases counter."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext() as ctx:
                assert ctx.iterations == 0
                ctx.increment_iteration()
                assert ctx.iterations == 1
                ctx.increment_iteration()
                assert ctx.iterations == 2

    @pytest.mark.asyncio
    async def test_trace_context_sets_output(self):
        """set_output stores final output."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext() as ctx:
                ctx.set_output("Final answer")

            assert ctx.final_output == "Final answer"

    @pytest.mark.asyncio
    async def test_trace_context_generates_trace_id(self):
        """TraceContext generates unique trace_id."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext() as ctx1:
                pass
            async with TraceContext() as ctx2:
                pass

            assert ctx1.trace_id != ctx2.trace_id
            assert len(ctx1.trace_id) == 8

    @pytest.mark.asyncio
    async def test_trace_context_to_trace(self):
        """to_trace converts to ExecutionTrace."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext(user_id=42, skill="coding") as ctx:
                ctx.set_output("Done")
                trace = ctx.to_trace()

            assert trace.user_id == 42
            assert trace.skill == "coding"
            assert trace.trace_id == ctx.trace_id

    @pytest.mark.asyncio
    async def test_trace_context_duration_ms(self):
        """_duration_ms calculates correctly."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext() as ctx:
                await asyncio.sleep(0.1)  # 100ms

            duration = ctx._duration_ms()
            assert duration >= 100
            assert duration < 500  # Sanity check

    def test_trace_context_duration_ms_before_exit(self):
        """_duration_ms returns 0 before context exits."""
        ctx = TraceContext()
        # ended_at is None before __aexit__
        assert ctx._duration_ms() == 0


class TestGetCurrentTrace:
    """Test current trace context variable."""

    @pytest.mark.asyncio
    async def test_get_current_trace_returns_context(self):
        """get_current_trace returns active context."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext() as ctx:
                current = get_current_trace()
                assert current is ctx

    @pytest.mark.asyncio
    async def test_get_current_trace_none_outside_context(self):
        """get_current_trace returns None outside context."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.set = AsyncMock()
            mock.return_value = manager

            async with TraceContext():
                pass

            assert get_current_trace() is None


class TestGetTrace:
    """Test get_trace function."""

    @pytest.mark.asyncio
    async def test_get_trace_validates_trace_id(self):
        """Invalid trace_id returns None."""
        result = await get_trace("")
        assert result is None

        result = await get_trace("invalid!@#$")
        assert result is None

        result = await get_trace("a" * 100)  # Too long
        assert result is None

    @pytest.mark.asyncio
    async def test_get_trace_valid_format(self):
        """Valid trace_id format accepted."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.get = AsyncMock(return_value=None)
            mock.return_value = manager

            result = await get_trace("abc12345")
            # Should call get, even if result is None
            manager.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_trace_returns_trace_when_found(self):
        """get_trace returns ExecutionTrace when data exists."""
        trace_data = {
            "trace_id": "abc12345",
            "user_id": 123,
            "skill": "test",
            "started_at": "2025-12-28T12:00:00+00:00",
            "ended_at": "2025-12-28T12:01:00+00:00",
            "iterations": 2,
            "tool_traces": [],
            "final_output": "Done",
            "status": "success",
            "metadata": {},
        }

        with patch("src.core.state.get_state_manager") as mock:
            manager = AsyncMock()
            manager.get = AsyncMock(return_value=trace_data)
            mock.return_value = manager

            result = await get_trace("abc12345")

            assert result is not None
            assert result.trace_id == "abc12345"
            assert result.user_id == 123
            assert result.status == "success"


class TestListTraces:
    """Test list_traces function."""

    @pytest.mark.asyncio
    async def test_list_traces_validates_status(self):
        """Invalid status ignored."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = MagicMock()
            db_mock = MagicMock()
            query_mock = MagicMock()
            query_mock.where.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.limit.return_value = query_mock
            query_mock.get.return_value = []
            db_mock.collection.return_value = query_mock
            manager._get_db.return_value = db_mock
            mock.return_value = manager

            # Invalid status should be ignored
            await list_traces(status="invalid_status")

    @pytest.mark.asyncio
    async def test_list_traces_clamps_limit(self):
        """limit < 1 or > 100 reset to 20."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = MagicMock()
            db_mock = MagicMock()
            query_mock = MagicMock()
            query_mock.where.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.limit.return_value = query_mock
            query_mock.get.return_value = []
            db_mock.collection.return_value = query_mock
            manager._get_db.return_value = db_mock
            mock.return_value = manager

            # Limit 0 should become 20
            await list_traces(limit=0)
            query_mock.limit.assert_called_with(20)

            # Limit 200 should become 20
            query_mock.limit.reset_mock()
            await list_traces(limit=200)
            query_mock.limit.assert_called_with(20)

    @pytest.mark.asyncio
    async def test_list_traces_with_user_id_filter(self):
        """list_traces applies user_id filter."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = MagicMock()
            db_mock = MagicMock()
            query_mock = MagicMock()
            query_mock.where.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.limit.return_value = query_mock
            query_mock.get.return_value = []
            db_mock.collection.return_value = query_mock
            manager._get_db.return_value = db_mock
            mock.return_value = manager

            await list_traces(user_id=42)

            # Check where was called with user_id
            query_mock.where.assert_called_with("user_id", "==", 42)

    @pytest.mark.asyncio
    async def test_list_traces_with_valid_status_filter(self):
        """list_traces applies valid status filter."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = MagicMock()
            db_mock = MagicMock()
            query_mock = MagicMock()
            query_mock.where.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.limit.return_value = query_mock
            query_mock.get.return_value = []
            db_mock.collection.return_value = query_mock
            manager._get_db.return_value = db_mock
            mock.return_value = manager

            await list_traces(status="error")

            # Check where was called with status
            query_mock.where.assert_called_with("status", "==", "error")

    @pytest.mark.asyncio
    async def test_list_traces_handles_exception(self):
        """list_traces returns empty list on exception."""
        with patch("src.core.state.get_state_manager") as mock:
            manager = MagicMock()
            db_mock = MagicMock()
            query_mock = MagicMock()
            query_mock.where.return_value = query_mock
            query_mock.order_by.return_value = query_mock
            query_mock.limit.return_value = query_mock
            # Exception on query.get()
            query_mock.get.side_effect = Exception("Database error")
            db_mock.collection.return_value = query_mock
            manager._get_db.return_value = db_mock
            mock.return_value = manager

            result = await list_traces()

            assert result == []


class TestConstants:
    """Test module constants."""

    def test_max_tool_traces_defined(self):
        """MAX_TOOL_TRACES constant exists."""
        assert MAX_TOOL_TRACES == 100

    def test_sensitive_keys_defined(self):
        """SENSITIVE_KEYS constant contains expected keys."""
        expected = {"api_key", "token", "password", "secret", "authorization", "auth", "key"}
        assert SENSITIVE_KEYS == expected

    def test_valid_statuses_defined(self):
        """VALID_STATUSES constant contains expected values."""
        expected = {"success", "error", "timeout", "running"}
        assert VALID_STATUSES == expected
