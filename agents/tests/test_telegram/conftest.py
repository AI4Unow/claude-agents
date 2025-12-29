"""Pytest fixtures for Telegram bot tests."""
import pytest
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add agents directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.mocks import MockStateManager, MockLLMClient, MockUser, MockChat, MockMessage


@pytest.fixture
def mock_env():
    """Set up environment variables for testing."""
    env_vars = {
        "TELEGRAM_BOT_TOKEN": "test_bot_token",
        "ADMIN_TELEGRAM_ID": "999999999",
        "TELEGRAM_WEBHOOK_SECRET": "",
        "ANTHROPIC_API_KEY": "test_key",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_state():
    """Provide MockStateManager and patch get_state_manager."""
    state = MockStateManager()
    with patch("src.core.state.get_state_manager", return_value=state):
        yield state


@pytest.fixture
def mock_llm():
    """Provide MockLLMClient and patch get_llm_client."""
    client = MockLLMClient()
    with patch("src.services.llm.get_llm_client", return_value=client):
        yield client


@pytest.fixture
def mock_telegram_api():
    """Mock all Telegram API calls."""
    with patch("main.send_telegram_message", new_callable=AsyncMock) as send, \
         patch("main.send_chat_action", new_callable=AsyncMock) as action, \
         patch("main.set_message_reaction", new_callable=AsyncMock) as react, \
         patch("main.send_progress_message", new_callable=AsyncMock, return_value=1) as progress, \
         patch("main.edit_progress_message", new_callable=AsyncMock) as edit, \
         patch("main.typing_indicator", new_callable=AsyncMock) as typing:
        yield {
            "send": send,
            "action": action,
            "react": react,
            "progress": progress,
            "edit": edit,
            "typing": typing,
        }


@pytest.fixture
def admin_user():
    """Create admin user (matches ADMIN_TELEGRAM_ID=999999999)."""
    return MockUser(id=999999999, first_name="Admin")


@pytest.fixture
def developer_user(mock_state):
    """Create developer tier user."""
    user = MockUser(id=111111111, first_name="Developer")
    mock_state.set_tier(user.id, "developer")
    return user


@pytest.fixture
def regular_user(mock_state):
    """Create regular user tier user."""
    user = MockUser(id=222222222, first_name="Regular")
    mock_state.set_tier(user.id, "user")
    return user


@pytest.fixture
def guest_user():
    """Create guest (unregistered) user."""
    return MockUser(id=333333333, first_name="Guest")


@pytest.fixture
def create_message():
    """Factory for creating test messages."""
    def _create(text: str, user: MockUser = None, chat_id: int = None) -> MockMessage:
        user = user or MockUser()
        chat_id = chat_id or user.id
        return MockMessage(
            text=text,
            from_user=user,
            chat=MockChat(id=chat_id),
        )
    return _create
