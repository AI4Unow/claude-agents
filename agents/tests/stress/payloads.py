"""Telegram webhook payload generators for stress tests."""

import random
import time
from typing import Dict, Any, Optional, List


def _base_update(user_id: int, chat_id: int = None) -> Dict[str, Any]:
    """Create base update structure."""
    return {
        "update_id": random.randint(100_000, 999_999),
        "message": {
            "message_id": random.randint(1, 99_999),
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": f"StressUser{user_id}",
                "username": f"stress_user_{user_id}",
            },
            "chat": {
                "id": chat_id or user_id,
                "type": "private",
            },
            "date": int(time.time()),
        },
    }


def text_message(
    user_id: int,
    text: str,
    chat_id: int = None,
) -> Dict[str, Any]:
    """Generate text message payload."""
    update = _base_update(user_id, chat_id)
    update["message"]["text"] = text
    return update


def voice_message(
    user_id: int,
    duration: int = 10,
    chat_id: int = None,
) -> Dict[str, Any]:
    """Generate voice message payload with simulated file_id."""
    update = _base_update(user_id, chat_id)
    update["message"]["voice"] = {
        "file_id": f"voice_{random.randint(1000, 9999)}_{user_id}",
        "file_unique_id": f"unique_{random.randint(1000, 9999)}",
        "duration": duration,
        "mime_type": "audio/ogg",
        "file_size": duration * 5000,  # ~5KB/sec
    }
    return update


def image_message(
    user_id: int,
    caption: str = None,
    chat_id: int = None,
) -> Dict[str, Any]:
    """Generate photo message payload."""
    update = _base_update(user_id, chat_id)

    # Telegram sends multiple sizes
    update["message"]["photo"] = [
        {
            "file_id": f"photo_s_{random.randint(1000, 9999)}",
            "file_unique_id": f"unique_s_{random.randint(1000, 9999)}",
            "width": 320,
            "height": 240,
            "file_size": 15000,
        },
        {
            "file_id": f"photo_m_{random.randint(1000, 9999)}",
            "file_unique_id": f"unique_m_{random.randint(1000, 9999)}",
            "width": 800,
            "height": 600,
            "file_size": 50000,
        },
        {
            "file_id": f"photo_l_{random.randint(1000, 9999)}",
            "file_unique_id": f"unique_l_{random.randint(1000, 9999)}",
            "width": 1280,
            "height": 960,
            "file_size": 100000,
        },
    ]

    if caption:
        update["message"]["caption"] = caption

    return update


def document_message(
    user_id: int,
    filename: str = "test.pdf",
    mime_type: str = "application/pdf",
    caption: str = None,
    chat_id: int = None,
) -> Dict[str, Any]:
    """Generate document message payload."""
    update = _base_update(user_id, chat_id)
    update["message"]["document"] = {
        "file_id": f"doc_{random.randint(1000, 9999)}_{user_id}",
        "file_unique_id": f"unique_doc_{random.randint(1000, 9999)}",
        "file_name": filename,
        "mime_type": mime_type,
        "file_size": random.randint(10000, 500000),
    }

    if caption:
        update["message"]["caption"] = caption

    return update


def callback_query(
    user_id: int,
    data: str,
    chat_id: int = None,
    message_id: int = None,
) -> Dict[str, Any]:
    """Generate callback query payload for inline keyboard interactions."""
    return {
        "update_id": random.randint(100_000, 999_999),
        "callback_query": {
            "id": str(random.randint(100_000_000, 999_999_999)),
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": f"StressUser{user_id}",
                "username": f"stress_user_{user_id}",
            },
            "message": {
                "message_id": message_id or random.randint(1, 99_999),
                "chat": {
                    "id": chat_id or user_id,
                    "type": "private",
                },
                "date": int(time.time()) - 60,  # Message sent 1 min ago
            },
            "data": data,
        },
    }


# Callback data patterns
CALLBACK_PATTERNS = {
    "category_select": lambda cat: f"cat:{cat}",
    "skill_select": lambda skill: f"skill:{skill}",
    "improvement_approve": lambda id: f"approve:{id}",
    "improvement_reject": lambda id: f"reject:{id}",
}


def category_callback(user_id: int, category: str) -> Dict[str, Any]:
    """Generate category selection callback."""
    return callback_query(user_id, CALLBACK_PATTERNS["category_select"](category))


def skill_callback(user_id: int, skill_name: str) -> Dict[str, Any]:
    """Generate skill selection callback."""
    return callback_query(user_id, CALLBACK_PATTERNS["skill_select"](skill_name))


# Chaos payloads for testing error handling
def malformed_json() -> str:
    """Return malformed JSON string."""
    return '{"update_id": 123, "message": {broken'


def empty_payload() -> Dict:
    """Return empty payload."""
    return {}


def missing_message() -> Dict[str, Any]:
    """Return update without message field."""
    return {"update_id": random.randint(100_000, 999_999)}


def huge_payload(size_mb: int = 1) -> Dict[str, Any]:
    """Generate oversized payload for memory limit testing."""
    huge_text = "x" * (size_mb * 1024 * 1024)
    return text_message(1_000_001, huge_text)


def invalid_user_id() -> Dict[str, Any]:
    """Generate payload with invalid user ID."""
    update = text_message(-1, "test")  # Negative ID
    return update


def string_user_id() -> Dict[str, Any]:
    """Generate payload with string user ID (wrong type)."""
    update = text_message(1_000_001, "test")
    update["message"]["from"]["id"] = "not_a_number"
    return update
