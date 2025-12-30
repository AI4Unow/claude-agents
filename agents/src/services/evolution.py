"""Evolution API client for WhatsApp messaging.

Handles sending text, media, and interactive messages via Evolution API.
Uses circuit breaker for reliability.
"""
import os
import httpx
from typing import Optional, Tuple, List
from dataclasses import dataclass

from src.core.resilience import CircuitBreaker
from src.utils.logging import get_logger

logger = get_logger()

# Constants
MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

# Circuit breaker for Evolution API
evolution_circuit = CircuitBreaker("evolution", threshold=3, cooldown=30)


def get_config() -> Tuple[str, str, str]:
    """Get Evolution API configuration from environment."""
    return (
        os.environ.get("EVOLUTION_API_URL", ""),
        os.environ.get("EVOLUTION_API_KEY", ""),
        os.environ.get("EVOLUTION_INSTANCE", "main")
    )


def format_jid(phone: str) -> str:
    """Format phone number as WhatsApp JID."""
    # Remove any non-digit characters
    clean = ''.join(c for c in phone if c.isdigit())
    # Add suffix if not present
    if "@" not in phone:
        return f"{clean}@s.whatsapp.net"
    return phone


async def send_text(
    phone: str,
    text: str,
    quote_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Send text message via Evolution API.

    Args:
        phone: Recipient phone number
        text: Message text
        quote_id: Optional message ID to quote/reply to

    Returns:
        (success, message_id) tuple
    """
    api_url, api_key, instance = get_config()

    if not api_url or not api_key:
        logger.error("evolution_config_missing")
        return False, None

    url = f"{api_url}/message/sendText/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    # Handle long messages by chunking
    chunks = chunk_text(text)
    message_id = None

    for chunk in chunks:
        payload = {
            "number": format_jid(phone),
            "text": chunk
        }

        if quote_id and chunks.index(chunk) == 0:  # Only quote first chunk
            payload["quoted"] = {"key": {"id": quote_id}}

        try:
            success, msg_id = await evolution_circuit.call(
                _api_request, "POST", url, headers, payload
            )
            if success:
                message_id = msg_id
            else:
                return False, None
        except Exception as e:
            logger.error("evolution_send_text_error", error=str(e)[:100])
            return False, None

    return True, message_id


async def send_image(
    phone: str,
    image_url: str,
    caption: Optional[str] = None
) -> bool:
    """Send image via Evolution API."""
    api_url, api_key, instance = get_config()

    url = f"{api_url}/message/sendMedia/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    payload = {
        "number": format_jid(phone),
        "mediatype": "image",
        "media": image_url
    }

    if caption:
        payload["caption"] = caption[:MAX_CAPTION_LENGTH]

    try:
        success, _ = await evolution_circuit.call(
            _api_request, "POST", url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("evolution_send_image_error", error=str(e)[:100])
        return False


async def send_document(
    phone: str,
    document_url: str,
    filename: str,
    caption: Optional[str] = None
) -> bool:
    """Send document via Evolution API."""
    api_url, api_key, instance = get_config()

    url = f"{api_url}/message/sendMedia/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    payload = {
        "number": format_jid(phone),
        "mediatype": "document",
        "media": document_url,
        "fileName": filename
    }

    if caption:
        payload["caption"] = caption[:MAX_CAPTION_LENGTH]

    try:
        success, _ = await evolution_circuit.call(
            _api_request, "POST", url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("evolution_send_document_error", error=str(e)[:100])
        return False


async def send_audio(
    phone: str,
    audio_url: str,
    as_ptt: bool = True
) -> bool:
    """Send audio/voice message via Evolution API.

    Args:
        phone: Recipient phone
        audio_url: URL to audio file
        as_ptt: If True, send as voice note (push-to-talk)
    """
    api_url, api_key, instance = get_config()

    url = f"{api_url}/message/sendWhatsAppAudio/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    payload = {
        "number": format_jid(phone),
        "audio": audio_url,
        "encoding": True  # Enable PTT encoding
    }

    try:
        success, _ = await evolution_circuit.call(
            _api_request, "POST", url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("evolution_send_audio_error", error=str(e)[:100])
        return False


async def send_buttons(
    phone: str,
    text: str,
    buttons: List[dict],
    title: Optional[str] = None,
    footer: Optional[str] = None
) -> bool:
    """Send button message via Evolution API.

    Args:
        phone: Recipient phone
        text: Message body
        buttons: List of {"buttonId": "id", "buttonText": {"displayText": "Label"}}
        title: Optional title
        footer: Optional footer

    Note: WhatsApp limits to 3 buttons max.
    """
    api_url, api_key, instance = get_config()

    url = f"{api_url}/message/sendButtons/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    payload = {
        "number": format_jid(phone),
        "buttons": buttons[:3],  # Max 3 buttons
        "text": text
    }

    if title:
        payload["title"] = title
    if footer:
        payload["footer"] = footer

    try:
        success, _ = await evolution_circuit.call(
            _api_request, "POST", url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("evolution_send_buttons_error", error=str(e)[:100])
        return False


async def send_list(
    phone: str,
    text: str,
    button_text: str,
    sections: List[dict],
    title: Optional[str] = None,
    footer: Optional[str] = None
) -> bool:
    """Send list message via Evolution API.

    Args:
        phone: Recipient phone
        text: Message body
        button_text: Text on the list button
        sections: List of sections with rows
        title: Optional title
        footer: Optional footer
    """
    api_url, api_key, instance = get_config()

    url = f"{api_url}/message/sendList/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    payload = {
        "number": format_jid(phone),
        "title": title or "Menu",
        "text": text,
        "buttonText": button_text,
        "sections": sections
    }

    if footer:
        payload["footer"] = footer

    try:
        success, _ = await evolution_circuit.call(
            _api_request, "POST", url, headers, payload
        )
        return success
    except Exception as e:
        logger.error("evolution_send_list_error", error=str(e)[:100])
        return False


async def get_connection_state() -> Optional[str]:
    """Get WhatsApp connection state."""
    api_url, api_key, instance = get_config()

    url = f"{api_url}/instance/connectionState/{instance}"
    headers = {"apikey": api_key}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("instance", {}).get("state")
    except Exception as e:
        logger.error("evolution_connection_state_error", error=str(e)[:50])

    return None


async def _api_request(
    method: str,
    url: str,
    headers: dict,
    payload: dict
) -> Tuple[bool, Optional[str]]:
    """Make API request to Evolution."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "POST":
            response = await client.post(url, headers=headers, json=payload)
        else:
            response = await client.get(url, headers=headers)

        if response.status_code in (200, 201):
            data = response.json()
            msg_id = data.get("key", {}).get("id")
            return True, msg_id

        logger.warning("evolution_api_error",
            status=response.status_code,
            url=url,
            body=response.text[:200]
        )
        return False, None


async def download_media(media_url: str) -> Optional[bytes]:
    """Download media from WhatsApp CDN via Evolution API.

    Note: Evolution API provides direct CDN URLs that require
    the apikey header for authentication.

    Args:
        media_url: URL from message payload

    Returns:
        Media bytes or None on failure
    """
    api_url, api_key, _ = get_config()

    if not media_url:
        return None

    # Evolution provides base64 endpoint for media
    # Or we can try direct download with auth

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Try direct download first (some CDN URLs work directly)
            response = await client.get(media_url, follow_redirects=True)

            if response.status_code == 200:
                return response.content

            # If direct fails, media might need Evolution proxy
            logger.warning("evolution_media_direct_failed", status=response.status_code)
            return None

    except Exception as e:
        logger.error("evolution_download_error", error=str(e)[:100])
        return None


async def get_media_base64(message_id: str) -> Optional[str]:
    """Get media as base64 from Evolution API.

    Alternative method using Evolution's media endpoint.
    """
    api_url, api_key, instance = get_config()

    url = f"{api_url}/chat/getBase64FromMediaMessage/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    payload = {
        "message": {"key": {"id": message_id}},
        "convertToMp4": False
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("base64")

    except Exception as e:
        logger.error("evolution_get_base64_error", error=str(e)[:100])

    return None


def chunk_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> List[str]:
    """Split long text into chunks."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_length:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > max_length:
                # Hard split
                for i in range(0, len(para), max_length - 10):
                    chunks.append(para[i:i + max_length - 10])
                current = ""
            else:
                current = para + "\n\n"

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_length]]
