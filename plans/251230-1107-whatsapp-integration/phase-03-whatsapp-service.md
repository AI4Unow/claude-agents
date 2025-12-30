# Phase 3: WhatsApp Service Module

**Status:** Ready
**Dependencies:** Phase 2
**Output:** `src/services/whatsapp.py` - mirrors telegram.py

## Overview

Create dedicated WhatsApp service module for message formatting, media handling, and API calls. Mirrors structure of `telegram.py`.

## Tasks

### 3.1 Create Base Module

**Create `src/services/whatsapp.py`:**

```python
"""WhatsApp Cloud API message formatting and utilities.

Mirrors telegram.py structure for consistency.
WhatsApp uses limited formatting: *bold*, _italic_, ```code```, ~~strike~~
"""
import re
import os
import httpx
from typing import List, Optional, Tuple
from dataclasses import dataclass

from src.utils.logging import get_logger
from src.core.resilience import CircuitBreaker

logger = get_logger()

# WhatsApp limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

# Circuit breaker for WhatsApp API
whatsapp_circuit = CircuitBreaker("whatsapp", threshold=3, cooldown=30)
```

### 3.2 Message Formatting Functions

WhatsApp supports limited formatting vs Telegram HTML.

```python
def markdown_to_whatsapp(text: str) -> str:
    """Convert markdown to WhatsApp formatting.

    WhatsApp supports:
    - *bold* (single asterisks)
    - _italic_ (underscores)
    - ~strikethrough~ (tildes)
    - ```code``` (backticks, monospace)
    - ```lang\ncode``` (code blocks)

    Does NOT support: links, headers, lists (kept as-is)
    """
    # Code blocks: keep triple backticks as-is (WhatsApp renders them)
    # Already correct format

    # Convert **bold** to *bold* (WhatsApp uses single asterisks)
    text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)

    # Convert ~~strike~~ to ~strike~ (WhatsApp uses single tildes)
    text = re.sub(r'~~([^~]+)~~', r'~\1~', text)

    # Keep _italic_ as-is (same format)

    # Keep `code` as-is (same format)

    # Convert markdown links [text](url) to "text (url)"
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)

    # Headers: convert # Header to *Header* (bold)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)

    # Lists: keep - item and * item as-is (readable without formatting)
    # Could convert to emoji bullets if desired

    return text


def escape_whatsapp(text: str) -> str:
    """Escape WhatsApp formatting characters.

    Use when text should be literal (e.g., code output).
    """
    # Escape formatting characters with backslash
    chars = ['*', '_', '~', '`']
    for char in chars:
        text = text.replace(char, '\\' + char)
    return text
```

### 3.3 Message Chunking

```python
def chunk_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split long message into chunks respecting formatting.

    Same logic as telegram.py but for WhatsApp limits.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_length:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())

            if len(para) > max_length:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current = ""
                for sentence in sentences:
                    if len(current) + len(sentence) + 1 <= max_length:
                        current += sentence + " "
                    else:
                        if current:
                            chunks.append(current.strip())
                        if len(sentence) > max_length:
                            for i in range(0, len(sentence), max_length - 10):
                                chunks.append(sentence[i:i + max_length - 10])
                            current = ""
                        else:
                            current = sentence + " "
            else:
                current = para + "\n\n"

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_length]]
```

### 3.4 Send Message Functions

```python
async def send_message(
    phone: str,
    text: str,
    reply_to: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Send text message via WhatsApp Cloud API.

    Args:
        phone: Recipient phone number (with country code)
        text: Message text
        reply_to: Optional message ID to reply to

    Returns:
        (success, message_id) tuple
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    if not token or not phone_id:
        logger.error("whatsapp_credentials_missing")
        return False, None

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}

    # Format text for WhatsApp
    formatted = markdown_to_whatsapp(text)

    # Handle long messages
    chunks = chunk_message(formatted)

    message_id = None
    for chunk in chunks:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"body": chunk}
        }

        if reply_to:
            payload["context"] = {"message_id": reply_to}

        try:
            success, msg_id = await whatsapp_circuit.call(
                _send_api_request, url, headers, payload
            )
            if success and msg_id:
                message_id = msg_id
            if not success:
                return False, None
        except Exception as e:
            logger.error("whatsapp_send_error", error=str(e)[:100])
            return False, None

    return True, message_id


async def _send_api_request(url: str, headers: dict, payload: dict) -> Tuple[bool, Optional[str]]:
    """Make API request to WhatsApp."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            msg_id = data.get("messages", [{}])[0].get("id")
            return True, msg_id

        logger.warning("whatsapp_api_error",
            status=response.status_code,
            body=response.text[:200]
        )
        return False, None
```

### 3.5 Send Media Functions

```python
async def send_image(
    phone: str,
    image_url: str,
    caption: Optional[str] = None
) -> bool:
    """Send image via WhatsApp."""
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "image",
        "image": {"link": image_url}
    }

    if caption:
        payload["image"]["caption"] = caption[:MAX_CAPTION_LENGTH]

    try:
        success, _ = await whatsapp_circuit.call(
            _send_api_request, url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("whatsapp_send_image_error", error=str(e)[:100])
        return False


async def send_document(
    phone: str,
    document_url: str,
    filename: str,
    caption: Optional[str] = None
) -> bool:
    """Send document via WhatsApp."""
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "document",
        "document": {
            "link": document_url,
            "filename": filename
        }
    }

    if caption:
        payload["document"]["caption"] = caption[:MAX_CAPTION_LENGTH]

    try:
        success, _ = await whatsapp_circuit.call(
            _send_api_request, url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("whatsapp_send_document_error", error=str(e)[:100])
        return False
```

### 3.6 Download Media Functions

```python
async def download_media(media_id: str) -> Optional[bytes]:
    """Download media from WhatsApp CDN.

    WhatsApp requires two API calls:
    1. Get media URL from media_id
    2. Download from URL

    Args:
        media_id: WhatsApp media ID

    Returns:
        Media bytes or None on failure
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    if not token:
        return None

    # Step 1: Get media URL
    url = f"https://graph.facebook.com/v21.0/{media_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                logger.warning("whatsapp_media_url_error", status=response.status_code)
                return None

            media_url = response.json().get("url")
            if not media_url:
                return None

            # Step 2: Download media
            media_response = await client.get(media_url, headers=headers)
            if media_response.status_code == 200:
                return media_response.content

            return None
    except Exception as e:
        logger.error("whatsapp_download_error", error=str(e)[:100])
        return None
```

### 3.7 Reply Buttons (Interactive Messages)

```python
async def send_buttons(
    phone: str,
    body: str,
    buttons: List[dict],
    header: Optional[str] = None,
    footer: Optional[str] = None
) -> bool:
    """Send interactive button message.

    Args:
        phone: Recipient phone
        body: Message body text
        buttons: List of {"id": "btn_id", "title": "Button Text"}
        header: Optional header text
        footer: Optional footer text

    WhatsApp limits: max 3 buttons, 20 chars per title
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}

    # Format buttons
    formatted_buttons = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
        for b in buttons[:3]  # Max 3 buttons
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": formatted_buttons}
        }
    }

    if header:
        payload["interactive"]["header"] = {"type": "text", "text": header}
    if footer:
        payload["interactive"]["footer"] = {"text": footer}

    try:
        success, _ = await whatsapp_circuit.call(
            _send_api_request, url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("whatsapp_buttons_error", error=str(e)[:100])
        return False
```

### 3.8 Typing Indicator

```python
async def send_typing(phone: str) -> bool:
    """Send typing indicator (mark as read + typing)."""
    # WhatsApp doesn't have explicit typing indicator
    # But we can mark messages as read
    return True  # No-op for now
```

## File Created

| File | Description |
|------|-------------|
| `src/services/whatsapp.py` | Complete WhatsApp service module |

## Verification

- [ ] Module imports without errors
- [ ] `send_message()` sends text successfully
- [ ] `markdown_to_whatsapp()` converts formatting correctly
- [ ] `chunk_message()` splits long messages
- [ ] `download_media()` retrieves media bytes
- [ ] Circuit breaker protects API calls
