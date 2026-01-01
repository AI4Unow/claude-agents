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
