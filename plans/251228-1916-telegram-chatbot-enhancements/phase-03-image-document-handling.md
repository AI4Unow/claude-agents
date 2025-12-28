---
phase: 3
title: "Image & Document Handling"
parent: plan.md
status: pending
effort: 3h
---

# Phase 3: Image & Document Handling

## Context

- Parent: [plan.md](./plan.md)
- Depends on: [Phase 2](./phase-02-voice-support.md)
- Code: `agents/main.py`, `agents/src/services/`

## Overview

Enable users to send images for analysis (Claude Vision) and documents for processing.

## Requirements

1. Detect photo/document in webhook
2. Download media from Telegram
3. Process images with Claude Vision API
4. Store documents in Firebase Storage (optional)
5. Allow referencing documents in conversation

## Architecture

```
Image → Download → Base64 encode → Claude Vision → Response
                                         ↓
                              "What's in this image?"

Document → Download → Extract text → Agentic Loop → Response
    ↓
  Store in Firebase (optional)
```

## Related Code Files

- `agents/main.py:191-238` - telegram_webhook
- `agents/src/services/llm.py` - Claude client
- NEW: `agents/src/services/media.py`

## Implementation Steps

### Step 1: Add photo/document detection

```python
# In telegram_webhook:
photo = message.get("photo")
document = message.get("document")
caption = message.get("caption", "")

if photo:
    # Photo array is sorted by size, get largest
    file_id = photo[-1].get("file_id")
    return await handle_image_message(file_id, caption, user, chat_id)

if document:
    file_id = document.get("file_id")
    file_name = document.get("file_name", "document")
    mime_type = document.get("mime_type", "")
    return await handle_document_message(file_id, file_name, mime_type, caption, user, chat_id)
```

### Step 2: Create media service

```python
# src/services/media.py
import httpx
import os
import base64

async def download_telegram_file(file_id: str) -> bytes:
    """Download file from Telegram servers."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id}
        )
        data = resp.json()
        if not data.get("ok"):
            raise ValueError(f"Failed to get file: {data}")

        file_path = data["result"]["file_path"]
        file_resp = await client.get(
            f"https://api.telegram.org/file/bot{token}/{file_path}"
        )
        return file_resp.content


def encode_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes to base64 for Claude Vision."""
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def get_media_type(file_path: str) -> str:
    """Determine media type from file extension."""
    ext = file_path.lower().split(".")[-1]
    types = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif",
        "webp": "image/webp"
    }
    return types.get(ext, "image/jpeg")
```

### Step 3: Add handle_image_message

```python
async def handle_image_message(
    file_id: str,
    caption: str,
    user: dict,
    chat_id: int
) -> str:
    """Process image with Claude Vision."""
    from src.services.media import download_telegram_file, encode_image_base64
    from src.services.llm import get_llm_client
    import structlog

    logger = structlog.get_logger()
    logger.info("image_message", user=user.get("id"))

    await send_chat_action(chat_id, "typing")

    try:
        # Download image
        image_bytes = await download_telegram_file(file_id)
        image_b64 = encode_image_base64(image_bytes)

        # Default prompt if no caption
        prompt = caption if caption else "What's in this image? Describe it in detail."

        # Call Claude with Vision
        llm = get_llm_client()
        response = llm.chat_with_image(
            image_base64=image_b64,
            prompt=prompt,
            max_tokens=1024
        )

        return response

    except Exception as e:
        logger.error("image_error", error=str(e))
        return "Sorry, I couldn't process the image."
```

### Step 4: Add chat_with_image to LLM service

```python
# In src/services/llm.py, add to LLMClient:

def chat_with_image(
    self,
    image_base64: str,
    prompt: str,
    media_type: str = "image/jpeg",
    max_tokens: int = 1024
) -> str:
    """Send image to Claude Vision for analysis."""
    response = self.client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }]
    )
    return response.content[0].text
```

### Step 5: Add handle_document_message

```python
async def handle_document_message(
    file_id: str,
    file_name: str,
    mime_type: str,
    caption: str,
    user: dict,
    chat_id: int
) -> str:
    """Process document: extract text and analyze."""
    from src.services.media import download_telegram_file
    import structlog

    logger = structlog.get_logger()
    logger.info("document_message", file_name=file_name, mime=mime_type)

    await send_chat_action(chat_id, "typing")

    # Supported text formats
    text_formats = ["text/plain", "text/markdown", "application/json"]
    pdf_formats = ["application/pdf"]

    try:
        doc_bytes = await download_telegram_file(file_id)

        if mime_type in text_formats or file_name.endswith(('.txt', '.md', '.json')):
            text = doc_bytes.decode("utf-8")
        elif mime_type in pdf_formats or file_name.endswith('.pdf'):
            # Use pypdf for text extraction
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(doc_bytes))
            text = "\n".join(page.extract_text() for page in reader.pages)
        else:
            return f"Sorry, I can't process {mime_type} files yet. Supported: txt, md, json, pdf"

        # Truncate if too long
        if len(text) > 10000:
            text = text[:10000] + "\n\n[Truncated...]"

        # Process with caption as instruction
        prompt = caption if caption else f"Analyze this document:\n\n{text}"
        if caption and text:
            prompt = f"{caption}\n\nDocument content:\n{text}"

        return await process_message(prompt, user, chat_id)

    except Exception as e:
        logger.error("document_error", error=str(e))
        return "Sorry, I couldn't process the document."
```

## Todo List

- [ ] Add photo/document detection in webhook
- [ ] Create src/services/media.py
- [ ] Add chat_with_image to LLM service
- [ ] Implement handle_image_message
- [ ] Implement handle_document_message
- [ ] Add PDF text extraction
- [ ] Test with various image formats
- [ ] Test with PDF documents

## Success Criteria

- [ ] Images analyzed with Claude Vision
- [ ] Image captions used as prompts
- [ ] PDF text extracted and processed
- [ ] Text files processed correctly
- [ ] Unsupported formats show clear message

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large image download | Medium | 20MB Telegram limit OK |
| PDF parsing failure | Low | Fallback error message |
| Vision API cost | Medium | Already using Claude |

## Security Considerations

- Validate file_id format
- Limit document size (10MB)
- Sanitize extracted text
- Don't store sensitive documents

## Next Steps

After completion, proceed to [Phase 4](./phase-04-reactions-progress.md).
