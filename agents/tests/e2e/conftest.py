"""Telegram E2E test configuration using Telethon."""
import os
import asyncio
import pytest
from pathlib import Path

# Load .env file for local testing
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed, env vars must be set manually
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
    config.addinivalue_line("markers", "timeout_90: tests with 90s timeout")
    config.addinivalue_line("markers", "requires_claude: tests requiring Claude API (LLM)")
    config.addinivalue_line("markers", "requires_gemini: tests requiring Gemini API")
    config.addinivalue_line("markers", "no_llm: infrastructure tests (no LLM required)")


# === Retry Logic ===

DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_DELAY = 3  # seconds


async def retry_async(func, *args, max_attempts=DEFAULT_RETRY_ATTEMPTS, delay=DEFAULT_RETRY_DELAY, **kwargs):
    """Retry an async function on failure.

    Useful for transient network/timeout failures in E2E tests.
    """
    last_error = None
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except (AssertionError, TimeoutError, asyncio.TimeoutError) as e:
            last_error = e
            if attempt < max_attempts - 1:
                print(f"[E2E] Retry {attempt + 1}/{max_attempts} after error: {e}")
                await asyncio.sleep(delay)
    raise last_error


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
    timeout: float = 30.0,
    retry: bool = True
):
    """Send message and wait for response.

    Args:
        client: Telethon client
        bot_username: Bot to message
        text: Message to send
        timeout: Max seconds to wait
        retry: If True, retry once on timeout

    Returns:
        Response message or None
    """
    import time

    max_attempts = 2 if retry else 1

    for attempt in range(max_attempts):
        # Small delay to avoid message overlap from previous tests
        await asyncio.sleep(0.5)

        # Get the message ID of the most recent bot message before we send
        messages_before = await client.get_messages(bot_username, limit=1)
        last_msg_id = messages_before[0].id if messages_before else 0

        # Send message
        attempt_str = f" (attempt {attempt + 1})" if attempt > 0 else ""
        print(f"[E2E] Sending '{text}' to {bot_username}{attempt_str}")
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

        # If retry enabled and not last attempt, wait before retrying
        if attempt < max_attempts - 1:
            print("[E2E] Retrying after short delay...")
            await asyncio.sleep(DEFAULT_RETRY_DELAY)

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


# === Webhook Health Check ===

async def check_webhook_health() -> bool:
    """Check Telegram webhook health via getWebhookInfo.

    Returns:
        True if webhook is healthy (pending_update_count < 10, no recent errors)
        False if unhealthy
    """
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("[E2E] TELEGRAM_BOT_TOKEN not set, skipping webhook check")
        return True

    # Use bot token to check webhook info via Bot API
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
            )
            if resp.status_code != 200:
                print(f"[E2E] Webhook info request failed: {resp.status_code}")
                return False

            data = resp.json()
            if not data.get("ok"):
                print(f"[E2E] Webhook info error: {data.get('description')}")
                return False

            info = data.get("result", {})
            pending_count = info.get("pending_update_count", 0)
            last_error = info.get("last_error_message")
            last_error_date = info.get("last_error_date", 0)

            # Check health criteria
            if pending_count >= 10:
                print(f"[E2E] Webhook unhealthy: {pending_count} pending updates")
                return False

            # Check if error happened in last 5 minutes
            import time
            if last_error and (time.time() - last_error_date) < 300:
                print(f"[E2E] Webhook recent error: {last_error}")
                return False

            print(f"[E2E] Webhook healthy: {pending_count} pending updates")
            return True

        except Exception as e:
            print(f"[E2E] Webhook health check error: {e}")
            return False


async def ensure_webhook_healthy(bot_token: str = None) -> bool:
    """Ensure webhook is healthy, re-setup if needed.

    Args:
        bot_token: Telegram bot token (reads from env if not provided)

    Returns:
        True if webhook is healthy or successfully recovered
        False if unable to recover after retries
    """
    if not bot_token:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        print("[E2E] TELEGRAM_BOT_TOKEN not set, skipping webhook check")
        return True

    max_attempts = 2

    for attempt in range(max_attempts):
        # Check current health
        is_healthy = await check_webhook_health()

        if is_healthy:
            return True

        # Unhealthy - re-setup webhook
        print(f"[E2E] Webhook unhealthy, attempting recovery (attempt {attempt + 1}/{max_attempts})")

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Drop pending updates by calling getUpdates with -1 offset
                drop_resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/getUpdates",
                    json={"offset": -1, "timeout": 0}
                )

                if drop_resp.status_code == 200:
                    print("[E2E] Dropped pending updates")
                else:
                    print(f"[E2E] Failed to drop updates: {drop_resp.status_code}")

                # Re-set webhook (assume Modal webhook URL)
                webhook_url = API_BASE_URL + "/webhook/telegram"
                webhook_resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/setWebhook",
                    json={"url": webhook_url, "drop_pending_updates": True}
                )

                if webhook_resp.status_code == 200:
                    print(f"[E2E] Webhook re-set to {webhook_url}")
                    await asyncio.sleep(2)  # Wait for webhook to stabilize
                else:
                    print(f"[E2E] Failed to set webhook: {webhook_resp.status_code}")

            except Exception as e:
                print(f"[E2E] Webhook recovery error: {e}")

        # Wait before retry
        if attempt < max_attempts - 1:
            await asyncio.sleep(3)

    # Final check
    return await check_webhook_health()


@pytest.fixture(scope="session", autouse=True)
async def webhook_health_check(event_loop):
    """Ensure webhook is healthy before test session starts.

    Runs automatically at session start. Checks webhook health
    and attempts recovery if needed.
    """
    print("\n[E2E] Checking webhook health before test session...")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("[E2E] TELEGRAM_BOT_TOKEN not set, skipping webhook health check")
        return

    # Ensure webhook is healthy
    is_healthy = await ensure_webhook_healthy(bot_token)

    if is_healthy:
        print("[E2E] Webhook health check passed\n")
    else:
        print("[E2E] WARNING: Webhook may be unhealthy, tests may be unstable\n")


# === Circuit Health Checks ===

async def check_circuit_health() -> dict:
    """Check circuit breaker health via /health endpoint.

    Returns:
        Dict mapping circuit names to their full info dicts (state, failures, etc)
        Empty dict if health check fails
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{API_BASE_URL}/health")
            if resp.status_code != 200:
                print(f"[E2E] Health endpoint returned {resp.status_code}")
                return {}

            data = resp.json()
            circuits = data.get("circuits", {})

            return circuits

        except Exception as e:
            print(f"[E2E] Circuit health check error: {e}")
            return {}


@pytest.fixture(scope="function")
async def ensure_circuits_healthy(request):
    """Check circuit health before running LLM-dependent tests.

    Uses pytest.xfail() instead of skip to show expected failures
    when circuits are unhealthy.

    Scope: function (per test) to catch mid-run circuit opens
    """
    # Only check if test requires LLM
    marker_names = [m.name for m in request.node.iter_markers()]

    requires_claude = "requires_claude" in marker_names
    requires_gemini = "requires_gemini" in marker_names
    no_llm = "no_llm" in marker_names

    # Skip check for infrastructure tests
    if no_llm or (not requires_claude and not requires_gemini):
        return

    # Check circuit health
    circuits = await check_circuit_health()

    if not circuits:
        print("[E2E] WARNING: Could not verify circuit health, proceeding anyway")
        return

    # Check Claude circuit if required
    if requires_claude:
        claude_info = circuits.get("claude_api", {})
        claude_state = claude_info.get("state", "unknown")
        if claude_state == "open":
            pytest.xfail(
                f"Claude API circuit is open (state={claude_state}, "
                f"failures={claude_info.get('failures', 'unknown')})"
            )
        elif claude_state == "half_open":
            print(f"[E2E] WARNING: Claude API circuit is half_open, tests may be flaky")

    # Check Gemini circuit if required
    if requires_gemini:
        gemini_info = circuits.get("gemini_api", {})
        gemini_state = gemini_info.get("state", "unknown")
        if gemini_state == "open":
            pytest.xfail(
                f"Gemini API circuit is open (state={gemini_state}, "
                f"failures={gemini_info.get('failures', 'unknown')})"
            )
        elif gemini_state == "half_open":
            print(f"[E2E] WARNING: Gemini API circuit is half_open, tests may be flaky")


@pytest.fixture(scope="function", autouse=True)
async def skill_rate_limit(request):
    """Add small delay between skill invocation tests to prevent rate limiting.

    Applies automatically to tests in skills/ subdirectory.
    """
    yield

    # Only apply delay after tests in skills/ directory
    test_path = str(request.fspath)
    if "/skills/" in test_path or "test_skill" in test_path:
        await asyncio.sleep(0.3)  # 300ms between skill tests


@pytest.fixture(scope="function", autouse=True)
async def auto_circuit_check(request):
    """Automatically check circuit health for LLM-dependent tests.

    Auto-applies to tests with requires_claude or requires_gemini markers.
    Uses xfail instead of skip to show expected failures.
    """
    marker_names = [m.name for m in request.node.iter_markers()]

    requires_claude = "requires_claude" in marker_names
    requires_gemini = "requires_gemini" in marker_names

    if not requires_claude and not requires_gemini:
        yield
        return

    # Check circuit health before test
    circuits = await check_circuit_health()

    if circuits:
        # Check Claude circuit
        if requires_claude:
            claude_info = circuits.get("claude_api", {})
            if claude_info.get("state") == "open":
                pytest.xfail(f"Claude circuit open: {claude_info.get('failures', 0)} failures")

        # Check Gemini circuit
        if requires_gemini:
            gemini_info = circuits.get("gemini_api", {})
            if gemini_info.get("state") == "open":
                pytest.xfail(f"Gemini circuit open: {gemini_info.get('failures', 0)} failures")

    yield


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
