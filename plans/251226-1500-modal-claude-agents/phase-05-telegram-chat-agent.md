# Phase 5: Telegram Chat Agent

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 4 - Vercel Edge Webhooks](./phase-04-vercel-edge-webhooks.md)
- Telegram Bot API: https://core.telegram.org/bots/api

## Overview

**Priority:** P1 - Primary Interface
**Status:** Pending
**Effort:** 3h

Build the Telegram Chat Agent as the primary user interface. Receives webhooks, processes messages with Claude, delegates to other agents, and responds to users.

## Why Telegram (Testing)

| Advantage | Details |
|-----------|---------|
| Easy setup | Create bot via @BotFather in minutes |
| No approval | Unlike Zalo OA, no business verification needed |
| Great API | Well-documented, webhook support, no rate limits |
| Free | No costs for bot usage |
| Global | Works worldwide for testing |

## Requirements

### Functional
- Receive Telegram webhooks (messages, commands)
- Process messages with Claude API
- Query conversation history from Qdrant
- Delegate tasks to other agents via Firebase
- Respond quickly (no strict timeout like Zalo)
- Handle bot commands (/start, /help, /status)

### Non-Functional
- Always-on via `min_containers=1`
- HTTPS endpoint (Modal provides)
- Structured logging for debugging

## Telegram Webhook Events

| Update Type | Description | Handler |
|-------------|-------------|---------|
| `message` | User sends message | Process with Claude |
| `callback_query` | Inline button pressed | Handle action |
| `edited_message` | Message edited | Optional: re-process |

## Message Flow

```
User (Telegram) ──► Telegram API ──► Modal Webhook
                                          │
                                          ▼
                                   ┌─────────────────┐
                                   │ Parse Update     │
                                   └────────┬────────┘
                                            │
                                   ┌────────▼────────┐
                                   │ Get User Context │◄── Qdrant
                                   └────────┬────────┘
                                            │
                                   ┌────────▼────────┐
                                   │ Process w/ Claude│◄── Anthropic
                                   └────────┬────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                    ┌──────────┐     ┌──────────┐     ┌──────────┐
                    │ Dispatch │     │ Store    │     │ Respond  │
                    │ Task     │     │ Memory   │     │ to User  │
                    └──────────┘     └──────────┘     └──────────┘
                         │                │                │
                    Firebase          Qdrant         Telegram API
```

## Implementation Steps

### 1. Create Telegram Bot

```bash
# In Telegram:
# 1. Message @BotFather
# 2. /newbot
# 3. Follow prompts, get token
# 4. Save token as Modal secret

modal secret create telegram-credentials \
  TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

### 2. Create Telegram Agent in main.py

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

web_app = FastAPI()

TELEGRAM_API = "https://api.telegram.org/bot{token}"

@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    min_containers=1,  # Always-on for fast response
    timeout=60,
    allow_concurrent_inputs=100,
)
@modal.asgi_app()
def telegram_chat_agent():
    """Telegram Chat Agent - Primary interface."""
    return web_app

@web_app.get("/health")
async def health():
    return {"status": "ok", "agent": "telegram"}

@web_app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates."""
    update = await request.json()

    # Extract message
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    user = message.get("from", {})

    if not chat_id or not text:
        return {"ok": True}

    # Handle commands
    if text.startswith("/"):
        response = await handle_command(text, user)
    else:
        response = await process_message(text, user, chat_id)

    # Send response
    await send_telegram_message(chat_id, response)

    return {"ok": True}

async def send_telegram_message(chat_id: int, text: str):
    """Send message via Telegram API."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })

async def handle_command(command: str, user: dict) -> str:
    """Handle bot commands."""
    cmd = command.split()[0].lower()

    if cmd == "/start":
        return f"👋 Hello {user.get('first_name', 'there')}! I'm your AI assistant."
    elif cmd == "/help":
        return "Available commands:\n/start - Welcome\n/help - This message\n/status - Check agent status"
    elif cmd == "/status":
        return "✅ Agent is running normally."
    else:
        return "Unknown command. Try /help"
```

### 3. Create TelegramAgent Class

```python
# agents/src/agents/telegram_chat.py
from src.agents.base import BaseAgent
from src.services.qdrant import get_conversation_context
from src.services.firebase import log_activity

class TelegramChatAgent(BaseAgent):
    """Telegram chat agent with self-improvement."""

    def __init__(self):
        super().__init__("telegram-chat")

    async def process(self, message: str, user_id: str, chat_id: int) -> str:
        # Get conversation context
        context = await get_conversation_context(user_id, limit=5)

        # Build prompt with context
        prompt = self._build_prompt(message, context)

        # Execute with LLM (includes circuit breaker, retries)
        response = await self.execute_with_llm(prompt)

        # Store in memory
        await self._store_message(user_id, message, response)

        # Log activity
        await log_activity(
            agent=self.agent_id,
            action="message_processed",
            details={"user_id": user_id, "chat_id": chat_id}
        )

        return response
```

### 4. Set Webhook URL

```python
# Run once to register webhook
async def set_telegram_webhook():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    webhook_url = "https://your-app.modal.run/webhook/telegram"

    url = f"https://api.telegram.org/bot{token}/setWebhook"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "url": webhook_url,
            "allowed_updates": ["message", "callback_query"],
        })
        print(response.json())
```

### 5. Update Modal Secrets

```bash
# Add Telegram token
modal secret create telegram-credentials \
  TELEGRAM_BOT_TOKEN=your-bot-token
```

## Files to Create/Modify

| Path | Action | Description |
|------|--------|-------------|
| `agents/main.py` | Modify | Add Telegram webhook endpoint |
| `agents/src/agents/telegram_chat.py` | Create | TelegramChatAgent class |
| `agents/skills/telegram-chat/info.md` | Create | Agent instructions |
| `agents/skills/telegram-chat/agent.py` | Create | Agent implementation |

## Todo List

- [ ] Create Telegram bot via @BotFather
- [ ] Save bot token as Modal secret
- [ ] Add webhook endpoint to main.py
- [ ] Create TelegramChatAgent class
- [ ] Create skills/telegram-chat/ directory
- [ ] Set webhook URL after deployment
- [ ] Test message flow end-to-end

## Success Criteria

- [ ] Bot responds to /start command
- [ ] Messages processed by Claude
- [ ] Conversation context retrieved from Qdrant
- [ ] Activities logged to Firebase
- [ ] Self-improvement loop functional

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Webhook not set | Bot won't receive messages | Verify webhook after deploy |
| Token exposed | Security breach | Use Modal Secrets only |
| Rate limiting | Delayed responses | Monitor usage, add caching |

## Security Considerations

- Store bot token in Modal Secrets only
- Validate incoming webhook payloads
- Don't log message content in production

## Telegram vs Zalo Comparison

| Feature | Telegram | Zalo |
|---------|----------|------|
| Setup time | ~5 minutes | Days (approval) |
| API quality | Excellent | Good |
| Response timeout | None | 2 seconds |
| Cost | Free | Free |
| Best for | Development/testing | Vietnam production |

## Next Steps

→ Phase 6: GitHub Agent
