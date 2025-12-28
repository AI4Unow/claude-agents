---
phase: 2
title: "Voice Message Support"
parent: plan.md
status: pending
effort: 3h
---

# Phase 2: Voice Message Support

## Context

- Parent: [plan.md](./plan.md)
- Depends on: [Phase 1](./phase-01-typing-indicators-ux.md)
- Code: `agents/main.py`, `agents/src/services/`

## Overview

Enable users to send voice messages that get transcribed and processed by the agentic loop.

## Requirements

1. Detect voice messages in webhook
2. Download voice file from Telegram
3. Transcribe using Whisper API (or Claude)
4. Process transcription through agentic loop
5. Respond with text (optional: TTS reply)

## Architecture

```
Voice Message → Download OGG → Transcribe (Whisper) → Agentic Loop → Response
                     ↓
            Telegram File API
                     ↓
            /getFile → file_path
                     ↓
            https://api.telegram.org/file/bot{token}/{file_path}
```

## Related Code Files

- `agents/main.py:191-238` - telegram_webhook
- NEW: `agents/src/services/transcription.py`

## Implementation Steps

### Step 1: Add voice message detection in webhook

```python
# In telegram_webhook, after extracting message:
voice = message.get("voice")
if voice:
    file_id = voice.get("file_id")
    duration = voice.get("duration")
    return await handle_voice_message(file_id, duration, user, chat_id)
```

### Step 2: Create transcription service

```python
# src/services/transcription.py
import httpx
import os

async def download_telegram_file(file_id: str) -> bytes:
    """Download file from Telegram servers."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    # Get file path
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id}
        )
        file_path = resp.json()["result"]["file_path"]

        # Download file content
        file_resp = await client.get(
            f"https://api.telegram.org/file/bot{token}/{file_path}"
        )
        return file_resp.content


async def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio using Whisper API."""
    import openai

    client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # Save to temp file (Whisper needs file)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        with open(temp_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"  # or auto-detect
            )
        return transcript.text
    finally:
        os.unlink(temp_path)
```

### Step 3: Add handle_voice_message function

```python
async def handle_voice_message(
    file_id: str,
    duration: int,
    user: dict,
    chat_id: int
) -> str:
    """Process voice message: download, transcribe, process."""
    from src.services.transcription import download_telegram_file, transcribe_audio
    import structlog

    logger = structlog.get_logger()
    logger.info("voice_message", duration=duration, user=user.get("id"))

    # Show "recording_voice" action while downloading
    await send_chat_action(chat_id, "record_voice")

    try:
        # Download
        audio_bytes = await download_telegram_file(file_id)

        # Show typing while transcribing
        await send_chat_action(chat_id, "typing")

        # Transcribe
        text = await transcribe_audio(audio_bytes)

        if not text or text.strip() == "":
            return "I couldn't understand the audio. Please try again."

        # Send transcription to user
        await send_telegram_message(
            chat_id,
            f"🎤 <i>Transcribed:</i>\n{text[:200]}..."
        )

        # Process through normal message handler
        return await process_message(text, user, chat_id)

    except Exception as e:
        logger.error("voice_error", error=str(e))
        return "Sorry, I couldn't process your voice message."
```

### Step 4: Add chat action helper

```python
async def send_chat_action(chat_id: int, action: str):
    """Send chat action (typing, upload_photo, record_voice, etc.)."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendChatAction",
            json={"chat_id": chat_id, "action": action}
        )
```

### Step 5: Add OpenAI secret to Modal

```bash
modal secret create openai-credentials OPENAI_API_KEY=sk-...
```

Update `secrets` list in main.py:
```python
secrets = [
    ...
    modal.Secret.from_name("openai-credentials"),
]
```

## Todo List

- [ ] Add voice detection in telegram_webhook
- [ ] Create src/services/transcription.py
- [ ] Implement download_telegram_file
- [ ] Implement transcribe_audio (Whisper)
- [ ] Add handle_voice_message to main.py
- [ ] Add send_chat_action helper
- [ ] Add OpenAI secret to Modal
- [ ] Test with various voice durations

## Success Criteria

- [ ] Voice messages detected and processed
- [ ] Transcription shown to user
- [ ] Response generated from transcribed text
- [ ] Duration limit enforced (< 60s)
- [ ] Proper error handling for failed transcriptions

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Whisper API cost | Medium | Limit duration to 60s |
| Large file download | Medium | Stream with timeout |
| Language detection | Low | Default to English or auto |

## Security Considerations

- Store OpenAI key in Modal secrets
- Validate file_id before download
- Limit voice duration to prevent abuse
- Delete temp files after processing

## Next Steps

After completion, proceed to [Phase 3](./phase-03-image-document-handling.md).
