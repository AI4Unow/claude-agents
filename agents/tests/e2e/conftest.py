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
    """Create event loop for session-scoped async fixtures.

    Set as the current event loop to avoid Telethon mismatch errors.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
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
async def telegram_client(e2e_env):
    """Create and connect Telethon client.

    Requires prior authentication via auth_session.py.
    The session file must exist and be valid.
    """
    from telethon import TelegramClient

    # Use file session for persistence (without .session extension)
    session_path = SESSION_DIR / SESSION_NAME

    # Check session file exists
    session_file = SESSION_DIR / f"{SESSION_NAME}.session"
    if not session_file.exists():
        pytest.skip(
            f"Session file not found: {session_file}\n"
            "Run: python3 tests/e2e/auth_session.py"
        )

    client = TelegramClient(
        str(session_path),
        e2e_env["api_id"],
        e2e_env["api_hash"]
    )

    # Connect without starting auth flow (session should be valid)
    await client.connect()

    # Verify we're authorized
    if not await client.is_user_authorized():
        await client.disconnect()
        pytest.skip(
            "Session expired or invalid. Re-authenticate:\n"
            "python3 tests/e2e/auth_session.py"
        )

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
    min_length: int = 0,
    after_timestamp: float = None
):
    """Wait for bot response message.

    Args:
        client: Telethon client
        bot_username: Bot to receive from
        timeout: Max seconds to wait
        min_length: Minimum response length
        after_timestamp: Only accept messages after this time (optional)

    Returns:
        Message object or None if timeout
    """
    import time

    start = time.time()
    cutoff = after_timestamp if after_timestamp else start
    last_message = None

    while time.time() - start < timeout:
        # Get recent messages from bot
        messages = await client.get_messages(bot_username, limit=5)
        for msg in messages:
            if msg.out:  # Skip our own messages
                continue
            if msg.date.timestamp() > cutoff:  # Message after our cutoff
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

    # Small delay to avoid message overlap from previous tests
    await asyncio.sleep(0.5)

    # Get the message ID of the most recent bot message before we send
    messages_before = await client.get_messages(bot_username, limit=1)
    last_msg_id = messages_before[0].id if messages_before else 0

    # Send message
    print(f"[E2E] Sending '{text}' to {bot_username}")
    sent_msg = await client.send_message(bot_username, text)
    print(f"[E2E] Message sent (id={sent_msg.id}), waiting up to {timeout}s for response...")

    # Wait for response with ID greater than our sent message
    start = time.time()
    while time.time() - start < timeout:
        messages = await client.get_messages(bot_username, limit=5)
        for msg in messages:
            if msg.out:
                continue
            # Response must have ID greater than our sent message
            if msg.id > sent_msg.id:
                # Skip "Processing..." placeholder messages
                if msg.text and "processing" in msg.text.lower() and len(msg.text) < 50:
                    continue
                print(f"[E2E] Got response (id={msg.id}): {msg.text[:100] if msg.text else '(no text)'}...")
                return msg

        await asyncio.sleep(1)

    print(f"[E2E] Timeout after {timeout}s - no response received")
    # Debug: show last messages
    messages = await client.get_messages(bot_username, limit=3)
    for i, msg in enumerate(messages):
        print(f"[E2E] Last msg {i}: id={msg.id} out={msg.out}, text={msg.text[:50] if msg.text else '(none)'}...")

    return None
