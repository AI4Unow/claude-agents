"""Full integration tests for Telegram bot flows."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

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


class TestNewUserOnboarding:
    """Test new user onboarding flow."""

    async def test_start_help_status_flow(self, mock_env, mock_state, mock_telegram_api):
        """New user: /start → /help → /status."""
        user = {"id": 111, "first_name": "NewUser"}

        # Step 1: /start (may return None if keyboard sent)
        start_result = await handle_command("/start", user, 111)
        if start_result is not None:
            assert "Hello" in start_result or "Welcome" in start_result
            assert "NewUser" in start_result

        # Step 2: /help
        with patch("src.services.firebase.has_permission", return_value=False):
            help_result = await handle_command("/help", user, 111)
        assert "/start" in help_result
        assert "/skills" in help_result or "/help" in help_result

        # Step 3: /status
        mock_state.set_tier(111, "guest")
        mock_state.set_mode(111, "simple")
        with patch("src.services.firebase.get_rate_limit", return_value=10):
            status_result = await handle_command("/status", user, 111)
        assert "guest" in status_result.lower()


class TestSkillExecutionFlow:
    """Test skill execution flow."""

    async def test_mode_set_then_complex(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """User sets auto mode, sends complex task."""
        from main import process_message

        user = {"id": 222, "first_name": "Developer"}
        mock_state.set_tier(222, "user")

        # Step 1: Set mode
        mode_result = await handle_command("/mode auto", user, 222)
        assert "auto" in mode_result.lower()

        # Step 2: Complex task
        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock, return_value="complex"), \
             patch("main._run_orchestrated", new_callable=AsyncMock, return_value="Task done"):

            result = await process_message("Build auth system", user, 222, 1)

        assert result is not None


class TestAdminWorkflow:
    """Test admin management workflow."""

    async def test_admin_grants_tier(self, mock_env, mock_state, mock_telegram_api):
        """Admin grants tier, user accesses /traces."""
        admin = {"id": 999999999, "first_name": "Admin"}
        user = {"id": 444, "first_name": "User"}

        # Step 1: Grant tier
        with patch("src.services.firebase.set_user_tier", new_callable=AsyncMock, return_value=True):
            grant_result = await handle_command("/grant 444 developer", admin, 999999999)
        assert "developer" in grant_result.lower() or "Granted" in grant_result

        # Step 2: User accesses /traces
        mock_state.set_tier(444, "developer")
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.trace.list_traces", new_callable=AsyncMock, return_value=[]):

            traces_result = await handle_command("/traces", user, 444)
        assert "denied" not in traces_result.lower()

    async def test_admin_resets_circuit(self, mock_env, mock_state, mock_telegram_api):
        """Admin resets open circuit."""
        admin = {"id": 999999999}
        mock_state.set_tier(999999999, "admin")

        # Check circuits
        mock_circuits = {"claude_api": {"state": "open", "failures": 3, "cooldown_remaining": 45}}
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.get_circuit_stats", return_value=mock_circuits):

            circuits_result = await handle_command("/circuits", admin, 999999999)
        assert "open" in circuits_result.lower() or "OPEN" in circuits_result

        # Reset circuit
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.reset_circuit", return_value=True):

            reset_result = await handle_command("/admin reset claude_api", admin, 999999999)
        assert "reset" in reset_result.lower()


class TestErrorHandling:
    """Test error handling and recovery."""

    async def test_rate_limit_then_recovery(self, mock_env, mock_state, mock_telegram_api):
        """User hits rate limit, recovers."""
        from main import process_message

        user = {"id": 555}
        mock_state.set_tier(555, "guest")

        # Simulate rate limit
        original = mock_state.check_rate_limit
        mock_state.check_rate_limit = lambda uid, tier: (False, 30)

        result = await process_message("hello", user, 555, 1)
        assert "Rate limited" in result or "Try again" in result

        # Recover
        mock_state.check_rate_limit = original
        with patch("main._run_simple", new_callable=AsyncMock, return_value="Hello!"):
            result = await process_message("hello", user, 555, 2)
        assert result is not None

    async def test_llm_error_fallback(self, mock_env, mock_state, mock_telegram_api):
        """LLM error returns graceful message."""
        from main import process_message

        user = {"id": 666}
        mock_state.set_tier(666, "user")
        mock_state.set_mode(666, "simple")

        with patch("main._run_simple", new_callable=AsyncMock, side_effect=Exception("LLM timeout")):
            result = await process_message("help", user, 666, 1)

        assert "error" in result.lower() or "sorry" in result.lower() or "try again" in result.lower()


class TestMediaHandling:
    """Test voice, image, document handling."""

    async def test_voice_message(self, mock_env, mock_state, mock_telegram_api):
        """Voice transcribed and processed."""
        from main import handle_voice_message

        user = {"id": 777}

        with patch("src.services.media.download_telegram_file", new_callable=AsyncMock, return_value=b"audio"), \
             patch("src.services.media.transcribe_audio_groq", new_callable=AsyncMock, return_value="Hello"), \
             patch("main.send_telegram_message", new_callable=AsyncMock), \
             patch("main.process_message", new_callable=AsyncMock, return_value="Response"):

            result = await handle_voice_message("voice123", 10, user, 777)

        assert result is not None

    async def test_voice_too_long(self, mock_env, mock_state, mock_telegram_api):
        """Voice > 60s rejected."""
        from main import handle_voice_message

        user = {"id": 888}
        result = await handle_voice_message("voice123", 120, user, 888)

        assert "too long" in result.lower() or "60" in result

    async def test_image_message(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Image analyzed with vision."""
        from main import handle_image_message

        user = {"id": 999}

        with patch("src.services.media.download_telegram_file", new_callable=AsyncMock, return_value=b"img"), \
             patch("src.services.media.encode_image_base64", return_value="base64"), \
             patch("src.services.llm.get_llm_client") as mock_client:

            mock_client.return_value.chat_with_image.return_value = "A cat"
            result = await handle_image_message("photo123", "What's this?", user, 999)

        assert result is not None

    async def test_unsupported_document(self, mock_env, mock_state, mock_telegram_api):
        """Unsupported document rejected."""
        from main import handle_document_message

        user = {"id": 1001}

        with patch("src.services.media.download_telegram_file", new_callable=AsyncMock, return_value=b"data"):
            result = await handle_document_message("doc123", "file.exe", "application/x-msdownload", "", user, 1001)

        assert "can't process" in result.lower() or "Supported" in result


class TestConcurrentRequests:
    """Test concurrent request handling."""

    async def test_multiple_users(self, mock_env, mock_state, mock_telegram_api):
        """Multiple users can send concurrently."""
        users = [
            {"id": 1001, "first_name": "User1"},
            {"id": 1002, "first_name": "User2"},
            {"id": 1003, "first_name": "User3"},
        ]

        async def request(u):
            return await handle_command("/status", u, u["id"])

        with patch("src.services.firebase.get_rate_limit", return_value=30):
            results = await asyncio.gather(*[request(u) for u in users])

        assert len(results) == 3
        assert all(r is not None for r in results)
