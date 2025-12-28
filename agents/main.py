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
    .add_local_dir("src", remote_path="/root/src")
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
]

# GitHub secret (separate for security)
github_secret = modal.Secret.from_name("github-credentials")


def create_web_app():
    """Create FastAPI app (called inside Modal container)."""
    from fastapi import FastAPI, Request, HTTPException, Header, Depends
    from typing import Optional
    from datetime import timezone
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    import hmac

    web_app = FastAPI()

    # Initialize rate limiter
    limiter = Limiter(key_func=get_remote_address)
    web_app.state.limiter = limiter
    web_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def verify_admin_token(x_admin_token: str = Header(None)):
        """Verify admin token from X-Admin-Token header."""
        expected_token = os.environ.get("ADMIN_TOKEN")
        if not expected_token:
            raise HTTPException(status_code=500, detail="Admin token not configured")
        if not x_admin_token or x_admin_token != expected_token:
            raise HTTPException(status_code=401, detail="Invalid or missing admin token")
        return True

    async def verify_telegram_webhook(request: Request) -> bool:
        """Verify Telegram webhook using secret token (timing-safe comparison).

        SECURITY: Fail-closed - requires secret to be configured in production.
        Set TELEGRAM_WEBHOOK_SECRET="" explicitly to disable (not recommended).
        """
        secret_token = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
        if secret_token is None:
            # Not configured - reject in production (fail-closed)
            import structlog
            structlog.get_logger().warning("telegram_webhook_secret_not_configured")
            raise HTTPException(status_code=500, detail="Webhook verification not configured")

        if secret_token == "":
            # Explicitly disabled (empty string) - allow but log warning
            return True

        header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        return hmac.compare_digest(secret_token, header_token)

    @web_app.get("/health")
    async def health():
        """Health check endpoint with circuit status."""
        from src.core.resilience import get_circuit_stats

        circuits = get_circuit_stats()
        any_open = any(c["state"] == "open" for c in circuits.values())

        return {
            "status": "degraded" if any_open else "healthy",
            "agent": "claude-agents",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "circuits": circuits,
        }

    @web_app.get("/api/traces")
    async def list_traces_endpoint(
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 20,
        _: bool = Depends(verify_admin_token)
    ):
        """List execution traces for debugging."""
        from src.core.trace import list_traces

        try:
            traces = await list_traces(user_id=user_id, status=status, limit=limit)
            return {
                "traces": [t.to_dict() for t in traces],
                "count": len(traces),
            }
        except Exception as e:
            return {"error": str(e)}, 500

    @web_app.get("/api/traces/{trace_id}")
    async def get_trace_endpoint(trace_id: str, _: bool = Depends(verify_admin_token)):
        """Get single trace by ID."""
        from src.core.trace import get_trace

        trace = await get_trace(trace_id)
        if trace:
            return trace.to_dict()
        return {"error": "Trace not found"}, 404

    @web_app.get("/api/circuits")
    async def get_circuits_endpoint(_: bool = Depends(verify_admin_token)):
        """Get circuit breaker status for all services."""
        from src.core.resilience import get_circuit_stats
        return get_circuit_stats()

    @web_app.post("/api/circuits/reset")
    async def reset_circuits_endpoint(_: bool = Depends(verify_admin_token)):
        """Reset all circuit breakers (admin only)."""
        from src.core.resilience import reset_all_circuits
        reset_all_circuits()
        return {"message": "All circuits reset"}

    @web_app.post("/webhook/telegram")
    @limiter.limit("30/minute")  # 30 requests per minute per IP
    async def telegram_webhook(request: Request):
        """Handle Telegram webhook updates."""
        import structlog
        logger = structlog.get_logger()

        # Verify webhook signature
        if not await verify_telegram_webhook(request):
            logger.warning("telegram_webhook_invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid webhook token")

        try:
            update = await request.json()
            logger.info("telegram_update", update_id=update.get("update_id"))

            # Check for callback query (button press)
            callback = update.get("callback_query")
            if callback:
                return await handle_callback(callback)

            # Extract message
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            user = message.get("from", {})

            if not chat_id or not text:
                return {"ok": True}

            logger.info("processing_message", chat_id=chat_id, text_len=len(text))

            # Handle commands
            if text.startswith("/"):
                response = await handle_command(text, user, chat_id)
            else:
                response = await process_message(text, user, chat_id)

            # Response may be None if already sent (e.g., keyboard)
            if response:
                logger.info("sending_response", chat_id=chat_id, response_len=len(response))
                await send_telegram_message(chat_id, response)

            return {"ok": True}

        except Exception as e:
            logger.error("webhook_error", error=str(e))
            return {"ok": False, "error": str(e)}

    @web_app.post("/webhook/github")
    async def github_webhook(request: Request):
        """Handle GitHub webhook events."""
        import structlog
        logger = structlog.get_logger()

        try:
            event = request.headers.get("X-GitHub-Event", "push")
            payload = await request.json()

            logger.info("github_webhook", event=event)

            task = {
                "type": "github",
                "payload": {
                    "action": f"handle_{event}",
                    "event": event,
                    "data": payload
                }
            }

            from src.agents.github_automation import process_github_task
            result = await process_github_task(task)
            return {"ok": True, "result": result}

        except Exception as e:
            logger.error("github_webhook_error", error=str(e))
            return {"ok": False, "error": str(e)}

    @web_app.post("/api/content")
    async def content_api(request: Request):
        """Content Agent HTTP API endpoint."""
        import structlog
        logger = structlog.get_logger()

        try:
            payload = await request.json()
            logger.info("content_api", action=payload.get("action"))

            task = {"type": "content", "payload": payload}

            from src.agents.content_generator import process_content_task
            result = await process_content_task(task)
            return {"ok": True, "result": result}

        except Exception as e:
            logger.error("content_api_error", error=str(e))
            return {"ok": False, "error": str(e)}

    @web_app.post("/api/skill")
    async def skill_api(request: Request):
        """II Framework Skill API endpoint.

        Invoke Modal-deployed skills from Claude Code.

        Request body:
        {
            "skill": "planning",
            "task": "Create a plan for user authentication",
            "context": {"project": "my-app"},  # optional
            "mode": "simple"  # simple|routed|orchestrated|chained|evaluated
        }
        """
        import structlog
        import time
        logger = structlog.get_logger()

        try:
            payload = await request.json()
            skill_name = payload.get("skill")
            task = payload.get("task", "")
            context = payload.get("context", {})
            mode = payload.get("mode", "simple")

            logger.info("skill_api", skill=skill_name, mode=mode, task_len=len(task))

            start = time.time()

            if mode == "simple":
                # Direct skill execution
                result = await execute_skill_simple(skill_name, task, context)
            elif mode == "routed":
                # Use router to find best skill
                result = await execute_skill_routed(task, context)
            elif mode == "orchestrated":
                # Use orchestrator for complex tasks
                result = await execute_skill_orchestrated(task, context)
            elif mode == "chained":
                # Execute skill chain
                skills = payload.get("skills", [skill_name])
                result = await execute_skill_chained(skills, task)
            elif mode == "evaluated":
                # Execute with quality evaluation
                result = await execute_skill_evaluated(skill_name, task)
            else:
                return {"ok": False, "error": f"Unknown mode: {mode}"}

            duration_ms = int((time.time() - start) * 1000)

            logger.info("skill_complete", skill=skill_name, mode=mode, duration_ms=duration_ms)

            return {
                "ok": True,
                "result": result,
                "skill": skill_name,
                "mode": mode,
                "duration_ms": duration_ms
            }

        except Exception as e:
            logger.error("skill_api_error", error=str(e))
            return {"ok": False, "error": str(e)}

    @web_app.get("/api/skills")
    async def list_skills():
        """List all available skills."""
        from src.skills.registry import get_registry

        registry = get_registry()
        summaries = registry.discover()

        return {
            "ok": True,
            "skills": [
                {"name": s.name, "description": s.description}
                for s in summaries
            ],
            "count": len(summaries)
        }

    return web_app


async def execute_skill_simple(skill_name: str, task: str, context: dict) -> str:
    """Execute a skill directly."""
    from src.skills.registry import get_registry
    from src.services.llm import get_llm_client

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


async def handle_command(command: str, user: dict, chat_id: int) -> str:
    """Handle bot commands including skill terminal commands."""
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        return f"Hello {user.get('first_name', 'there')}! I'm your AI assistant powered by II Framework.\n\nUse /skills to browse available skills or /help for commands."

    elif cmd == "/help":
        return (
            "<b>Available commands:</b>\n\n"
            "/start - Welcome\n"
            "/help - This message\n"
            "/status - Check agent status\n"
            "/skills - Browse all skills (interactive menu)\n"
            "/skill &lt;name&gt; &lt;task&gt; - Execute a skill directly\n"
            "/mode &lt;simple|routed|evaluated&gt; - Set execution mode\n"
            "/cancel - Cancel pending operation\n"
            "/clear - Clear conversation history\n"
            "/translate &lt;text&gt; - Translate to English\n"
            "/summarize &lt;text&gt; - Summarize text\n"
            "/rewrite &lt;text&gt; - Improve text"
        )

    elif cmd == "/status":
        return "Agent is running normally."

    elif cmd == "/skills":
        # Show inline keyboard with skill categories
        await send_skills_menu(chat_id)
        return None  # Message already sent

    elif cmd == "/skill":
        if not args:
            return "Usage: /skill &lt;name&gt; &lt;task&gt;\nExample: /skill planning Create auth system"

        skill_parts = args.split(maxsplit=1)
        skill_name = skill_parts[0]
        task = skill_parts[1] if len(skill_parts) > 1 else ""

        if not task:
            return f"Please provide a task for skill '{skill_name}'.\nUsage: /skill {skill_name} &lt;task&gt;"

        # Validate skill exists
        from src.skills.registry import get_registry
        registry = get_registry()
        skill = registry.get_full(skill_name)

        if not skill:
            # Suggest similar skills
            summaries = registry.discover()
            names = [s.name for s in summaries]
            suggestions = [n for n in names if n.startswith(skill_name[:3]) or skill_name in n]

            if suggestions:
                return f"Skill '{skill_name}' not found. Did you mean: {', '.join(suggestions[:3])}?"
            return f"Skill '{skill_name}' not found. Use /skills to see available skills."

        # Get user's preferred mode from StateManager
        from src.core.state import get_state_manager
        state = get_state_manager()
        mode = await state.get_user_mode(user.get("id"))

        import time
        start = time.time()
        result = await execute_skill_simple(skill_name, task, {"user": user})
        duration_ms = int((time.time() - start) * 1000)

        from src.services.telegram import format_skill_result
        return format_skill_result(skill_name, result, duration_ms)

    elif cmd == "/mode":
        valid_modes = ["simple", "routed", "evaluated"]
        from src.core.state import get_state_manager
        state = get_state_manager()
        if args not in valid_modes:
            current = await state.get_user_mode(user.get("id"))
            return f"Current mode: <b>{current}</b>\nValid modes: {', '.join(valid_modes)}\nUsage: /mode &lt;mode&gt;"

        await state.set_user_mode(user.get("id"), args)
        return f"Execution mode set to: <b>{args}</b>"

    elif cmd == "/cancel":
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.clear_pending_skill(user.get("id"))
        return "Operation cancelled."

    elif cmd == "/clear":
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.clear_conversation(user.get("id"))
        return "Conversation history cleared."

    elif cmd == "/translate" and args:
        from src.agents.content_generator import process_content_task
        task = {"payload": {"action": "translate", "text": args, "target": "en"}}
        result = await process_content_task(task)
        return result.get("message", result.get("translation", "Translation failed"))

    elif cmd == "/summarize" and args:
        from src.agents.content_generator import process_content_task
        task = {"payload": {"action": "summarize", "text": args}}
        result = await process_content_task(task)
        return result.get("message", result.get("summary", "Summary failed"))

    elif cmd == "/rewrite" and args:
        from src.agents.content_generator import process_content_task
        task = {"payload": {"action": "rewrite", "text": args}}
        result = await process_content_task(task)
        return result.get("message", result.get("rewritten", "Rewrite failed"))

    elif cmd in ["/translate", "/summarize", "/rewrite"]:
        return f"Usage: {cmd} &lt;text&gt;"

    else:
        return "Unknown command. Try /help"


async def process_message(text: str, user: dict, chat_id: int) -> str:
    """Process a regular message with agentic loop (tools enabled)."""
    from src.services.agentic import run_agentic_loop
    from src.core.state import get_state_manager
    from pathlib import Path
    import structlog
    import time
    import aiofiles

    logger = structlog.get_logger()
    state = get_state_manager()

    # Check for pending skill (user selected from /skills menu)
    pending_skill = await state.get_pending_skill(user.get("id"))

    if pending_skill:
        # Execute pending skill with this message as task
        await state.clear_pending_skill(user.get("id"))

        start = time.time()
        result = await execute_skill_simple(pending_skill, text, {"user": user})
        duration_ms = int((time.time() - start) * 1000)

        from src.services.telegram import format_skill_result
        return format_skill_result(pending_skill, result, duration_ms)

    # Normal agentic loop
    # Read instructions from skills volume (async to avoid blocking)
    info_path = Path("/skills/telegram-chat/info.md")
    system_prompt = "You are a helpful AI assistant with web search capability. Use the web_search tool when users ask about current events, weather, news, prices, or anything requiring up-to-date information."

    if info_path.exists():
        async with aiofiles.open(info_path, 'r') as f:
            system_prompt = await f.read()

    try:
        response = await run_agentic_loop(
            user_message=text,
            system=system_prompt,
            user_id=user.get("id"),
            skill=pending_skill,  # Pass skill name for tracing
        )
        return response
    except Exception as e:
        logger.error("agentic_error", error=str(e))
        return f"Sorry, I encountered an error processing your request."


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
        return create_web_app()


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
        "telegram-chat": """# Telegram Chat Agent

## Instructions
You are a helpful AI assistant communicating via Telegram.
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
def main():
    """Local test entrypoint."""
    print("Testing LLM...")
    result = test_llm.remote()
    print(f"LLM test result: {result}")
    print("\nDeploy URL: https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run")
