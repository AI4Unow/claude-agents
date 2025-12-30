"""Unit tests for CommandRouter.

Tests command registration, routing, and permission checking.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, 'agents')

from commands.base import CommandRouter, CommandDefinition


class TestCommandRouter:
    """Tests for CommandRouter class."""

    def test_command_decorator_registers_handler(self):
        """Test that @command decorator registers handler correctly."""
        router = CommandRouter()

        @router.command(
            name="test",
            description="Test command",
            permission="guest",
            category="testing"
        )
        async def test_handler(args: str, user: dict, chat_id: int) -> str:
            return "test response"

        assert "/test" in router._commands
        cmd = router._commands["/test"]
        assert cmd.name == "/test"
        assert cmd.description == "Test command"
        assert cmd.permission_level == "guest"
        assert cmd.category == "testing"

    def test_command_with_slash_prefix(self):
        """Test command with leading slash is handled correctly."""
        router = CommandRouter()

        @router.command(name="/already-slashed", description="Has slash")
        async def handler(args, user, chat_id):
            return "ok"

        assert "/already-slashed" in router._commands

    def test_category_tracking(self):
        """Test commands are tracked by category."""
        router = CommandRouter()

        @router.command(name="cmd1", category="cat1")
        async def h1(a, u, c): return "1"

        @router.command(name="cmd2", category="cat1")
        async def h2(a, u, c): return "2"

        @router.command(name="cmd3", category="cat2")
        async def h3(a, u, c): return "3"

        assert "cat1" in router._categories
        assert "cat2" in router._categories
        assert len(router._categories["cat1"]) == 2
        assert len(router._categories["cat2"]) == 1

    @pytest.mark.asyncio
    async def test_handle_routes_to_handler(self):
        """Test handle() routes to correct handler."""
        router = CommandRouter()

        @router.command(name="greet", permission="guest")
        async def greet(args: str, user: dict, chat_id: int) -> str:
            return f"Hello {args}!"

        result = await router.handle("/greet World", {"id": 123}, 456)
        assert result == "Hello World!"

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self):
        """Test unknown command returns helpful message."""
        router = CommandRouter()

        result = await router.handle("/unknown", {"id": 123}, 456)
        assert "Unknown command" in result
        assert "/help" in result

    @pytest.mark.asyncio
    async def test_handle_similar_command_suggestion(self):
        """Test similar commands are suggested for typos."""
        router = CommandRouter()

        @router.command(name="status")
        async def status(a, u, c): return "ok"

        result = await router.handle("/sta", {"id": 123}, 456)
        assert "Did you mean" in result

    @pytest.mark.asyncio
    async def test_permission_check_guest_allows_all(self):
        """Test guest permission allows everyone."""
        router = CommandRouter()

        @router.command(name="public", permission="guest")
        async def public_cmd(a, u, c): return "public"

        result = await router.handle("/public", {"id": 999}, 123)
        assert result == "public"

    @pytest.mark.asyncio
    async def test_permission_check_admin_requires_admin_id(self):
        """Test admin permission requires ADMIN_TELEGRAM_ID match."""
        router = CommandRouter()

        @router.command(name="admin_only", permission="admin")
        async def admin_cmd(a, u, c): return "admin access"

        with patch.dict('os.environ', {'ADMIN_TELEGRAM_ID': '999999'}):
            # Non-admin user
            result = await router.handle("/admin_only", {"id": 123}, 456)
            assert "Access denied" in result

            # Admin user
            result = await router.handle("/admin_only", {"id": 999999}, 456)
            assert result == "admin access"

    @pytest.mark.asyncio
    async def test_permission_check_user_tier(self):
        """Test user/developer permission checks Firebase tier."""
        router = CommandRouter()

        @router.command(name="user_cmd", permission="user")
        async def user_cmd(a, u, c): return "user access"

        mock_state = AsyncMock()
        mock_state.get_user_tier_cached = AsyncMock(return_value="user")

        with patch("commands.base.get_state_manager", return_value=mock_state):
            result = await router.handle("/user_cmd", {"id": 123}, 456)
            assert result == "user access"

    @pytest.mark.asyncio
    async def test_permission_check_denied_for_lower_tier(self):
        """Test lower tier denied access to higher permission command."""
        router = CommandRouter()

        @router.command(name="dev_cmd", permission="developer")
        async def dev_cmd(a, u, c): return "dev access"

        mock_state = AsyncMock()
        mock_state.get_user_tier_cached = AsyncMock(return_value="guest")

        with patch("commands.base.get_state_manager", return_value=mock_state):
            result = await router.handle("/dev_cmd", {"id": 123}, 456)
            assert "Access denied" in result

    @pytest.mark.asyncio
    async def test_handle_exception_in_handler(self):
        """Test handler exception returns error message."""
        router = CommandRouter()

        @router.command(name="crash", permission="guest")
        async def crash(a, u, c):
            raise ValueError("Something broke")

        result = await router.handle("/crash", {"id": 123}, 456)
        assert "Error" in result
        assert "Something broke" in result

    def test_get_help_text_filters_by_tier(self):
        """Test help text shows only commands available to tier."""
        router = CommandRouter()

        @router.command(name="public", permission="guest", description="For all")
        async def pub(a, u, c): return "ok"

        @router.command(name="admin", permission="admin", description="Admin only")
        async def adm(a, u, c): return "ok"

        # Guest help shouldn't show admin command
        guest_help = router.get_help_text("guest")
        assert "/public" in guest_help
        assert "/admin" not in guest_help

        # Admin help shows all
        admin_help = router.get_help_text("admin")
        assert "/public" in admin_help
        assert "/admin" in admin_help

    def test_list_commands(self):
        """Test list_commands returns all definitions."""
        router = CommandRouter()

        @router.command(name="a")
        async def a(a, u, c): pass

        @router.command(name="b")
        async def b(a, u, c): pass

        commands = router.list_commands()
        assert len(commands) == 2
        assert all(isinstance(c, CommandDefinition) for c in commands)

    def test_get_command(self):
        """Test get_command returns specific command."""
        router = CommandRouter()

        @router.command(name="find_me", description="Found")
        async def find(a, u, c): pass

        cmd = router.get_command("/find_me")
        assert cmd is not None
        assert cmd.description == "Found"

        # Non-existent
        assert router.get_command("/nope") is None
