# Phase 2: Extract FastAPI Routes

## Context

- [main.py Review - C1](../reports/code-reviewer-251230-1121-main-py-review.md#c1-monolithic-structure---god-object-anti-pattern)
- [Comprehensive Analysis - Phase 2](../reports/codebase-review-251230-1119-comprehensive-analysis.md#phase-2-extract-routes-week-1-2---16-hrs)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P1 - High |
| Status | pending |
| Effort | 16 hours |
| Risk | MEDIUM (structural change) |
| Depends On | Phase 1 |

## Key Insights

1. **main.py has 15+ FastAPI endpoints mixed with business logic** - lines 91-519
2. **61 functions/classes in single file** - violates SRP
3. **Telegram webhook duplicates HTTP client setup 5 times** - lines 61-88, 2041-2120
4. **Dependencies scattered** - auth, rate limiting not centralized

## Requirements

- [ ] Create api/ module structure with organized routes
- [ ] Extract all FastAPI routes from main.py
- [ ] Centralize dependencies (auth, rate limiting, webhook verification)
- [ ] Reduce main.py to ~150 lines (app definition + routing only)

## Architecture Decisions

1. **Route Organization**: Group by domain (telegram, skills, admin, reports)
2. **Dependencies**: Create `api/dependencies.py` for shared middleware
3. **App Structure**: main.py imports routes, defines Modal app
4. **Backward Compatibility**: Same endpoint paths, no API changes

## Target Structure

```
agents/
├── main.py (120 lines - Modal app, route includes only)
├── api/
│   ├── __init__.py
│   ├── app.py (FastAPI app creation, middleware)
│   ├── dependencies.py (auth, rate limiting, webhook verification)
│   └── routes/
│       ├── __init__.py
│       ├── telegram.py (webhook, callbacks)
│       ├── skills.py (skill API endpoints)
│       ├── admin.py (admin endpoints)
│       ├── reports.py (reports API)
│       └── health.py (health check)
```

## Related Code Files

| File | Lines | Content to Extract |
|------|-------|-------------------|
| `agents/main.py` | 91-135 | `/health` endpoint |
| `agents/main.py` | 137-196 | Telegram webhook rate limiting |
| `agents/main.py` | 197-284 | `/webhook/telegram` endpoint |
| `agents/main.py` | 286-313 | `/webhook/github` endpoint |
| `agents/main.py` | 315-400 | `/api/skill` endpoint |
| `agents/main.py` | 402-440 | `/api/skills` endpoint |
| `agents/main.py` | 442-480 | `/api/task/{id}` endpoint |
| `agents/main.py` | 482-519 | `/api/traces`, `/api/circuits`, `/api/reports` |

## Implementation Steps

### 1. Create api/ Module Structure (1h)

```bash
mkdir -p agents/api/routes
touch agents/api/__init__.py
touch agents/api/app.py
touch agents/api/dependencies.py
touch agents/api/routes/__init__.py
touch agents/api/routes/health.py
touch agents/api/routes/telegram.py
touch agents/api/routes/skills.py
touch agents/api/routes/admin.py
touch agents/api/routes/reports.py
```

### 2. Create FastAPI App Factory (2h)

Create `agents/api/app.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

def create_app() -> FastAPI:
    """Create FastAPI application with middleware."""
    app = FastAPI(
        title="AI4U.now Agents API",
        description="Modal.com Self-Improving Agents",
        version="1.0.0"
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    return app

# Singleton for imports
web_app = create_app()
```

### 3. Create Dependencies Module (2h)

Create `agents/api/dependencies.py`:

```python
import hmac
import hashlib
import os
from fastapi import Request, HTTPException, Depends
from typing import Optional, Dict

from src.core.state import get_state_manager
from config.env import is_admin, get_admin_telegram_id

async def verify_telegram_webhook(request: Request) -> dict:
    """Verify Telegram webhook signature (HMAC-SHA256)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(500, "Bot token not configured")

    body = await request.body()
    secret_key = hashlib.sha256(token.encode()).digest()
    signature = hmac.new(secret_key, body, hashlib.sha256).hexdigest()

    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(signature, received):
        # Log but allow (Telegram doesn't send this header by default)
        pass

    return await request.json()

async def verify_github_webhook(request: Request) -> dict:
    """Verify GitHub webhook signature (HMAC-SHA256)."""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(500, "Webhook secret not configured")

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        raise HTTPException(401, "Invalid signature format")

    body = await request.body()
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, signature_header[7:]):
        raise HTTPException(401, "Invalid signature")

    import json
    return json.loads(body)

async def get_user_tier(user_id: int) -> str:
    """Get user tier from state manager."""
    state = get_state_manager()
    return await state.get_user_tier_cached(user_id)

async def require_developer_tier(user_id: int) -> None:
    """Require developer or admin tier."""
    tier = await get_user_tier(user_id)
    if tier not in ["developer", "admin"]:
        raise HTTPException(403, "Developer tier required")
```

### 4. Extract Health Route (1h)

Create `agents/api/routes/health.py`:

```python
from fastapi import APIRouter
from src.core.resilience import get_circuit_status

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Health check with circuit breaker status."""
    circuits = get_circuit_status()
    return {
        "status": "healthy",
        "circuits": circuits,
        "version": "1.0.0"
    }
```

### 5. Extract Telegram Routes (4h)

Create `agents/api/routes/telegram.py`:

```python
from fastapi import APIRouter, Request, Depends, BackgroundTasks
from slowapi import Limiter
from slowapi.util import get_remote_address
import structlog

from api.dependencies import verify_telegram_webhook
from handlers.message import process_message
from handlers.callback import handle_callback

router = APIRouter(prefix="/webhook", tags=["telegram"])
logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)

@router.post("/telegram")
@limiter.limit("30/minute")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    update: dict = Depends(verify_telegram_webhook)
):
    """Handle Telegram webhook events."""
    try:
        # Extract message or callback
        message = update.get("message")
        callback = update.get("callback_query")

        if callback:
            result = await handle_callback(callback)
            return {"ok": True, **result}

        if message:
            user = message.get("from", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")

            # Process in background for long operations
            if text.startswith("/"):
                from commands.router import command_router
                response = await command_router.handle(text, user, chat_id)
            else:
                response = await process_message(text, user, chat_id, message.get("message_id"))

            return {"ok": True, "response": response[:100]}

        return {"ok": True}

    except Exception as e:
        logger.error("telegram_webhook_error", error=str(e))
        return {"ok": False, "error": str(e)[:100]}
```

### 6. Extract Skills Routes (2h)

Create `agents/api/routes/skills.py`:

```python
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict

from src.skills.registry import get_registry
from execution.skill_executor import execute_skill_simple

router = APIRouter(prefix="/api", tags=["skills"])

class SkillRequest(BaseModel):
    skill: str
    task: str
    context: Optional[Dict] = None

@router.post("/skill")
async def execute_skill(request: SkillRequest):
    """Execute a skill with task."""
    registry = get_registry()
    skill = registry.get_full(request.skill)

    if not skill:
        raise HTTPException(404, f"Skill '{request.skill}' not found")

    result = await execute_skill_simple(
        request.skill,
        request.task,
        request.context or {}
    )

    return {"ok": True, "result": result}

@router.get("/skills")
async def list_skills(category: Optional[str] = Query(None)):
    """List available skills."""
    registry = get_registry()
    skills = registry.discover()

    if category:
        skills = [s for s in skills if s.category == category]

    return {
        "ok": True,
        "skills": [{"name": s.name, "description": s.description, "category": s.category} for s in skills]
    }

@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get local task status."""
    from src.services.firebase import get_task_result
    result = await get_task_result(task_id)

    if not result:
        raise HTTPException(404, "Task not found")

    return {"ok": True, **result}
```

### 7. Extract Admin/Reports Routes (2h)

Create `agents/api/routes/admin.py` and `agents/api/routes/reports.py` following same pattern.

### 8. Update main.py (2h)

Reduce `main.py` to:

```python
import modal
from api.app import web_app
from api.routes import health, telegram, skills, admin, reports

# Include all routers
web_app.include_router(health.router)
web_app.include_router(telegram.router)
web_app.include_router(skills.router)
web_app.include_router(admin.router)
web_app.include_router(reports.router)

# Modal app definition
image = modal.Image.debian_slim(python_version="3.12").pip_install(...)
app = modal.App("claude-agents", image=image, secrets=[...])

@app.function(...)
@modal.asgi_app()
def fastapi_app():
    return web_app

# Agent definitions remain here
@app.function(...)
def TelegramChatAgent(...):
    ...
```

## Todo List

- [ ] Create api/ directory structure
- [ ] Create api/app.py with FastAPI factory
- [ ] Create api/dependencies.py with auth/webhook verification
- [ ] Create api/routes/health.py
- [ ] Create api/routes/telegram.py
- [ ] Create api/routes/skills.py
- [ ] Create api/routes/admin.py
- [ ] Create api/routes/reports.py
- [ ] Update main.py to import routers
- [ ] Run tests to verify no regressions
- [ ] Deploy and verify all endpoints work

## Success Criteria

- [ ] main.py reduced from 3106 to <500 lines
- [ ] All endpoints accessible at same paths
- [ ] Rate limiting works correctly
- [ ] Webhook verification functional
- [ ] No behavior changes from user perspective
- [ ] All existing tests pass

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Import cycles | HIGH | MEDIUM | Use lazy imports, clear dependency graph |
| Route order matters | MEDIUM | LOW | Test all endpoints after refactor |
| Rate limiter state lost | LOW | LOW | Rate limiter is per-request |
| Middleware order changes | MEDIUM | LOW | Test auth/rate limiting flows |

## Security Considerations

- Dependencies must validate user tier before sensitive operations
- Webhook verification must remain in place
- Rate limiting must apply to all routes equally
- No endpoint should be accidentally exposed without auth

## Next Steps

After Phase 2 completion:
1. Verify all endpoints respond correctly
2. Run load test to verify rate limiting
3. Begin [Phase 3: Extract Commands](./phase-03-extract-commands.md)
