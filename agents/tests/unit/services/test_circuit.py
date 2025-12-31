"""Unit tests for Firebase circuit breaker decorator.

Tests circuit state handling and error recording.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import sys
sys.path.insert(0, 'agents')

from src.core.resilience import CircuitState


class TestWithFirebaseCircuit:
    """Tests for with_firebase_circuit decorator."""

    @pytest.mark.asyncio
    async def test_circuit_closed_executes_function(self):
        """When circuit closed, execute function normally."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.CLOSED
        mock_circuit._record_success = MagicMock()

        @with_firebase_circuit(open_return=None)
        async def test_func():
            return "success"

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            result = await test_func()

        assert result == "success"
        mock_circuit._record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_open_returns_default(self):
        """When circuit open, return open_return value."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.OPEN

        @with_firebase_circuit(open_return=[])
        async def test_func():
            return "success"

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            result = await test_func()

        assert result == []

    @pytest.mark.asyncio
    async def test_circuit_open_returns_none(self):
        """When circuit open with open_return=None, return None."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.OPEN

        @with_firebase_circuit(open_return=None)
        async def get_user():
            return {"name": "Test"}

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            result = await get_user()

        assert result is None

    @pytest.mark.asyncio
    async def test_circuit_open_returns_false(self):
        """When circuit open with open_return=False, return False."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.OPEN

        @with_firebase_circuit(open_return=False)
        async def check_exists():
            return True

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            result = await check_exists()

        assert result is False

    @pytest.mark.asyncio
    async def test_circuit_open_raises_when_configured(self):
        """When circuit open with raise_on_open=True, raise error."""
        from src.services.firebase._circuit import with_firebase_circuit
        from src.core.resilience import CircuitOpenError

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.OPEN
        mock_circuit._cooldown_remaining = MagicMock(return_value=30)

        @with_firebase_circuit(raise_on_open=True)
        async def must_execute():
            return "success"

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            with pytest.raises(CircuitOpenError):
                await must_execute()

    @pytest.mark.asyncio
    async def test_function_error_records_failure(self):
        """Function exceptions are recorded as failures."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.CLOSED
        mock_circuit._record_failure = MagicMock()

        @with_firebase_circuit(open_return=None)
        async def failing_func():
            raise ValueError("Database error")

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            with pytest.raises(ValueError):
                await failing_func()

        mock_circuit._record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_operation_name(self):
        """Custom operation name is used in logging."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.OPEN

        mock_logger = MagicMock()

        @with_firebase_circuit(operation="custom_op", open_return=None)
        async def generic_func():
            return "ok"

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            with patch("src.services.firebase._circuit.logger", mock_logger):
                await generic_func()

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[1]["operation"] == "custom_op"

    @pytest.mark.asyncio
    async def test_auto_operation_name_from_function(self):
        """Operation name defaults to function name."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.OPEN

        mock_logger = MagicMock()

        @with_firebase_circuit(open_return=None)
        async def get_user_by_id():
            return {"id": 1}

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            with patch("src.services.firebase._circuit.logger", mock_logger):
                await get_user_by_id()

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[1]["operation"] == "get_user_by_id"

    @pytest.mark.asyncio
    async def test_half_open_allows_execution(self):
        """HALF_OPEN state allows execution (not OPEN)."""
        from src.services.firebase._circuit import with_firebase_circuit

        mock_circuit = MagicMock()
        mock_circuit.state = CircuitState.HALF_OPEN
        mock_circuit._record_success = MagicMock()

        @with_firebase_circuit(open_return=None)
        async def probe_func():
            return "probing"

        with patch("src.services.firebase._circuit.firebase_circuit", mock_circuit):
            result = await probe_func()

        assert result == "probing"
        mock_circuit._record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """Decorator preserves function name and docstring."""
        from src.services.firebase._circuit import with_firebase_circuit

        @with_firebase_circuit(open_return=None)
        async def documented_function():
            """This is the docstring."""
            return "ok"

        assert documented_function.__name__ == "documented_function"
        assert "docstring" in documented_function.__doc__
