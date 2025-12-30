"""Unit tests for user commands.

Tests /start, /help, /status, /tier, /clear, /cancel commands.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, 'agents')


class TestStartCommand:
    """Tests for /start command."""

    @pytest.mark.asyncio
    async def test_start_returns_welcome_with_name(self):
        """Test /start includes user's first name."""
        from commands.user import start_command

        user = {"id": 123, "first_name": "Alice"}
        result = await start_command("", user, 456)

        assert "Hello Alice" in result
        assert "AI4U.now Bot" in result
        assert "/help" in result
        assert "/skills" in result

    @pytest.mark.asyncio
    async def test_start_fallback_name(self):
        """Test /start uses 'there' when no first_name."""
        from commands.user import start_command

        user = {"id": 123}
        result = await start_command("", user, 456)

        assert "Hello there" in result


class TestHelpCommand:
    """Tests for /help command."""

    @pytest.mark.asyncio
    async def test_help_returns_command_list(self):
        """Test /help returns available commands."""
        from commands.user import help_command

        mock_state = AsyncMock()
        mock_state.get_user_tier_cached = AsyncMock(return_value="user")

        with patch("commands.user.get_state_manager", return_value=mock_state):
            result = await help_command("", {"id": 123}, 456)

        assert "Available Commands" in result or "Commands" in result

    @pytest.mark.asyncio
    async def test_help_filters_by_tier(self):
        """Test /help filters commands based on user tier."""
        from commands.user import help_command
        from commands.router import command_router

        mock_state = AsyncMock()

        # Guest tier
        mock_state.get_user_tier_cached = AsyncMock(return_value="guest")
        with patch("commands.user.get_state_manager", return_value=mock_state):
            guest_help = await help_command("", {"id": 123}, 456)

        # Admin tier
        mock_state.get_user_tier_cached = AsyncMock(return_value="admin")
        with patch("commands.user.get_state_manager", return_value=mock_state):
            admin_help = await help_command("", {"id": 123}, 456)

        # Admin help should be longer (more commands visible)
        assert len(admin_help) >= len(guest_help)


class TestStatusCommand:
    """Tests for /status command."""

    @pytest.mark.asyncio
    async def test_status_shows_tier_and_mode(self):
        """Test /status shows user's tier and mode."""
        from commands.user import status_command

        mock_state = AsyncMock()
        mock_state.get_user_tier_cached = AsyncMock(return_value="developer")
        mock_state.get_user_mode = AsyncMock(return_value="routed")

        with patch("commands.user.get_state_manager", return_value=mock_state):
            with patch("commands.user.get_circuit_status", return_value={"claude": "closed"}):
                result = await status_command("", {"id": 123, "first_name": "Bob"}, 456)

        assert "developer" in result
        assert "routed" in result
        assert "Bob" in result
        assert "claude" in result

    @pytest.mark.asyncio
    async def test_status_shows_circuits(self):
        """Test /status includes circuit breaker status."""
        from commands.user import status_command

        mock_state = AsyncMock()
        mock_state.get_user_tier_cached = AsyncMock(return_value="user")
        mock_state.get_user_mode = AsyncMock(return_value="auto")

        circuits = {"claude": "closed", "firebase": "half_open", "telegram": "closed"}

        with patch("commands.user.get_state_manager", return_value=mock_state):
            with patch("commands.user.get_circuit_status", return_value=circuits):
                result = await status_command("", {"id": 123, "first_name": "Test"}, 456)

        assert "claude" in result
        assert "firebase" in result


class TestTierCommand:
    """Tests for /tier command."""

    @pytest.mark.asyncio
    async def test_tier_shows_user_tier(self):
        """Test /tier displays current tier."""
        from commands.user import tier_command

        mock_state = AsyncMock()
        mock_state.get_user_tier_cached = AsyncMock(return_value="developer")

        with patch("commands.user.get_state_manager", return_value=mock_state):
            with patch("commands.user.get_rate_limit", return_value=100):
                result = await tier_command("", {"id": 123}, 456)

        assert "developer" in result
        assert "100" in result
        assert "Full access" in result

    @pytest.mark.asyncio
    async def test_tier_shows_rate_limit(self):
        """Test /tier shows rate limit for tier."""
        from commands.user import tier_command

        mock_state = AsyncMock()
        mock_state.get_user_tier_cached = AsyncMock(return_value="guest")

        with patch("commands.user.get_state_manager", return_value=mock_state):
            with patch("commands.user.get_rate_limit", return_value=10):
                result = await tier_command("", {"id": 123}, 456)

        assert "10" in result
        assert "requests/min" in result


class TestClearCommand:
    """Tests for /clear command."""

    @pytest.mark.asyncio
    async def test_clear_clears_conversation(self):
        """Test /clear calls clear_conversation."""
        from commands.user import clear_command

        mock_state = AsyncMock()
        mock_state.clear_conversation = AsyncMock()

        with patch("commands.user.get_state_manager", return_value=mock_state):
            result = await clear_command("", {"id": 123}, 456)

        mock_state.clear_conversation.assert_called_once_with(123)
        assert "cleared" in result.lower()


class TestCancelCommand:
    """Tests for /cancel command."""

    @pytest.mark.asyncio
    async def test_cancel_clears_pending_skill(self):
        """Test /cancel calls clear_pending_skill."""
        from commands.user import cancel_command

        mock_state = AsyncMock()
        mock_state.clear_pending_skill = AsyncMock()

        with patch("commands.user.get_state_manager", return_value=mock_state):
            result = await cancel_command("", {"id": 123}, 456)

        mock_state.clear_pending_skill.assert_called_once_with(123)
        assert "cancelled" in result.lower()
