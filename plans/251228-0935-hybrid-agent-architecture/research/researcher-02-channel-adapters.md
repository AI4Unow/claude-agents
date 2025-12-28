# Research: Multi-Channel Adapter Pattern

**Date:** 2025-12-28
**Topic:** Unified interface for Discord, Slack, Telegram, WhatsApp

## Core Concept

Decouple **Chatbot Logic** from **Messaging Platforms** via abstraction layer.

## Key Components

### 1. Unified Data Models

```python
@dataclass
class UnifiedMessage:
    message_id: str
    user_id: str
    channel_id: str
    platform: str  # telegram, discord, slack
    text: str
    timestamp: datetime
    attachments: List[Attachment]
    raw_data: dict  # Platform-specific metadata

@dataclass
class UnifiedResponse:
    text: str
    buttons: Optional[List[Button]]
    attachments: Optional[List[Attachment]]
```

### 2. Adapter Interface

```python
class BaseChannelAdapter(ABC):
    @abstractmethod
    async def connect(self): ...

    @abstractmethod
    async def disconnect(self): ...

    @abstractmethod
    async def send_message(self, response: UnifiedResponse): ...

    @abstractmethod
    def normalize_incoming(self, raw: dict) -> UnifiedMessage: ...

    @abstractmethod
    def format_response(self, response: UnifiedResponse) -> dict: ...
```

### 3. Platform Adapters

| Adapter | SDK | Notes |
|---------|-----|-------|
| TelegramAdapter | python-telegram-bot | Webhook/polling |
| DiscordAdapter | discord.py | Gateway WebSocket |
| SlackAdapter | Slack Bolt | Events API + Challenge |
| WhatsAppAdapter | Meta Cloud API | Webhook |

## Workflow

```
[Platform Webhook] → Adapter.normalize() → UnifiedMessage
                                               ↓
                                        Core Logic (AgenticLoop)
                                               ↓
                                        UnifiedResponse
                                               ↓
[Platform API] ← Adapter.format() ← UnifiedResponse
```

## Benefits

- **Modularity:** New channel = new adapter only
- **Consistency:** Same bot personality everywhere
- **Maintenance:** Fix once, apply everywhere

## Application to Agents Project

Current: Telegram only (in main.py)
Target: Extract to `src/adapters/` with unified interface

```
src/adapters/
├── base.py           # BaseChannelAdapter
├── telegram.py       # TelegramAdapter (refactor from main.py)
├── discord.py        # Future
└── slack.py          # Future
```

## Citations

- Microsoft Bot Framework Connectors
- Slack Bolt SDK
- discord.py Documentation
