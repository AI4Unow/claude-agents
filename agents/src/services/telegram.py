"""Telegram message formatting utilities.

Provides HTML conversion, message chunking, and skill result formatting
for Telegram Bot API 4096 character limit.
"""
import re
from typing import List

MAX_MESSAGE_LENGTH = 4096
CODE_BLOCK_PATTERN = r'```(\w+)?\n([\s\S]*?)```'


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))


def format_code_blocks(text: str) -> str:
    """Convert markdown code blocks to HTML <pre><code>."""
    def replace_block(match):
        lang = match.group(1) or ""
        code = escape_html(match.group(2))
        if lang:
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
        return f'<pre>{code}</pre>'

    return re.sub(CODE_BLOCK_PATTERN, replace_block, text)


def format_inline_code(text: str) -> str:
    """Convert `code` to <code>code</code>."""
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', text)


def format_bold(text: str) -> str:
    """Convert **bold** to <b>bold</b>."""
    return re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)


def format_italic(text: str) -> str:
    """Convert _italic_ to <i>italic</i>."""
    return re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<i>\1</i>', text)


def markdown_to_html(text: str) -> str:
    """Convert markdown to Telegram HTML.

    Order matters: code blocks first to avoid formatting inside code.
    """
    text = format_code_blocks(text)
    text = format_inline_code(text)
    text = format_bold(text)
    text = format_italic(text)
    return text


def chunk_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split long message into chunks respecting formatting.

    Tries to split at paragraph boundaries first, then sentences.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    # Split by paragraphs first
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_length:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())

            # Handle paragraph longer than max_length
            if len(para) > max_length:
                # Split by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current = ""
                for sentence in sentences:
                    if len(current) + len(sentence) + 1 <= max_length:
                        current += sentence + " "
                    else:
                        if current:
                            chunks.append(current.strip())
                        # If single sentence too long, hard split
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


def format_skill_result(skill_name: str, result: str, duration_ms: int) -> str:
    """Format skill execution result with header and footer."""
    header = f"<b>Skill:</b> {skill_name}\n\n"
    footer = f"\n\n<i>Duration: {duration_ms}ms</i>"

    # Calculate available space for result
    overhead = len(header) + len(footer) + 20
    available = MAX_MESSAGE_LENGTH - overhead

    # Escape HTML in result but preserve already-formatted content
    if len(result) > available:
        result = result[:available] + "..."

    return header + result + footer


def format_improvement_proposal(proposal: dict) -> str:
    """Format improvement proposal for Telegram HTML."""
    skill = escape_html(proposal.get("skill_name", "unknown"))
    error = escape_html(proposal.get("error_summary", "")[:300])
    memory = escape_html(proposal.get("proposed_memory_addition", "")[:500])
    error_entry = escape_html(proposal.get("proposed_error_entry", "")[:200])
    proposal_id = proposal.get("id", "?")[:8]

    return f"""🔧 <b>Improvement Proposal</b>

<b>Skill:</b> {skill}

<b>Error:</b>
<pre>{error}</pre>

<b>Proposed Memory Addition:</b>
<pre>{memory}</pre>

<b>Error History Entry:</b>
<pre>{error_entry}</pre>

<i>Proposal ID: {proposal_id}...</i>"""


def build_improvement_keyboard(proposal_id: str) -> list:
    """Build inline keyboard for approve/reject."""
    return [
        [
            {"text": "✅ Approve", "callback_data": f"improve_approve:{proposal_id}"},
            {"text": "❌ Reject", "callback_data": f"improve_reject:{proposal_id}"},
        ]
    ]


async def update_progress_message(
    chat_id: int,
    message_id: int,
    text: str,
    bot_token: str = None,
) -> bool:
    """Update existing message with progress (for streaming).

    Uses edit_message_text to update in-place.
    Rate limited by Telegram to ~30 edits/minute.

    Args:
        chat_id: Telegram chat ID
        message_id: Message ID to update
        text: New message text
        bot_token: Optional bot token override

    Returns:
        True if update successful
    """
    import httpx
    import os

    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/editMessageText"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
            })
            return response.status_code == 200
    except Exception:
        return False


async def send_with_progress(
    chat_id: int,
    initial_text: str,
    bot_token: str = None,
) -> int:
    """Send initial message and return message_id for progress updates.

    Args:
        chat_id: Telegram chat ID
        initial_text: Initial message text
        bot_token: Optional bot token override

    Returns:
        message_id for subsequent updates, 0 if failed
    """
    import httpx
    import os

    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": initial_text,
                "parse_mode": "HTML",
            })
            if response.status_code == 200:
                return response.json()["result"]["message_id"]
            return 0
    except Exception:
        return 0
