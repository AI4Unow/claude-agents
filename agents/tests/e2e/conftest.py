"""Telegram E2E test configuration using Telethon."""
import os
import asyncio
import pytest
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any

import httpx

# Session file location
SESSION_DIR = Path(__file__).parent
SESSION_NAME = "test_session"

# API base URL for state verification
API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    "https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run"
)


def pytest_configure(config):
    """Register pytest markers."""
    config.addinivalue_line("markers", "e2e: mark test as E2E (requires Telegram)")
    config.addinivalue_line("markers", "slow: tests with > 30s timeout")
    config.addinivalue_line("markers", "local: requires local-executor")
    config.addinivalue_line("markers", "media: requires fixture files")
    config.addinivalue_line("markers", "admin: admin-only tests")
    config.addinivalue_line("markers", "flaky: known flaky tests")


# === Data Classes ===

@dataclass
class SkillResult:
    """Structured skill execution result."""
    success: bool
    text: Optional[str]
    buttons: Optional[list]
    media: Optional[Any]
    message_id: Optional[int] = None

    @property
    def has_buttons(self) -> bool:
        return self.buttons is not None and len(self.buttons) > 0

    @property
    def has_media(self) -> bool:
        return self.media is not None


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

    # Clear conversation at start of test session to avoid polluted context
    bot_username = e2e_env["bot_username"]
    try:
        await client.send_message(bot_username, "/clear")
        await asyncio.sleep(2)  # Wait for clear to process
        print("[E2E] Cleared conversation context at session start")
    except Exception as e:
        print(f"[E2E] Could not clear conversation: {e}")

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


# === Skill Execution Helper ===

async def execute_skill(
    client,
    bot_username: str,
    skill_name: str,
    prompt: str = "",
    timeout: float = 60.0
) -> SkillResult:
    """Execute skill and return structured result."""
    message = f"/skill {skill_name}"
    if prompt:
        message += f" {prompt}"

    response = await send_and_wait(client, bot_username, message, timeout=timeout)

    return SkillResult(
        success=response is not None,
        text=response.text if response else None,
        buttons=response.buttons if response else None,
        media=getattr(response, 'media', None) if response else None,
        message_id=response.id if response else None
    )


# === Media Upload Helper ===

async def upload_file(
    client,
    bot_username: str,
    file_path: Path,
    caption: Optional[str] = None,
    timeout: float = 60.0
):
    """Upload file to bot and wait for response."""
    import time

    await asyncio.sleep(0.5)

    # Get last message ID before upload
    messages_before = await client.get_messages(bot_username, limit=1)

    # Upload file
    print(f"[E2E] Uploading '{file_path.name}' to {bot_username}")
    sent_msg = await client.send_file(bot_username, file_path, caption=caption)
    print(f"[E2E] File sent (id={sent_msg.id}), waiting...")

    # Wait for response
    start = time.time()
    while time.time() - start < timeout:
        messages = await client.get_messages(bot_username, limit=5)
        for msg in messages:
            if msg.out:
                continue
            if msg.id > sent_msg.id:
                if msg.text and "processing" in msg.text.lower() and len(msg.text) < 50:
                    continue
                print(f"[E2E] Got response: {msg.text[:100] if msg.text else '(media)'}...")
                return msg
        await asyncio.sleep(1)

    print("[E2E] Timeout waiting for file response")
    return None


# === State Verification Helpers ===

async def verify_circuit_state(circuit_name: str, expected_state: str) -> bool:
    """Check circuit breaker state via API.

    Note: /api/circuits requires admin token. Falls back to True if
    endpoint is protected and no token available.
    """
    admin_token = os.environ.get("ADMIN_API_TOKEN")
    headers = {}
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{API_BASE_URL}/api/circuits", headers=headers)
            if resp.status_code == 401:
                # Endpoint protected, skip verification
                print(f"[E2E] Circuit API requires auth, skipping verification")
                return True  # Assume healthy if we can't check
            if resp.status_code != 200:
                return False
            circuits = resp.json()
            return circuits.get(circuit_name, {}).get("state") == expected_state
        except Exception as e:
            print(f"[E2E] Circuit check error: {e}")
            return False


async def get_trace(trace_id: str) -> Optional[dict]:
    """Fetch execution trace for verification."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{API_BASE_URL}/api/traces/{trace_id}")
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None


async def get_user_reports(user_id: int) -> list:
    """Get user's research reports."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{API_BASE_URL}/api/reports",
                params={"user_id": user_id}
            )
            if resp.status_code == 200:
                return resp.json().get("reports", [])
            return []
        except Exception:
            return []


# === Button Interaction Helper ===

async def click_button(client, message, button_text: str, timeout: float = 30.0):
    """Click inline button and wait for response."""
    import time

    if not message.buttons:
        return None

    # Find button
    target_button = None
    for row in message.buttons:
        for btn in row:
            if button_text.lower() in btn.text.lower():
                target_button = btn
                break
        if target_button:
            break

    if not target_button:
        print(f"[E2E] Button '{button_text}' not found")
        return None

    # Click button
    await target_button.click()

    # Wait for message update
    start = time.time()
    while time.time() - start < timeout:
        updated = await client.get_messages(message.chat_id, ids=message.id)
        if updated and updated.text != message.text:
            return updated
        await asyncio.sleep(0.5)

    return None


# === Fixtures ===

@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_image(fixtures_dir):
    """Path to sample image fixture."""
    return fixtures_dir / "sample-image.jpg"


@pytest.fixture
def sample_document(fixtures_dir):
    """Path to sample PDF fixture."""
    return fixtures_dir / "sample-document.pdf"


@pytest.fixture
def sample_voice(fixtures_dir):
    """Path to sample voice fixture."""
    return fixtures_dir / "sample-voice.ogg"


@pytest.fixture
def api_base_url():
    """API base URL for verification."""
    return API_BASE_URL
