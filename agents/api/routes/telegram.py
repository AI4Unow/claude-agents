"""Telegram webhook endpoints.

Handles incoming Telegram bot updates including messages, callbacks, and media.
"""
from fastapi import APIRouter, Request, HTTPException
import structlog
import time
from typing import Dict


router = APIRouter(prefix="/webhook", tags=["telegram"])
logger = structlog.get_logger()


# Module-level deduplication cache
_processed_updates: Dict[int, float] = {}
DEDUPLICATION_TTL = 60


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates.

    Processes:
    - Text messages and commands
    - Voice messages
    - Photo messages
    - Document messages
    - Callback queries (button presses)

    Rate limited to 30 requests/minute per IP.
    """
    from api.dependencies import verify_telegram_webhook

    # Import command router (refactored pattern)
    from commands.router import command_router
    # Auto-register all commands by importing command modules
    from commands import user, skills, admin, personalization, developer, reminders, pkm

    # Import handlers locally to avoid circular dependency
    import sys
    main_module = sys.modules.get("main")
    if not main_module:
        import main as main_module

    handle_callback = main_module.handle_callback
    handle_voice_message = main_module.handle_voice_message
    handle_image_message = main_module.handle_image_message
    handle_document_message = main_module.handle_document_message
    process_message = main_module.process_message
    send_telegram_message = main_module.send_telegram_message

    # Verify webhook signature
    if not await verify_telegram_webhook(request):
        logger.warning("telegram_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        update = await request.json()
        update_id = update.get("update_id")

        if update_id:
            now = time.time()
            # Clean old entries (periodically or every request)
            if len(_processed_updates) > 1000: # Simple cap to prevent memory leak
                expired = [uid for uid, ts in _processed_updates.items() if now - ts > DEDUPLICATION_TTL]
                for uid in expired:
                    _processed_updates.pop(uid, None)

            # Check for duplicate
            if update_id in _processed_updates:
                if now - _processed_updates[update_id] < DEDUPLICATION_TTL:
                    logger.info("telegram_duplicate_update", update_id=update_id)
                    return {"ok": True}

            _processed_updates[update_id] = now

        logger.info("telegram_update", update_id=update_id)

        # Check for callback query (button press)
        callback = update.get("callback_query")
        if callback:
            return await handle_callback(callback)

        # Extract message
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        user_data = message.get("from", {})

        if not chat_id:
            return {"ok": True}

        # Handle voice messages
        voice = message.get("voice")
        if voice:
            file_id = voice.get("file_id")
            duration = voice.get("duration", 0)
            response = await handle_voice_message(file_id, duration, user_data, chat_id)
            if response:
                await send_telegram_message(chat_id, response)
            return {"ok": True}

        # Handle photo messages
        photo = message.get("photo")
        if photo:
            # Photo array is sorted by size, get largest (up to 1280px per validation)
            file_id = photo[-1].get("file_id")
            caption = message.get("caption", "")
            response = await handle_image_message(file_id, caption, user_data, chat_id)
            if response:
                await send_telegram_message(chat_id, response)
            return {"ok": True}

        # Handle document messages
        document = message.get("document")
        if document:
            file_id = document.get("file_id")
            file_name = document.get("file_name", "document")
            mime_type = document.get("mime_type", "")
            caption = message.get("caption", "")
            response = await handle_document_message(
                file_id, file_name, mime_type, caption, user_data, chat_id
            )
            if response:
                await send_telegram_message(chat_id, response)
            return {"ok": True}

        # Skip if no text
        if not text:
            return {"ok": True}

        logger.info("processing_message", chat_id=chat_id, text_len=len(text))

        # Get message_id for reactions
        message_id = message.get("message_id")

        # Handle commands using refactored CommandRouter
        if text.startswith("/"):
            response = await command_router.handle(text, user_data, chat_id)
        else:
            # Use SDK handler for message processing (new path)
            # Fallback to old process_message if SDK fails
            try:
                from src.sdk.telegram_handler import handle_telegram_message
                from src.core.state import get_state_manager
                
                state = get_state_manager()
                tier = await state.get_user_tier_cached(user_data.get("id"))
                
                response = await handle_telegram_message(
                    user_id=user_data.get("id"),
                    message=text,
                    tier=tier,
                    context={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "platform": "telegram"
                    }
                )
            except Exception as sdk_error:
                # Fallback to old implementation
                logger.warning("sdk_handler_fallback", error=str(sdk_error)[:100])
                response = await process_message(text, user_data, chat_id, message_id)

        # Response may be None if already sent (e.g., keyboard)
        if response:
            logger.info("sending_response", chat_id=chat_id, response_len=len(response))
            await send_telegram_message(chat_id, response)

        return {"ok": True}

    except Exception as e:
        logger.error("webhook_error", error=str(e))
        return {"ok": False, "error": str(e)}
