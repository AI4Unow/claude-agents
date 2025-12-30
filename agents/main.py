"""Modal app entry point for Claude Agents.

This file defines the Modal application, container image, and core functions.
All agents mount the skills volume for II Framework functionality.
"""
import modal
import os
import subprocess
from datetime import datetime

# Define the Modal app
app = modal.App("claude-agents")

# Define container image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl")
    .pip_install_from_requirements("requirements.txt")
    .env({"PYTHONPATH": "/root"})
    .add_local_dir("src", remote_path="/root/src")
    .add_local_dir("skills", remote_path="/root/skills_source")  # For deploy-time sync
)

# Skills volume - stores mutable info.md files (II Framework: Information layer)
skills_volume = modal.Volume.from_name("skills-volume", create_if_missing=True)

# Define secrets
secrets = [
    modal.Secret.from_name("anthropic-credentials"),
    modal.Secret.from_name("firebase-credentials"),
    modal.Secret.from_name("telegram-credentials"),
    modal.Secret.from_name("qdrant-credentials"),
    modal.Secret.from_name("exa-credentials"),
    modal.Secret.from_name("tavily-credentials"),
    modal.Secret.from_name("admin-credentials"),
    modal.Secret.from_name("groq-credentials"),
    modal.Secret.from_name("gcp-credentials"),
    modal.Secret.from_name("evolution-credentials"),
]

# GitHub secret (separate for security)
github_secret = modal.Secret.from_name("github-credentials")


def is_local_skill(skill_name: str) -> bool:
    """Check if skill requires local execution.

    Returns True if skill's deployment field is 'local'.
    Skills with 'remote' or 'both' are executed on Modal.
    """
    from src.skills.registry import get_registry

    registry = get_registry()
    summaries = registry.discover()

    for s in summaries:
        if s.name == skill_name:
            return s.deployment == "local"
    return False


async def notify_task_queued(user_id: int, skill_name: str, task_id: str):
    """Notify user that task was queued for local execution."""
    import httpx

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token or not user_id:
        return

    message = (
        f"⏳ *Task Queued*\n\n"
        f"Skill: `{skill_name}`\n"
        f"Task ID: `{task_id[:8]}...`\n\n"
        f"This skill requires local execution. "
        f"You'll be notified when it completes."
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
            )
    except Exception:
        pass  # Non-blocking, log errors elsewhere


# ==================== FastAPI App Setup ====================

# Import web_app and include all routers
from api.app import web_app
from api.routes import health, telegram, whatsapp, skills, reports, admin

# Include all route modules
web_app.include_router(health.router)
web_app.include_router(telegram.router)
web_app.include_router(whatsapp.router)
web_app.include_router(skills.router)
web_app.include_router(reports.router)
web_app.include_router(admin.router)


# ==================== Skill Execution Functions ====================

async def execute_skill_simple(skill_name: str, task: str, context: dict) -> str:
    """Execute a skill directly."""
    from src.skills.registry import get_registry
    from src.services.llm import get_llm_client

    # Handle Gemini skills specially
    GEMINI_SKILLS = {
        "gemini-deep-research",
        "gemini-grounding",
        "gemini-thinking",
        "gemini-vision",
    }

    if skill_name in GEMINI_SKILLS:
        from src.tools.gemini_tools import (
            execute_deep_research,
            execute_grounded_query,
            execute_thinking,
            execute_vision,
        )
        import json

        user_id = context.get("user_id", 0)

        if skill_name == "gemini-deep-research":
            result = await execute_deep_research(
                query=task,
                user_id=user_id,
                max_iterations=context.get("max_iterations", 10)
            )
        elif skill_name == "gemini-grounding":
            result = await execute_grounded_query(query=task)
        elif skill_name == "gemini-thinking":
            result = await execute_thinking(
                prompt=task,
                thinking_level=context.get("thinking_level", "high")
            )
        elif skill_name == "gemini-vision":
            result = await execute_vision(
                image_base64=context.get("image_base64", ""),
                prompt=task,
                media_type=context.get("media_type", "image/jpeg")
            )

        # Return formatted result
        if result.get("success"):
            if "report" in result:
                return result["report"]
            elif "answer" in result:
                return result["answer"]
            elif "analysis" in result:
                return result["analysis"]
            return json.dumps(result)
        else:
            return f"Error: {result.get('error', 'Unknown error')}"

    registry = get_registry()
    skill = registry.get_full(skill_name)

    if not skill:
        return f"Skill not found: {skill_name}"

    llm = get_llm_client()

    context_str = ""
    if context:
        context_str = f"\n\nContext: {context}"

    response = llm.chat(
        messages=[{"role": "user", "content": f"{task}{context_str}"}],
        system=skill.get_system_prompt(),
        max_tokens=4096
    )

    return response


async def execute_skill_routed(task: str, context: dict) -> str:
    """Route task to best skill and execute."""
    from src.core.router import SkillRouter

    router = SkillRouter()
    skill = await router.route_single(task)

    if not skill:
        return "No matching skill found for this task."

    return await execute_skill_simple(skill.name, task, context)


async def execute_skill_orchestrated(task: str, context: dict) -> str:
    """Execute task with orchestration."""
    from src.core.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    result = await orchestrator.execute(task, context)

    return result


async def execute_skill_chained(skills: list, task: str) -> str:
    """Execute skills in sequence."""
    from src.core.chain import ChainedExecution

    chain = ChainedExecution()
    result = await chain.execute(skills, task)

    return result.final_output


async def execute_skill_evaluated(skill_name: str, task: str) -> str:
    """Execute skill with quality evaluation."""
    from src.core.evaluator import EvaluatorOptimizer
    from src.skills.registry import get_registry

    registry = get_registry()
    skill = registry.get_full(skill_name)

    if not skill:
        return f"Skill not found: {skill_name}"

    evaluator = EvaluatorOptimizer()
    result = await evaluator.generate_with_evaluation(skill, task)

    return result.final_output



async def handle_voice_message(
    file_id: str,
    duration: int,
    user: dict,
    chat_id: int
) -> str:
    """Process voice message: download, transcribe, process."""
    from src.services.media import download_telegram_file, transcribe_audio_groq
    import structlog

    logger = structlog.get_logger()
    logger.info("voice_message", duration=duration, user=user.get("id"))

    # Show recording action while downloading
    await send_chat_action(chat_id, "record_voice")

    try:
        # Check duration limit (validated: 60s max)
        if duration > 60:
            return "⚠️ Voice message too long. Maximum is 60 seconds."

        # Download
        audio_bytes = await download_telegram_file(file_id)

        # Show typing while transcribing
        await send_chat_action(chat_id, "typing")

        # Transcribe with Groq Whisper
        text = await transcribe_audio_groq(audio_bytes, duration)

        if not text or text.strip() == "":
            return "I couldn't understand the audio. Please try again."

        # Send transcription to user
        transcription_preview = text[:200] + "..." if len(text) > 200 else text
        await send_telegram_message(
            chat_id,
            f"🎤 <i>Transcribed:</i>\n{transcription_preview}"
        )

        # Process through normal message handler
        return await process_message(text, user, chat_id)

    except Exception as e:
        logger.error("voice_error", error=str(e))
        return f"Sorry, I couldn't process your voice message: {str(e)[:100]}"


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


async def handle_document_message(
    file_id: str,
    file_name: str,
    mime_type: str,
    caption: str,
    user: dict,
    chat_id: int
) -> str:
    """Process document: extract text and analyze."""
    from src.services.media import download_telegram_file, extract_pdf_text
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
            text = await extract_pdf_text(doc_bytes)
        else:
            return f"Sorry, I can't process {mime_type or 'this'} files yet. Supported: txt, md, json, pdf"

        # Process with caption as instruction
        if caption and text:
            prompt = f"{caption}\n\nDocument content:\n{text}"
        elif caption:
            prompt = caption
        else:
            prompt = f"Analyze this document:\n\n{text}"

        return await process_message(prompt, user, chat_id)

    except Exception as e:
        logger.error("document_error", error=str(e))
        return "Sorry, I couldn't process the document."


async def send_chat_action(chat_id: int, action: str):
    """Send chat action (typing, upload_photo, record_voice, etc.)."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendChatAction",
                json={"chat_id": chat_id, "action": action}
            )
    except Exception:
        pass  # Non-blocking


async def set_message_reaction(chat_id: int, message_id: int, emoji: str = "👀"):
    """Set reaction emoji on a message."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/setMessageReaction",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reaction": [{"type": "emoji", "emoji": emoji}],
                    "is_big": False
                }
            )
    except Exception:
        pass  # Non-blocking, ignore failures


async def send_progress_message(chat_id: int, text: str) -> int:
    """Send progress message and return message_id for editing."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
            )
            result = resp.json()
            return result.get("result", {}).get("message_id", 0)
    except Exception:
        return 0


async def edit_progress_message(chat_id: int, message_id: int, text: str):
    """Edit progress message with new status."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not message_id:
        return

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
            )
    except Exception:
        pass  # Non-blocking


async def send_typing_action(chat_id: int):
    """Send typing indicator to show bot is processing."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"}
            )
    except Exception:
        pass  # Non-blocking, ignore failures


async def typing_indicator(chat_id: int, cancel_event):
    """Send typing indicator every 4 seconds until cancelled."""
    import asyncio

    while not cancel_event.is_set():
        await send_typing_action(chat_id)
        try:
            await asyncio.wait_for(cancel_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


ERROR_SUGGESTIONS = {
    "timeout": "Try again or simplify your request.",
    "circuit_open": "Service temporarily unavailable. Try in 30 seconds.",
    "rate_limit": "Too many requests. Please wait a moment.",
    "connection": "Network issue. Please try again.",
    "max_iterations": "Request was too complex. Try breaking it down.",
}


def format_error_message(error: str) -> str:
    """Format error with helpful suggestion."""
    error_lower = error.lower()
    for key, suggestion in ERROR_SUGGESTIONS.items():
        if key in error_lower:
            return f"❌ {error}\n\n💡 {suggestion}"
    return "❌ Sorry, something went wrong. Please try again."


async def _run_simple(
    text: str,
    user: dict,
    chat_id: int,
    progress_msg_id: int,
    progress_callback,
    model: str = None,
) -> str:
    """Run direct LLM response (existing agentic loop).

    Args:
        text: User message
        user: User dict
        chat_id: Telegram chat ID
        progress_msg_id: Progress message ID
        progress_callback: Callback for progress updates
        model: Optional model override (e.g., haiku for simple queries)
    """
    from src.services.agentic import run_agentic_loop
    from pathlib import Path
    import aiofiles

    info_path = Path("/skills/telegram-chat/info.md")
    system_prompt = """Your name is AI4U.now Bot. You were created by the AI4U.now team.

You are a unified AI assistant that provides access to multiple AI models (Gemini, Claude, GPT) through a single Telegram interface.

When users ask who you are, introduce yourself as "AI4U.now Bot". When asked about your creator, say you were made by the "AI4U.now team".

You have web search capability. Use the web_search tool when users ask about current events, weather, news, prices, or anything requiring up-to-date information."""

    if info_path.exists():
        async with aiofiles.open(info_path, 'r') as f:
            system_prompt = await f.read()

    return await run_agentic_loop(
        user_message=text,
        system=system_prompt,
        user_id=user.get("id"),
        progress_callback=progress_callback,
        model=model,
    )


async def _run_routed(
    text: str,
    user: dict,
    chat_id: int,
    progress_msg_id: int
) -> str:
    """Route to best skill and execute."""
    from src.core.router import SkillRouter
    import time

    await edit_progress_message(chat_id, progress_msg_id, "🔍 <i>Finding skill...</i>")

    router = SkillRouter()
    skill = await router.route_single(text)

    if not skill:
        # No skill matched, fallback to simple
        async def update_progress(status: str):
            await edit_progress_message(chat_id, progress_msg_id, status)
        return await _run_simple(text, user, chat_id, progress_msg_id, update_progress)

    await edit_progress_message(chat_id, progress_msg_id, f"🔧 <i>Using: {skill.name}</i>")

    start = time.time()
    result = await execute_skill_simple(skill.name, text, {"user": user})
    duration_ms = int((time.time() - start) * 1000)

    from src.services.telegram import format_skill_result
    return format_skill_result(skill.name, result, duration_ms)


async def _run_orchestrated(
    text: str,
    user: dict,
    chat_id: int,
    progress_msg_id: int
) -> str:
    """Run orchestrated multi-skill execution with Telegram progress."""
    from src.core.orchestrator import Orchestrator
    import structlog
    import time

    logger = structlog.get_logger()

    # Track progress updates to avoid Telegram rate limiting
    last_update_time = [0.0]  # Use list for mutable closure
    min_update_interval = 1.0  # 1 second between updates

    async def progress_callback(status: str):
        """Throttled progress callback for Telegram."""
        current_time = time.time()

        # Throttle updates to avoid rate limits
        if current_time - last_update_time[0] < min_update_interval:
            return

        last_update_time[0] = current_time

        try:
            await edit_progress_message(chat_id, progress_msg_id, status)
        except Exception as e:
            logger.warning("progress_update_failed", error=str(e)[:50])

    orchestrator = Orchestrator()

    result = await orchestrator.execute(
        task=text,
        context={"user": user, "user_id": user.get("id")},
        progress_callback=progress_callback
    )

    return result


async def process_message(
    text: str,
    user: dict,
    chat_id,  # int for Telegram, str for WhatsApp
    message_id: int = None
) -> str:
    """Process a regular message with agentic loop (tools enabled).

    Supports both Telegram (chat_id: int) and WhatsApp (chat_id: str).
    """
    import asyncio
    from src.services.agentic import run_agentic_loop
    from src.core.state import get_state_manager
    from pathlib import Path
    import structlog
    import time
    import aiofiles

    logger = structlog.get_logger()
    state = get_state_manager()
    user_id = user.get("id")

    # Detect platform
    is_telegram = isinstance(chat_id, int)
    platform = user.get("platform", "telegram" if is_telegram else "whatsapp")

    # Get tier and check rate limit
    tier = await state.get_user_tier_cached(user_id)
    allowed, reset_in = state.check_rate_limit(user_id, tier)

    if not allowed:
        return f"Rate limited. Try again in {reset_in}s.\n\nUpgrade tier for higher limits."

    # FAQ check - fast path for common questions (identity, capabilities, etc.)
    # Skip for long messages (likely not FAQ)
    if len(text) <= 200:
        try:
            from src.core.faq import get_faq_matcher
            faq_answer = await get_faq_matcher().match(text)
            if faq_answer:
                logger.info("faq_response", user_id=user_id, platform=platform)
                return faq_answer
        except Exception as e:
            logger.error("faq_check_error", error=str(e)[:50])
            # Continue to normal flow on error

    # React to acknowledge receipt (Telegram only)
    if is_telegram and message_id:
        await set_message_reaction(chat_id, message_id, "👀")

    # Send initial progress message (Telegram only)
    progress_msg_id = 0
    if is_telegram:
        progress_msg_id = await send_progress_message(chat_id, "⏳ <i>Processing...</i>")

    # Create progress callback for tool updates (Telegram only)
    async def update_progress(status: str):
        if is_telegram:
            await edit_progress_message(chat_id, progress_msg_id, status)

    # Start typing indicator (Telegram only)
    cancel_event = asyncio.Event()
    typing_task = None
    if is_telegram:
        typing_task = asyncio.create_task(typing_indicator(chat_id, cancel_event))

    # Check for pending skill (user selected from /skills menu)
    pending_skill = await state.get_pending_skill(user.get("id"))

    try:
        if pending_skill:
            # Execute pending skill with this message as task
            await state.clear_pending_skill(user.get("id"))

            start = time.time()
            result = await execute_skill_simple(pending_skill, text, {"user": user})
            duration_ms = int((time.time() - start) * 1000)

            # Success reaction (Telegram only)
            if is_telegram and message_id:
                await set_message_reaction(chat_id, message_id, "✅")

            # Update progress with completion (Telegram only)
            if is_telegram:
                await edit_progress_message(chat_id, progress_msg_id, "✅ <i>Complete</i>")

            from src.services.telegram import format_skill_result
            return format_skill_result(pending_skill, result, duration_ms)

        # Normal agentic loop
        # Get user's mode preference
        mode = await state.get_user_mode(user_id)

        # Route based on mode
        if mode == "auto":
            from src.core.intent import classify_intent
            from src.core.router import parse_explicit_skill
            from src.skills.registry import get_registry

            # Check explicit skill invocation first (/skill or @skill)
            explicit = parse_explicit_skill(text, get_registry())
            if explicit:
                skill_name, remaining_text = explicit
                if is_telegram:
                    await edit_progress_message(chat_id, progress_msg_id, f"🎯 <i>{skill_name}</i>")
                result = await execute_skill_simple(skill_name, remaining_text or text, {"user": user})
                from src.services.telegram import format_skill_result
                response = format_skill_result(skill_name, result, 0)
            else:
                # Intent classification (CHAT/SKILL/ORCHESTRATE)
                if is_telegram:
                    await edit_progress_message(chat_id, progress_msg_id, "🧠 <i>Analyzing...</i>")
                intent = await classify_intent(text)
                logger.info("intent_detected", intent=intent, mode=mode)

                if intent == "orchestrate":
                    if is_telegram:
                        await edit_progress_message(chat_id, progress_msg_id, "🔧 <i>Orchestrating...</i>")
                    response = await _run_orchestrated(text, user, chat_id, progress_msg_id)
                elif intent == "skill":
                    # Route to best matching skill via semantic search
                    if is_telegram:
                        await edit_progress_message(chat_id, progress_msg_id, "🔍 <i>Finding skill...</i>")
                    from src.core.router import SkillRouter
                    router = SkillRouter()
                    skill = await router.route_single(text)
                    if skill:
                        if is_telegram:
                            await edit_progress_message(chat_id, progress_msg_id, f"🎯 <i>{skill.name}</i>")
                        result = await execute_skill_simple(skill.name, text, {"user": user})
                        from src.services.telegram import format_skill_result
                        response = format_skill_result(skill.name, result, 0)
                    else:
                        # No skill matched, fall back to chat
                        response = await _run_simple(
                            text, user, chat_id, progress_msg_id, update_progress,
                            model="kiro-claude-opus-4-5-agentic"
                        )
                else:
                    # CHAT intent - use Haiku for fast, cheap responses
                    response = await _run_simple(
                        text, user, chat_id, progress_msg_id, update_progress,
                        model="kiro-claude-opus-4-5-agentic"
                    )

        elif mode == "routed":
            # Route to best skill
            response = await _run_routed(text, user, chat_id, progress_msg_id)

        else:
            # Default: simple mode - use Haiku for fast, cheap responses
            response = await _run_simple(
                text, user, chat_id, progress_msg_id, update_progress,
                model="kiro-claude-opus-4-5-agentic"
            )

        # Success reaction (Telegram only)
        if is_telegram and message_id:
            await set_message_reaction(chat_id, message_id, "✅")

        # Update progress with completion (Telegram only)
        if is_telegram:
            await edit_progress_message(chat_id, progress_msg_id, "✅ <i>Complete</i>")

        # Log activity (fire-and-forget, non-blocking)
        try:
            from src.services.activity import log_activity
            from src.services.user_context import extract_and_update_context

            # Determine action type and skill used
            action_type = "chat"
            skill_used = None

            if pending_skill:
                action_type = "skill_invoke"
                skill_used = pending_skill
            elif mode == "routed" or (mode == "auto" and 'skill' in locals()):
                # Check if a skill was used
                action_type = "skill_invoke"
                skill_used = skill.name if 'skill' in locals() and skill else None

            # Fire and forget activity logging
            asyncio.create_task(
                log_activity(
                    user_id=user_id,
                    action_type=action_type,
                    summary=text[:100],
                    skill=skill_used,
                    duration_ms=0  # Duration tracking would require refactoring
                )
            )

            # Update work context with message patterns (fire and forget)
            asyncio.create_task(
                extract_and_update_context(user_id, text, skill_used)
            )
        except Exception as e:
            logger.warning("activity_log_failed", error=str(e)[:50])

        return response

    except Exception as e:
        logger.error("agentic_error", error=str(e))

        # Error reaction (Telegram only)
        if is_telegram and message_id:
            await set_message_reaction(chat_id, message_id, "❌")

        # Update progress with error (Telegram only)
        if is_telegram:
            await edit_progress_message(chat_id, progress_msg_id, f"❌ <i>Error: {str(e)[:100]}</i>")

        return format_error_message(str(e))

    finally:
        # Stop typing indicator (Telegram only)
        cancel_event.set()
        if typing_task:
            typing_task.cancel()


async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """Send message via Telegram API with HTML formatting and chunking."""
    import httpx
    import structlog
    from src.services.telegram import chunk_message, markdown_to_html

    logger = structlog.get_logger()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not token:
        logger.error("telegram_no_token")
        return False

    # Convert markdown to HTML if using HTML mode
    if parse_mode == "HTML":
        text = markdown_to_html(text)

    # Chunk if too long
    chunks = chunk_message(text)

    try:
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
                    logger.warning("telegram_html_failed", error=result.get("description"))
                    await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": chunk}
                    )

            logger.info("telegram_sent", chat_id=chat_id, chunks=len(chunks))
            return True

    except Exception as e:
        logger.error("telegram_exception", error=str(e), chat_id=chat_id)
        return False


async def send_telegram_keyboard(chat_id: int, text: str, keyboard: list):
    """Send message with inline keyboard."""
    import httpx
    import structlog

    logger = structlog.get_logger()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "reply_markup": {"inline_keyboard": keyboard},
                    "parse_mode": "HTML"
                }
            )
            result = response.json()
            if not result.get("ok"):
                logger.error("telegram_keyboard_failed", error=result.get("description"))
                return False
            return True
    except Exception as e:
        logger.error("telegram_keyboard_error", error=str(e))
        return False


async def send_skills_menu(chat_id: int):
    """Send skills menu with inline keyboard categories."""
    keyboard = build_skills_keyboard()
    await send_telegram_keyboard(
        chat_id,
        "<b>Select a skill category:</b>",
        keyboard
    )


def build_skills_keyboard(category: str = None) -> list:
    """Build inline keyboard for skills navigation."""
    from src.skills.registry import get_registry

    registry = get_registry()
    summaries = registry.discover()

    if category is None:
        # Show categories
        categories = {}
        for s in summaries:
            cat = getattr(s, 'category', 'general') or 'general'
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        # Build keyboard with 2 buttons per row
        keyboard = []
        row = []
        for cat, count in sorted(categories.items()):
            row.append({
                "text": f"{cat.title()} ({count})",
                "callback_data": f"cat:{cat}"
            })
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        return keyboard
    else:
        # Show skills in category
        skills_in_cat = [s for s in summaries if (getattr(s, 'category', 'general') or 'general') == category]

        keyboard = []
        for s in skills_in_cat:
            keyboard.append([{
                "text": s.name,
                "callback_data": f"skill:{s.name}"
            }])

        # Add back button
        keyboard.append([{"text": "« Back", "callback_data": "cat:main"}])

        return keyboard


async def handle_callback(callback: dict) -> dict:
    """Handle inline keyboard button press."""
    import structlog
    logger = structlog.get_logger()

    callback_id = callback.get("id")
    data = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    message_id = callback.get("message", {}).get("message_id")
    user = callback.get("from", {})

    logger.info("callback_received", data=data, chat_id=chat_id)

    # Parse callback data
    action, value = data.split(":", 1) if ":" in data else (data, "")

    # Answer callback to remove loading state
    await answer_callback(callback_id)

    if action == "cat":
        # Category selected - show skills
        await handle_category_select(chat_id, message_id, value)

    elif action == "skill":
        # Skill selected - prompt for task
        await handle_skill_select(chat_id, value, user)

    elif action == "mode":
        # Mode selected
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.set_user_mode(user.get("id"), value)
        await send_telegram_message(chat_id, f"Mode set to: <b>{value}</b>")

    elif action == "improve_approve":
        # Improvement proposal approved
        await handle_improvement_approve(chat_id, value, user)

    elif action == "improve_reject":
        # Improvement proposal rejected
        await handle_improvement_reject(chat_id, value, user)

    elif action == "forget_confirm":
        # User confirmed data deletion
        from src.services.data_deletion import delete_all_user_data, format_deletion_result
        results = await delete_all_user_data(user.get("id"))
        await send_telegram_message(chat_id, format_deletion_result(results))

    elif action == "forget_cancel":
        await send_telegram_message(chat_id, "Data deletion cancelled. Your data is safe.")

    elif action == "demo":
        # Onboarding demo button pressed
        await handle_demo_callback(chat_id, value, user)

    elif action == "qr":
        # Quick reply button pressed
        await handle_quick_reply_callback(chat_id, value, user)

    return {"ok": True}


async def answer_callback(callback_id: str, text: str = None):
    """Answer callback query to dismiss loading state."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id,
                "text": text
            }
        )


async def handle_category_select(chat_id: int, message_id: int, category: str):
    """Handle category button press - update message with skills."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if category == "main":
        keyboard = build_skills_keyboard()
        text = "<b>Select a skill category:</b>"
    else:
        keyboard = build_skills_keyboard(category)
        text = f"<b>{category.title()}</b> skills:\nSelect one to use:"

    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard},
                "parse_mode": "HTML"
            }
        )


async def handle_skill_select(chat_id: int, skill_name: str, user: dict):
    """Handle skill button press - prompt for task."""
    from src.skills.registry import get_registry
    from src.services.telegram import escape_html
    from src.core.state import get_state_manager

    registry = get_registry()
    skill = registry.get_full(skill_name)

    if not skill:
        await send_telegram_message(chat_id, f"Skill '{escape_html(skill_name)}' not found.")
        return

    # Store pending skill in user session (StateManager)
    state = get_state_manager()
    await state.set_session(user.get("id"), {"pending_skill": skill_name})

    desc = escape_html(skill.description[:100]) if hasattr(skill, 'description') else ""
    message = (
        f"<b>{escape_html(skill_name)}</b>\n"
        f"{desc}\n\n"
        "Send your task now (or /cancel to exit):"
    )

    await send_telegram_message(chat_id, message)


async def handle_demo_callback(chat_id: int, demo_type: str, user: dict):
    """Handle onboarding demo button press.

    Args:
        chat_id: Telegram chat ID
        demo_type: Type of demo (research, code, design, skip)
        user: User dict from Telegram
    """
    from src.core.onboarding import (
        mark_demo_tried,
        get_demo_prompt,
        set_onboarding_step,
        OnboardingStep,
    )

    user_id = user.get("id")

    if demo_type == "skip":
        # User skipped onboarding
        await set_onboarding_step(user_id, OnboardingStep.COMPLETE)
        await send_telegram_message(
            chat_id,
            "✨ You're all set! Just send any message to get started."
        )
        return

    # Get demo prompt
    prompt = get_demo_prompt(demo_type)
    if not prompt:
        return

    # Mark demo tried
    await mark_demo_tried(user_id, demo_type)

    # Show demo prompt
    await send_telegram_message(
        chat_id,
        f"<i>Demo: {demo_type.title()}</i>\n\n<b>Trying:</b> {prompt}"
    )

    # Execute demo (reuse process_message)
    response = await process_message(prompt, user, chat_id)
    if response:
        await send_telegram_message(chat_id, response)

    # Show completion message
    await send_telegram_message(
        chat_id,
        "✨ <b>Great!</b> You've seen what I can do. Try another demo or just ask me anything!"
    )


async def handle_quick_reply_callback(chat_id: int, value: str, user: dict):
    """Handle quick reply button press.

    Args:
        chat_id: Telegram chat ID
        value: Callback value (action:skill)
        user: User dict from Telegram
    """
    from src.core.quick_replies import get_action_prompt, is_special_action
    from src.core.state import get_state_manager

    # Parse value: action:skill or just action
    parts = value.split(":", 1)
    action = parts[0] if parts else ""
    skill = parts[1] if len(parts) > 1 else ""

    # Get original context
    state = get_state_manager()
    context = await state.get("quick_reply_context", str(user.get("id"))) or {}
    context["skill"] = skill or context.get("skill")

    # Special actions
    if is_special_action(action):
        if action == "download_report":
            await send_telegram_message(
                chat_id,
                "📥 Use /reports to see your available reports."
            )
        elif action == "share_report":
            await send_telegram_message(
                chat_id,
                "📤 Forward my previous message to share, or use /reports for links."
            )
        elif action in ("resize", "search_doc"):
            await send_telegram_message(chat_id, "What would you like? Please describe.")
        return

    # Get action prompt
    prompt = get_action_prompt(action, context)
    if not prompt:
        await send_telegram_message(chat_id, "Action not available.")
        return

    # Execute prompt
    response = await process_message(prompt, user, chat_id)
    if response:
        await send_telegram_message(chat_id, response)


async def handle_improvement_approve(chat_id: int, proposal_id: str, user: dict):
    """Handle improvement proposal approval."""
    import structlog
    from src.core.improvement import get_improvement_service

    logger = structlog.get_logger()

    # Verify admin
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != str(admin_id):
        await send_telegram_message(chat_id, "⛔ Only admin can approve proposals.")
        return

    service = get_improvement_service()
    success = await service.apply_proposal(proposal_id, user.get("id"))

    if success:
        try:
            skills_volume.commit()
            await send_telegram_message(
                chat_id,
                f"✅ <b>Proposal approved!</b>\n\n"
                f"Skill info.md updated.\n"
                f"Modal Volume committed.\n"
                f"<i>ID: {proposal_id[:8]}...</i>"
            )
            logger.info("proposal_approved", id=proposal_id)
        except Exception as e:
            await send_telegram_message(
                chat_id,
                f"⚠️ Proposal applied but Volume commit failed:\n<pre>{str(e)[:100]}</pre>"
            )
    else:
        await send_telegram_message(chat_id, "❌ Failed to apply proposal. Check logs.")


async def handle_improvement_reject(chat_id: int, proposal_id: str, user: dict):
    """Handle improvement proposal rejection."""
    import structlog
    from src.core.improvement import get_improvement_service

    logger = structlog.get_logger()

    # Verify admin
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != str(admin_id):
        await send_telegram_message(chat_id, "⛔ Only admin can reject proposals.")
        return

    service = get_improvement_service()
    success = await service.reject_proposal(proposal_id, user.get("id"), "Rejected by admin")

    if success:
        await send_telegram_message(
            chat_id,
            f"❌ <b>Proposal rejected.</b>\n<i>ID: {proposal_id[:8]}...</i>"
        )
        logger.info("proposal_rejected", id=proposal_id)
    else:
        await send_telegram_message(chat_id, "❌ Failed to reject proposal. Check logs.")


async def send_improvement_notification(proposal: dict) -> bool:
    """Send improvement proposal to admin for approval."""
    import structlog
    from src.services.telegram import format_improvement_proposal, build_improvement_keyboard

    logger = structlog.get_logger()

    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if not admin_id:
        logger.warning("admin_telegram_id_not_configured")
        return False

    try:
        admin_id = int(admin_id)
    except ValueError:
        logger.error("invalid_admin_telegram_id")
        return False

    message = format_improvement_proposal(proposal)
    keyboard = build_improvement_keyboard(proposal["id"])

    return await send_telegram_keyboard(admin_id, message, keyboard)


# ==================== WhatsApp Handlers ====================

async def handle_whatsapp_text(text: str, user: dict, phone: str) -> str:
    """Handle WhatsApp text message.

    Routes to existing command and message handlers, reusing Telegram logic.
    """
    import structlog
    from commands.router import command_router
    # Auto-register all commands
    from commands import user as user_cmds, skills, admin, personalization, developer, reminders, pkm

    logger = structlog.get_logger()

    if not text:
        return None

    logger.info("whatsapp_text", phone=phone[:6] + "...", len=len(text))

    # Handle commands using existing command router
    if text.startswith("/"):
        # command_router expects chat_id but we pass phone (string)
        # Commands will work since phone is valid user ID
        return await command_router.handle(text, user, phone)

    # Regular message processing (reuse Telegram logic)
    # process_message expects chat_id as int for Telegram, but accepts string for WhatsApp
    return await process_message(text, user, phone)


async def handle_whatsapp_image(image: dict, user: dict, phone: str) -> str:
    """Handle WhatsApp image message with vision analysis."""
    from src.services.evolution import download_media
    from src.services.llm import get_llm_client
    import base64
    import structlog

    logger = structlog.get_logger()
    logger.info("whatsapp_image", phone=phone[:6] + "...")

    try:
        # Get image URL from payload
        image_url = image.get("url")
        caption = image.get("caption", "")

        if not image_url:
            return "Could not access image."

        # Download image
        image_bytes = await download_media(image_url)
        if not image_bytes:
            return "Failed to download image."

        # Encode to base64 for vision
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Determine mime type
        mime_type = image.get("mimetype", "image/jpeg")

        # Default prompt if no caption
        prompt = caption if caption else "What's in this image? Describe it in detail."

        # Call Claude with Vision
        llm = get_llm_client()
        response = llm.chat_with_image(
            image_base64=image_b64,
            prompt=prompt,
            media_type=mime_type,
            max_tokens=1024
        )

        return response

    except Exception as e:
        logger.error("whatsapp_image_error", error=str(e)[:100])
        return "Sorry, I couldn't process the image."


async def handle_whatsapp_audio(audio: dict, user: dict, phone: str) -> str:
    """Handle WhatsApp voice message with transcription."""
    from src.services.evolution import download_media
    from src.services.media import transcribe_audio_groq
    import structlog

    logger = structlog.get_logger()
    logger.info("whatsapp_audio", phone=phone[:6] + "...")

    try:
        audio_url = audio.get("url")
        duration = audio.get("seconds", 0)
        is_ptt = audio.get("ptt", False)

        if not audio_url:
            return "Could not access audio."

        # Check duration limit
        if duration > 60:
            return "⚠️ Voice message too long. Maximum is 60 seconds."

        # Download audio
        audio_bytes = await download_media(audio_url)
        if not audio_bytes:
            return "Failed to download voice message."

        # Transcribe with Groq Whisper
        text = await transcribe_audio_groq(audio_bytes, duration)

        if not text or text.strip() == "":
            return "I couldn't understand the audio. Please try again."

        # Send transcription preview
        transcription_preview = text[:200] + "..." if len(text) > 200 else text
        await send_evolution_message(phone, f"🎤 _Transcribed:_\n{transcription_preview}")

        # Process through normal message handler
        return await process_message(text, user, phone)

    except Exception as e:
        logger.error("whatsapp_audio_error", error=str(e)[:100])
        return "Sorry, I couldn't process your voice message."


async def handle_whatsapp_document(doc: dict, user: dict, phone: str) -> str:
    """Handle WhatsApp document message."""
    from src.services.evolution import download_media
    from src.services.media import extract_pdf_text
    import structlog

    logger = structlog.get_logger()

    filename = doc.get("fileName", "document")
    mime_type = doc.get("mimetype", "")
    doc_url = doc.get("url")
    caption = doc.get("caption", "")

    logger.info("whatsapp_document", filename=filename, mime=mime_type)

    if not doc_url:
        return "Could not access document."

    try:
        doc_bytes = await download_media(doc_url)
        if not doc_bytes:
            return "Failed to download document."

        # Handle by mime type
        if mime_type == "application/pdf" or filename.endswith(".pdf"):
            # Extract text from PDF
            text = await extract_pdf_text(doc_bytes)
            if not text:
                return "Could not extract text from PDF."

            # Summarize or analyze
            prompt = caption or f"Summarize this document ({filename}):"
            combined = f"{prompt}\n\n{text[:10000]}"  # Limit context

            return await process_message(combined, user, phone)

        elif mime_type.startswith("text/") or filename.endswith((".txt", ".md", ".json")):
            # Text file
            try:
                content = doc_bytes.decode("utf-8")[:5000]
                prompt = caption or f"Analyze this file ({filename}):"
                return await process_message(f"{prompt}\n\n{content}", user, phone)
            except UnicodeDecodeError:
                return "Could not read file as text."

        else:
            return f"Received document: {filename}\nDocument type ({mime_type}) not yet supported."

    except Exception as e:
        logger.error("whatsapp_document_error", error=str(e)[:100])
        return "Sorry, I couldn't process the document."


async def handle_whatsapp_callback(callback_id: str, user: dict, phone: str) -> str:
    """Handle WhatsApp button/list selection callback.

    Args:
        callback_id: Button ID or row ID from interactive message response
        user: User dict with platform info
        phone: User's phone number

    Returns:
        Response message to send back to user
    """
    import structlog
    logger = structlog.get_logger()

    logger.info("whatsapp_callback", id=callback_id, phone=phone[:6] + "...")

    if callback_id.startswith("skill_"):
        # User selected a skill from menu
        skill_name = callback_id[6:]  # Remove "skill_" prefix
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.set_pending_skill(phone, skill_name)
        return f"Selected skill: *{skill_name}*\n\nSend your task now."

    return f"Unknown selection: {callback_id}"


async def send_skill_menu_whatsapp(phone: str, skills: list) -> bool:
    """Send skill selection menu via WhatsApp list message.

    Args:
        phone: Phone number to send menu to
        skills: List of skill objects with name and description

    Returns:
        True if sent successfully
    """
    from src.services.evolution import send_list

    sections = [{
        "title": "Available Skills",
        "rows": [
            {
                "rowId": f"skill_{s.name}",
                "title": s.name[:24],
                "description": (s.description or "")[:72]
            }
            for s in skills[:10]  # Max 10 per section
        ]
    }]

    return await send_list(
        phone=phone,
        text="Select a skill to use:",
        button_text="View Skills",
        sections=sections,
        title="Skills Menu"
    )


async def send_evolution_message(phone: str, text: str) -> bool:
    """Send message via Evolution API.

    Args:
        phone: Phone number (e.g., "5511999999999" or "5511999999999@s.whatsapp.net")
        text: Message text (max 4096 chars)

    Returns:
        True if sent successfully
    """
    import httpx
    import structlog

    logger = structlog.get_logger()

    api_url = os.environ.get("EVOLUTION_API_URL", "")
    api_key = os.environ.get("EVOLUTION_API_KEY", "")
    instance = os.environ.get("EVOLUTION_INSTANCE", "main")

    if not api_url or not api_key:
        logger.error("evolution_credentials_missing")
        return False

    url = f"{api_url}/message/sendText/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    # Format phone number (add @s.whatsapp.net if needed)
    remote_jid = phone if "@" in phone else f"{phone}@s.whatsapp.net"

    payload = {
        "number": remote_jid,
        "text": text[:4096]  # WhatsApp limit
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200 or response.status_code == 201:
                logger.info("evolution_sent", phone=phone[:6] + "...")
                return True
            else:
                logger.warning("evolution_send_failed",
                    status=response.status_code,
                    body=response.text[:200]
                )
                return False

    except Exception as e:
        logger.error("evolution_send_error", error=str(e)[:100])
        return False


@app.cls(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    min_containers=1,  # Always-on for fast response
    timeout=60,
)
@modal.concurrent(max_inputs=100)
class TelegramChatAgent:
    """Telegram Chat Agent with cache warming."""

    @modal.enter()
    async def warm_caches(self):
        """Warm caches when container starts."""
        import structlog
        logger = structlog.get_logger()

        try:
            from src.core.state import get_state_manager
            state = get_state_manager()
            await state.warm()
            logger.info("cache_warming_done")
        except Exception as e:
            logger.warning("cache_warming_failed", error=str(e))

    @modal.asgi_app()
    def app(self):
        return web_app


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("telegram-credentials")],
    volumes={"/skills": skills_volume},
    timeout=120,
)
def sync_skills_from_github():
    """Sync skills from GitHub repo to Modal Volume (filtering local-only skills)."""
    import re
    import yaml
    from pathlib import Path

    repo_url = os.environ.get("SKILLS_REPO", "")
    branch = os.environ.get("SKILLS_BRANCH", "main")
    skills_path_in_repo = os.environ.get("SKILLS_PATH", "skills")

    if not repo_url:
        return {"status": "skipped", "reason": "SKILLS_REPO not configured"}

    token = os.environ.get("GITHUB_TOKEN", "")
    repo_dir = "/tmp/repo"

    if os.path.exists(repo_dir):
        subprocess.run(["git", "-C", repo_dir, "pull", "origin", branch], check=True)
    else:
        if token:
            clone_url = f"https://{token}@github.com/{repo_url}.git"
        else:
            clone_url = f"https://github.com/{repo_url}.git"
        subprocess.run(["git", "clone", "--depth", "1", "-b", branch, clone_url, repo_dir], check=True)

    src_skills = os.path.join(repo_dir, skills_path_in_repo)
    if os.path.exists(src_skills):
        synced = []
        skipped = []

        for skill_dir in Path(src_skills).iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            # Check deployment field in frontmatter
            info_file = skill_dir / "info.md"
            deployment = "remote"  # Default: sync to Modal

            if info_file.exists():
                content = info_file.read_text()
                if content.startswith('---'):
                    end_match = re.search(r'\n---\n', content[3:])
                    if end_match:
                        try:
                            fm = yaml.safe_load(content[3:end_match.start() + 3]) or {}
                            deployment = fm.get('deployment', 'remote')
                        except yaml.YAMLError:
                            pass

            # Only sync remote or both skills
            if deployment in ['remote', 'both']:
                dest = Path(f"/skills/{skill_dir.name}")
                dest.mkdir(parents=True, exist_ok=True)
                subprocess.run(["cp", "-r", f"{skill_dir}/.", str(dest)], check=True)
                synced.append(skill_dir.name)
            else:
                skipped.append(skill_dir.name)

        skills_volume.commit()

        return {
            "status": "synced",
            "repo": repo_url,
            "branch": branch,
            "synced": synced,
            "synced_count": len(synced),
            "skipped": skipped,
            "skipped_count": len(skipped),
        }

    return {"status": "skipped", "reason": "skills path not found in repo"}


# ==================== GitHub Agent ====================

@app.function(
    image=image,
    secrets=secrets + [github_secret],
    volumes={"/skills": skills_volume},
    timeout=120,
)
async def github_agent(task: dict):
    """GitHub Agent - Repository automation."""
    from src.agents.github_automation import process_github_task
    return await process_github_task(task)


@app.function(
    image=image,
    secrets=secrets + [github_secret],
    volumes={"/skills": skills_volume},
    schedule=modal.Cron("0 * * * *"),  # Every hour for repo monitoring
    timeout=300,
)
async def github_monitor():
    """Monitor configured repositories for new activity (hourly)."""
    from src.agents.github_automation import monitor_repositories
    import structlog
    import aiofiles
    logger = structlog.get_logger()

    # Read monitored repos from skill file (async)
    from pathlib import Path
    info_path = Path("/skills/github/info.md")
    repos = []

    if info_path.exists():
        async with aiofiles.open(info_path, 'r') as f:
            content = await f.read()
        # Parse repos from info.md (look for ## Monitored Repos section)
        if "## Monitored Repos" in content:
            lines = content.split("## Monitored Repos")[1].split("##")[0].strip().split("\n")
            repos = [l.strip("- ").strip() for l in lines if l.strip().startswith("-")]

    if not repos:
        logger.info("github_monitor_skip", reason="No repos configured")
        return {"status": "skipped", "reason": "No repos configured in skill"}

    result = await monitor_repositories(repos)
    logger.info("github_monitor_complete", repos=len(repos))
    return result


# ==================== Data Agent ====================

@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=180,
)
async def data_agent(task: dict):
    """Data Agent - Analytics and reporting."""
    from src.agents.data_processor import process_data_task
    return await process_data_task(task)


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    schedule=modal.Cron("0 1 * * *"),  # 1 AM UTC = 8 AM ICT
    timeout=300,
)
async def daily_summary():
    """Generate daily activity summary (8 AM ICT)."""
    import structlog
    logger = structlog.get_logger()

    task = {"type": "data", "payload": {"action": "daily_summary"}}
    result = await data_agent.remote.aio(task)

    logger.info("daily_summary_complete", status=result.get("status"))
    return result


# ==================== Reminder Cron ====================

@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
    timeout=60,
)
async def send_due_reminders():
    """Check for due reminders and send them."""
    import structlog
    from src.services.firebase import (
        init_firebase, get_due_reminders, mark_reminder_sent
    )

    logger = structlog.get_logger()
    init_firebase()

    try:
        reminders = await get_due_reminders()
        logger.info("checking_reminders", count=len(reminders))

        for reminder in reminders:
            chat_id = reminder.get("chat_id")
            message = reminder.get("message")
            reminder_id = reminder.get("id")

            # Send notification
            await send_telegram_message(
                chat_id,
                f"⏰ <b>Reminder</b>\n\n{message}"
            )

            # Mark as sent
            await mark_reminder_sent(reminder_id)
            logger.info("reminder_sent", id=reminder_id)

    except Exception as e:
        logger.error("reminder_error", error=str(e))


# ==================== Content Agent ====================

@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=120,
)
async def content_agent(task: dict):
    """Content Agent - Content generation and transformation."""
    from src.agents.content_generator import process_content_task
    return await process_content_task(task)


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=60,
)
def init_skills():
    """Initialize skills directory with all agent info.md files."""
    from pathlib import Path

    skills = {
        "telegram-chat": """# AI4U.now Bot

## Your Identity
Your name is AI4U.now Bot. You were created by the AI4U.now team. You are a unified AI assistant that provides access to multiple AI models through a single Telegram interface.

When users ask who you are, introduce yourself as "AI4U.now Bot". When asked about your creator, say you were made by the "AI4U.now team".

## Instructions
- Be concise and friendly
- Use markdown formatting when helpful
- Respond in the same language as the user

## Tools Available
- web_search: Search the web for current information
- get_datetime: Get current date/time in any timezone
- run_python: Execute Python code for calculations
- read_webpage: Fetch and read URL content
- search_memory: Query past conversations

## Commands
- /start - Welcome message
- /help - Show available commands
- /status - Check agent status
- /translate <text> - Translate to English
- /summarize <text> - Summarize text
- /rewrite <text> - Improve text
""",
        "github": """# GitHub Agent

## Instructions
You are a GitHub automation agent. Handle repository tasks efficiently.

## Tools Available
- create_issue: Create new GitHub issues
- summarize_pr: Summarize pull requests with LLM
- repo_stats: Get repository statistics
- list_issues: List open issues

## Monitored Repos
[Add repos here, one per line with - prefix]

## Memory
[Past interactions and learnings]
""",
        "data": """# Data Agent

## Instructions
You are a data analysis agent. Generate reports and insights.

## Tools Available
- daily_summary: Generate daily activity summary
- analyze_data: Analyze provided data with LLM
- generate_report: Create formatted reports

## Schedule
- Daily summary: 8 AM ICT (1 AM UTC)

## Memory
[Past reports and patterns]
""",
        "content": """# Content Agent

## Instructions
You are a content generation agent. Write, translate, and transform text.

## Tools Available
- write_content: Generate new content on any topic
- translate: Translate between languages
- summarize: Summarize long text
- rewrite: Improve and rewrite text
- email_draft: Draft professional emails

## API Access
- Telegram: /translate, /summarize, /rewrite commands
- HTTP: POST /api/content with {action, ...params}

## Memory
[Content patterns and preferences]
""",
    }

    created = []
    for skill_name, content in skills.items():
        skill_path = Path(f"/skills/{skill_name}/info.md")
        if not skill_path.exists():
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(content)
            created.append(f"{skill_name}/info.md")

    if created:
        skills_volume.commit()
        return {"status": "initialized", "files": created}

    return {"status": "already_initialized", "skills": list(skills.keys())}


# =============================================================================
# SKILL SYNC FUNCTIONS
# =============================================================================

def _extract_section(content: str, section_name: str) -> str:
    """Extract content of a markdown section."""
    import re
    pattern = rf"## {section_name}\n([\s\S]*?)(?=\n## |\Z)"
    match = re.search(pattern, content)
    return match.group(1).strip() if match else ""


def _update_section(content: str, section_name: str, new_content: str) -> str:
    """Update or append a markdown section."""
    import re
    pattern = rf"(## {section_name}\n)[\s\S]*?(?=\n## |\Z)"
    replacement = f"## {section_name}\n\n{new_content}\n\n"
    if re.search(pattern, content):
        return re.sub(pattern, replacement, content)
    return content.rstrip() + f"\n\n{replacement}"


@app.function(
    image=image,
    volumes={"/skills": skills_volume},
    timeout=120,
)
def sync_skills_from_local():
    """Sync skills from container's skills_source to Modal Volume.

    Called on deploy to ensure Volume has latest skill definitions.
    Preserves Memory and Error History sections from Volume (runtime learnings).

    Local-First Flow:
    1. Local changes applied via pull-improvements.py
    2. git commit && git push
    3. modal deploy → this function syncs to Volume
    4. Volume Memory/Error History preserved (runtime learnings)
    """
    import shutil
    from pathlib import Path
    import structlog

    logger = structlog.get_logger()
    source_dir = Path("/root/skills_source")
    target_dir = Path("/skills")

    if not source_dir.exists():
        return {"status": "skipped", "reason": "No skills_source directory"}

    synced = []
    preserved_memory = []

    for skill_dir in source_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
            continue

        target_skill = target_dir / skill_dir.name
        target_skill.mkdir(parents=True, exist_ok=True)

        source_info = skill_dir / "info.md"
        target_info = target_skill / "info.md"

        if source_info.exists():
            if target_info.exists():
                # Preserve existing Memory and Error History from Volume
                existing_content = target_info.read_text()
                memory = _extract_section(existing_content, "Memory")
                errors = _extract_section(existing_content, "Error History")

                new_content = source_info.read_text()

                # Preserve runtime learnings from Volume if they exist
                if memory and "[Accumulated learnings" not in memory:
                    new_content = _update_section(new_content, "Memory", memory)
                    preserved_memory.append(skill_dir.name)
                if errors and "[Past errors" not in errors:
                    new_content = _update_section(new_content, "Error History", errors)

                target_info.write_text(new_content)
            else:
                shutil.copy2(source_info, target_info)

            synced.append(skill_dir.name)

        # Sync scripts/ and references/ directories
        for subdir in ["scripts", "references"]:
            source_sub = skill_dir / subdir
            if source_sub.exists():
                target_sub = target_skill / subdir
                if target_sub.exists():
                    shutil.rmtree(target_sub)
                shutil.copytree(source_sub, target_sub)

    skills_volume.commit()
    logger.info("skills_synced", count=len(synced), preserved=len(preserved_memory))

    return {
        "status": "synced",
        "skills": synced,
        "count": len(synced),
        "preserved_memory": preserved_memory
    }


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_firebase():
    """Test Firebase connection."""
    from src.services.firebase import init_firebase

    db = init_firebase()
    # Test write
    db.collection("_test").document("ping").set({"status": "ok", "timestamp": datetime.utcnow()})
    # Test read
    doc = db.collection("_test").document("ping").get()
    data = doc.to_dict()
    print(f"Firebase test result: {data}")
    # Cleanup
    db.collection("_test").document("ping").delete()

    # Return simple dict that can be serialized without google.api_core
    return {"status": "success", "verified": True}


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_embeddings():
    """Test Z.AI embedding generation."""
    from src.services.embeddings import EMBEDDING_MODEL, VECTOR_DIM

    try:
        from src.services.embeddings import get_embedding
        text = "Hello, this is a test message for embedding generation."
        embedding = get_embedding(text)

        dim = len(embedding)
        print(f"Embedding dimension: {dim}")
        print(f"Expected dimension: {VECTOR_DIM}")
        print(f"First 5 values: {embedding[:5]}")

        return {
            "status": "success",
            "dimension": dim,
            "expected_dim": VECTOR_DIM,
        }
    except Exception as e:
        print(f"Embedding service not available: {e}")
        return {
            "status": "skipped",
            "reason": "Embedding model not available in API tier",
            "model": EMBEDDING_MODEL,
        }


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_qdrant():
    """Test Qdrant connection and operations."""
    from src.services.qdrant import is_enabled, init_collections

    if not is_enabled():
        return {"status": "skipped", "reason": "Qdrant credentials not configured"}

    result = init_collections()
    return {"status": "success", **result}


@app.function(
    image=image,
    secrets=secrets,
    timeout=120,
)
def test_github():
    """Test GitHub agent connection."""
    from src.agents.github_automation import is_configured

    if not is_configured():
        return {"status": "skipped", "reason": "GitHub token not configured"}

    # Test basic GitHub API access
    from github import Github
    g = Github(os.environ.get("GITHUB_TOKEN", ""))

    try:
        user = g.get_user()
        return {
            "status": "success",
            "login": user.login,
            "public_repos": user.public_repos,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_llm():
    """Test LLM providers (Anthropic primary, Z.AI fallback)."""
    from src.services.llm import get_llm_client

    client = get_llm_client()

    try:
        response = client.chat(
            messages=[{"role": "user", "content": "Say hello in exactly 5 words"}],
            max_tokens=50,
        )
        return {
            "status": "success",
            "response": response,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.local_entrypoint()
def main(sync: bool = False):
    """Local entrypoint with optional skill sync.

    Args:
        sync: If True, sync skills from local to Volume before testing

    Usage:
        modal run main.py           # Test LLM only
        modal run main.py --sync    # Sync skills then test
        modal deploy main.py        # Deploy (skills bundled in image)
    """
    if sync:
        print("Syncing skills to Volume...")
        result = sync_skills_from_local.remote()
        print(f"Sync result: {result}")
        print()

    print("Testing LLM...")
    result = test_llm.remote()
    print(f"LLM test result: {result}")
    print("\nDeploy URL: https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run")


@app.function(image=image, secrets=secrets)
async def _test_gemini_remote():
    """Run Gemini test on Modal."""
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    result = await client.chat(
        messages=[{"role": "user", "content": "Hello, test message. Reply briefly."}],
    )
    return {
        "project": client.project_id,
        "location": client.location,
        "response": result[:500] if result else "No response"
    }


@app.function(image=image, secrets=secrets)
async def _test_grounding_remote():
    """Run grounding test on Modal."""
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    result = await client.grounded_query(
        query="What's the current price of Bitcoin?"
    )
    return {
        "answer": result.text[:500] if result.text else "No answer",
        "citations": len(result.citations) if result.citations else 0
    }


@app.function(image=image, secrets=secrets, timeout=300)
async def _test_deep_research_remote(user_id: int = 123456):
    """Run deep research test on Modal."""
    from src.tools.gemini_tools import execute_deep_research

    result = await execute_deep_research(
        query="Current state of AI agents in 2025",
        user_id=user_id,
        progress_callback=lambda s: print(f"Progress: {s}"),
        max_iterations=2
    )
    return result


@app.local_entrypoint()
def test_gemini():
    """Test Gemini client initialization."""
    print("Running Gemini test on Modal...")
    result = _test_gemini_remote.remote()
    print(f"Project: {result['project']}")
    print(f"Location: {result['location']}")
    print(f"Response: {result['response']}")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("firebase-credentials"), modal.Secret.from_name("admin-credentials")]
)
async def _grant_user_tier(telegram_id: int, tier: str):
    """Grant tier to user (runs on Modal)."""
    import os
    from src.services.firebase import set_user_tier, get_user_tier

    admin_id = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))

    current = await get_user_tier(telegram_id)
    success = await set_user_tier(telegram_id, tier, admin_id)
    new_tier = await get_user_tier(telegram_id) if success else current

    return {
        "telegram_id": telegram_id,
        "previous_tier": current,
        "new_tier": new_tier,
        "success": success
    }


@app.local_entrypoint()
def grant_user(telegram_id: int, tier: str = "user"):
    """Grant tier to user. Usage: modal run main.py::grant_user --telegram-id 123 --tier user"""
    print(f"Granting {tier} tier to {telegram_id}...")
    result = _grant_user_tier.remote(telegram_id, tier)
    print(f"Previous tier: {result['previous_tier']}")
    print(f"New tier: {result['new_tier']}")
    print(f"Success: {result['success']}")


@app.local_entrypoint()
def test_grounding():
    """Test grounded query."""
    print("Running grounding test on Modal...")
    result = _test_grounding_remote.remote()
    print(f"Answer: {result['answer']}")
    print(f"Citations: {result['citations']}")


@app.local_entrypoint()
def test_deep_research():
    """Test deep research skill."""
    print("Running deep research test on Modal...")
    result = _test_deep_research_remote.remote()
    print(f"\nSuccess: {result['success']}")
    if result['success']:
        print(f"Queries: {result['query_count']}")
        print(f"Duration: {result['duration_seconds']:.1f}s")
        if result.get('report_id'):
            print(f"\nReport ID: {result['report_id']}")
            print(f"Download URL: {result['download_url']}")
        print(f"\n{'='*60}\nFULL REPORT:\n{'='*60}\n")
        print(result.get('report', result['summary']))
        if result.get('citations'):
            print(f"\n{'='*60}\nCITATIONS:\n{'='*60}\n")
            print(result['citations'])
