# Phase 4: Unified Messaging Abstraction

**Status:** Ready
**Dependencies:** Phase 2, Phase 3
**Output:** `src/core/messaging.py` - platform-agnostic layer

## Overview

Create abstraction layer to normalize messages across platforms. Enables code reuse and consistent handling regardless of source (Telegram, WhatsApp, future platforms).

## Design Rationale

**Current State:**
- Telegram webhook extracts `message.from.id`, `message.text`, `message.voice`, etc.
- WhatsApp webhook extracts `messages[0].from`, `messages[0].text.body`, etc.
- Different user ID formats (int vs phone string)
- Different formatting (HTML vs WhatsApp markdown)
- Same processing logic duplicated

**Target State:**
- Single `NormalizedMessage` dataclass
- Platform adapters convert raw payloads
- Shared processing pipeline
- Platform-specific formatters for output

## Tasks

### 4.1 Create Messaging Module

**Create `src/core/messaging.py`:**

```python
"""Platform-agnostic messaging abstraction.

Normalizes messages from Telegram, WhatsApp, and future platforms
into a common format for unified processing.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Protocol, Callable, Awaitable
from abc import ABC, abstractmethod


class Platform(Enum):
    """Supported messaging platforms."""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"


class MessageType(Enum):
    """Normalized message types."""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    DOCUMENT = "document"
    COMMAND = "command"
    CALLBACK = "callback"


@dataclass
class MediaInfo:
    """Normalized media information."""
    media_id: str  # Platform-specific ID
    mime_type: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[int] = None  # For voice/video
    caption: Optional[str] = None


@dataclass
class UserInfo:
    """Normalized user information."""
    user_id: str  # Normalized to string (phone or int->str)
    platform: Platform
    display_name: str
    username: Optional[str] = None
    language_code: Optional[str] = None

    @property
    def platform_user_id(self) -> Any:
        """Get platform-native user ID format."""
        if self.platform == Platform.TELEGRAM:
            return int(self.user_id)
        return self.user_id  # Phone string for WhatsApp


@dataclass
class NormalizedMessage:
    """Platform-agnostic message representation."""
    message_id: str
    chat_id: str  # Normalized to string
    user: UserInfo
    message_type: MessageType
    platform: Platform
    timestamp: str  # ISO format

    # Content (depends on type)
    text: Optional[str] = None
    media: Optional[MediaInfo] = None

    # For commands
    command: Optional[str] = None
    command_args: Optional[str] = None

    # For callbacks (button presses)
    callback_data: Optional[str] = None

    # Raw payload for platform-specific handling
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_command(self) -> bool:
        return self.message_type == MessageType.COMMAND or (
            self.text and self.text.startswith("/")
        )
```

### 4.2 Platform Adapters

```python
class PlatformAdapter(ABC):
    """Abstract base for platform-specific adapters."""

    @abstractmethod
    def parse_message(self, raw_payload: Dict) -> Optional[NormalizedMessage]:
        """Parse raw webhook payload into normalized message."""
        pass

    @abstractmethod
    async def send_text(self, chat_id: str, text: str, reply_to: Optional[str] = None) -> bool:
        """Send text message."""
        pass

    @abstractmethod
    async def send_typing(self, chat_id: str) -> bool:
        """Send typing indicator."""
        pass

    @abstractmethod
    def format_text(self, text: str) -> str:
        """Format text for platform (HTML for Telegram, markdown for WhatsApp)."""
        pass


class TelegramAdapter(PlatformAdapter):
    """Telegram platform adapter."""

    def parse_message(self, raw_payload: Dict) -> Optional[NormalizedMessage]:
        """Parse Telegram update into NormalizedMessage."""
        message = raw_payload.get("message", {})
        if not message:
            # Check for callback query
            callback = raw_payload.get("callback_query")
            if callback:
                return self._parse_callback(callback)
            return None

        user_data = message.get("from", {})
        chat = message.get("chat", {})

        user = UserInfo(
            user_id=str(user_data.get("id", "")),
            platform=Platform.TELEGRAM,
            display_name=user_data.get("first_name", "User"),
            username=user_data.get("username"),
            language_code=user_data.get("language_code")
        )

        # Determine message type and content
        text = message.get("text", "")
        msg_type = MessageType.TEXT
        media = None
        command = None
        command_args = None

        if text.startswith("/"):
            msg_type = MessageType.COMMAND
            parts = text.split(None, 1)
            command = parts[0][1:]  # Remove /
            command_args = parts[1] if len(parts) > 1 else None

        if message.get("voice"):
            msg_type = MessageType.VOICE
            voice = message["voice"]
            media = MediaInfo(
                media_id=voice["file_id"],
                mime_type=voice.get("mime_type"),
                duration_seconds=voice.get("duration")
            )

        if message.get("photo"):
            msg_type = MessageType.IMAGE
            photo = message["photo"][-1]  # Largest
            media = MediaInfo(
                media_id=photo["file_id"],
                size_bytes=photo.get("file_size")
            )
            text = message.get("caption", "")

        if message.get("document"):
            msg_type = MessageType.DOCUMENT
            doc = message["document"]
            media = MediaInfo(
                media_id=doc["file_id"],
                mime_type=doc.get("mime_type"),
                filename=doc.get("file_name"),
                size_bytes=doc.get("file_size")
            )
            text = message.get("caption", "")

        return NormalizedMessage(
            message_id=str(message.get("message_id", "")),
            chat_id=str(chat.get("id", "")),
            user=user,
            message_type=msg_type,
            platform=Platform.TELEGRAM,
            timestamp=str(message.get("date", "")),
            text=text,
            media=media,
            command=command,
            command_args=command_args,
            raw=raw_payload
        )

    def _parse_callback(self, callback: Dict) -> NormalizedMessage:
        """Parse callback query."""
        user_data = callback.get("from", {})
        message = callback.get("message", {})

        user = UserInfo(
            user_id=str(user_data.get("id", "")),
            platform=Platform.TELEGRAM,
            display_name=user_data.get("first_name", "User"),
            username=user_data.get("username")
        )

        return NormalizedMessage(
            message_id=callback.get("id", ""),
            chat_id=str(message.get("chat", {}).get("id", "")),
            user=user,
            message_type=MessageType.CALLBACK,
            platform=Platform.TELEGRAM,
            timestamp="",
            callback_data=callback.get("data"),
            raw=callback
        )

    async def send_text(self, chat_id: str, text: str, reply_to: Optional[str] = None) -> bool:
        """Send via Telegram."""
        from src.services.telegram import markdown_to_html, chunk_message
        # Import existing send function
        # ... implementation uses existing telegram send logic
        return True

    async def send_typing(self, chat_id: str) -> bool:
        """Send typing via Telegram."""
        return True

    def format_text(self, text: str) -> str:
        """Format as Telegram HTML."""
        from src.services.telegram import markdown_to_html
        return markdown_to_html(text)


class WhatsAppAdapter(PlatformAdapter):
    """WhatsApp platform adapter."""

    def parse_message(self, raw_payload: Dict) -> Optional[NormalizedMessage]:
        """Parse WhatsApp webhook into NormalizedMessage."""
        entry = raw_payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        messages = value.get("messages", [])
        if not messages:
            return None

        message = messages[0]
        contacts = value.get("contacts", [{}])
        contact = contacts[0] if contacts else {}

        phone = message.get("from", "")
        user = UserInfo(
            user_id=phone,
            platform=Platform.WHATSAPP,
            display_name=contact.get("profile", {}).get("name", "User")
        )

        msg_type_str = message.get("type", "text")
        text = ""
        media = None
        command = None
        command_args = None

        if msg_type_str == "text":
            text = message.get("text", {}).get("body", "")
            msg_type = MessageType.TEXT
            if text.startswith("/"):
                msg_type = MessageType.COMMAND
                parts = text.split(None, 1)
                command = parts[0][1:]
                command_args = parts[1] if len(parts) > 1 else None

        elif msg_type_str == "audio":
            msg_type = MessageType.VOICE
            audio = message.get("audio", {})
            media = MediaInfo(
                media_id=audio.get("id", ""),
                mime_type=audio.get("mime_type")
            )

        elif msg_type_str == "image":
            msg_type = MessageType.IMAGE
            image = message.get("image", {})
            media = MediaInfo(
                media_id=image.get("id", ""),
                mime_type=image.get("mime_type")
            )
            text = image.get("caption", "")

        elif msg_type_str == "document":
            msg_type = MessageType.DOCUMENT
            doc = message.get("document", {})
            media = MediaInfo(
                media_id=doc.get("id", ""),
                mime_type=doc.get("mime_type"),
                filename=doc.get("filename")
            )
            text = doc.get("caption", "")

        elif msg_type_str == "interactive":
            # Button response
            msg_type = MessageType.CALLBACK
            interactive = message.get("interactive", {})
            button = interactive.get("button_reply", {})
            return NormalizedMessage(
                message_id=message.get("id", ""),
                chat_id=phone,
                user=user,
                message_type=msg_type,
                platform=Platform.WHATSAPP,
                timestamp=str(message.get("timestamp", "")),
                callback_data=button.get("id"),
                raw=raw_payload
            )
        else:
            msg_type = MessageType.TEXT

        return NormalizedMessage(
            message_id=message.get("id", ""),
            chat_id=phone,
            user=user,
            message_type=msg_type,
            platform=Platform.WHATSAPP,
            timestamp=str(message.get("timestamp", "")),
            text=text,
            media=media,
            command=command,
            command_args=command_args,
            raw=raw_payload
        )

    async def send_text(self, chat_id: str, text: str, reply_to: Optional[str] = None) -> bool:
        """Send via WhatsApp."""
        from src.services.whatsapp import send_message
        success, _ = await send_message(chat_id, text, reply_to)
        return success

    async def send_typing(self, chat_id: str) -> bool:
        """WhatsApp doesn't have typing indicator."""
        return True

    def format_text(self, text: str) -> str:
        """Format as WhatsApp markdown."""
        from src.services.whatsapp import markdown_to_whatsapp
        return markdown_to_whatsapp(text)
```

### 4.3 Adapter Registry

```python
# Adapter instances
_adapters: Dict[Platform, PlatformAdapter] = {}


def get_adapter(platform: Platform) -> PlatformAdapter:
    """Get adapter for platform."""
    if platform not in _adapters:
        if platform == Platform.TELEGRAM:
            _adapters[platform] = TelegramAdapter()
        elif platform == Platform.WHATSAPP:
            _adapters[platform] = WhatsAppAdapter()
        else:
            raise ValueError(f"Unknown platform: {platform}")
    return _adapters[platform]


def parse_webhook(platform: Platform, payload: Dict) -> Optional[NormalizedMessage]:
    """Parse webhook payload into normalized message."""
    return get_adapter(platform).parse_message(payload)
```

### 4.4 Update main.py to Use Abstraction

**Refactor telegram webhook:**

```python
@web_app.post("/webhook/telegram")
@limiter.limit("30/minute")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates."""
    from src.core.messaging import parse_webhook, Platform

    if not await verify_telegram_webhook(request):
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        data = await request.json()

        # Parse to normalized message
        msg = parse_webhook(Platform.TELEGRAM, data)
        if not msg:
            return {"ok": True}

        # Process normalized message
        response = await process_normalized_message(msg)

        if response:
            await send_telegram_message(int(msg.chat_id), response)

        return {"ok": True}

    except Exception as e:
        logger.error("webhook_error", error=str(e))
        return {"ok": False, "error": str(e)}
```

**Refactor whatsapp webhook:**

```python
@web_app.api_route("/webhook/whatsapp", methods=["GET", "POST"])
async def whatsapp_webhook(request: Request):
    from src.core.messaging import parse_webhook, Platform

    if request.method == "GET":
        # Verification...
        ...

    if not await verify_whatsapp_signature(request):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = await request.json()

        msg = parse_webhook(Platform.WHATSAPP, data)
        if not msg:
            return {"status": "ok"}

        response = await process_normalized_message(msg)

        if response:
            from src.services.whatsapp import send_message
            await send_message(msg.chat_id, response)

        return {"status": "ok"}

    except Exception as e:
        logger.error("whatsapp_webhook_error", error=str(e))
        return {"status": "error"}
```

### 4.5 Unified Message Processing

```python
async def process_normalized_message(msg: NormalizedMessage) -> Optional[str]:
    """Process any platform message through unified pipeline."""
    from src.core.messaging import MessageType

    # Convert user info to dict format expected by existing code
    user = {
        "id": msg.user.platform_user_id,
        "first_name": msg.user.display_name,
        "username": msg.user.username,
        "platform": msg.platform.value
    }

    chat_id = msg.user.platform_user_id  # For Telegram int, for WhatsApp phone

    if msg.message_type == MessageType.COMMAND:
        return await handle_command(f"/{msg.command} {msg.command_args or ''}", user, chat_id)

    elif msg.message_type == MessageType.TEXT:
        return await process_message(msg.text, user, chat_id)

    elif msg.message_type == MessageType.VOICE:
        return await handle_voice_message_unified(msg)

    elif msg.message_type == MessageType.IMAGE:
        return await handle_image_message_unified(msg)

    elif msg.message_type == MessageType.DOCUMENT:
        return await handle_document_message_unified(msg)

    elif msg.message_type == MessageType.CALLBACK:
        return await handle_callback_unified(msg)

    return None
```

## File Changes

| File | Change |
|------|--------|
| `src/core/messaging.py` | Create - abstraction layer |
| `main.py` | Refactor webhooks to use abstraction |

## Verification

- [ ] Telegram messages parse correctly
- [ ] WhatsApp messages parse correctly
- [ ] Commands work on both platforms
- [ ] Text processing works on both platforms
- [ ] User IDs normalized correctly
