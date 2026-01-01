# Phase 3: Telegram E2E Tests

## Context Links

- Main plan: [plan.md](./plan.md)
- Brainstorm: `plans/reports/brainstorm-260101-0714-telegram-ux-testing.md`
- Bot commands: `agents/commands/`

## Overview

Implement end-to-end tests using Telethon to simulate real user interactions with the Telegram bot. Tests cover onboarding flows, command execution, skill invocation, media handling, and error recovery.

## Key Insights

1. **Telethon vs Bot API** - Telethon acts as a user client, not bot, for realistic E2E testing
2. **Session persistence** - Session file avoids repeated phone auth
3. **Response waiting** - Need utility to wait for bot responses with timeout
4. **Production bot** - Test against real deployed bot for true E2E

## Requirements

### Functional
- Test complete onboarding flow (/start -> /help -> /status)
- Test all major commands (/skills, /mode, /translate, etc.)
- Test skill execution (web search, translate, summarize)
- Test media handling (voice, image)
- Test error recovery (rate limits, timeouts)

### Non-Functional
- Session file for persistent auth
- Configurable timeouts per test
- Skip in CI by default (`pytest -m "not e2e"`)
- Parallel test execution where possible

## Architecture

```
tests/e2e/
+-- conftest.py           # Telethon client fixtures
+-- test_onboarding.py    # New user flow
+-- test_commands.py      # Command responses
+-- test_skills.py        # Skill execution
+-- test_media.py         # Voice, image handling
+-- test_error_recovery.py # Edge cases
```

### Telethon Session Flow

```
1. First run: Phone auth -> Session file created
2. Subsequent: Session file loaded -> No auth needed

Session file: tests/e2e/test_session.session
```

## Related Code Files

| File | Purpose |
|------|---------|
| `commands/user.py` | /start, /help, /status |
| `commands/skills.py` | /skills, /skill, /use |
| `commands/developer.py` | /traces, /circuits |
| `src/services/telegram.py` | Telegram utilities |

## Implementation Steps

### Step 1: Create tests/e2e/conftest.py

```python
"""Telegram E2E test configuration using Telethon."""
import os
import asyncio
import pytest
from pathlib import Path

# Session file location
SESSION_DIR = Path(__file__).parent
SESSION_NAME = "test_session"


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: mark test as E2E (requires Telegram)")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def e2e_env():
    """Validate E2E environment variables."""
    required = [
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "TELEGRAM_PHONE",
        "TELEGRAM_BOT_USERNAME",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        pytest.skip(f"Missing env vars for E2E: {missing}")
    return {
        "api_id": int(os.environ["TELEGRAM_API_ID"]),
        "api_hash": os.environ["TELEGRAM_API_HASH"],
        "phone": os.environ["TELEGRAM_PHONE"],
        "bot_username": os.environ["TELEGRAM_BOT_USERNAME"],
    }


@pytest.fixture(scope="session")
async def telegram_client(e2e_env, event_loop):
    """Create and connect Telethon client."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    # Use file session for persistence
    session_file = SESSION_DIR / f"{SESSION_NAME}.session"

    client = TelegramClient(
        str(session_file),
        e2e_env["api_id"],
        e2e_env["api_hash"]
    )

    await client.start(phone=e2e_env["phone"])
    yield client
    await client.disconnect()


@pytest.fixture
def bot_username(e2e_env):
    """Get bot username for testing."""
    return e2e_env["bot_username"]


async def wait_for_response(
    client,
    bot_username: str,
    timeout: float = 30.0,
    min_length: int = 0
):
    """Wait for bot response message.

    Args:
        client: Telethon client
        bot_username: Bot to receive from
        timeout: Max seconds to wait
        min_length: Minimum response length

    Returns:
        Message object or None if timeout
    """
    from telethon import events
    import time

    start = time.time()
    last_message = None

    while time.time() - start < timeout:
        # Get recent messages from bot
        messages = await client.get_messages(bot_username, limit=5)
        for msg in messages:
            if msg.out:  # Skip our own messages
                continue
            if msg.date.timestamp() > start - 5:  # Recent message
                if len(msg.text or "") >= min_length:
                    return msg
                last_message = msg

        await asyncio.sleep(0.5)

    return last_message


async def send_and_wait(
    client,
    bot_username: str,
    text: str,
    timeout: float = 30.0
):
    """Send message and wait for response.

    Args:
        client: Telethon client
        bot_username: Bot to message
        text: Message to send
        timeout: Max seconds to wait

    Returns:
        Response message or None
    """
    import time

    # Record time before sending
    before_send = time.time()

    # Send message
    await client.send_message(bot_username, text)

    # Wait for response newer than our message
    start = time.time()
    while time.time() - start < timeout:
        messages = await client.get_messages(bot_username, limit=3)
        for msg in messages:
            if msg.out:
                continue
            # Response must be after we sent
            if msg.date.timestamp() > before_send:
                return msg

        await asyncio.sleep(0.5)

    return None
```

### Step 2: Create tests/e2e/test_onboarding.py

```python
"""E2E tests for new user onboarding flow."""
import pytest
from conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_start_command(telegram_client, bot_username):
    """Test /start returns welcome message."""
    response = await send_and_wait(telegram_client, bot_username, "/start")

    assert response is not None, "No response to /start"
    text = response.text.lower()
    assert any(word in text for word in ["hello", "welcome", "hi"]), \
        f"Unexpected /start response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_help_command(telegram_client, bot_username):
    """Test /help shows available commands."""
    response = await send_and_wait(telegram_client, bot_username, "/help")

    assert response is not None, "No response to /help"
    text = response.text

    # Should contain command references
    assert "/start" in text, "Missing /start in help"
    assert "/help" in text or "help" in text.lower(), "Missing help reference"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_status_command(telegram_client, bot_username):
    """Test /status shows agent status."""
    response = await send_and_wait(telegram_client, bot_username, "/status")

    assert response is not None, "No response to /status"
    text = response.text.lower()

    # Should indicate some status
    assert any(word in text for word in ["status", "running", "online", "tier"]), \
        f"Unexpected /status response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_onboarding_flow(telegram_client, bot_username):
    """Test complete onboarding: /start -> /help -> /status."""
    # Step 1: Start
    start_resp = await send_and_wait(telegram_client, bot_username, "/start", timeout=15)
    assert start_resp is not None, "No /start response"

    # Small delay between commands
    import asyncio
    await asyncio.sleep(1)

    # Step 2: Help
    help_resp = await send_and_wait(telegram_client, bot_username, "/help", timeout=15)
    assert help_resp is not None, "No /help response"

    await asyncio.sleep(1)

    # Step 3: Status
    status_resp = await send_and_wait(telegram_client, bot_username, "/status", timeout=15)
    assert status_resp is not None, "No /status response"

    # All three should have meaningful content
    assert len(start_resp.text) > 20, "Start response too short"
    assert len(help_resp.text) > 50, "Help response too short"
    assert len(status_resp.text) > 20, "Status response too short"
```

### Step 3: Create tests/e2e/test_commands.py

```python
"""E2E tests for all major commands."""
import pytest
from conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skills_command(telegram_client, bot_username):
    """Test /skills shows skill list."""
    response = await send_and_wait(telegram_client, bot_username, "/skills", timeout=20)

    assert response is not None, "No response to /skills"

    # May have inline keyboard or text list
    text = response.text.lower() if response.text else ""
    has_keyboard = response.buttons is not None

    assert has_keyboard or "skill" in text, \
        "Expected skill list or inline keyboard"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_tier_command(telegram_client, bot_username):
    """Test /tier shows user tier."""
    response = await send_and_wait(telegram_client, bot_username, "/tier")

    assert response is not None, "No response to /tier"
    text = response.text.lower()

    # Should mention tier level
    assert any(tier in text for tier in ["guest", "user", "developer", "admin", "tier"]), \
        f"No tier info in response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mode_command(telegram_client, bot_username):
    """Test /mode shows or sets execution mode."""
    response = await send_and_wait(telegram_client, bot_username, "/mode")

    assert response is not None, "No response to /mode"
    text = response.text.lower()

    # Should mention mode options
    assert any(mode in text for mode in ["simple", "routed", "auto", "mode"]), \
        f"No mode info in response: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_translate_command(telegram_client, bot_username):
    """Test /translate works."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/translate Bonjour le monde",
        timeout=30
    )

    assert response is not None, "No response to /translate"

    # Should contain English translation
    text = response.text.lower()
    assert any(word in text for word in ["hello", "world", "greet"]), \
        f"Translation not recognized: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_summarize_command(telegram_client, bot_username):
    """Test /summarize works."""
    long_text = (
        "This is a test paragraph that contains multiple sentences. "
        "It discusses various topics including testing, automation, and bots. "
        "The purpose is to verify that the summarization feature works correctly. "
        "We expect a shorter version of this text."
    )

    response = await send_and_wait(
        telegram_client,
        bot_username,
        f"/summarize {long_text}",
        timeout=30
    )

    assert response is not None, "No response to /summarize"
    assert len(response.text) > 20, "Summary too short"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_clear_command(telegram_client, bot_username):
    """Test /clear resets conversation."""
    response = await send_and_wait(telegram_client, bot_username, "/clear")

    assert response is not None, "No response to /clear"
    text = response.text.lower()

    assert any(word in text for word in ["clear", "reset", "conversation"]), \
        f"Clear confirmation not found: {text[:100]}"
```

### Step 4: Create tests/e2e/test_skills.py

```python
"""E2E tests for skill execution."""
import pytest
from conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_web_search_skill(telegram_client, bot_username):
    """Test web search returns results."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill web-search What is Python programming?",
        timeout=60  # Skills take longer
    )

    assert response is not None, "No response to skill"
    text = response.text.lower()

    assert len(text) > 100, "Response too short for search"
    assert "python" in text, "No relevant content"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_not_found(telegram_client, bot_username):
    """Test non-existent skill handling."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill nonexistent-skill-xyz Do something",
        timeout=20
    )

    assert response is not None, "No response"
    text = response.text.lower()

    # Should indicate skill not found
    assert any(word in text for word in ["not found", "unknown", "error", "doesn't exist"]), \
        f"Expected not found message: {text[:100]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_use_command(telegram_client, bot_username):
    """Test /use skill shorthand."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/use translate Hola mundo",
        timeout=30
    )

    # May succeed or show usage - either is valid
    assert response is not None, "No response to /use"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_skill_execution_progress(telegram_client, bot_username):
    """Test that long-running skills show progress."""
    # This test is more observational - we just verify response arrives
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/skill research Brief summary of AI trends",
        timeout=120  # Research takes time
    )

    # Response should eventually arrive
    if response:
        assert len(response.text) > 50, "Research output too short"
```

### Step 5: Create tests/e2e/test_media.py

```python
"""E2E tests for media handling (voice, images)."""
import pytest
import base64
from conftest import wait_for_response


# Minimal valid PNG (1x1 transparent pixel)
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_image_upload(telegram_client, bot_username):
    """Test image upload and analysis."""
    import io

    # Create minimal image
    image_data = base64.b64decode(TINY_PNG_B64)

    # Send image with caption
    await telegram_client.send_file(
        bot_username,
        io.BytesIO(image_data),
        caption="What is in this image?",
        file_name="test.png"
    )

    # Wait for response
    response = await wait_for_response(telegram_client, bot_username, timeout=30)

    # Bot should respond (may be vision analysis or acknowledgment)
    assert response is not None, "No response to image"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_document_upload(telegram_client, bot_username):
    """Test document upload handling."""
    import io

    # Create simple text file
    text_content = b"This is a test document for the bot."

    await telegram_client.send_file(
        bot_username,
        io.BytesIO(text_content),
        caption="Summarize this document",
        file_name="test.txt"
    )

    response = await wait_for_response(telegram_client, bot_username, timeout=30)

    # Should acknowledge or process
    assert response is not None, "No response to document"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Voice requires audio file - skip for now")
async def test_voice_message(telegram_client, bot_username):
    """Test voice message handling."""
    # Would need actual audio file
    pass
```

### Step 6: Create tests/e2e/test_error_recovery.py

```python
"""E2E tests for error handling and recovery."""
import pytest
import asyncio
from conftest import send_and_wait


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_empty_command_handling(telegram_client, bot_username):
    """Test bot handles empty input gracefully."""
    response = await send_and_wait(telegram_client, bot_username, "/skill")

    assert response is not None, "No response to empty skill"
    # Should show usage or help
    text = response.text.lower()
    assert any(word in text for word in ["usage", "help", "specify", "name"]), \
        "Expected usage hint"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_invalid_command_handling(telegram_client, bot_username):
    """Test unknown command is handled."""
    response = await send_and_wait(
        telegram_client,
        bot_username,
        "/unknowncommandxyz123"
    )

    # Should get some response (error or default)
    assert response is not None, "No response to invalid command"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_rate_limit_behavior(telegram_client, bot_username):
    """Test rapid messages don't break the bot."""
    responses = []

    # Send 5 messages rapidly
    for i in range(5):
        await telegram_client.send_message(bot_username, f"/status {i}")

    # Wait for responses
    await asyncio.sleep(5)

    messages = await telegram_client.get_messages(bot_username, limit=10)
    bot_responses = [m for m in messages if not m.out]

    # Should get at least some responses
    assert len(bot_responses) >= 1, "No responses to rapid messages"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_long_input_handling(telegram_client, bot_username):
    """Test very long input is handled."""
    long_input = "x" * 2000  # Near Telegram limit

    response = await send_and_wait(
        telegram_client,
        bot_username,
        f"/summarize {long_input}",
        timeout=30
    )

    # Should respond (either process or error gracefully)
    assert response is not None, "No response to long input"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_special_characters(telegram_client, bot_username):
    """Test special characters don't break parsing."""
    special = 'Test with "quotes" and <html> and `code`'

    response = await send_and_wait(
        telegram_client,
        bot_username,
        f"/translate {special}",
        timeout=30
    )

    assert response is not None, "No response with special chars"
```

## Todo List

- [ ] Create `tests/e2e/` directory
- [ ] Create `tests/e2e/conftest.py` with Telethon fixtures
- [ ] Create `tests/e2e/test_onboarding.py`
- [ ] Create `tests/e2e/test_commands.py`
- [ ] Create `tests/e2e/test_skills.py`
- [ ] Create `tests/e2e/test_media.py`
- [ ] Create `tests/e2e/test_error_recovery.py`
- [ ] Add `telethon>=1.30.0` to requirements.txt
- [ ] Document Telegram API credentials setup
- [ ] Create session file on first run
- [ ] Update pytest.ini to skip e2e by default

## Success Criteria

- [ ] Onboarding flow completes successfully
- [ ] All command tests pass
- [ ] Skill execution verified E2E
- [ ] Media upload handled
- [ ] Error cases gracefully handled
- [ ] Tests skip cleanly without credentials

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Telethon auth issues | Medium | High | Document setup, session file |
| Bot response timeout | Medium | Medium | Generous timeouts, retries |
| Rate limiting | Low | Medium | Delays between tests |
| Session invalidation | Low | Medium | Regenerate session |
| Telegram API changes | Low | Medium | Pin Telethon version |
