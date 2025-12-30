"""WhatsApp webhook endpoints via Evolution API.

Handles incoming WhatsApp messages from Evolution API webhooks.
"""
from fastapi import APIRouter, Request
import structlog


router = APIRouter(prefix="/webhook", tags=["whatsapp"])
logger = structlog.get_logger()


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Handle WhatsApp messages from Evolution API.

    Processes:
    - Text messages and commands
    - Image messages (stub - Phase 5)
    - Audio messages (stub - Phase 5)
    - Document messages (stub - Phase 5)

    Rate limited to 60 requests/minute.
    """
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    # Import handlers from main module
    import sys
    main_module = sys.modules.get("main")
    if not main_module:
        import main as main_module

    handle_whatsapp_text = main_module.handle_whatsapp_text
    handle_whatsapp_image = main_module.handle_whatsapp_image
    handle_whatsapp_audio = main_module.handle_whatsapp_audio
    handle_whatsapp_document = main_module.handle_whatsapp_document
    handle_whatsapp_callback = main_module.handle_whatsapp_callback
    send_evolution_message = main_module.send_evolution_message

    # Apply rate limiting (higher than Telegram for Evolution API)
    limiter = Limiter(key_func=get_remote_address)
    await limiter.limit("60/minute")(request)

    try:
        data = await request.json()
        event = data.get("event", "")
        instance = data.get("instance", "")

        logger.info("whatsapp_webhook",
            event=event,
            instance=instance
        )

        # Only process message events
        if event != "messages.upsert":
            return {"status": "ignored", "event": event}

        # Extract message data
        msg_data = data.get("data", {})
        key = msg_data.get("key", {})

        # Skip messages from self
        if key.get("fromMe", False):
            return {"status": "ignored", "reason": "from_me"}

        # Extract sender info
        remote_jid = key.get("remoteJid", "")
        phone = remote_jid.split("@")[0]  # Remove @s.whatsapp.net
        sender_name = msg_data.get("pushName", "User")
        message_id = key.get("id", "")

        # Extract message content by type
        message = msg_data.get("message", {})
        msg_type = msg_data.get("messageType", "")

        logger.info("whatsapp_message",
            phone=phone[:6] + "...",
            type=msg_type,
            sender=sender_name
        )

        # Build user dict (compatible with existing handlers)
        user = {
            "id": phone,  # Use phone as user ID (string)
            "first_name": sender_name,
            "platform": "whatsapp"
        }

        # Route by message type
        response = None

        if msg_type == "conversation":
            text = message.get("conversation", "")
            response = await handle_whatsapp_text(text, user, phone)

        elif msg_type == "extendedTextMessage":
            text = message.get("extendedTextMessage", {}).get("text", "")
            response = await handle_whatsapp_text(text, user, phone)

        elif msg_type == "imageMessage":
            image = message.get("imageMessage", {})
            response = await handle_whatsapp_image(image, user, phone)

        elif msg_type == "audioMessage":
            audio = message.get("audioMessage", {})
            response = await handle_whatsapp_audio(audio, user, phone)

        elif msg_type == "documentMessage":
            doc = message.get("documentMessage", {})
            response = await handle_whatsapp_document(doc, user, phone)

        elif msg_type == "listResponseMessage":
            # User selected item from list menu
            selected = message.get("listResponseMessage", {})
            row_id = selected.get("singleSelectReply", {}).get("selectedRowId", "")
            response = await handle_whatsapp_callback(row_id, user, phone)

        elif msg_type == "buttonsResponseMessage":
            # User clicked a button
            selected = message.get("buttonsResponseMessage", {})
            button_id = selected.get("selectedButtonId", "")
            response = await handle_whatsapp_callback(button_id, user, phone)

        else:
            response = f"Unsupported message type: {msg_type}"
            logger.warning("whatsapp_unsupported_type", type=msg_type)

        # Send response back via Evolution API
        if response:
            await send_evolution_message(phone, response)

        return {"status": "ok"}

    except Exception as e:
        logger.error("whatsapp_webhook_error", error=str(e))
        return {"status": "error", "message": str(e)}
