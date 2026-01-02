# agents/tests/e2e/mocks/test_mock_client.py
"""Tests for mock Telegram client - verifies mock behavior matches expectations."""
import pytest
from .telegram_mocks import (
    MockTelegramClient,
    MockMessage,
    create_mock_response,
    create_standard_handler
)

pytestmark = [pytest.mark.asyncio, pytest.mark.no_llm]


class TestMockTelegramClient:
    """Tests for MockTelegramClient behavior."""

    async def test_connect_disconnect(self):
        """Client should track connection state."""
        client = MockTelegramClient()
        assert not client._connected

        await client.connect()
        assert client._connected

        await client.disconnect()
        assert not client._connected

    async def test_is_authorized(self):
        """Client should report authorization state."""
        client = MockTelegramClient()
        assert await client.is_user_authorized()

        client.set_authorized(False)
        assert not await client.is_user_authorized()

    async def test_send_message_stores_and_returns(self):
        """Sent messages should be stored and returned."""
        client = MockTelegramClient()
        await client.connect()

        sent = await client.send_message("testbot", "hello")

        assert sent.text == "hello"
        assert sent.out is True
        assert sent.id > 0

    async def test_get_messages_returns_stored(self):
        """get_messages should return stored messages."""
        client = MockTelegramClient()
        await client.connect()

        await client.send_message("testbot", "msg1")
        await client.send_message("testbot", "msg2")

        messages = await client.get_messages("testbot", limit=5)

        assert len(messages) == 2
        # Newest first
        assert messages[0].text == "msg2"
        assert messages[1].text == "msg1"

    async def test_response_handler_generates_replies(self):
        """Response handler should generate bot replies."""
        client = MockTelegramClient()
        client.set_response_handler(create_standard_handler())
        await client.connect()

        await client.send_message("testbot", "/start")

        messages = await client.get_messages("testbot", limit=5)

        # Should have our message + bot response
        assert len(messages) == 2
        # Bot response (first = newest)
        assert "Welcome" in messages[0].text
        assert messages[0].out is False
        # Our message
        assert messages[1].text == "/start"
        assert messages[1].out is True

    async def test_send_file_with_caption(self):
        """send_file should store file message with caption."""
        client = MockTelegramClient()
        await client.connect()

        sent = await client.send_file("testbot", "/path/to/file.pdf", caption="My PDF")

        assert sent.text == "My PDF"
        assert sent.media is not None
        assert "file.pdf" in str(sent.media)

    async def test_get_message_by_id(self):
        """get_messages with ids should return specific message."""
        client = MockTelegramClient()
        await client.connect()

        sent1 = await client.send_message("testbot", "first")
        sent2 = await client.send_message("testbot", "second")

        result = await client.get_messages("testbot", ids=sent1.id)

        assert result.id == sent1.id
        assert result.text == "first"

    async def test_add_mock_response(self):
        """add_mock_response should inject bot messages."""
        client = MockTelegramClient()
        await client.connect()

        client.add_mock_response("testbot", create_mock_response("Injected response"))

        messages = await client.get_messages("testbot", limit=5)

        assert len(messages) == 1
        assert messages[0].text == "Injected response"
        assert messages[0].out is False

    async def test_clear_messages(self):
        """clear_messages should remove stored messages."""
        client = MockTelegramClient()
        await client.connect()

        await client.send_message("testbot", "msg1")
        await client.send_message("testbot", "msg2")

        client.clear_messages("testbot")
        messages = await client.get_messages("testbot", limit=5)

        assert len(messages) == 0


class TestMockHelpers:
    """Tests for mock helper functions."""

    def test_create_mock_response_basic(self):
        """create_mock_response should create message with text."""
        msg = create_mock_response("Hello!")

        assert msg.text == "Hello!"
        assert msg.out is False
        assert msg.buttons is None

    def test_create_mock_response_with_buttons(self):
        """create_mock_response should create message with buttons."""
        msg = create_mock_response(
            "Choose:",
            buttons=[["Option A", "Option B"], ["Cancel"]]
        )

        assert msg.buttons is not None
        assert len(msg.buttons) == 2
        assert len(msg.buttons[0]) == 2
        assert msg.buttons[0][0].text == "Option A"

    def test_standard_handler_commands(self):
        """Standard handler should respond to commands."""
        handler = create_standard_handler()

        start_resp = handler("bot", "/start")
        assert "Welcome" in start_resp.text

        help_resp = handler("bot", "/help")
        assert "commands" in help_resp.text.lower()

        status_resp = handler("bot", "/status")
        assert "Status" in status_resp.text

    def test_standard_handler_skills(self):
        """Standard handler should respond to skill invocations."""
        handler = create_standard_handler()

        resp = handler("bot", "/skill planning create a feature")

        assert "planning" in resp.text.lower()
        assert "Executing" in resp.text or "Processing" in resp.text

    def test_standard_handler_chat(self):
        """Standard handler should respond to regular messages."""
        handler = create_standard_handler()

        resp = handler("bot", "Hello, how are you?")

        assert resp is not None
        assert "received" in resp.text.lower()
