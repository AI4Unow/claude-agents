# Phase 5: Channel Adapters

## Context

Decouple chatbot logic from messaging platforms via adapter pattern. Based on research in `research/researcher-02-channel-adapters.md`. Currently Telegram-only, target multi-channel support.

## Overview

Create BaseChannelAdapter interface with platform-specific implementations. Core logic (AgenticLoop) works with UnifiedMessage/UnifiedResponse, adapters handle platform specifics.

## Key Insights

- New channel = new adapter only (no core changes)
- Same bot personality everywhere
- Per-channel state via platform+user_id keys
- Gradual rollout possible

## Unified Data Models

```python
# src/adapters/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

class Platform(Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    API = "api"  # Direct API calls


@dataclass
class Attachment:
    """File or media attachment."""
    type: str            # image, video, audio, document
    url: Optional[str]
    file_id: Optional[str]  # Platform-specific ID
    filename: Optional[str]
    mime_type: Optional[str]


@dataclass
class Button:
    """Interactive button."""
    text: str
    callback_data: str


@dataclass
class UnifiedMessage:
    """Platform-agnostic incoming message."""
    message_id: str
    user_id: str
    channel_id: str
    platform: Platform
    text: str
    timestamp: datetime
    attachments: List[Attachment] = field(default_factory=list)
    reply_to: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def state_key(self) -> str:
        """Unique key for state management."""
        return f"{self.platform.value}:{self.user_id}"


@dataclass
class UnifiedResponse:
    """Platform-agnostic outgoing response."""
    text: str
    buttons: Optional[List[List[Button]]] = None  # Rows of buttons
    attachments: Optional[List[Attachment]] = None
    reply_to: Optional[str] = None
    parse_mode: Optional[str] = None  # markdown, html
```

## Base Adapter Interface

```python
# src/adapters/base.py

from abc import ABC, abstractmethod
from typing import Optional
from .models import UnifiedMessage, UnifiedResponse, Platform


class BaseChannelAdapter(ABC):
    """Abstract base for channel adapters."""

    platform: Platform

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection (if needed)."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Cleanup connection."""
        pass

    @abstractmethod
    def normalize_incoming(self, raw: dict) -> UnifiedMessage:
        """Convert platform-specific payload to UnifiedMessage."""
        pass

    @abstractmethod
    def format_response(self, response: UnifiedResponse) -> dict:
        """Convert UnifiedResponse to platform-specific payload."""
        pass

    @abstractmethod
    async def send_message(
        self,
        channel_id: str,
        response: UnifiedResponse
    ) -> None:
        """Send message to platform."""
        pass

    @abstractmethod
    async def send_typing(self, channel_id: str) -> None:
        """Send typing indicator."""
        pass

    async def handle_callback(self, callback_data: dict) -> Optional[str]:
        """Handle button callback. Override if platform supports."""
        return None
```

## Adapter Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHANNEL ADAPTER PATTERN                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INCOMING FLOW                                                   │
│  ─────────────                                                   │
│  Platform Webhook                                                │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────┐                                            │
│  │ Adapter.normalize│                                            │
│  │ _incoming()      │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  UnifiedMessage                                                  │
│  {                                                               │
│    message_id: "msg_123",                                        │
│    user_id: "12345",                                             │
│    platform: Platform.TELEGRAM,                                  │
│    text: "Help me plan...",                                      │
│  }                                                               │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────────────────────────────────┐                │
│  │              CORE LOGIC                       │                │
│  │  ┌────────────────────────────────────────┐  │                │
│  │  │ AgenticLoop.process(unified_message)   │  │                │
│  │  │  • Load conversation from state_key    │  │                │
│  │  │  • Execute skill with tools            │  │                │
│  │  │  • Save conversation                   │  │                │
│  │  └────────────────────────────────────────┘  │                │
│  └──────────────────────────────────────────────┘                │
│           │                                                      │
│           ▼                                                      │
│  UnifiedResponse                                                 │
│  {                                                               │
│    text: "Here's your plan...",                                  │
│    buttons: [[Button("Approve", "approve_123")]],                │
│  }                                                               │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ Adapter.format   │                                            │
│  │ _response()      │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  Platform API (send_message)                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## TelegramAdapter Implementation

Refactor from current main.py:

```python
# src/adapters/telegram.py

import os
from datetime import datetime, timezone
from typing import Optional
import httpx

from .base import BaseChannelAdapter
from .models import (
    UnifiedMessage, UnifiedResponse, Platform,
    Attachment, Button
)
from src.utils.logging import get_logger

logger = get_logger()


class TelegramAdapter(BaseChannelAdapter):
    """Telegram Bot API adapter."""

    platform = Platform.TELEGRAM

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.api_base = f"https://api.telegram.org/bot{self.token}"

    async def connect(self) -> None:
        """Set webhook (if not already set)."""
        pass

    async def disconnect(self) -> None:
        """Remove webhook."""
        pass

    def normalize_incoming(self, raw: dict) -> UnifiedMessage:
        """Convert Telegram update to UnifiedMessage."""
        message = raw.get("message", {})
        chat = message.get("chat", {})
        user = message.get("from", {})

        attachments = []
        if "photo" in message:
            # Get largest photo
            photo = message["photo"][-1]
            attachments.append(Attachment(
                type="image",
                url=None,
                file_id=photo["file_id"],
                filename=None,
                mime_type="image/jpeg"
            ))

        return UnifiedMessage(
            message_id=str(message.get("message_id", "")),
            user_id=str(user.get("id", "")),
            channel_id=str(chat.get("id", "")),
            platform=Platform.TELEGRAM,
            text=message.get("text", ""),
            timestamp=datetime.fromtimestamp(
                message.get("date", 0),
                tz=timezone.utc
            ),
            attachments=attachments,
            reply_to=str(message.get("reply_to_message", {}).get("message_id"))
                if message.get("reply_to_message") else None,
            raw_data=raw
        )

    def format_response(self, response: UnifiedResponse) -> dict:
        """Convert UnifiedResponse to Telegram sendMessage params."""
        payload = {
            "text": response.text,
            "parse_mode": response.parse_mode or "Markdown"
        }

        if response.buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": btn.text, "callback_data": btn.callback_data}
                     for btn in row]
                    for row in response.buttons
                ]
            }

        return payload

    async def send_message(
        self,
        channel_id: str,
        response: UnifiedResponse
    ) -> None:
        """Send message via Telegram API."""
        payload = self.format_response(response)
        payload["chat_id"] = channel_id

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.api_base}/sendMessage",
                json=payload,
                timeout=10.0
            )

    async def send_typing(self, channel_id: str) -> None:
        """Send typing indicator."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.api_base}/sendChatAction",
                json={"chat_id": channel_id, "action": "typing"},
                timeout=5.0
            )

    async def handle_callback(self, callback_data: dict) -> Optional[str]:
        """Handle inline button press."""
        callback_query = callback_data
        data = callback_query.get("data", "")
        callback_id = callback_query.get("id")

        # Answer callback to remove loading state
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.api_base}/answerCallbackQuery",
                json={"callback_query_id": callback_id}
            )

        return data
```

## Future Adapters

### DiscordAdapter Skeleton

```python
# src/adapters/discord.py

class DiscordAdapter(BaseChannelAdapter):
    """Discord Bot adapter via discord.py."""

    platform = Platform.DISCORD

    def normalize_incoming(self, raw: dict) -> UnifiedMessage:
        # Convert Discord message to UnifiedMessage
        pass

    def format_response(self, response: UnifiedResponse) -> dict:
        # Convert to Discord embed/message
        pass
```

### SlackAdapter Skeleton

```python
# src/adapters/slack.py

class SlackAdapter(BaseChannelAdapter):
    """Slack Bot adapter via Bolt SDK."""

    platform = Platform.SLACK

    def normalize_incoming(self, raw: dict) -> UnifiedMessage:
        # Handle Slack events/mentions
        pass

    def format_response(self, response: UnifiedResponse) -> dict:
        # Convert to Slack blocks
        pass
```

## Directory Structure

```
src/adapters/
├── __init__.py
├── base.py           # BaseChannelAdapter ABC
├── models.py         # UnifiedMessage, UnifiedResponse, etc.
├── telegram.py       # TelegramAdapter (refactored)
├── discord.py        # DiscordAdapter (future)
└── slack.py          # SlackAdapter (future)
```

## Refactored Webhook Handler

```python
# In main.py

from src.adapters.telegram import TelegramAdapter

telegram_adapter = TelegramAdapter()

@web_app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    raw = await request.json()

    # Check for callback
    if "callback_query" in raw:
        data = await telegram_adapter.handle_callback(raw["callback_query"])
        return await process_callback(data, raw)

    # Normalize to unified message
    message = telegram_adapter.normalize_incoming(raw)

    if not message.text:
        return {"ok": True}

    # Process with core logic
    response_text = await process_unified_message(message)

    # Send response
    response = UnifiedResponse(text=response_text)
    await telegram_adapter.send_message(message.channel_id, response)

    return {"ok": True}
```

## Per-Channel State

Use `UnifiedMessage.state_key` for state management:

```python
# state_key = "telegram:12345" or "discord:67890"

async def get_conversation(message: UnifiedMessage) -> List[dict]:
    state = get_state_manager()
    return await state.get_conversation(message.state_key)

async def save_conversation(message: UnifiedMessage, msgs: List[dict]):
    state = get_state_manager()
    await state.add_message(message.state_key, msgs[-1])
```

## Implementation Steps

1. [ ] Create src/adapters/ directory structure
2. [ ] Implement models.py with dataclasses
3. [ ] Implement base.py with ABC
4. [ ] Refactor Telegram logic to TelegramAdapter
5. [ ] Update main.py to use adapter
6. [ ] Add adapter to state key format
7. [ ] Test with existing Telegram flow

## Todo List

- [ ] Handle Telegram media (photos, documents)
- [ ] Implement rate limiting per channel
- [ ] Add Discord skeleton
- [ ] Add Slack skeleton

## Success Criteria

- [ ] TelegramAdapter fully functional
- [ ] main.py simplified using adapter
- [ ] State management uses platform prefix
- [ ] Easy to add new channels
