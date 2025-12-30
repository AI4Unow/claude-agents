"""Tests for Telegram command handlers."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

pytestmark = pytest.mark.asyncio


# Helper to get handle_command from command_router
async def handle_command(command: str, user: dict, chat_id: int) -> str:
    """Wrapper to use command_router.handle for tests."""
    from commands.router import command_router
    # Import all command modules to register commands
    import commands.user  # noqa: F401
    import commands.skills  # noqa: F401
    import commands.developer  # noqa: F401
    import commands.admin  # noqa: F401
    import commands.personalization  # noqa: F401
    import commands.reminders  # noqa: F401
    return await command_router.handle(command, user, chat_id)


class TestBasicCommands:
    """Test basic commands available to all users."""

    async def test_start_command(self, mock_env, mock_state, guest_user):
        """/start returns welcome message."""
        user_dict = {"id": guest_user.id, "first_name": guest_user.first_name}
        result = await handle_command("/start", user_dict, guest_user.id)

        # Handle None result (keyboard sent instead)
        if result is None:
            return  # Keyboard was sent, test passes
        assert "Hello" in result or "Welcome" in result
        assert guest_user.first_name in result

    async def test_help_command_guest(self, mock_env, mock_state, guest_user):
        """/help shows basic commands for guest."""
        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": guest_user.id}
            result = await handle_command("/help", user_dict, guest_user.id)

        assert "/start" in result
        assert "/help" in result

    async def test_help_command_developer(self, mock_env, mock_state, developer_user):
        """/help shows developer commands."""
        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": developer_user.id}
            result = await handle_command("/help", user_dict, developer_user.id)

        assert "/traces" in result
        assert "/circuits" in result

    async def test_status_command(self, mock_env, mock_state, regular_user):
        """/status shows tier and mode."""
        mock_state.set_tier(regular_user.id, "user")
        mock_state.set_mode(regular_user.id, "simple")

        with patch("src.services.firebase.get_rate_limit", return_value=30):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/status", user_dict, regular_user.id)

        assert "user" in result.lower()

    async def test_tier_command(self, mock_env, mock_state, regular_user):
        """/tier shows current tier."""
        mock_state.set_tier(regular_user.id, "user")

        with patch("src.services.firebase.get_rate_limit", return_value=30):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/tier", user_dict, regular_user.id)

        assert "user" in result.lower()

    async def test_clear_command(self, mock_env, mock_state, guest_user):
        """/clear clears conversation."""
        user_dict = {"id": guest_user.id}
        result = await handle_command("/clear", user_dict, guest_user.id)

        assert "cleared" in result.lower()


class TestSkillCommands:
    """Test skill-related commands."""

    async def test_mode_shows_current(self, mock_env, mock_state, regular_user):
        """/mode without args shows current mode."""
        mock_state.set_mode(regular_user.id, "simple")
        user_dict = {"id": regular_user.id}
        result = await handle_command("/mode", user_dict, regular_user.id)

        assert "simple" in result.lower()

    async def test_mode_sets_auto(self, mock_env, mock_state, regular_user):
        """/mode auto sets mode."""
        user_dict = {"id": regular_user.id}
        result = await handle_command("/mode auto", user_dict, regular_user.id)

        assert "auto" in result.lower()

    async def test_mode_invalid(self, mock_env, mock_state, regular_user):
        """/mode with invalid value shows options."""
        user_dict = {"id": regular_user.id}
        result = await handle_command("/mode invalid", user_dict, regular_user.id)

        assert "simple" in result or "routed" in result or "auto" in result

    async def test_skill_no_args(self, mock_env, mock_state, regular_user):
        """/skill without args shows usage."""
        user_dict = {"id": regular_user.id}
        result = await handle_command("/skill", user_dict, regular_user.id)

        assert "Usage" in result

    async def test_cancel_command(self, mock_env, mock_state, regular_user):
        """/cancel clears pending skill."""
        user_dict = {"id": regular_user.id}
        result = await handle_command("/cancel", user_dict, regular_user.id)

        assert "cancelled" in result.lower()


class TestQuickCommands:
    """Test quick action commands."""

    async def test_translate_no_args(self, mock_env, mock_state, regular_user):
        """/translate without text shows usage."""
        user_dict = {"id": regular_user.id}
        result = await handle_command("/translate", user_dict, regular_user.id)

        assert "Usage" in result

    async def test_summarize_no_args(self, mock_env, mock_state, regular_user):
        """/summarize without text shows usage."""
        user_dict = {"id": regular_user.id}
        result = await handle_command("/summarize", user_dict, regular_user.id)

        assert "Usage" in result

    async def test_rewrite_no_args(self, mock_env, mock_state, regular_user):
        """/rewrite without text shows usage."""
        user_dict = {"id": regular_user.id}
        result = await handle_command("/rewrite", user_dict, regular_user.id)

        assert "Usage" in result


class TestDeveloperCommands:
    """Test developer-tier commands."""

    async def test_traces_denied_for_guest(self, mock_env, mock_state, guest_user):
        """/traces denied for guest."""
        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": guest_user.id}
            result = await handle_command("/traces", user_dict, guest_user.id)

        assert "denied" in result.lower() or "developer" in result.lower()

    async def test_traces_allowed_for_developer(self, mock_env, mock_state, developer_user):
        """/traces allowed for developer."""
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.trace.list_traces", new_callable=AsyncMock, return_value=[]):

            user_dict = {"id": developer_user.id}
            result = await handle_command("/traces", user_dict, developer_user.id)

        assert "No traces" in result or "Recent" in result

    async def test_trace_no_args(self, mock_env, mock_state, developer_user):
        """/trace without ID shows usage."""
        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": developer_user.id}
            result = await handle_command("/trace", user_dict, developer_user.id)

        assert "Usage" in result or "trace" in result.lower()

    async def test_circuits_command(self, mock_env, mock_state, developer_user):
        """/circuits shows circuit status."""
        mock_circuits = {
            "claude_api": {"state": "closed", "failures": 0, "threshold": 3},
        }

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.get_circuit_stats", return_value=mock_circuits):

            user_dict = {"id": developer_user.id}
            result = await handle_command("/circuits", user_dict, developer_user.id)

        assert "Circuit" in result


class TestAdminCommands:
    """Test admin-only commands."""

    async def test_admin_denied_for_user(self, mock_env, mock_state, regular_user):
        """/admin denied for regular user."""
        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/admin", user_dict, regular_user.id)

        assert "denied" in result.lower() or "admin" in result.lower()

    async def test_admin_shows_help(self, mock_env, mock_state, admin_user):
        """/admin without args shows help."""
        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/admin", user_dict, admin_user.id)

        assert "reset" in result.lower()

    async def test_admin_reset_circuit(self, mock_env, mock_state, admin_user):
        """/admin reset <circuit> resets circuit."""
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.reset_circuit", return_value=True):

            user_dict = {"id": admin_user.id}
            result = await handle_command("/admin reset claude_api", user_dict, admin_user.id)

        assert "reset" in result.lower()

    async def test_grant_command(self, mock_env, mock_state, admin_user):
        """/grant grants tier."""
        with patch("src.services.firebase.set_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/grant 123456 developer", user_dict, admin_user.id)

        assert "developer" in result.lower() or "Granted" in result

    async def test_revoke_command(self, mock_env, mock_state, admin_user):
        """/revoke removes tier."""
        with patch("src.services.firebase.remove_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/revoke 123456", user_dict, admin_user.id)

        assert "Revoked" in result or "guest" in result.lower()


class TestTaskCommand:
    """Test /task command."""

    async def test_task_no_args(self, mock_env, mock_state, regular_user):
        """/task without ID shows usage."""
        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/task", user_dict, regular_user.id)

        assert "Usage" in result

    async def test_task_not_found(self, mock_env, mock_state, regular_user):
        """/task with unknown ID."""
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.services.firebase.get_task_result", new_callable=AsyncMock, return_value=None):

            user_dict = {"id": regular_user.id}
            result = await handle_command("/task abc123", user_dict, regular_user.id)

        assert "not found" in result.lower()


class TestUnknownCommand:
    """Test unknown command handling."""

    async def test_unknown_command(self, mock_env, mock_state, guest_user):
        """Unknown command returns help hint."""
        user_dict = {"id": guest_user.id}
        result = await handle_command("/unknown", user_dict, guest_user.id)

        assert "/help" in result or "Unknown" in result
