# agents/tests/e2e/mocks/telegram_mocks.py
"""Mock Telegram client for offline testing.

Provides MockTelegramClient and MockMessage that simulate Telethon behavior
without requiring actual Telegram credentials or network access.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, List, Callable, Dict
from unittest.mock import AsyncMock


@dataclass
class MockButton:
    """Mock inline keyboard button."""
    text: str
    data: Optional[str] = None
    url: Optional[str] = None

    async def click(self):
        """Simulate button click."""
        return True


@dataclass
class MockMessage:
    """Mock Telegram message matching Telethon Message interface."""
    id: int
    text: Optional[str] = None
    out: bool = False  # True if sent by us
    date: datetime = field(default_factory=datetime.now)
    chat_id: int = 0
    buttons: Optional[List[List[MockButton]]] = None
    media: Optional[Any] = None
    reply_to_msg_id: Optional[int] = None

    @property
    def raw_text(self) -> str:
        return self.text or ""


class MockTelegramClient:
    """Mock Telethon client for offline testing.

    Simulates the Telethon TelegramClient interface without
    requiring network access or credentials.

    Usage:
        client = MockTelegramClient()
        client.set_response_handler(my_handler)
        await client.send_message("bot", "hello")
        messages = await client.get_messages("bot", limit=5)
    """

    def __init__(self):
        self._message_id = 0
        self._messages: Dict[str, List[MockMessage]] = {}
        self._response_handler: Optional[Callable] = None
        self._connected = False
        self._authorized = True

    async def connect(self):
        """Simulate connection."""
        self._connected = True

    async def disconnect(self):
        """Simulate disconnection."""
        self._connected = False

    async def is_user_authorized(self) -> bool:
        """Check if user is authorized."""
        return self._authorized

    def set_authorized(self, authorized: bool):
        """Set authorization state for testing."""
        self._authorized = authorized

    def set_response_handler(self, handler: Callable[[str, str], MockMessage]):
        """Set handler that generates bot responses.

        Args:
            handler: Function(chat_id, text) -> MockMessage
        """
        self._response_handler = handler

    def _next_id(self) -> int:
        """Generate next message ID."""
        self._message_id += 1
        return self._message_id

    async def send_message(
        self,
        entity: str,
        message: str,
        **kwargs
    ) -> MockMessage:
        """Send a message (mock).

        Args:
            entity: Chat/user to send to
            message: Text message

        Returns:
            MockMessage representing sent message
        """
        msg_id = self._next_id()
        sent_msg = MockMessage(
            id=msg_id,
            text=message,
            out=True,
            chat_id=hash(entity) % 1000000,
            date=datetime.now()
        )

        # Store message
        if entity not in self._messages:
            self._messages[entity] = []
        self._messages[entity].append(sent_msg)

        # Generate response if handler set
        if self._response_handler:
            await asyncio.sleep(0.1)  # Simulate delay
            response = self._response_handler(entity, message)
            if response:
                response.id = self._next_id()
                response.out = False
                response.chat_id = sent_msg.chat_id
                self._messages[entity].append(response)

        return sent_msg

    async def send_file(
        self,
        entity: str,
        file: Any,
        caption: Optional[str] = None,
        **kwargs
    ) -> MockMessage:
        """Send a file (mock).

        Args:
            entity: Chat/user to send to
            file: File path or bytes
            caption: Optional caption

        Returns:
            MockMessage representing sent file
        """
        msg_id = self._next_id()
        sent_msg = MockMessage(
            id=msg_id,
            text=caption,
            out=True,
            chat_id=hash(entity) % 1000000,
            date=datetime.now(),
            media={"file": str(file)}
        )

        if entity not in self._messages:
            self._messages[entity] = []
        self._messages[entity].append(sent_msg)

        # Generate response for file
        if self._response_handler:
            await asyncio.sleep(0.1)
            response = self._response_handler(entity, f"[FILE: {file}]")
            if response:
                response.id = self._next_id()
                response.out = False
                self._messages[entity].append(response)

        return sent_msg

    async def get_messages(
        self,
        entity: str,
        limit: int = 10,
        ids: Optional[int] = None,
        **kwargs
    ) -> List[MockMessage]:
        """Get messages from a chat (mock).

        Args:
            entity: Chat/user to get messages from
            limit: Max messages to return
            ids: Specific message ID to get

        Returns:
            List of MockMessage objects
        """
        messages = self._messages.get(entity, [])

        if ids is not None:
            # Return specific message
            for msg in messages:
                if msg.id == ids:
                    return msg
            return None

        # Return last N messages, newest first
        return list(reversed(messages[-limit:]))

    def add_mock_response(self, entity: str, response: MockMessage):
        """Add a mock response to the message list.

        Useful for simulating incoming messages from the bot.
        """
        response.id = self._next_id()
        response.out = False
        if entity not in self._messages:
            self._messages[entity] = []
        self._messages[entity].append(response)

    def clear_messages(self, entity: Optional[str] = None):
        """Clear stored messages."""
        if entity:
            self._messages[entity] = []
        else:
            self._messages.clear()


def create_mock_response(
    text: str,
    buttons: Optional[List[List[str]]] = None,
    media: Optional[Any] = None
) -> MockMessage:
    """Helper to create mock bot response.

    Args:
        text: Response text
        buttons: Optional button labels [[row1], [row2]]
        media: Optional media attachment

    Returns:
        MockMessage configured as bot response
    """
    mock_buttons = None
    if buttons:
        mock_buttons = [
            [MockButton(text=btn) for btn in row]
            for row in buttons
        ]

    return MockMessage(
        id=0,  # Will be set by client
        text=text,
        out=False,
        buttons=mock_buttons,
        media=media
    )


def create_standard_handler():
    """Create handler with standard bot responses.

    Returns:
        Handler function for common commands/messages
    """
    responses = {
        "/start": "Welcome! I'm your AI assistant. Use /help to see commands.",
        "/help": "Available commands:\n/start - Start\n/help - Help\n/skills - List skills\n/status - Status",
        "/status": "Status: Online\nTier: user\nMode: chat",
        "/skills": "Available skills:\n- planning\n- debugging\n- research\n- code-review",
        "/clear": "Conversation cleared.",
        "/tier": "Your tier: user\nRate limit: 100/hour",
    }

    def handler(entity: str, text: str) -> Optional[MockMessage]:
        # Check for exact command match
        cmd = text.split()[0] if text else ""
        if cmd in responses:
            return create_mock_response(responses[cmd])

        # Check for skill invocation
        if text.startswith("/skill "):
            skill_name = text[7:].split()[0]
            return create_mock_response(
                f"Executing skill: {skill_name}\n\nProcessing your request..."
            )

        # Default chat response
        return create_mock_response(
            f"I received your message: '{text[:50]}...'"
        )

    return handler
