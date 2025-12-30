# Phase 5: Media Handling (Feature Parity)

**Status:** Ready
**Dependencies:** Phase 3, Phase 4
**Output:** Voice, image, document handling for WhatsApp

## Overview

Implement media handling for WhatsApp matching Telegram capabilities. Key difference: WhatsApp uses media IDs that must be fetched via API, while Telegram uses file_id with getFile.

## Tasks

### 5.1 Voice Message Handling

**Add to main.py (or unified handler):**

```python
async def handle_voice_message_unified(msg: NormalizedMessage) -> str:
    """Handle voice message from any platform."""
    from src.core.messaging import Platform

    if msg.platform == Platform.TELEGRAM:
        # Existing Telegram flow
        return await handle_voice_message(
            msg.media.media_id,
            msg.media.duration_seconds or 0,
            {"id": msg.user.platform_user_id, "first_name": msg.user.display_name},
            msg.user.platform_user_id
        )

    elif msg.platform == Platform.WHATSAPP:
        # WhatsApp voice flow
        from src.services.whatsapp import download_media
        from src.tools.gemini_tools import transcribe_audio

        # Download audio from WhatsApp CDN
        audio_bytes = await download_media(msg.media.media_id)
        if not audio_bytes:
            return "Failed to download voice message."

        # Transcribe using Gemini
        try:
            transcription = await transcribe_audio(audio_bytes, msg.media.mime_type or "audio/ogg")
            if not transcription:
                return "Could not transcribe voice message."

            # Process transcribed text
            return await process_message(
                transcription,
                {"id": msg.user.user_id, "first_name": msg.user.display_name, "platform": "whatsapp"},
                msg.chat_id
            )
        except Exception as e:
            logger.error("whatsapp_voice_error", error=str(e)[:100])
            return "Voice processing failed."

    return "Voice messages not supported on this platform."
```

### 5.2 Image Handling

```python
async def handle_image_message_unified(msg: NormalizedMessage) -> str:
    """Handle image message from any platform."""
    from src.core.messaging import Platform

    if msg.platform == Platform.TELEGRAM:
        return await handle_image_message(
            msg.media.media_id,
            msg.media.caption or "",
            {"id": msg.user.platform_user_id, "first_name": msg.user.display_name},
            msg.user.platform_user_id
        )

    elif msg.platform == Platform.WHATSAPP:
        from src.services.whatsapp import download_media
        from src.tools.gemini_tools import analyze_image

        # Download image from WhatsApp CDN
        image_bytes = await download_media(msg.media.media_id)
        if not image_bytes:
            return "Failed to download image."

        # Analyze with Gemini Vision
        try:
            prompt = msg.text or "Describe this image in detail."
            analysis = await analyze_image(image_bytes, prompt, msg.media.mime_type or "image/jpeg")
            return analysis or "Could not analyze image."
        except Exception as e:
            logger.error("whatsapp_image_error", error=str(e)[:100])
            return "Image analysis failed."

    return "Images not supported on this platform."
```

### 5.3 Document Handling

```python
async def handle_document_message_unified(msg: NormalizedMessage) -> str:
    """Handle document message from any platform."""
    from src.core.messaging import Platform

    if msg.platform == Platform.TELEGRAM:
        return await handle_document_message(
            msg.media.media_id,
            msg.media.filename or "document",
            msg.media.mime_type or "",
            msg.media.caption or "",
            {"id": msg.user.platform_user_id, "first_name": msg.user.display_name},
            msg.user.platform_user_id
        )

    elif msg.platform == Platform.WHATSAPP:
        from src.services.whatsapp import download_media

        # Download document
        doc_bytes = await download_media(msg.media.media_id)
        if not doc_bytes:
            return "Failed to download document."

        # Route based on MIME type
        mime = msg.media.mime_type or ""
        filename = msg.media.filename or "document"

        if mime == "application/pdf" or filename.endswith(".pdf"):
            from src.tools.gemini_tools import analyze_pdf
            analysis = await analyze_pdf(doc_bytes, msg.text or "Summarize this document.")
            return analysis or "Could not analyze PDF."

        elif mime.startswith("text/") or filename.endswith((".txt", ".md", ".json", ".yaml", ".yml")):
            # Text file - read and process
            try:
                content = doc_bytes.decode("utf-8")[:5000]  # Limit size
                return await process_message(
                    f"Analyze this file ({filename}):\n\n{content}",
                    {"id": msg.user.user_id, "first_name": msg.user.display_name},
                    msg.chat_id
                )
            except UnicodeDecodeError:
                return "Could not read file as text."

        else:
            return f"Received document: {filename} ({mime}). Document type not yet supported."

    return "Documents not supported on this platform."
```

### 5.4 Callback (Button Press) Handling

```python
async def handle_callback_unified(msg: NormalizedMessage) -> Optional[str]:
    """Handle button press callback from any platform."""
    from src.core.messaging import Platform

    callback_data = msg.callback_data
    if not callback_data:
        return None

    if msg.platform == Platform.TELEGRAM:
        # Use existing callback handler
        return await handle_callback({
            "id": msg.message_id,
            "from": {"id": msg.user.platform_user_id, "first_name": msg.user.display_name},
            "message": {"chat": {"id": int(msg.chat_id)}},
            "data": callback_data
        })

    elif msg.platform == Platform.WHATSAPP:
        # WhatsApp button callbacks
        # callback_data contains button ID set during send_buttons()

        # Route based on callback prefix
        if callback_data.startswith("skill_"):
            skill_name = callback_data[6:]  # Remove "skill_" prefix
            from src.core.state import get_state_manager
            state = get_state_manager()
            await state.set_pending_skill(msg.user.user_id, skill_name)
            return f"Selected skill: *{skill_name}*\n\nSend your task now."

        elif callback_data.startswith("improve_"):
            # Improvement approval/rejection
            action, proposal_id = callback_data.split(":", 1)
            if action == "improve_approve":
                return await approve_improvement(proposal_id, msg.user.user_id)
            elif action == "improve_reject":
                return await reject_improvement(proposal_id, msg.user.user_id)

        return f"Button pressed: {callback_data}"

    return None
```

### 5.5 Reply Buttons Equivalent

WhatsApp uses different interactive message format than Telegram inline keyboards.

```python
async def send_skill_menu_whatsapp(phone: str, skills: list) -> bool:
    """Send skill selection menu for WhatsApp.

    WhatsApp limits: max 3 buttons per message.
    For more skills, use List Message instead.
    """
    from src.services.whatsapp import send_buttons

    # If <= 3 skills, use buttons
    if len(skills) <= 3:
        buttons = [
            {"id": f"skill_{s.name}", "title": s.name[:20]}
            for s in skills[:3]
        ]
        return await send_buttons(
            phone,
            body="Select a skill:",
            buttons=buttons,
            header="Skills"
        )

    # For more skills, use list message
    from src.services.whatsapp import send_list
    return await send_list(
        phone,
        body="Select a skill from the list:",
        button_text="View Skills",
        sections=[{
            "title": "Available Skills",
            "rows": [
                {"id": f"skill_{s.name}", "title": s.name[:24], "description": s.description[:72]}
                for s in skills[:10]  # Max 10 rows per section
            ]
        }]
    )
```

### 5.6 Add List Message to whatsapp.py

```python
async def send_list(
    phone: str,
    body: str,
    button_text: str,
    sections: List[dict],
    header: Optional[str] = None,
    footer: Optional[str] = None
) -> bool:
    """Send interactive list message.

    Args:
        phone: Recipient phone
        body: Message body
        button_text: Text on the list button (max 20 chars)
        sections: List of {"title": str, "rows": [{"id", "title", "description"}]}

    WhatsApp limits:
    - Max 10 sections
    - Max 10 rows per section
    - Title max 24 chars, description max 72 chars
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text[:20],
                "sections": sections[:10]
            }
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
        logger.error("whatsapp_list_error", error=str(e)[:100])
        return False
```

## File Changes

| File | Change |
|------|--------|
| `main.py` | Add unified media handlers |
| `src/services/whatsapp.py` | Add `send_list()` function |

## Feature Parity Matrix

| Feature | Telegram | WhatsApp |
|---------|----------|----------|
| Text messages | ✅ | ✅ |
| Voice messages | ✅ | ✅ |
| Image analysis | ✅ | ✅ |
| Document processing | ✅ | ✅ |
| Commands (/help) | ✅ | ✅ |
| Reply buttons | ✅ (Inline Keyboard) | ✅ (Reply Buttons) |
| Skill menu | ✅ (Inline Keyboard) | ✅ (List Message) |
| Callback handling | ✅ | ✅ |

## Verification

- [ ] Voice messages transcribed and processed
- [ ] Images analyzed with Gemini Vision
- [ ] PDFs summarized
- [ ] Text documents processed
- [ ] Button presses trigger callbacks
- [ ] Skill menu works with list selection
