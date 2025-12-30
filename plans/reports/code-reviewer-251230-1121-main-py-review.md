# Code Review: agents/main.py

**Reviewer:** code-reviewer
**Date:** 2025-12-30
**Scope:** Full file review (3106 lines)
**Focus:** Monolithic structure, SRP violations, DRY issues, security, error handling

---

## Executive Summary

**Overall Assessment:** HIGH technical debt. File has grown to 3106 lines mixing routing, business logic, infrastructure, and feature implementations. Immediate refactoring required to maintain velocity.

**Critical Issues:** 2
**High Priority:** 8
**Medium Priority:** 12
**Low Priority:** 6

**Recommended Action:** Break into 8-10 focused modules over 2-3 iterations.

---

## Critical Issues

### C1. Monolithic Structure - God Object Anti-Pattern
**Severity:** HIGH
**Lines:** 1-3106
**Impact:** Maintenance nightmare, testing difficulty, merge conflicts, onboarding friction

**Problem:**
Single 3106-line file handles:
- FastAPI routing (15+ endpoints)
- Telegram webhook processing
- Command handling (30+ commands)
- Message processing pipeline
- Skill execution orchestration
- Admin operations
- Callback handling
- Multiple agent definitions
- Helper functions
- Test functions

**Evidence:**
- 61 functions/classes in single file
- 57 try/except blocks
- 40+ os.environ.get() calls scattered throughout
- Multiple nested async functions
- Mixed concerns (HTTP, Telegram, domain logic)

**Fix:**
```
Proposed structure:
agents/
├── main.py (120 lines - app definition, routing only)
├── api/
│   ├── routes/
│   │   ├── telegram.py (webhook, callbacks)
│   │   ├── skills.py (skill API endpoints)
│   │   ├── admin.py (admin endpoints)
│   │   └── reports.py (reports API)
│   └── dependencies.py (auth, rate limiting)
├── commands/
│   ├── base.py (command router)
│   ├── user.py (/start, /help, /status, /tier)
│   ├── skills.py (/skills, /skill, /mode)
│   ├── admin.py (/grant, /revoke, /admin, /faq)
│   ├── personalization.py (/profile, /context, /macro)
│   └── developer.py (/traces, /circuits)
├── handlers/
│   ├── message.py (process_message)
│   ├── voice.py (handle_voice_message)
│   ├── image.py (handle_image_message)
│   └── document.py (handle_document_message)
├── execution/
│   ├── modes.py (_run_simple, _run_routed, _run_orchestrated)
│   └── skill_executor.py (execute_skill_*)
└── config/
    └── env.py (centralized env var access)
```

**Benefits:**
- Testable modules (unit test each route/command)
- Clear ownership (easier code review)
- Reduced merge conflicts
- Faster navigation
- Easier onboarding

---

### C2. Security - Admin ID Repeated Without Centralization
**Severity:** HIGH
**Lines:** 743, 779, 891, 928, 953, 983, 1107, 2309, 2345, 2370
**Impact:** Security misconfiguration risk, inconsistent access control

**Problem:**
Admin ID fetched from env vars 10+ times across file:
```python
admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
if str(user.get("id")) != str(admin_id):
    return "Admin only command."
```

No validation that ADMIN_TELEGRAM_ID is:
- Set (could be None)
- Valid integer
- Single source of truth

**Fix:**
```python
# config/env.py
from functools import lru_cache
import os

class ConfigurationError(Exception):
    pass

@lru_cache(maxsize=1)
def get_admin_telegram_id() -> int:
    """Get admin Telegram ID from environment (validated, cached)."""
    admin_id_str = os.environ.get("ADMIN_TELEGRAM_ID")
    if not admin_id_str:
        raise ConfigurationError("ADMIN_TELEGRAM_ID not set")
    try:
        return int(admin_id_str)
    except ValueError:
        raise ConfigurationError(f"Invalid ADMIN_TELEGRAM_ID: {admin_id_str}")

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    try:
        return user_id == get_admin_telegram_id()
    except ConfigurationError:
        return False

# Usage in commands/admin.py
from config.env import is_admin

if not is_admin(user.get("id")):
    return "Admin only command."
```

**Additional Issues:**
- TELEGRAM_BOT_TOKEN fetched 8+ times (lines 65, 1602, 1617, 1637, 1658, 1681, 2048, 2096, 2237, 2252)
- No validation that tokens exist before HTTP calls
- Silent failures with empty strings

---

## High Priority Findings

### H1. DRY Violation - Telegram API Calls Duplicated
**Severity:** HIGH
**Lines:** 61-88, 2041-2088, 2090-2120, 2234-2246, 2249-2272

**Problem:**
5 functions for sending Telegram messages with duplicated HTTP client setup, error handling, token fetching:

1. `notify_task_queued()` - lines 61-88
2. `send_telegram_message()` - lines 2041-2088
3. `send_telegram_keyboard()` - lines 2090-2120
4. `answer_callback()` - lines 2234-2246
5. `handle_category_select()` - inline HTTP - lines 2249-2272

Each re-implements:
- Token fetching from env
- httpx.AsyncClient setup
- Error handling
- Timeout configuration

**Fix:**
```python
# services/telegram_client.py
import httpx
import os
from typing import Optional, List, Dict
import structlog

logger = structlog.get_logger()

class TelegramClient:
    """Centralized Telegram Bot API client."""

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not self.token:
            logger.error("telegram_token_missing")
            raise ValueError("TELEGRAM_BOT_TOKEN not configured")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict] = None
    ) -> bool:
        """Send message with optional keyboard."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/sendMessage",
                    json=payload
                )
                result = resp.json()
                if not result.get("ok"):
                    logger.warning("telegram_send_failed", error=result.get("description"))
                    return False
                return True
        except Exception as e:
            logger.error("telegram_exception", error=str(e), chat_id=chat_id)
            return False

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict] = None
    ) -> bool:
        """Edit existing message."""
        # ... similar pattern

    async def answer_callback(self, callback_id: str, text: Optional[str] = None):
        """Answer callback query."""
        # ... similar pattern

    async def send_chat_action(self, chat_id: int, action: str):
        """Send typing/upload/recording action."""
        # ... similar pattern
```

**Impact:** Reduces ~200 lines to ~100, single source of truth, easier testing.

---

### H2. SRP Violation - handle_command() is 800-line Command Router
**Severity:** HIGH
**Lines:** 649-1440

**Problem:**
Single function handles 30+ commands with deeply nested if/elif chains:

```python
async def handle_command(command: str, user: dict, chat_id: int) -> str:
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        return f"""..."""  # 25 lines
    elif cmd == "/help":
        # ... 75 lines
    elif cmd == "/status":
        # ... 32 lines
    elif cmd == "/skills":
        # ... 3 lines
    # ... 25+ more commands
```

**Issues:**
- Untestable (can't unit test individual commands)
- Hard to modify (search 800 lines to find command)
- Permission checks scattered (admin_id fetched 6 times inside)
- Business logic mixed with routing

**Fix:**
```python
# commands/base.py
from typing import Protocol, Dict, Callable, Awaitable
from dataclasses import dataclass

CommandHandler = Callable[[str, dict, int], Awaitable[str]]

@dataclass
class CommandDefinition:
    handler: CommandHandler
    description: str
    permission_level: str = "guest"  # guest, user, developer, admin

class CommandRouter:
    """Route commands to handlers with permission checking."""

    def __init__(self):
        self._commands: Dict[str, CommandDefinition] = {}

    def register(self, command: str, permission: str = "guest"):
        """Decorator to register command handler."""
        def decorator(func: CommandHandler):
            self._commands[command] = CommandDefinition(
                handler=func,
                description=func.__doc__ or "",
                permission_level=permission
            )
            return func
        return decorator

    async def handle(self, command: str, args: str, user: dict, chat_id: int) -> str:
        """Route command to handler with permission check."""
        cmd_def = self._commands.get(command)
        if not cmd_def:
            return "Unknown command. Try /help"

        # Permission check
        from src.services.auth import has_permission
        if not has_permission(user.get("id"), cmd_def.permission_level):
            return f"Access denied. Requires {cmd_def.permission_level} tier."

        return await cmd_def.handler(args, user, chat_id)

# commands/user.py
from .base import CommandRouter

router = CommandRouter()

@router.register("/start", permission="guest")
async def start_command(args: str, user: dict, chat_id: int) -> str:
    """Welcome message."""
    return f"""Hello {user.get('first_name', 'there')}! 👋

I'm <b>AI4U.now Bot</b> — your unified AI assistant..."""

@router.register("/help", permission="guest")
async def help_command(args: str, user: dict, chat_id: int) -> str:
    """Help text."""
    # ... implementation

# commands/admin.py
@router.register("/grant", permission="admin")
async def grant_command(args: str, user: dict, chat_id: int) -> str:
    """Grant tier to user."""
    # ... implementation
```

**Benefits:**
- Each command is unit-testable
- Permission checks centralized
- Commands self-document via decorator
- Easy to add/remove commands
- Clear dependency graph

---

### H3. Error Handling - Bare Exception Handlers
**Severity:** HIGH
**Lines:** 87-88, 170, 283-284, 311-313, 419-421, 1509-1511, 1548-1550, 1594-1596, 1610-1611, 1630-1631, 1674-1675, 1689-1690, 2023-2033, 2085-2087

**Problem:**
14 instances of bare `except Exception` with silent failures or generic errors:

```python
# Line 87-88 - Silent failure
except Exception:
    pass  # Non-blocking, log errors elsewhere

# Line 283-284 - Generic error
except Exception as e:
    logger.error("webhook_error", error=str(e))
    return {"ok": False, "error": str(e)}

# Line 2023-2033 - Overly broad
except Exception as e:
    logger.error("agentic_error", error=str(e))
    if message_id:
        await set_message_reaction(chat_id, message_id, "❌")
    await edit_progress_message(chat_id, progress_msg_id, f"❌ <i>Error: {str(e)[:100]}</i>")
    return format_error_message(str(e))
```

**Issues:**
- Catches all exceptions (KeyError, ValueError, network errors, DB errors)
- No differentiation between retryable vs fatal errors
- Silent failures hide bugs
- User gets generic "something went wrong"

**Fix:**
```python
# handlers/errors.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserError(Exception):
    """User-facing error with helpful message."""
    message: str
    suggestion: Optional[str] = None

    def format(self) -> str:
        if self.suggestion:
            return f"❌ {self.message}\n\n💡 {self.suggestion}"
        return f"❌ {self.message}"

class RateLimitError(UserError):
    """Rate limit exceeded."""
    pass

class CircuitOpenError(UserError):
    """Service circuit breaker open."""
    pass

class ValidationError(UserError):
    """Input validation failed."""
    pass

# handlers/message.py
async def process_message(text: str, user: dict, chat_id: int, message_id: int = None) -> str:
    try:
        # ... processing
        return response

    except RateLimitError as e:
        logger.warning("rate_limit", user_id=user.get("id"))
        return e.format()

    except CircuitOpenError as e:
        logger.warning("circuit_open", service=e.message)
        return e.format()

    except ValidationError as e:
        return e.format()

    except httpx.TimeoutError:
        logger.error("external_timeout", user_id=user.get("id"))
        return "⏱️ Request timed out. Please try again."

    except httpx.NetworkError as e:
        logger.error("network_error", error=str(e))
        return "🌐 Network error. Check your connection and retry."

    except Exception as e:
        # Unknown error - log full context
        logger.exception("unexpected_error", user_id=user.get("id"), text_len=len(text))
        # Notify admin for unknown errors
        await notify_admin_error(e, user, text)
        return "❌ Unexpected error. Admins notified."

    finally:
        # Cleanup always runs
        cancel_event.set()
        typing_task.cancel()
```

**Benefits:**
- Specific error types for specific handling
- User gets actionable feedback
- Admins alerted to unknown errors
- Retryable errors can be retried automatically

---

### H4. DRY Violation - Admin Permission Checks
**Severity:** MEDIUM
**Lines:** 743-744, 779-780, 891-893, 928-930, 953-955, 983-985, 1107-1109, 2309-2311, 2345-2347

**Problem:**
Admin check pattern repeated 9 times:

```python
admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
if str(user.get("id")) != str(admin_id):
    return "Admin only command."
```

**Fix:**
```python
# services/auth.py
from functools import lru_cache
from typing import Optional
import os

@lru_cache(maxsize=1)
def _get_admin_id() -> Optional[int]:
    """Get admin ID (cached)."""
    admin_str = os.environ.get("ADMIN_TELEGRAM_ID")
    if not admin_str:
        return None
    try:
        return int(admin_str)
    except ValueError:
        return None

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    admin_id = _get_admin_id()
    return admin_id is not None and user_id == admin_id

def require_admin(user_id: int) -> None:
    """Raise UserError if not admin."""
    if not is_admin(user_id):
        from .errors import UserError
        raise UserError("Admin access required", "Contact admin for access")

# Usage in commands
from services.auth import require_admin

async def grant_command(args: str, user: dict, chat_id: int) -> str:
    require_admin(user.get("id"))
    # ... implementation
```

---

### H5. Missing Input Validation - User Input Directly Used
**Severity:** HIGH
**Lines:** 832, 1162-1163, 1346-1348, 1904, 1932, 1952

**Problem:**
User input from Telegram used without validation in:

1. Skill execution (line 832):
```python
result = await execute_skill_simple(skill_name, task, {"user": user})
```

2. FAQ creation (lines 1162-1163):
```python
faq_id = re.sub(r'[^a-z0-9]+', '-', pattern.lower())[:30]
```

3. Macro creation (lines 1346-1348):
```python
trigger = trigger_part.strip('"').strip("'")
```

**Issues:**
- No length limits (DoS via huge messages)
- No character sanitization (injection risks)
- No rate limiting on expensive operations
- Skill name not validated before execution

**Fix:**
```python
# validators/input.py
from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class ValidationResult:
    valid: bool
    value: Optional[str] = None
    error: Optional[str] = None

class InputValidator:
    """Validate user inputs."""

    @staticmethod
    def skill_name(name: str) -> ValidationResult:
        """Validate skill name (alphanumeric + hyphens)."""
        if not name or len(name) > 50:
            return ValidationResult(False, error="Skill name must be 1-50 chars")

        if not re.match(r'^[a-z0-9-]+$', name):
            return ValidationResult(
                False,
                error="Skill name must be lowercase alphanumeric with hyphens"
            )

        return ValidationResult(True, value=name)

    @staticmethod
    def text_input(text: str, max_length: int = 4000) -> ValidationResult:
        """Validate text input with length limit."""
        if not text or len(text) > max_length:
            return ValidationResult(False, error=f"Text must be 1-{max_length} chars")

        # Remove control characters except newlines/tabs
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)

        return ValidationResult(True, value=cleaned)

    @staticmethod
    def faq_pattern(pattern: str) -> ValidationResult:
        """Validate FAQ pattern."""
        if len(pattern) > 200:
            return ValidationResult(False, error="Pattern too long (max 200 chars)")

        if not pattern.strip():
            return ValidationResult(False, error="Pattern cannot be empty")

        return ValidationResult(True, value=pattern.strip())

# Usage
from validators.input import InputValidator
from handlers.errors import ValidationError

async def handle_skill_command(skill_name: str, task: str, user: dict):
    # Validate skill name
    skill_val = InputValidator.skill_name(skill_name)
    if not skill_val.valid:
        raise ValidationError(skill_val.error)

    # Validate task
    task_val = InputValidator.text_input(task, max_length=4000)
    if not task_val.valid:
        raise ValidationError(task_val.error)

    # Execute with validated inputs
    result = await execute_skill_simple(skill_val.value, task_val.value, {"user": user})
```

---

### H6. Function Length - process_message() is 200 Lines
**Severity:** MEDIUM
**Lines:** 1841-2039

**Problem:**
Single function handles:
- Rate limiting
- FAQ matching
- Message reactions
- Progress tracking
- Typing indicators
- Pending skill execution
- Mode routing (auto/routed/simple)
- Intent classification
- Skill routing
- Orchestration
- Activity logging
- Context extraction
- Error handling

**Fix:**
```python
# handlers/message.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class MessageContext:
    """Context for message processing."""
    text: str
    user: dict
    chat_id: int
    message_id: Optional[int]
    tier: str
    mode: str
    pending_skill: Optional[str]

class MessageHandler:
    """Handle incoming messages with pipeline."""

    async def process(self, ctx: MessageContext) -> str:
        """Process message through pipeline."""
        # 1. Rate limit check
        if not self._check_rate_limit(ctx):
            return self._rate_limit_response(ctx)

        # 2. FAQ fast path
        if faq_answer := await self._check_faq(ctx):
            return faq_answer

        # 3. Set up progress tracking
        await self._setup_progress(ctx)

        try:
            # 4. Execute based on mode
            response = await self._execute(ctx)

            # 5. Log activity (fire-and-forget)
            await self._log_activity(ctx, response)

            return response

        except Exception as e:
            return await self._handle_error(ctx, e)

        finally:
            await self._cleanup(ctx)

    async def _execute(self, ctx: MessageContext) -> str:
        """Execute message based on mode."""
        if ctx.pending_skill:
            return await self._execute_pending_skill(ctx)

        if ctx.mode == "auto":
            return await self._execute_auto(ctx)
        elif ctx.mode == "routed":
            return await self._execute_routed(ctx)
        else:
            return await self._execute_simple(ctx)
```

---

### H7. DRY Violation - Progress Message Updates
**Severity:** MEDIUM
**Lines:** 1634-1653, 1655-1676, 1678-1691, 1693-1703

**Problem:**
4 similar functions for progress updates:

```python
async def send_progress_message(chat_id: int, text: str) -> int
async def edit_progress_message(chat_id: int, message_id: int, text: str)
async def send_typing_action(chat_id: int)
async def typing_indicator(chat_id: int, cancel_event)
```

All duplicate:
- Token fetching
- HTTP client setup
- Error handling
- Non-blocking failure pattern

**Fix:**
```python
# services/progress.py
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

class ProgressTracker:
    """Track and update progress for long operations."""

    def __init__(self, telegram_client):
        self.client = telegram_client
        self._typing_task: Optional[asyncio.Task] = None
        self._cancel_event: Optional[asyncio.Event] = None

    @asynccontextmanager
    async def track(self, chat_id: int, initial_message: str = "⏳ Processing..."):
        """Context manager for progress tracking with typing indicator."""
        # Send initial message
        msg_id = await self.client.send_message(chat_id, initial_message)

        # Start typing indicator
        self._cancel_event = asyncio.Event()
        self._typing_task = asyncio.create_task(
            self._typing_loop(chat_id, self._cancel_event)
        )

        try:
            yield ProgressUpdater(self.client, chat_id, msg_id)
        finally:
            # Stop typing
            self._cancel_event.set()
            if self._typing_task:
                self._typing_task.cancel()

    async def _typing_loop(self, chat_id: int, cancel_event: asyncio.Event):
        """Send typing indicator every 4s until cancelled."""
        while not cancel_event.is_set():
            await self.client.send_chat_action(chat_id, "typing")
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                continue

class ProgressUpdater:
    """Update progress message."""

    def __init__(self, client, chat_id: int, message_id: int):
        self.client = client
        self.chat_id = chat_id
        self.message_id = message_id
        self._last_update = 0.0
        self._min_interval = 1.0  # Rate limit updates

    async def update(self, text: str, force: bool = False):
        """Update progress (throttled)."""
        import time
        now = time.time()
        if not force and (now - self._last_update) < self._min_interval:
            return

        self._last_update = now
        await self.client.edit_message(self.chat_id, self.message_id, text)

# Usage
async def process_message(text: str, user: dict, chat_id: int):
    tracker = ProgressTracker(telegram_client)

    async with tracker.track(chat_id, "⏳ Processing...") as progress:
        await progress.update("🧠 Analyzing...")
        result = await analyze(text)

        await progress.update("🔍 Finding skill...")
        skill = await route_skill(result)

        await progress.update(f"🎯 {skill.name}")
        return await execute_skill(skill, text)
```

---

### H8. Missing Webhook Signature Verification for GitHub
**Severity:** HIGH
**Lines:** 286-313

**Problem:**
GitHub webhook handler has no signature verification:

```python
@web_app.post("/webhook/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    try:
        event = request.headers.get("X-GitHub-Event", "push")
        payload = await request.json()
        # ... process without verification
```

Compare to Telegram webhook which does verify (lines 117-135).

**Security Risk:**
- Anyone can send fake webhook payloads
- Could trigger unauthorized actions
- No authentication on public endpoint

**Fix:**
```python
# api/dependencies.py
import hmac
import hashlib
from fastapi import Request, HTTPException

async def verify_github_webhook(request: Request) -> dict:
    """Verify GitHub webhook signature (HMAC-SHA256)."""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    # Get signature from header
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid signature format")

    expected_signature = signature_header[7:]  # Remove "sha256=" prefix

    # Compute HMAC
    body = await request.body()
    computed_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    # Timing-safe comparison
    if not hmac.compare_digest(computed_signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Return parsed payload
    import json
    return json.loads(body)

# api/routes/github.py
@web_app.post("/webhook/github")
async def github_webhook(payload: dict = Depends(verify_github_webhook)):
    """Handle GitHub webhook events (verified)."""
    event = request.headers.get("X-GitHub-Event", "push")
    # ... process verified payload
```

---

## Medium Priority Improvements

### M1. Imports Scattered Throughout Functions
**Severity:** MEDIUM
**Lines:** 50, 63, 93-99, 126, 140, 161, ... (40+ instances)

**Problem:**
Imports inside functions instead of module level:

```python
def is_local_skill(skill_name: str) -> bool:
    from src.skills.registry import get_registry  # Line 50
    registry = get_registry()
```

**Issues:**
- Re-imports on every call (minor perf hit)
- Hides dependencies (can't see what file needs at glance)
- Harder to detect circular imports
- IDE autocomplete doesn't work

**Fix:**
Move to top of file or module-level lazy imports:

```python
# Top of file
from src.skills.registry import get_registry
from src.core.state import get_state_manager
from src.services.firebase import (
    create_local_task,
    get_task_result,
    has_permission,
)

def is_local_skill(skill_name: str) -> bool:
    registry = get_registry()
    # ...
```

---

### M2. Magic Numbers - Timeouts and Limits Not Configurable
**Severity:** MEDIUM
**Lines:** 78, 196, 1027-1028, 1484, 1640, 1664, 1684, 1813, 1869, 2062

**Problem:**
Hardcoded values throughout:

```python
async with httpx.AsyncClient(timeout=10.0) as client:  # Line 78
@limiter.limit("30/minute")  # Line 196
if duration > 60:  # Line 1484
async with httpx.AsyncClient(timeout=30.0) as client:  # Line 2062
if len(text) <= 200:  # Line 1869 (FAQ check)
```

**Fix:**
```python
# config/constants.py
from dataclasses import dataclass

@dataclass(frozen=True)
class TelegramConfig:
    """Telegram API configuration."""
    REQUEST_TIMEOUT: float = 30.0
    CALLBACK_TIMEOUT: float = 10.0
    WEBHOOK_RATE_LIMIT: str = "30/minute"
    MAX_VOICE_DURATION: int = 60  # seconds
    MAX_MESSAGE_LENGTH: int = 4000
    CHUNK_SIZE: int = 4000

@dataclass(frozen=True)
class AppConfig:
    """Application configuration."""
    FAQ_MAX_LENGTH: int = 200
    TRACE_LIMIT_DEFAULT: int = 10
    TRACE_LIMIT_MAX: int = 20
    PROGRESS_UPDATE_INTERVAL: float = 1.0

# Usage
from config.constants import TelegramConfig, AppConfig

if duration > TelegramConfig.MAX_VOICE_DURATION:
    return f"Voice message too long. Maximum is {TelegramConfig.MAX_VOICE_DURATION}s."

if len(text) <= AppConfig.FAQ_MAX_LENGTH:
    # Check FAQ
```

---

### M3. No Type Hints on Many Functions
**Severity:** MEDIUM
**Lines:** 2132-2177, 2180-2231, 2745-2760

**Problem:**
Several functions lack type hints:

```python
def build_skills_keyboard(category: str = None) -> list:  # Generic 'list'
async def handle_callback(callback: dict) -> dict:  # Generic 'dict'
def _extract_section(content: str, section_name: str) -> str:  # OK
```

**Fix:**
```python
from typing import List, Dict, Optional

def build_skills_keyboard(category: Optional[str] = None) -> List[List[Dict[str, str]]]:
    """Build inline keyboard for skills navigation.

    Returns:
        List of button rows, each row is list of button dicts
    """
    # ...

async def handle_callback(callback: Dict[str, Any]) -> Dict[str, bool]:
    """Handle inline keyboard button press.

    Args:
        callback: Telegram callback query dict

    Returns:
        Response dict with 'ok' status
    """
    # ...
```

---

### M4. Duplicate Skill Existence Check
**Severity:** MEDIUM
**Lines:** 579-582, 638-641, 810-823

**Problem:**
Same pattern repeated 3 times:

```python
# Line 579-582
registry = get_registry()
skill = registry.get_full(skill_name)
if not skill:
    return f"Skill not found: {skill_name}"

# Line 638-641
registry = get_registry()
skill = registry.get_full(skill_name)
if not skill:
    return f"Skill not found: {skill_name}"

# Line 810-823
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
```

**Fix:**
```python
# services/skills.py
from typing import Optional, List
from src.skills.registry import get_registry, SkillInfo

class SkillNotFoundError(Exception):
    """Skill not found with suggestions."""
    def __init__(self, skill_name: str, suggestions: List[str]):
        self.skill_name = skill_name
        self.suggestions = suggestions
        super().__init__(f"Skill '{skill_name}' not found")

    def format_message(self) -> str:
        if self.suggestions:
            return (
                f"Skill '{self.skill_name}' not found. "
                f"Did you mean: {', '.join(self.suggestions[:3])}?"
            )
        return f"Skill '{self.skill_name}' not found. Use /skills to see available."

def get_skill_or_error(skill_name: str) -> SkillInfo:
    """Get skill by name or raise SkillNotFoundError with suggestions."""
    registry = get_registry()
    skill = registry.get_full(skill_name)

    if skill:
        return skill

    # Find suggestions
    summaries = registry.discover()
    names = [s.name for s in summaries]
    suggestions = [
        n for n in names
        if n.startswith(skill_name[:3]) or skill_name in n
    ]

    raise SkillNotFoundError(skill_name, suggestions)

# Usage
try:
    skill = get_skill_or_error(skill_name)
    result = await execute_skill(skill, task)
except SkillNotFoundError as e:
    return e.format_message()
```

---

### M5. Unclear Naming - _run_simple/routed/orchestrated
**Severity:** LOW
**Lines:** 1723-1764, 1767-1795, 1798-1838

**Problem:**
Function names don't indicate they're execution modes:

```python
async def _run_simple(...)  # What is "simple"?
async def _run_routed(...)  # Routed where?
async def _run_orchestrated(...)  # Orchestrated how?
```

User sees modes as "simple", "routed", "auto" but implementation uses different terms.

**Fix:**
```python
# execution/modes.py
async def execute_direct_llm(
    text: str,
    user: dict,
    chat_id: int,
    progress_callback,
    model: str = None
) -> str:
    """Execute direct LLM response without skill routing.

    Mode: simple
    Strategy: Use agentic loop with tools, no skill selection
    """
    # ...

async def execute_skill_routed(
    text: str,
    user: dict,
    chat_id: int,
    progress_msg_id: int
) -> str:
    """Route to best matching skill and execute.

    Mode: routed
    Strategy: Semantic search to find best skill, execute single skill
    """
    # ...

async def execute_orchestrated(
    text: str,
    user: dict,
    chat_id: int,
    progress_msg_id: int
) -> str:
    """Execute with multi-skill orchestration.

    Mode: auto (orchestrate intent)
    Strategy: Break down complex task, execute multiple skills, combine results
    """
    # ...
```

---

### M6. Callback Data Not Validated
**Severity:** MEDIUM
**Lines:** 2180-2231

**Problem:**
Callback data from Telegram split on `:` without validation:

```python
# Line 2194
action, value = data.split(":", 1) if ":" in data else (data, "")

# What if data is malformed? "::::" or "a:b:c:d"?
# What if value is SQL injection attempt?
```

**Fix:**
```python
# handlers/callbacks.py
from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class CallbackData:
    """Parsed callback data."""
    action: str
    value: str

    @classmethod
    def parse(cls, data: str) -> Optional['CallbackData']:
        """Parse callback data with validation."""
        if not data or len(data) > 100:
            return None

        # Format: action:value
        parts = data.split(":", 1)
        if len(parts) != 2:
            return None

        action, value = parts

        # Validate action (alphanumeric + underscore)
        if not re.match(r'^[a-z_]+$', action):
            return None

        # Validate value (alphanumeric + underscore + hyphen)
        if not re.match(r'^[a-z0-9_-]+$', value):
            return None

        return cls(action=action, value=value)

async def handle_callback(callback: dict) -> dict:
    """Handle inline keyboard button press."""
    callback_id = callback.get("id")
    data_str = callback.get("data", "")

    # Parse and validate
    data = CallbackData.parse(data_str)
    if not data:
        await answer_callback(callback_id, "Invalid action")
        return {"ok": False}

    await answer_callback(callback_id)

    # Route to handler
    if data.action == "cat":
        await handle_category_select(chat_id, message_id, data.value)
    elif data.action == "skill":
        await handle_skill_select(chat_id, data.value, user)
    # ...
```

---

### M7. Modal Function Definitions Mixed with FastAPI
**Severity:** LOW
**Lines:** 2387-2843

**Problem:**
File mixes FastAPI route definitions (lines 91-519) with Modal function definitions (lines 2387-2843). Hard to find what's deployed where.

**Fix:**
Separate files:

```
agents/
├── main.py (Modal app definition)
├── api/
│   ├── app.py (FastAPI app creation)
│   └── routes/ (route modules)
└── modal_functions/
    ├── agents.py (TelegramChatAgent, github_agent, data_agent)
    ├── cron.py (scheduled functions)
    ├── sync.py (skill sync functions)
    └── tests.py (test_* functions)
```

---

### M8. No Request ID Tracing
**Severity:** MEDIUM
**Lines:** 197-284 (telegram webhook)

**Problem:**
Cannot correlate logs across async operations:

```python
logger.info("telegram_update", update_id=update.get("update_id"))
# ... many async calls later
logger.info("sending_response", chat_id=chat_id)
# How to link these in logs?
```

**Fix:**
```python
# middleware/tracing.py
import contextvars
import uuid

request_id_var = contextvars.ContextVar('request_id', default=None)

def get_request_id() -> str:
    """Get current request ID."""
    rid = request_id_var.get()
    if rid is None:
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
    return rid

# Middleware
@web_app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to context."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_var.set(request_id)

    # Add to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Usage in logs
import structlog

logger = structlog.get_logger()

async def process_message(text: str, user: dict, chat_id: int):
    request_id = get_request_id()
    logger.info("message_start", request_id=request_id, user_id=user.get("id"))

    # ... processing

    logger.info("message_complete", request_id=request_id, duration_ms=100)
```

---

### M9. FAQ Command Parsing Fragile
**Severity:** MEDIUM
**Lines:** 1148-1159, 1186-1198

**Problem:**
FAQ add/edit commands split on pipe `|` without error handling:

```python
# Line 1149-1150
if len(parts) < 2 or "|" not in parts[1]:
    return "Usage: /faq add <pattern> | <answer>"

content = parts[1]
pipe_idx = content.index("|")  # Crashes if "|" not in content (already checked above, but fragile)
```

**Fix:**
```python
# commands/faq.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class FAQInput:
    """Parsed FAQ input."""
    pattern: str
    answer: str

    @classmethod
    def parse(cls, text: str) -> Optional['FAQInput']:
        """Parse 'pattern | answer' format."""
        if "|" not in text:
            return None

        parts = text.split("|", 1)
        if len(parts) != 2:
            return None

        pattern = parts[0].strip()
        answer = parts[1].strip()

        if not pattern or not answer:
            return None

        if len(pattern) > 200 or len(answer) > 1000:
            return None

        return cls(pattern=pattern, answer=answer)

async def faq_add_command(args: str, user: dict, chat_id: int) -> str:
    """Add FAQ entry."""
    faq_input = FAQInput.parse(args)
    if not faq_input:
        return (
            "Usage: /faq add <pattern> | <answer>\n\n"
            "Example: /faq add how to deploy | Run modal deploy main.py"
        )

    # Generate ID
    faq_id = re.sub(r'[^a-z0-9]+', '-', faq_input.pattern.lower())[:30]
    # ... rest of implementation
```

---

### M10. StateManager Access Pattern Inconsistent
**Severity:** MEDIUM
**Lines:** 685, 761, 826, 840, 857, 864, 974, 1000, 1016, 1850

**Problem:**
StateManager accessed 10+ times with same pattern:

```python
from src.core.state import get_state_manager
state = get_state_manager()
tier = await state.get_user_tier_cached(user_id)
```

No caching of state manager instance, re-imported each time.

**Fix:**
```python
# At module level
from src.core.state import get_state_manager

_state_manager = None

def get_state() -> StateManager:
    """Get cached state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = get_state_manager()
    return _state_manager

# Usage
state = get_state()
tier = await state.get_user_tier_cached(user_id)
```

Or use dependency injection with FastAPI:

```python
# api/dependencies.py
from functools import lru_cache
from src.core.state import StateManager, get_state_manager

@lru_cache(maxsize=1)
def get_cached_state_manager() -> StateManager:
    """Get singleton state manager."""
    return get_state_manager()

# In routes
from fastapi import Depends

async def some_route(
    state: StateManager = Depends(get_cached_state_manager)
):
    tier = await state.get_user_tier_cached(user_id)
```

---

### M11. Unclear Variable Names
**Severity:** LOW
**Lines:** 1813, 2054-2055

**Problem:**
Unclear variable names:

```python
# Line 1813 - List used for mutable closure
last_update_time = [0.0]  # Why list? Use nonlocal instead

# Line 2054-2055
text = markdown_to_html(text)  # Mutating parameter
```

**Fix:**
```python
# Use nonlocal for closures
async def progress_callback(status: str):
    """Throttled progress callback for Telegram."""
    nonlocal last_update_time  # Declare nonlocal

    current_time = time.time()
    if current_time - last_update_time < min_update_interval:
        return

    last_update_time = current_time
    # ...

# Don't mutate parameters
html_text = markdown_to_html(text)
chunks = chunk_message(html_text)
```

---

### M12. No Structured Logging for Errors
**Severity:** MEDIUM
**Lines:** 283-284, 311-313, 419-421, 1510-1511

**Problem:**
Errors logged without context:

```python
logger.error("webhook_error", error=str(e))
```

Missing:
- User ID
- Message content (truncated)
- Request ID
- Timestamp
- Stack trace

**Fix:**
```python
# Use logger.exception() for full stack traces
logger.exception(
    "webhook_error",
    user_id=user.get("id"),
    chat_id=chat_id,
    message_preview=text[:100],
    update_id=update.get("update_id"),
    error_type=type(e).__name__
)
```

---

## Low Priority Suggestions

### L1. Docstrings Inconsistent
**Severity:** LOW
**Lines:** Throughout

**Problem:**
Some functions have detailed docstrings, others have none:

```python
def is_local_skill(skill_name: str) -> bool:
    """Check if skill requires local execution.  # Good

    Returns True if skill's deployment field is 'local'.
    Skills with 'remote' or 'both' are executed on Modal.
    """

async def notify_task_queued(user_id: int, skill_name: str, task_id: str):
    """Notify user that task was queued for local execution."""  # OK

def build_skills_keyboard(category: str = None) -> list:
    """Build inline keyboard for skills navigation."""  # Missing params, return details
```

**Fix:**
Follow Google or NumPy docstring style consistently:

```python
def build_skills_keyboard(category: Optional[str] = None) -> List[List[Dict[str, str]]]:
    """Build inline keyboard for skills navigation.

    Args:
        category: Optional category to show skills for.
                  If None, shows category list.

    Returns:
        List of button rows. Each row is list of button dicts with:
        - text: Button label
        - callback_data: Callback action string

    Example:
        >>> keyboard = build_skills_keyboard("development")
        >>> assert keyboard[0][0]["text"] == "planning"
    """
```

---

### L2. Use Enums for String Constants
**Severity:** LOW
**Lines:** 650-1440 (command names), 1705-1711 (error types), 839 (valid_modes)

**Problem:**
String constants used directly:

```python
if cmd == "/start":  # Typo-prone
if tier not in ["user", "developer"]:  # Magic strings
valid_modes = ["simple", "routed", "auto"]
```

**Fix:**
```python
# models/enums.py
from enum import Enum, auto

class UserTier(str, Enum):
    """User tier levels."""
    GUEST = "guest"
    USER = "user"
    DEVELOPER = "developer"
    ADMIN = "admin"

class ExecutionMode(str, Enum):
    """Skill execution modes."""
    SIMPLE = "simple"
    ROUTED = "routed"
    AUTO = "auto"

class CommandName(str, Enum):
    """Bot command names."""
    START = "/start"
    HELP = "/help"
    STATUS = "/status"
    SKILLS = "/skills"
    # ...

# Usage
from models.enums import UserTier, ExecutionMode, CommandName

if tier not in [UserTier.USER, UserTier.DEVELOPER]:
    return f"Tier must be {UserTier.USER} or {UserTier.DEVELOPER}"

if cmd == CommandName.START:
    return start_command(user)
```

---

### L3. Consider Using Pydantic Models
**Severity:** LOW
**Lines:** Throughout (dict types everywhere)

**Problem:**
Many functions accept generic `dict` types:

```python
async def handle_command(command: str, user: dict, chat_id: int) -> str:
async def process_message(text: str, user: dict, chat_id: int, message_id: int = None) -> str:
```

**Fix:**
```python
# models/telegram.py
from pydantic import BaseModel, Field
from typing import Optional

class TelegramUser(BaseModel):
    """Telegram user."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

class TelegramMessage(BaseModel):
    """Telegram message."""
    message_id: int
    from_: TelegramUser = Field(alias="from")
    chat: dict  # Could be further typed
    text: Optional[str] = None
    voice: Optional[dict] = None
    photo: Optional[list] = None

# Usage
async def handle_command(command: str, user: TelegramUser, chat_id: int) -> str:
    # Now have autocomplete and validation
    name = user.first_name  # Typed!
```

---

### L4. Missing Function Return Type Hints
**Severity:** LOW
**Lines:** 1442-1463, 2745-2760

**Problem:**
Some functions missing return type:

```python
def parse_reminder_time(time_str: str):  # Missing -> Optional[datetime]
def _extract_section(content: str, section_name: str) -> str:  # OK
def _update_section(content: str, section_name: str, new_content: str) -> str:  # OK
```

**Fix:**
```python
from typing import Optional
from datetime import datetime

def parse_reminder_time(time_str: str) -> Optional[datetime]:
    """Parse relative time string like '30m', '2h', '1d'.

    Returns:
        datetime object or None if invalid format
    """
```

---

### L5. Consider Using asynccontextmanager for Resources
**Severity:** LOW
**Lines:** 1891-1893, 2035-2038

**Problem:**
Typing indicator started/stopped manually:

```python
cancel_event = asyncio.Event()
typing_task = asyncio.create_task(typing_indicator(chat_id, cancel_event))

try:
    # ... work
finally:
    cancel_event.set()
    typing_task.cancel()
```

**Fix:**
```python
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def typing_context(chat_id: int):
    """Context manager for typing indicator."""
    cancel_event = asyncio.Event()
    task = asyncio.create_task(typing_indicator(chat_id, cancel_event))

    try:
        yield
    finally:
        cancel_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

# Usage
async def process_message(...):
    async with typing_context(chat_id):
        result = await do_work()
    return result
```

---

### L6. Hardcoded Error Messages
**Severity:** LOW
**Lines:** Throughout

**Problem:**
Error messages duplicated:

```python
return "Admin only command."  # Line 955
return "⛔ This command is admin only."  # Line 893
return "Admin access required."  # Different wording
```

**Fix:**
```python
# constants/messages.py
class ErrorMessages:
    """Centralized error messages."""
    ADMIN_ONLY = "⛔ Admin access required."
    INVALID_INPUT = "❌ Invalid input. Please try again."
    RATE_LIMITED = "⏱️ Too many requests. Please wait {seconds}s."
    SKILL_NOT_FOUND = "❌ Skill '{name}' not found. Use /skills to browse."

# Usage
from constants.messages import ErrorMessages

if not is_admin(user_id):
    return ErrorMessages.ADMIN_ONLY
```

---

## Positive Observations

1. **Good use of circuit breakers** - Resilience patterns implemented (lines 140-151)
2. **Rate limiting configured** - SlowAPI used correctly (lines 103-106, 196)
3. **Webhook verification** - Telegram webhook has proper HMAC verification (lines 117-135)
4. **Progress indicators** - Good UX with typing indicators and progress messages
5. **Structured logging** - Consistent use of structlog throughout
6. **Type hints on many functions** - Better than average Python codebase
7. **Good separation of Modal functions** - Clear deployment boundaries
8. **Skill sync logic well thought out** - Preserves runtime learnings (lines 2768-2843)
9. **FAQ system architecture** - Hybrid keyword/semantic matching is solid
10. **Personalization features** - Well-designed user profile/context system

---

## Recommended Refactoring Plan

### Phase 1: Extract Route Handlers (Week 1)
**Impact:** HIGH
**Effort:** 2-3 days

1. Create `api/` module structure
2. Move FastAPI routes to `api/routes/`
3. Extract dependencies to `api/dependencies.py`
4. Update imports in `main.py`

**Files to create:**
- `api/routes/telegram.py` (webhook, callbacks)
- `api/routes/skills.py` (skill API)
- `api/routes/admin.py` (admin endpoints)
- `api/dependencies.py` (auth, rate limit)

**Result:** `main.py` reduced to ~150 lines

---

### Phase 2: Extract Command Handlers (Week 1-2)
**Impact:** HIGH
**Effort:** 3-4 days

1. Create command router pattern
2. Split commands by category
3. Centralize permission checks
4. Add unit tests for each command

**Files to create:**
- `commands/base.py` (router, decorators)
- `commands/user.py` (start, help, status)
- `commands/skills.py` (skills, skill, mode)
- `commands/admin.py` (grant, revoke, faq)
- `commands/personalization.py` (profile, context, macro)

**Result:** `handle_command()` becomes 20-line router

---

### Phase 3: Extract Message Handlers (Week 2)
**Impact:** MEDIUM
**Effort:** 2 days

1. Create `handlers/` module
2. Extract voice/image/document handlers
3. Extract message processing pipeline
4. Add error handling hierarchy

**Files to create:**
- `handlers/message.py` (MessageHandler class)
- `handlers/voice.py`
- `handlers/image.py`
- `handlers/document.py`
- `handlers/errors.py` (error hierarchy)

---

### Phase 4: Centralize Services (Week 2-3)
**Impact:** MEDIUM
**Effort:** 2 days

1. Create `TelegramClient` wrapper
2. Centralize env var access
3. Extract progress tracking
4. Add input validation layer

**Files to create:**
- `services/telegram_client.py`
- `config/env.py`
- `services/progress.py`
- `validators/input.py`

---

### Phase 5: Add Tests (Week 3-4)
**Impact:** HIGH
**Effort:** 3-4 days

1. Unit tests for commands
2. Integration tests for routes
3. Mock Telegram API
4. Test error handling

**Files to create:**
- `tests/unit/test_commands.py`
- `tests/unit/test_handlers.py`
- `tests/integration/test_routes.py`
- `tests/mocks/telegram.py`

---

## Security Checklist

- [x] Telegram webhook signature verified (HMAC)
- [ ] GitHub webhook signature verified (missing - HIGH)
- [x] Admin token validation (exists but scattered)
- [ ] Input validation on user data (missing - HIGH)
- [x] Rate limiting configured
- [ ] SQL injection prevention (N/A - using Firestore)
- [ ] XSS prevention (HTML escaped in telegram module)
- [ ] CSRF tokens (N/A - webhook-only)
- [ ] Secrets not logged (good - using structlog)
- [ ] Environment variables validated at startup (missing)

---

## Performance Considerations

1. **Imports in functions** - Minor perf hit, move to module level
2. **StateManager recreation** - Cache singleton instance
3. **FAQ check on every message** - Good caching (lines 1867-1878)
4. **Progress update throttling** - Good (lines 1813-1828)
5. **Typing indicator** - Non-blocking, good
6. **Circuit breakers** - Prevent cascade failures, good
7. **L1/L2 cache strategy** - Well designed

---

## Metrics Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| File size | 3106 lines | <500 | ❌ CRITICAL |
| Functions/classes | 61 | <15 per file | ❌ |
| Cyclomatic complexity (handle_command) | ~40 | <10 | ❌ |
| Import count | 40+ | <10 | ⚠️ |
| Try/except blocks | 57 | <5 per file | ❌ |
| Type hint coverage | ~70% | 95%+ | ⚠️ |
| Test coverage | 0% | 80%+ | ❌ |
| Security issues | 2 critical | 0 | ❌ |

---

## Unresolved Questions

1. **Skill execution security** - How are remote skills sandboxed?
2. **Rate limit persistence** - Is rate limit state shared across containers?
3. **Database migrations** - How are Firestore schema changes handled?
4. **Deployment strategy** - Blue/green? Canary? Zero-downtime?
5. **Error budget** - What's acceptable error rate for users?
6. **Local skill executor** - How is `local-executor.py` monitored?
7. **Modal volume backup** - Are skill learnings backed up?
8. **Telegram outage handling** - What happens if Telegram API is down?
9. **LLM quota limits** - How are Claude API quota exhaustion errors handled?
10. **Personalization data retention** - GDPR compliance for `/forget`?

---

## Next Steps

1. **Immediate (This Week)**
   - Fix GitHub webhook signature verification (C2)
   - Add input validation for skill names (H5)
   - Centralize admin ID checking (C2)

2. **Short-term (2 Weeks)**
   - Refactor Phase 1 (extract routes)
   - Refactor Phase 2 (extract commands)
   - Add error handling hierarchy (H3)

3. **Medium-term (1 Month)**
   - Complete refactoring Phases 3-4
   - Add comprehensive test suite (Phase 5)
   - Document architecture decisions

4. **Long-term (2+ Months)**
   - Consider microservices split (if scale demands)
   - Add OpenTelemetry tracing
   - Implement chaos engineering tests

---

**Review Complete**
*Token-efficient report: 8500 words, structured for action*
