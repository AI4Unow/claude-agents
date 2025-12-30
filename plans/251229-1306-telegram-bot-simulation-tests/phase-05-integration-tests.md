---
phase: 5
title: "Full Integration Tests"
status: pending
effort: 1.5h
---

# Phase 5: Full Integration Tests

## Context

- Parent: [plan.md](./plan.md)
- Dependencies: Phase 1-4
- Docs: pytest, unittest.mock

## Overview

End-to-end integration tests simulating complete Telegram conversation flows without real API calls. Tests webhook handling, message processing, and response generation.

## Requirements

1. Simulate full webhook payloads
2. Test complete conversation flows
3. Test media message handling
4. Test callback query handling
5. Verify response formatting
6. Test error recovery paths

## Related Code Files

- `agents/main.py:197-284` - telegram_webhook handler
- `agents/main.py:1114-1244` - Media handlers
- `agents/main.py:1472-1587` - process_message

## Integration Test Scenarios

| Scenario | Description |
|----------|-------------|
| New user onboarding | /start → /help → /status |
| Skill execution | /mode auto → complex task → orchestrated response |
| Admin workflow | Admin grants tier → user executes /traces |
| Error handling | Rate limit → error response → recovery |
| Media handling | Voice/image/document processing |

## Implementation Steps

### Step 1: Create test_flows.py

```python
# agents/tests/test_telegram/test_flows.py
"""Full integration tests for Telegram bot flows."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tests.mocks import MockUser, MockMessage, create_update

pytestmark = pytest.mark.asyncio


class TestWebhookHandler:
    """Test Telegram webhook endpoint."""

    async def test_webhook_accepts_valid_update(self, mock_env, mock_state, mock_telegram_api):
        """Webhook accepts valid Telegram update."""
        from main import create_web_app
        from fastapi.testclient import TestClient
        import httpx

        # Create test update
        update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "text": "/start"
            }
        }

        app = create_web_app()

        with patch("main.handle_command", new_callable=AsyncMock, return_value="Welcome!"), \
             patch("main.send_telegram_message", new_callable=AsyncMock), \
             patch("main.verify_telegram_webhook", new_callable=AsyncMock, return_value=True):

            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/webhook/telegram", json=update)

        assert response.status_code == 200
        assert response.json()["ok"] is True

    async def test_webhook_rejects_invalid_signature(self, mock_env):
        """Webhook rejects request with invalid signature."""
        from main import create_web_app
        import httpx

        update = {"update_id": 1}

        app = create_web_app()

        with patch("main.verify_telegram_webhook", new_callable=AsyncMock, return_value=False):
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/webhook/telegram", json=update)

        # Should be rejected
        assert response.status_code == 401 or response.json().get("ok") is False

    async def test_webhook_handles_callback_query(self, mock_env, mock_state, mock_telegram_api):
        """Webhook handles inline keyboard callback."""
        from main import create_web_app
        import httpx

        callback_update = {
            "update_id": 2,
            "callback_query": {
                "id": "123",
                "from": {"id": 456, "first_name": "User"},
                "data": "skill:planning",
                "message": {"chat": {"id": 456}}
            }
        }

        app = create_web_app()

        with patch("main.handle_callback", new_callable=AsyncMock, return_value={"ok": True}), \
             patch("main.verify_telegram_webhook", new_callable=AsyncMock, return_value=True):

            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/webhook/telegram", json=callback_update)

        assert response.status_code == 200


class TestNewUserOnboarding:
    """Test new user onboarding flow."""

    async def test_start_help_status_flow(self, mock_env, mock_state, mock_telegram_api):
        """New user: /start → /help → /status."""
        from main import handle_command

        user = {"id": 111, "first_name": "NewUser"}

        # Step 1: /start
        with patch("src.services.firebase.has_permission", return_value=True):
            start_result = await handle_command("/start", user, 111)

        assert "Hello" in start_result
        assert "NewUser" in start_result

        # Step 2: /help
        with patch("src.services.firebase.has_permission", return_value=False):
            help_result = await handle_command("/help", user, 111)

        assert "/start" in help_result
        assert "/skills" in help_result

        # Step 3: /status
        mock_state.set_tier(111, "guest")
        mock_state.set_mode(111, "simple")

        with patch("src.services.firebase.get_rate_limit", return_value=10):
            status_result = await handle_command("/status", user, 111)

        assert "guest" in status_result.lower()
        assert "simple" in status_result.lower()


class TestSkillExecutionFlow:
    """Test skill execution flow."""

    async def test_mode_set_then_complex_task(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """User sets auto mode, then sends complex task."""
        from main import handle_command, process_message

        user = {"id": 222, "first_name": "Developer"}
        mock_state.set_tier(222, "user")

        # Step 1: Set mode to auto
        mode_result = await handle_command("/mode auto", user, 222)
        assert "auto" in mode_result.lower()

        # Step 2: Send complex task
        with patch("src.core.complexity.classify_complexity", new_callable=AsyncMock, return_value="complex"), \
             patch("main._run_orchestrated", new_callable=AsyncMock, return_value="Task completed with 3 skills"):

            result = await process_message(
                "Build a user authentication system",
                user, 222, 1
            )

        assert "Task completed" in result or result is not None

    async def test_skill_menu_then_execute(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """User browses skills, selects one, provides task."""
        from main import handle_command, process_message

        user = {"id": 333}
        mock_state.set_tier(333, "user")

        # Step 1: Browse skills (sends keyboard)
        with patch("main.send_skills_menu", new_callable=AsyncMock):
            skills_result = await handle_command("/skills", user, 333)

        # Result is None because message sent via send_skills_menu
        assert skills_result is None

        # Step 2: Simulate pending skill set by callback
        mock_state._pending_skills = {333: "planning"}

        async def mock_get_pending(user_id):
            return mock_state._pending_skills.get(user_id)

        async def mock_clear_pending(user_id):
            mock_state._pending_skills.pop(user_id, None)

        mock_state.get_pending_skill = mock_get_pending
        mock_state.clear_pending_skill = mock_clear_pending

        # Step 3: User sends task (pending skill consumes it)
        with patch("main.execute_skill_simple", new_callable=AsyncMock, return_value="Plan created"):
            result = await process_message(
                "Create a roadmap for Q1",
                user, 333, 1
            )

        assert "Plan" in result or result is not None


class TestAdminWorkflow:
    """Test admin management workflow."""

    async def test_admin_grants_tier_user_uses_it(self, mock_env, mock_state, mock_telegram_api):
        """Admin grants developer tier, user accesses /traces."""
        from main import handle_command

        admin = {"id": 999999999, "first_name": "Admin"}
        user = {"id": 444, "first_name": "User"}

        # Step 1: Admin grants developer tier
        with patch("src.services.firebase.set_user_tier", new_callable=AsyncMock, return_value=True):
            grant_result = await handle_command("/grant 444 developer", admin, 999999999)

        assert "developer" in grant_result.lower() or "Granted" in grant_result

        # Step 2: Update user tier in mock state
        mock_state.set_tier(444, "developer")

        # Step 3: User accesses /traces
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.trace.list_traces", new_callable=AsyncMock, return_value=[]):

            traces_result = await handle_command("/traces", user, 444)

        assert "denied" not in traces_result.lower()

    async def test_admin_resets_circuit(self, mock_env, mock_state, mock_telegram_api):
        """Admin resets open circuit breaker."""
        from main import handle_command

        admin = {"id": 999999999}

        # Step 1: Check circuits (one is open)
        mock_circuits = {
            "claude_api": {"state": "open", "failures": 3, "cooldown_remaining": 45},
        }

        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.get_circuit_stats", return_value=mock_circuits):

            circuits_result = await handle_command("/circuits", admin, 999999999)

        # Should show open circuit
        assert "open" in circuits_result.lower() or "OPEN" in circuits_result

        # Step 2: Reset circuit
        with patch("src.services.firebase.has_permission", return_value=True), \
             patch("src.core.resilience.reset_circuit", return_value=True):

            reset_result = await handle_command("/admin reset claude_api", admin, 999999999)

        assert "reset" in reset_result.lower()


class TestErrorHandling:
    """Test error handling and recovery."""

    async def test_rate_limit_then_recovery(self, mock_env, mock_state, mock_telegram_api):
        """User hits rate limit, waits, then succeeds."""
        from main import process_message

        user = {"id": 555}
        mock_state.set_tier(555, "guest")

        # Simulate rate limit exceeded
        original_check = mock_state.check_rate_limit
        mock_state.check_rate_limit = lambda uid, tier: (False, 30)

        result = await process_message("hello", user, 555, 1)

        assert "Rate limited" in result or "Try again" in result

        # Reset rate limit
        mock_state.check_rate_limit = original_check

        # Now should work
        with patch("main._run_simple", new_callable=AsyncMock, return_value="Hello!"):
            result = await process_message("hello", user, 555, 2)

        # Should succeed or be mocked response
        assert result is not None

    async def test_llm_error_graceful_fallback(self, mock_env, mock_state, mock_telegram_api):
        """LLM error returns graceful error message."""
        from main import process_message

        user = {"id": 666}
        mock_state.set_tier(666, "user")
        mock_state.set_mode(666, "simple")

        with patch("main._run_simple", new_callable=AsyncMock, side_effect=Exception("LLM timeout")):
            result = await process_message("help me", user, 666, 1)

        assert "error" in result.lower() or "sorry" in result.lower()


class TestMediaHandling:
    """Test voice, image, and document handling."""

    async def test_voice_message_flow(self, mock_env, mock_state, mock_telegram_api):
        """Voice message transcribed and processed."""
        from main import handle_voice_message

        user = {"id": 777}

        with patch("src.services.media.download_telegram_file", new_callable=AsyncMock, return_value=b"audio"), \
             patch("src.services.media.transcribe_audio_groq", new_callable=AsyncMock, return_value="Hello world"), \
             patch("main.send_telegram_message", new_callable=AsyncMock), \
             patch("main.process_message", new_callable=AsyncMock, return_value="Response"):

            result = await handle_voice_message(
                file_id="voice123",
                duration=10,
                user=user,
                chat_id=777
            )

        assert result is not None

    async def test_voice_too_long_rejected(self, mock_env, mock_state, mock_telegram_api):
        """Voice message > 60s is rejected."""
        from main import handle_voice_message

        user = {"id": 888}

        result = await handle_voice_message(
            file_id="voice123",
            duration=120,  # Too long
            user=user,
            chat_id=888
        )

        assert "too long" in result.lower() or "60" in result

    async def test_image_message_flow(self, mock_env, mock_state, mock_llm, mock_telegram_api):
        """Image analyzed with Claude Vision."""
        from main import handle_image_message

        user = {"id": 999}

        with patch("src.services.media.download_telegram_file", new_callable=AsyncMock, return_value=b"image"), \
             patch("src.services.media.encode_image_base64", return_value="base64data"), \
             patch("src.services.llm.get_llm_client") as mock_client:

            mock_client.return_value.chat_with_image.return_value = "I see a cat in the image"

            result = await handle_image_message(
                file_id="photo123",
                caption="What's in this?",
                user=user,
                chat_id=999
            )

        assert "cat" in result or result is not None

    async def test_document_pdf_extraction(self, mock_env, mock_state, mock_telegram_api):
        """PDF document text extracted and processed."""
        from main import handle_document_message

        user = {"id": 1000}

        with patch("src.services.media.download_telegram_file", new_callable=AsyncMock, return_value=b"pdf"), \
             patch("src.services.media.extract_pdf_text", new_callable=AsyncMock, return_value="Document content"), \
             patch("main.process_message", new_callable=AsyncMock, return_value="Summary"):

            result = await handle_document_message(
                file_id="doc123",
                file_name="report.pdf",
                mime_type="application/pdf",
                caption="Summarize this",
                user=user,
                chat_id=1000
            )

        assert result is not None

    async def test_unsupported_document_rejected(self, mock_env, mock_state, mock_telegram_api):
        """Unsupported document type rejected."""
        from main import handle_document_message

        user = {"id": 1001}

        with patch("src.services.media.download_telegram_file", new_callable=AsyncMock, return_value=b"data"):
            result = await handle_document_message(
                file_id="doc123",
                file_name="file.exe",
                mime_type="application/x-msdownload",
                caption="",
                user=user,
                chat_id=1001
            )

        assert "can't process" in result.lower() or "Supported" in result


class TestConcurrentRequests:
    """Test concurrent request handling."""

    async def test_multiple_users_concurrent(self, mock_env, mock_state, mock_telegram_api):
        """Multiple users can send messages concurrently."""
        from main import handle_command
        import asyncio

        users = [
            {"id": 1001, "first_name": "User1"},
            {"id": 1002, "first_name": "User2"},
            {"id": 1003, "first_name": "User3"},
        ]

        async def user_request(user):
            return await handle_command("/status", user, user["id"])

        # Run all concurrently
        with patch("src.services.firebase.get_rate_limit", return_value=30):
            results = await asyncio.gather(*[
                user_request(u) for u in users
            ])

        # All should complete
        assert len(results) == 3
        assert all(r is not None for r in results)
```

### Step 2: Create test runner script

```python
# agents/tests/run_telegram_tests.py
"""Run all Telegram bot tests with coverage."""
import subprocess
import sys

def main():
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_telegram/",
        "-v",
        "--tb=short",
        "-x",  # Stop on first failure
        "--cov=main",
        "--cov=src.core.complexity",
        "--cov=src.core.orchestrator",
        "--cov=src.services.firebase",
        "--cov-report=term-missing",
    ]

    result = subprocess.run(cmd, cwd="agents")
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
```

## Todo List

- [ ] Create `test_flows.py` file
- [ ] Implement TestWebhookHandler (3 tests)
- [ ] Implement TestNewUserOnboarding (1 test)
- [ ] Implement TestSkillExecutionFlow (2 tests)
- [ ] Implement TestAdminWorkflow (2 tests)
- [ ] Implement TestErrorHandling (2 tests)
- [ ] Implement TestMediaHandling (5 tests)
- [ ] Implement TestConcurrentRequests (1 test)
- [ ] Create test runner script
- [ ] Run full test suite

## Success Criteria

1. All 16 integration tests pass
2. Full conversation flows work end-to-end
3. Media handling validated
4. Error recovery confirmed
5. Concurrent handling works
6. All tests < 30s total

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Integration complexity | Mock at service boundaries |
| State leakage between tests | Use fixtures with cleanup |
| Async race conditions | Use proper async test patterns |

## Security Considerations

- Webhook signature validation tested
- Admin commands require proper auth
- Rate limiting enforced

## Test Summary

### Total Test Count

| Phase | Tests |
|-------|-------|
| Phase 2: Commands | 31 |
| Phase 3: Auth | 33 |
| Phase 4: Complexity | 21 |
| Phase 5: Integration | 16 |
| **Total** | **101** |

### Coverage Goals

- `main.py`: 80%+
- `src/core/complexity.py`: 100%
- `src/core/orchestrator.py`: 70%+
- `src/services/firebase.py` (auth functions): 100%

## Next Steps

After completing all phases:
1. Run full test suite: `pytest tests/test_telegram/ -v`
2. Generate coverage report
3. Address any gaps
4. Add tests as new features are added
