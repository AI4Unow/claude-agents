# Phase 2: Webhook Endpoint

**Status:** Ready
**Dependencies:** Phase 1 (secrets)
**Output:** `/webhook/whatsapp` endpoint in main.py

## Overview

Add WhatsApp webhook endpoint to Modal FastAPI app. Handles both GET (verification) and POST (messages).

## Tasks

### 2.1 Add Webhook Verification Handler

WhatsApp sends GET request with challenge on webhook registration.

**Add to `main.py` after github webhook:**

```python
@web_app.api_route("/webhook/whatsapp", methods=["GET", "POST"])
async def whatsapp_webhook(request: Request):
    """Handle WhatsApp Cloud API webhooks."""
    import structlog
    import hmac
    import hashlib
    logger = structlog.get_logger()

    if request.method == "GET":
        # Webhook verification
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        expected_token = os.environ.get("WHATSAPP_VERIFY_TOKEN")

        if mode == "subscribe" and token == expected_token:
            logger.info("whatsapp_webhook_verified")
            return int(challenge)  # Must return challenge as plain int

        logger.warning("whatsapp_webhook_verification_failed")
        raise HTTPException(status_code=403, detail="Verification failed")

    # POST - message handling (Phase 2.2)
    ...
```

### 2.2 Add Signature Validation

Meta signs webhooks with X-Hub-Signature-256 header.

```python
async def verify_whatsapp_signature(request: Request) -> bool:
    """Verify X-Hub-Signature-256 from Meta webhook."""
    app_secret = os.environ.get("WHATSAPP_APP_SECRET")
    if not app_secret:
        import structlog
        structlog.get_logger().warning("whatsapp_app_secret_not_configured")
        return False

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        return False

    body = await request.body()
    expected = "sha256=" + hmac.new(
        app_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)
```

### 2.3 Add POST Handler

```python
@web_app.api_route("/webhook/whatsapp", methods=["GET", "POST"])
@limiter.limit("30/minute")
async def whatsapp_webhook(request: Request):
    """Handle WhatsApp Cloud API webhooks."""
    import structlog
    logger = structlog.get_logger()

    if request.method == "GET":
        # ... verification from 2.1 ...

    # POST - incoming message/status
    if not await verify_whatsapp_signature(request):
        logger.warning("whatsapp_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = await request.json()
        logger.info("whatsapp_webhook", data_keys=list(data.keys()))

        # Extract message from nested structure
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # Check for messages
        messages = value.get("messages", [])
        if not messages:
            # Status update or other event, acknowledge
            return {"status": "ok"}

        message = messages[0]
        phone = message.get("from")  # Sender phone number
        msg_id = message.get("id")
        msg_type = message.get("type")  # text, image, audio, document, etc.

        # Extract sender info
        contacts = value.get("contacts", [{}])
        sender_name = contacts[0].get("profile", {}).get("name", "User")

        logger.info("whatsapp_message",
            phone=phone[:6] + "...",
            type=msg_type,
            msg_id=msg_id[:10]
        )

        # Route by message type
        if msg_type == "text":
            text = message.get("text", {}).get("body", "")
            response = await handle_whatsapp_text(text, phone, sender_name)
        elif msg_type == "audio":
            audio_id = message.get("audio", {}).get("id")
            response = await handle_whatsapp_audio(audio_id, phone, sender_name)
        elif msg_type == "image":
            image_id = message.get("image", {}).get("id")
            caption = message.get("image", {}).get("caption", "")
            response = await handle_whatsapp_image(image_id, caption, phone, sender_name)
        elif msg_type == "document":
            doc = message.get("document", {})
            response = await handle_whatsapp_document(
                doc.get("id"), doc.get("filename"), doc.get("mime_type"),
                doc.get("caption", ""), phone, sender_name
            )
        else:
            response = f"Unsupported message type: {msg_type}"

        if response:
            await send_whatsapp_message(phone, response)

        return {"status": "ok"}

    except Exception as e:
        logger.error("whatsapp_webhook_error", error=str(e))
        return {"status": "error", "message": str(e)}
```

### 2.4 Add Handler Stubs

Temporary stubs until Phase 4 unifies handling:

```python
async def handle_whatsapp_text(text: str, phone: str, name: str) -> str:
    """Handle WhatsApp text message (temporary stub)."""
    # TODO: Unify with Telegram in Phase 4
    user = {"id": phone, "first_name": name, "platform": "whatsapp"}

    if text.startswith("/"):
        return await handle_command(text, user, phone)
    else:
        return await process_message(text, user, phone)

async def handle_whatsapp_audio(audio_id: str, phone: str, name: str) -> str:
    """Handle WhatsApp audio message (stub)."""
    return "Voice messages coming soon."

async def handle_whatsapp_image(image_id: str, caption: str, phone: str, name: str) -> str:
    """Handle WhatsApp image message (stub)."""
    return "Image analysis coming soon."

async def handle_whatsapp_document(doc_id: str, filename: str, mime: str, caption: str, phone: str, name: str) -> str:
    """Handle WhatsApp document message (stub)."""
    return "Document processing coming soon."
```

### 2.5 Add Send Function Stub

```python
async def send_whatsapp_message(phone: str, text: str) -> bool:
    """Send WhatsApp message (temporary stub)."""
    import httpx

    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text[:4096]}  # WhatsApp limit
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            return response.status_code == 200
    except Exception:
        return False
```

## File Changes

| File | Change |
|------|--------|
| `main.py` | Add `/webhook/whatsapp` endpoint |
| `main.py` | Add `verify_whatsapp_signature()` |
| `main.py` | Add handler stubs |
| `main.py` | Add `send_whatsapp_message()` stub |
| `main.py` | Add whatsapp-credentials to secrets list |

## Testing

1. Deploy to Modal: `modal deploy agents/main.py`
2. Configure webhook in Meta Dashboard:
   - URL: `https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/webhook/whatsapp`
   - Verify Token: (from Phase 1)
   - Subscribe to: `messages`
3. Send test message from WhatsApp to test number
4. Check Modal logs for webhook receipt

## Verification

- [ ] GET verification returns challenge
- [ ] POST receives messages
- [ ] Signature validation works
- [ ] Text messages trigger response
- [ ] Response sent back to user
