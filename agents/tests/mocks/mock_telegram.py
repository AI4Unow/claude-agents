"""Telegram API mocks for testing."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class MockUser:
    """Simulated Telegram user."""
    id: int = 123456789
    first_name: str = "Test"
    last_name: str = "User"
    username: str = "testuser"
    is_bot: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
            "is_bot": self.is_bot,
        }


@dataclass
class MockChat:
    """Simulated Telegram chat."""
    id: int = 123456789
    type: str = "private"

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type}


@dataclass
class MockMessage:
    """Simulated Telegram message."""
    message_id: int = 1
    from_user: MockUser = field(default_factory=MockUser)
    chat: MockChat = field(default_factory=MockChat)
    text: str = ""
    caption: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from": self.from_user.to_dict(),
            "chat": self.chat.to_dict(),
            "text": self.text,
            "caption": self.caption,
        }


def create_update(message: MockMessage, update_id: int = 1) -> Dict[str, Any]:
    """Create Telegram update payload."""
    return {
        "update_id": update_id,
        "message": message.to_dict(),
    }


def create_callback_query(
    callback_id: str = "123",
    data: str = "test_data",
    user: MockUser = None,
    chat_id: int = 123456789
) -> Dict[str, Any]:
    """Create callback query for inline keyboard."""
    user = user or MockUser()
    return {
        "callback_query": {
            "id": callback_id,
            "from": user.to_dict(),
            "data": data,
            "message": {"chat": {"id": chat_id}},
        }
    }
