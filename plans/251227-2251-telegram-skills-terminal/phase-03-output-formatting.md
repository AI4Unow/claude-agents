---
phase: 3
title: "Output Formatting"
status: pending
effort: 1.5h
---

# Phase 3: Output Formatting

## Objective

Enhance Telegram message formatting with HTML mode, code blocks, and long output chunking.

## Implementation Steps

### 1. Create telegram.py utilities module

**New file**: `agents/src/services/telegram.py`

```python
"""Telegram message formatting utilities."""
import re
from typing import List, Tuple

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


def markdown_to_html(text: str) -> str:
    """Convert markdown to Telegram HTML."""
    text = format_code_blocks(text)
    text = format_inline_code(text)
    text = format_bold(text)
    return text


def chunk_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split long message into chunks respecting formatting."""
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
                        current = sentence + " "
            else:
                current = para + "\n\n"

    if current:
        chunks.append(current.strip())

    return chunks


def format_skill_result(skill_name: str, result: str, duration_ms: int) -> str:
    """Format skill execution result."""
    header = f"<b>Skill:</b> {skill_name}\n"
    footer = f"\n\n<i>Duration: {duration_ms}ms</i>"

    # Calculate available space for result
    available = MAX_MESSAGE_LENGTH - len(header) - len(footer) - 10

    if len(result) > available:
        result = result[:available] + "..."

    return header + result + footer
```

### 2. Update send_telegram_message()

**Modify** main.py send_telegram_message():

```python
async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """Send message via Telegram API with formatting."""
    import httpx
    from src.services.telegram import chunk_message, markdown_to_html

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False

    # Convert markdown to HTML if using HTML mode
    if parse_mode == "HTML":
        text = markdown_to_html(text)

    # Chunk if too long
    chunks = chunk_message(text)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in chunks:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode
                }
            )
            result = response.json()
            if not result.get("ok"):
                # Fallback to no parsing if HTML fails
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk}
                )

    return True
```

### 3. Format skill execution output

**Update** /skill handler to use formatting:

```python
elif cmd == "/skill":
    # ... validation ...

    import time
    start = time.time()
    result = await execute_skill_simple(skill_name, task, {"user": user})
    duration_ms = int((time.time() - start) * 1000)

    from src.services.telegram import format_skill_result
    return format_skill_result(skill_name, result, duration_ms)
```

### 4. Add file attachment fallback

For very long outputs (>4 chunks):

```python
async def send_as_file(chat_id: int, content: str, filename: str):
    """Send long content as file attachment."""
    import httpx
    import io

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=60.0) as client:
        files = {"document": (filename, io.BytesIO(content.encode()))}
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat_id},
            files=files
        )
        return response.json()
```

## Code Changes Summary

| File | Section | Change |
|------|---------|--------|
| src/services/telegram.py | new file | Formatting utilities |
| main.py | send_telegram_message() | Add HTML conversion, chunking |
| main.py | /skill handler | Use format_skill_result() |

## Testing

1. Send skill output with code blocks - Should render as `<pre>`
2. Send output >4096 chars - Should split into multiple messages
3. Send malformed HTML - Should fallback to plain text

## Success Criteria

- [ ] Code blocks render correctly in Telegram
- [ ] Long outputs split without breaking mid-word
- [ ] Skill results show name and duration
- [ ] HTML parse errors fallback gracefully

## Risks

| Risk | Mitigation |
|------|------------|
| HTML escaping missed | Use escape_html() for all user content |
| Code block split mid-block | Keep code blocks intact in chunking |
| Very long single paragraph | Split by sentences as fallback |
