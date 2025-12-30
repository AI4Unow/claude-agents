---
phase: 1
title: "Test Infrastructure and Fixtures"
status: pending
effort: 1h
---

# Phase 1: Test Infrastructure and Fixtures

## Context

- Parent: [plan.md](./plan.md)
- Dependencies: None
- Docs: pytest-asyncio, unittest.mock

## Overview

Create foundational test infrastructure with reusable fixtures and mock modules for simulating Telegram bot interactions without real API calls.

## Requirements

1. Mock modules for external services
2. Shared pytest fixtures for common patterns
3. Test data factories for generating test objects
4. AsyncMock helpers for Telegram/Firebase/LLM

## Architecture

```
agents/tests/
├── mocks/
│   ├── __init__.py
│   ├── mock_telegram.py   # TelegramUpdate, TelegramResponse mocks
│   ├── mock_firebase.py   # StateManager, Firebase mocks
│   └── mock_llm.py        # LLM client mocks
└── test_telegram/
    ├── __init__.py
    └── conftest.py        # Telegram-specific fixtures
```

## Related Code Files

- `agents/tests/conftest.py` - Existing fixtures (extend)
- `agents/main.py:197-284` - Telegram webhook handler
- `agents/src/core/state.py` - StateManager
- `agents/src/services/llm.py` - LLM client

## Implementation Steps

### Step 1: Create mocks/ directory structure

```python
# agents/tests/mocks/__init__.py
from .mock_telegram import *
from .mock_firebase import *
from .mock_llm import *
```

### Step 2: Create Telegram mock module

```python
# agents/tests/mocks/mock_telegram.py
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

@dataclass
class MockChat:
    """Simulated Telegram chat."""
    id: int = 123456789
    type: str = "private"

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
            "from": {
                "id": self.from_user.id,
                "first_name": self.from_user.first_name,
                "last_name": self.from_user.last_name,
                "username": self.from_user.username,
                "is_bot": self.from_user.is_bot,
            },
            "chat": {"id": self.chat.id, "type": self.chat.type},
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
            "from": {
                "id": user.id,
                "first_name": user.first_name,
            },
            "data": data,
            "message": {"chat": {"id": chat_id}},
        }
    }
```

### Step 3: Create Firebase mock module

```python
# agents/tests/mocks/mock_firebase.py
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, Optional

class MockStateManager:
    """Mock StateManager for testing."""

    def __init__(self):
        self._tiers: Dict[int, str] = {}  # user_id -> tier
        self._modes: Dict[int, str] = {}  # user_id -> mode
        self._l1_cache: Dict[str, Any] = {}

    async def get_user_tier_cached(self, user_id: int) -> str:
        return self._tiers.get(user_id, "guest")

    async def get_user_mode(self, user_id: int) -> str:
        return self._modes.get(user_id, "simple")

    async def set_user_mode(self, user_id: int, mode: str):
        self._modes[user_id] = mode

    async def get_pending_skill(self, user_id: int) -> Optional[str]:
        return None

    async def clear_pending_skill(self, user_id: int):
        pass

    async def clear_conversation(self, user_id: int):
        pass

    async def invalidate_user_tier(self, user_id: int):
        self._tiers.pop(user_id, None)

    def check_rate_limit(self, user_id: int, tier: str) -> tuple:
        """Always allow in tests."""
        return (True, 0)

    def set_tier(self, user_id: int, tier: str):
        """Test helper to set tier."""
        self._tiers[user_id] = tier

    def set_mode(self, user_id: int, mode: str):
        """Test helper to set mode."""
        self._modes[user_id] = mode

def mock_has_permission(tier: str, required: str) -> bool:
    """Test version of has_permission."""
    TIER_LEVELS = {"guest": 0, "user": 1, "developer": 2, "admin": 3}
    return TIER_LEVELS.get(tier, 0) >= TIER_LEVELS.get(required, 0)

def mock_get_rate_limit(tier: str) -> int:
    """Test version of get_rate_limit."""
    LIMITS = {"guest": 10, "user": 30, "developer": 100, "admin": 1000}
    return LIMITS.get(tier, 10)
```

### Step 4: Create LLM mock module

```python
# agents/tests/mocks/mock_llm.py
from unittest.mock import MagicMock
from typing import List, Dict, Optional

class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self):
        self.responses: List[str] = []
        self.call_count = 0

    def set_responses(self, responses: List[str]):
        """Queue responses for sequential calls."""
        self.responses = responses

    def chat(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 1024
    ) -> str:
        """Return queued response or default."""
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return "Mock LLM response"

    def chat_with_image(
        self,
        image_base64: str,
        prompt: str,
        max_tokens: int = 1024
    ) -> str:
        """Return mock image analysis."""
        self.call_count += 1
        return "Mock image analysis response"

class MockComplexityClassifier:
    """Mock complexity classifier."""

    def __init__(self, default: str = "simple"):
        self.default = default
        self.overrides: Dict[str, str] = {}

    def classify(self, message: str) -> str:
        """Return complexity for message."""
        for keyword, complexity in self.overrides.items():
            if keyword.lower() in message.lower():
                return complexity
        return self.default
```

### Step 5: Create Telegram test conftest.py

```python
# agents/tests/test_telegram/conftest.py
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from tests.mocks import MockStateManager, MockLLMClient, MockUser, MockMessage

@pytest.fixture
def mock_env():
    """Set up environment variables for testing."""
    with patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "test_bot_token",
        "ADMIN_TELEGRAM_ID": "999999999",
        "TELEGRAM_WEBHOOK_SECRET": "",  # Disabled for tests
    }):
        yield

@pytest.fixture
def mock_state():
    """Provide MockStateManager."""
    state = MockStateManager()
    with patch("src.core.state.get_state_manager", return_value=state):
        yield state

@pytest.fixture
def mock_llm():
    """Provide MockLLMClient."""
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
         patch("main.edit_progress_message", new_callable=AsyncMock) as edit:
        yield {
            "send": send,
            "action": action,
            "react": react,
            "progress": progress,
            "edit": edit,
        }

@pytest.fixture
def admin_user():
    """Create admin user (matches ADMIN_TELEGRAM_ID)."""
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
```

### Step 6: Update main conftest.py

Add imports and shared fixtures to existing `agents/tests/conftest.py`.

## Todo List

- [ ] Create `tests/mocks/` directory structure
- [ ] Create `mock_telegram.py` with MockUser, MockMessage, helpers
- [ ] Create `mock_firebase.py` with MockStateManager
- [ ] Create `mock_llm.py` with MockLLMClient
- [ ] Create `tests/test_telegram/conftest.py` with fixtures
- [ ] Update main `conftest.py` to import new mocks
- [ ] Verify fixtures work with simple smoke test

## Success Criteria

1. All mock modules importable without errors
2. Fixtures create valid test objects
3. MockStateManager supports tier/mode operations
4. MockLLMClient returns queued responses
5. Telegram API calls properly mocked
6. Smoke test passes

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Mocks diverge from real API | Review when real code changes |
| Async mock complexity | Use pytest-asyncio patterns |
| Missing edge cases | Add mocks as tests reveal gaps |

## Security Considerations

- No real tokens in test files
- Environment variables mocked, not real
- Test data doesn't leak to logs

## Next Steps

After completing this phase:
1. Proceed to Phase 2: Command Handler Tests
2. Use fixtures to test all 20+ commands
