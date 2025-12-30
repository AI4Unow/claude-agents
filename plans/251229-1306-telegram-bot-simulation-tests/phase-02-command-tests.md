---
phase: 2
title: "Command Handler Tests"
status: pending
effort: 1.5h
---

# Phase 2: Command Handler Tests

## Context

- Parent: [plan.md](./plan.md)
- Dependencies: Phase 1 (Test Infrastructure)
- Docs: pytest, unittest.mock

## Overview

Test all 20+ Telegram bot commands with full coverage of success paths, error handling, and edge cases. Uses fixtures from Phase 1.

## Requirements

1. Test every command in handle_command()
2. Validate response formatting
3. Test permission enforcement
4. Cover error paths and edge cases

## Related Code Files

- `agents/main.py:649-1087` - handle_command function
- `agents/src/services/telegram.py` - Formatters

## Command Categories

| Category | Commands | Tests |
|----------|----------|-------|
| Basic | /start, /help, /status, /clear, /tier | 5 |
| Skills | /skills, /skill, /mode, /cancel | 4 |
| Quick | /translate, /summarize, /rewrite | 6 |
| Developer | /traces, /trace, /circuits | 6 |
| Admin | /admin, /grant, /revoke, /remind, /reminders | 10 |
| Task | /task | 2 |
| Unknown | Invalid commands | 1 |

## Implementation Steps

### Step 1: Create test_commands.py

```python
# agents/tests/test_telegram/test_commands.py
"""Tests for Telegram command handlers."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

# Import after mocks are set up
pytestmark = pytest.mark.asyncio


class TestBasicCommands:
    """Test basic commands available to all users."""

    async def test_start_command(self, mock_env, mock_state, guest_user):
        """Test /start returns welcome message."""
        from main import handle_command

        user_dict = {"id": guest_user.id, "first_name": guest_user.first_name}
        result = await handle_command("/start", user_dict, guest_user.id)

        assert "Hello" in result
        assert guest_user.first_name in result
        assert "II Framework" in result

    async def test_help_command_guest(self, mock_env, mock_state, guest_user):
        """Test /help shows basic commands for guest."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": guest_user.id}
            result = await handle_command("/help", user_dict, guest_user.id)

        assert "/start" in result
        assert "/help" in result
        assert "/status" in result
        # Guest doesn't see developer commands
        assert "/traces" not in result

    async def test_help_command_developer(self, mock_env, mock_state, developer_user):
        """Test /help shows developer commands."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", side_effect=lambda t, r: r in ["developer", "user", "guest"]):
            mock_state.set_tier(developer_user.id, "developer")
            user_dict = {"id": developer_user.id}
            result = await handle_command("/help", user_dict, developer_user.id)

        assert "/traces" in result
        assert "/circuits" in result

    async def test_help_command_admin(self, mock_env, mock_state, admin_user):
        """Test /help shows admin commands."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/help", user_dict, admin_user.id)

        assert "/grant" in result
        assert "/revoke" in result
        assert "/admin" in result

    async def test_status_command(self, mock_env, mock_state, regular_user):
        """Test /status shows tier and mode."""
        from main import handle_command

        mock_state.set_tier(regular_user.id, "user")
        mock_state.set_mode(regular_user.id, "simple")

        with patch("src.services.firebase.get_rate_limit", return_value=30):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/status", user_dict, regular_user.id)

        assert "user" in result.lower()
        assert "simple" in result.lower()
        assert "30" in result

    async def test_tier_command(self, mock_env, mock_state, regular_user):
        """Test /tier shows current tier."""
        from main import handle_command

        mock_state.set_tier(regular_user.id, "user")

        with patch("src.services.firebase.get_rate_limit", return_value=30):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/tier", user_dict, regular_user.id)

        assert "user" in result.lower()
        assert "30" in result

    async def test_clear_command(self, mock_env, mock_state, guest_user):
        """Test /clear clears conversation."""
        from main import handle_command

        user_dict = {"id": guest_user.id}
        result = await handle_command("/clear", user_dict, guest_user.id)

        assert "cleared" in result.lower()


class TestSkillCommands:
    """Test skill-related commands."""

    async def test_mode_command_shows_current(self, mock_env, mock_state, regular_user):
        """Test /mode without args shows current mode."""
        from main import handle_command

        mock_state.set_mode(regular_user.id, "simple")
        user_dict = {"id": regular_user.id}
        result = await handle_command("/mode", user_dict, regular_user.id)

        assert "simple" in result.lower()
        assert "simple" in result or "routed" in result or "auto" in result

    async def test_mode_command_sets_mode(self, mock_env, mock_state, regular_user):
        """Test /mode auto sets mode."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/mode auto", user_dict, regular_user.id)

        assert "auto" in result.lower()
        assert mock_state._modes.get(regular_user.id) == "auto"

    async def test_mode_command_invalid(self, mock_env, mock_state, regular_user):
        """Test /mode with invalid value shows help."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/mode invalid", user_dict, regular_user.id)

        assert "simple" in result or "routed" in result or "auto" in result

    async def test_skill_command_no_args(self, mock_env, mock_state, regular_user):
        """Test /skill without args shows usage."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/skill", user_dict, regular_user.id)

        assert "Usage:" in result

    async def test_skill_command_not_found(self, mock_env, mock_state, mock_llm, regular_user):
        """Test /skill with unknown skill."""
        from main import handle_command

        with patch("src.skills.registry.get_registry") as mock_reg:
            mock_reg.return_value.get_full.return_value = None
            mock_reg.return_value.discover.return_value = []

            user_dict = {"id": regular_user.id}
            result = await handle_command("/skill unknown-skill test task", user_dict, regular_user.id)

        assert "not found" in result.lower()

    async def test_cancel_command(self, mock_env, mock_state, regular_user):
        """Test /cancel clears pending skill."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/cancel", user_dict, regular_user.id)

        assert "cancelled" in result.lower()


class TestQuickCommands:
    """Test quick action commands."""

    async def test_translate_no_args(self, mock_env, mock_state, regular_user):
        """Test /translate without text shows usage."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/translate", user_dict, regular_user.id)

        assert "Usage:" in result

    async def test_translate_with_text(self, mock_env, mock_state, regular_user):
        """Test /translate with text."""
        from main import handle_command

        with patch("src.agents.content_generator.process_content_task", new_callable=AsyncMock) as mock_task:
            mock_task.return_value = {"translation": "Hello"}

            user_dict = {"id": regular_user.id}
            result = await handle_command("/translate Bonjour", user_dict, regular_user.id)

        mock_task.assert_called_once()

    async def test_summarize_no_args(self, mock_env, mock_state, regular_user):
        """Test /summarize without text shows usage."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/summarize", user_dict, regular_user.id)

        assert "Usage:" in result

    async def test_rewrite_no_args(self, mock_env, mock_state, regular_user):
        """Test /rewrite without text shows usage."""
        from main import handle_command

        user_dict = {"id": regular_user.id}
        result = await handle_command("/rewrite", user_dict, regular_user.id)

        assert "Usage:" in result


class TestDeveloperCommands:
    """Test developer-tier commands."""

    async def test_traces_denied_for_guest(self, mock_env, mock_state, guest_user):
        """Test /traces denied for guest."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": guest_user.id}
            result = await handle_command("/traces", user_dict, guest_user.id)

        assert "denied" in result.lower() or "developer" in result.lower()

    async def test_traces_allowed_for_developer(self, mock_env, mock_state, developer_user):
        """Test /traces allowed for developer."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.trace.list_traces", new_callable=AsyncMock, return_value=[]), \
             patch("src.services.telegram.format_traces_list", return_value="<i>No traces found.</i>"):

            user_dict = {"id": developer_user.id}
            result = await handle_command("/traces", user_dict, developer_user.id)

        assert "No traces" in result or "Recent Traces" in result

    async def test_trace_no_args(self, mock_env, mock_state, developer_user):
        """Test /trace without ID shows usage."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": developer_user.id}
            result = await handle_command("/trace", user_dict, developer_user.id)

        assert "Usage:" in result or "trace_id" in result.lower()

    async def test_circuits_command(self, mock_env, mock_state, developer_user):
        """Test /circuits shows circuit status."""
        from main import handle_command

        mock_circuits = {
            "claude_api": {"state": "closed", "failures": 0, "threshold": 3},
            "firebase": {"state": "open", "failures": 5, "threshold": 5, "cooldown_remaining": 30},
        }

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.get_circuit_stats", return_value=mock_circuits), \
             patch("src.services.telegram.format_circuits_status") as fmt:
            fmt.return_value = "<b>Circuit Breakers</b>"

            user_dict = {"id": developer_user.id}
            result = await handle_command("/circuits", user_dict, developer_user.id)

        assert "Circuit" in result


class TestAdminCommands:
    """Test admin-only commands."""

    async def test_admin_denied_for_user(self, mock_env, mock_state, regular_user):
        """Test /admin denied for regular user."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=False):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/admin", user_dict, regular_user.id)

        assert "denied" in result.lower() or "admin" in result.lower()

    async def test_admin_shows_help(self, mock_env, mock_state, admin_user):
        """Test /admin without args shows help."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/admin", user_dict, admin_user.id)

        assert "reset" in result.lower()

    async def test_admin_reset_circuit(self, mock_env, mock_state, admin_user):
        """Test /admin reset <circuit> resets circuit."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.reset_circuit", return_value=True):

            user_dict = {"id": admin_user.id}
            result = await handle_command("/admin reset claude_api", user_dict, admin_user.id)

        assert "reset" in result.lower()

    async def test_admin_reset_unknown_circuit(self, mock_env, mock_state, admin_user):
        """Test /admin reset unknown shows error."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.reset_circuit", return_value=False):

            user_dict = {"id": admin_user.id}
            result = await handle_command("/admin reset unknown", user_dict, admin_user.id)

        assert "not found" in result.lower() or "Available" in result

    async def test_grant_command(self, mock_env, mock_state, admin_user):
        """Test /grant grants tier."""
        from main import handle_command

        with patch("src.services.firebase.set_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/grant 123456 developer", user_dict, admin_user.id)

        assert "developer" in result.lower() or "Granted" in result

    async def test_grant_invalid_tier(self, mock_env, mock_state, admin_user):
        """Test /grant with invalid tier."""
        from main import handle_command

        user_dict = {"id": admin_user.id}
        result = await handle_command("/grant 123456 superadmin", user_dict, admin_user.id)

        assert "user" in result.lower() or "developer" in result.lower()

    async def test_revoke_command(self, mock_env, mock_state, admin_user):
        """Test /revoke removes tier."""
        from main import handle_command

        with patch("src.services.firebase.remove_user_tier", new_callable=AsyncMock, return_value=True):
            user_dict = {"id": admin_user.id}
            result = await handle_command("/revoke 123456", user_dict, admin_user.id)

        assert "Revoked" in result or "guest" in result.lower()


class TestTaskCommand:
    """Test /task command."""

    async def test_task_no_args(self, mock_env, mock_state, regular_user):
        """Test /task without ID shows usage."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True):
            user_dict = {"id": regular_user.id}
            result = await handle_command("/task", user_dict, regular_user.id)

        assert "Usage:" in result

    async def test_task_not_found(self, mock_env, mock_state, regular_user):
        """Test /task with unknown ID."""
        from main import handle_command

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.services.firebase.get_task", new_callable=AsyncMock, return_value=None), \
             patch("src.services.telegram.format_task_status", return_value="<i>Task not found.</i>"):

            user_dict = {"id": regular_user.id}
            result = await handle_command("/task abc123", user_dict, regular_user.id)

        assert "not found" in result.lower()


class TestUnknownCommand:
    """Test unknown command handling."""

    async def test_unknown_command(self, mock_env, mock_state, guest_user):
        """Test unknown command returns help hint."""
        from main import handle_command

        user_dict = {"id": guest_user.id}
        result = await handle_command("/unknown", user_dict, guest_user.id)

        assert "/help" in result or "Unknown" in result
```

## Todo List

- [ ] Create `test_commands.py` file
- [ ] Implement TestBasicCommands (7 tests)
- [ ] Implement TestSkillCommands (6 tests)
- [ ] Implement TestQuickCommands (4 tests)
- [ ] Implement TestDeveloperCommands (4 tests)
- [ ] Implement TestAdminCommands (7 tests)
- [ ] Implement TestTaskCommand (2 tests)
- [ ] Implement TestUnknownCommand (1 test)
- [ ] Run tests and fix any failures

## Success Criteria

1. All 31 tests pass
2. 100% command coverage
3. Permission checks validated
4. Error paths covered
5. No real API calls made

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Mock patches too broad | Use specific patch targets |
| Missing permission checks | Test both allowed and denied |
| Response format changes | Assert key content, not exact format |

## Next Steps

After completing this phase:
1. Proceed to Phase 3: Tier/Auth Tests
2. Deep dive into permission edge cases
