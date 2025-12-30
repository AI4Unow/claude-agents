# Phase 5: Polish

**Status:** pending
**Effort:** 1-2 days
**Depends on:** Phases 1-4

## Context

- [plan.md](plan.md) - Overview
- [phase-04-semantic-orchestration.md](phase-04-semantic-orchestration.md) - Previous phase

## Overview

Final polish: tier-based rate limiting, comprehensive error handling, updated help text, and user-facing tier info. Ensure production-ready quality.

## Key Insights

1. Rate limiting should vary by tier (guest < user < developer)
2. Error messages should be user-friendly with suggestions
3. Help text should reflect new commands
4. `/status` should show user tier and mode

## Requirements

- [ ] Tier-based rate limiting
- [ ] Comprehensive error handling
- [ ] Updated `/help` command
- [ ] Tier info in `/status`
- [ ] Edge case handling
- [ ] Integration testing checklist

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TIER-BASED RATE LIMITING                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TIER          │  RATE LIMIT     │  FEATURES                            │
│  ──────────────┼─────────────────┼─────────────────────────────         │
│  guest         │  5/min          │  Chat only, no skills                │
│  user          │  20/min         │  Skills, orchestration               │
│  developer     │  50/min         │  + traces, circuits                  │
│  admin         │  unlimited      │  + reset, grant tokens               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| File | Purpose | Changes |
|------|---------|---------|
| `agents/main.py` | Commands, rate limiting | Multiple updates |
| `agents/src/services/telegram.py` | Formatters | Help text |
| `agents/src/core/state.py` | Rate limit tracking | Add rate limit cache |

## Implementation Steps

### Step 1: Tier-Based Rate Limiting (main.py)

Add rate limiting based on user tier:

```python
# agents/main.py

from datetime import datetime, timezone
from collections import defaultdict

# Rate limits by tier (requests per minute)
TIER_RATE_LIMITS = {
    "guest": 5,
    "user": 20,
    "developer": 50,
    "admin": 1000  # Effectively unlimited
}

# In-memory rate limit tracking (per container)
_rate_limit_cache: Dict[int, List[datetime]] = defaultdict(list)


def check_rate_limit(user_id: int, tier: str) -> tuple[bool, int]:
    """Check if user is within rate limit.

    Args:
        user_id: Telegram user ID
        tier: User's tier

    Returns:
        (allowed: bool, remaining: int)
    """
    limit = TIER_RATE_LIMITS.get(tier, 5)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=1)

    # Clean old entries
    _rate_limit_cache[user_id] = [
        t for t in _rate_limit_cache[user_id]
        if t > window_start
    ]

    current_count = len(_rate_limit_cache[user_id])

    if current_count >= limit:
        return False, 0

    _rate_limit_cache[user_id].append(now)
    return True, limit - current_count - 1


# In telegram_webhook(), add rate limiting after tier check:

async def telegram_webhook(request: Request):
    # ... existing code ...

    # After extracting user info
    user_id = user.get("id")

    # Get tier for rate limiting
    from src.core.state import get_state_manager
    state = get_state_manager()
    tier = await state.get_user_tier_cached(user_id)

    # Check rate limit
    allowed, remaining = check_rate_limit(user_id, tier)
    if not allowed:
        await send_telegram_message(
            chat_id,
            f"⚠️ Rate limit exceeded. Try again in 1 minute.\n"
            f"Tier: {tier} ({TIER_RATE_LIMITS[tier]} req/min)"
        )
        return {"ok": True}

    # ... continue processing ...
```

### Step 2: Comprehensive Error Handling (main.py)

Enhance error messages with suggestions:

```python
# agents/main.py

# Extended error suggestions
ERROR_SUGGESTIONS = {
    "timeout": "Request timed out. Try simplifying your request.",
    "circuit_open": "Service temporarily unavailable. Retry in 30 seconds.",
    "rate_limit": "Too many requests. Wait a moment before trying again.",
    "connection": "Network issue. Check connection and retry.",
    "max_iterations": "Task too complex. Try breaking it into smaller parts.",
    "access_denied": "Permission denied. Check your tier with /status.",
    "skill_not_found": "Skill not found. Use /skills to see available options.",
    "invalid_token": "Invalid or expired token. Request a new one from admin.",
    "firebase": "Database temporarily unavailable. Retry in a moment.",
    "groq": "Classification service unavailable. Defaulting to simple mode.",
}


def format_error_message(error: str, tier: str = "guest") -> str:
    """Format error with user-friendly message and suggestion.

    Args:
        error: Error message or type
        tier: User's tier for context

    Returns:
        Formatted error message
    """
    error_lower = error.lower()

    # Find matching suggestion
    suggestion = None
    for key, value in ERROR_SUGGESTIONS.items():
        if key in error_lower:
            suggestion = value
            break

    # Build response
    lines = [f"❌ <b>Error</b>"]

    # Sanitize error for display
    safe_error = error[:100].replace("<", "&lt;").replace(">", "&gt;")
    lines.append(f"<i>{safe_error}</i>")

    if suggestion:
        lines.append(f"\n💡 {suggestion}")

    # Tier-specific help
    if tier == "guest" and "access" in error_lower:
        lines.append("\nNeed access? Contact admin for an auth token.")

    return "\n".join(lines)


# Wrap process_message with better error handling
async def process_message(text: str, user: dict, chat_id: int, message_id: int = None) -> str:
    """Process message with comprehensive error handling."""
    import asyncio
    import structlog
    from src.core.state import get_state_manager

    logger = structlog.get_logger()
    state = get_state_manager()
    user_id = user.get("id")
    tier = await state.get_user_tier_cached(user_id)

    try:
        # ... existing processing logic ...
        pass

    except asyncio.TimeoutError:
        return format_error_message("Request timeout", tier)

    except CircuitOpenError as e:
        return format_error_message(f"circuit_open: {e.service}", tier)

    except Exception as e:
        logger.error("process_message_error", error=str(e), user_id=user_id)
        return format_error_message(str(e), tier)
```

### Step 3: Updated /help Command (main.py)

Comprehensive help with tier-aware visibility:

```python
# agents/main.py - update /help handler

elif cmd == "/help":
    # Get user tier for context-aware help
    from src.core.state import get_state_manager
    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))

    # Base commands (everyone)
    help_text = [
        "<b>📖 Commands</b>\n",
        "<b>Basic:</b>",
        "/start - Welcome message",
        "/help - This help text",
        "/status - Check your status and tier",
        "/clear - Clear conversation history",
    ]

    # User+ commands
    if has_permission(tier, "user") or tier == "guest":
        help_text.extend([
            "",
            "<b>Skills:</b>",
            "/skills - Browse skills (menu)",
            "/skill &lt;name&gt; &lt;task&gt; - Execute skill",
            "/mode &lt;simple|routed|auto&gt; - Set mode",
            "/task &lt;id&gt; - Check task status",
        ])

    # Quick actions
    help_text.extend([
        "",
        "<b>Quick Actions:</b>",
        "/translate &lt;text&gt; - Translate to English",
        "/summarize &lt;text&gt; - Summarize text",
        "/rewrite &lt;text&gt; - Improve text",
    ])

    # Developer+ commands
    if has_permission(tier, "developer"):
        help_text.extend([
            "",
            "<b>Developer:</b>",
            "/traces [limit] - Recent execution traces",
            "/trace &lt;id&gt; - Trace details",
            "/circuits - Circuit breaker status",
        ])

    # Admin commands
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) == str(admin_id):
        help_text.extend([
            "",
            "<b>Admin:</b>",
            "/grant &lt;user|developer&gt; - Generate auth token",
            "/admin reset &lt;circuit&gt; - Reset circuit",
            "/admin stats - System statistics",
            "/remind &lt;time&gt; &lt;msg&gt; - Set reminder",
            "/reminders - List reminders",
        ])

    # Auth info
    if tier == "guest":
        help_text.extend([
            "",
            "<i>You're a guest. Use /auth &lt;token&gt; to unlock skills.</i>",
        ])
    else:
        help_text.append(f"\n<i>Your tier: {tier}</i>")

    return "\n".join(help_text)
```

### Step 4: Enhanced /status Command (main.py)

Show tier, mode, and usage info:

```python
# agents/main.py - update /status handler

elif cmd == "/status":
    from src.core.state import get_state_manager
    from src.core.resilience import get_circuit_stats

    state = get_state_manager()
    user_id = user.get("id")

    tier = await state.get_user_tier_cached(user_id)
    mode = await state.get_user_mode(user_id)

    # Rate limit info
    limit = TIER_RATE_LIMITS.get(tier, 5)
    used = len([t for t in _rate_limit_cache.get(user_id, [])
                if t > datetime.now(timezone.utc) - timedelta(minutes=1)])

    lines = [
        "<b>📊 Status</b>\n",
        f"<b>Tier:</b> {tier}",
        f"<b>Mode:</b> {mode}",
        f"<b>Rate:</b> {used}/{limit} req/min",
    ]

    # Admin sees system status
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user_id) == str(admin_id):
        circuits = get_circuit_stats()
        open_count = sum(1 for c in circuits.values() if c.get("state") == "open")

        lines.extend([
            "",
            "<b>System:</b>",
            f"Circuits Open: {open_count}/{len(circuits)}",
            f"Cache Size: {len(state._l1_cache)}",
        ])

    return "\n".join(lines)
```

### Step 5: Edge Case Handling

Handle edge cases throughout:

```python
# agents/main.py - Various edge case handlers

# Empty message handling
if not text or text.strip() == "":
    return None  # Silent ignore

# Very long message truncation
MAX_MESSAGE_LENGTH = 4000
if len(text) > MAX_MESSAGE_LENGTH:
    text = text[:MAX_MESSAGE_LENGTH] + "... [truncated]"
    await send_telegram_message(
        chat_id,
        "⚠️ Message truncated to 4000 chars."
    )

# Invalid command arguments
def validate_command_args(args: str, max_length: int = 500) -> str:
    """Validate and sanitize command arguments."""
    if not args:
        return ""
    # Truncate
    args = args[:max_length]
    # Remove control characters
    args = "".join(c for c in args if c.isprintable() or c in "\n\t")
    return args.strip()

# Handle blocked users gracefully
async def is_user_blocked(user_id: int) -> bool:
    """Check if user is blocked."""
    # Could be extended with Firebase blocklist
    return False

# In telegram_webhook:
if await is_user_blocked(user_id):
    return {"ok": True}  # Silent ignore
```

## Todo List

- [ ] Implement `check_rate_limit()` function
- [ ] Add rate limit check in `telegram_webhook()`
- [ ] Update `format_error_message()` with suggestions
- [ ] Update `/help` command with tier-aware content
- [ ] Update `/status` command with tier and rate info
- [ ] Add input validation helpers
- [ ] Add edge case handling
- [ ] Add integration tests
- [ ] Update documentation

## Integration Testing Checklist

### Auth Flow
- [ ] Guest user gets tier info in /status
- [ ] /auth with valid token upgrades tier
- [ ] /auth with used token fails
- [ ] /auth with invalid token fails
- [ ] Tier persists across sessions

### Admin Commands
- [ ] Guest cannot access /traces
- [ ] Developer can access /traces
- [ ] Admin can reset circuits
- [ ] /grant generates valid token

### Complexity Detection
- [ ] "Hi" routes to simple
- [ ] "Build a login system" routes to complex
- [ ] /mode auto enables detection
- [ ] /mode simple bypasses detection

### Orchestration
- [ ] Multi-skill task shows progress
- [ ] Each skill shows "Using: ..." message
- [ ] Results show after each skill
- [ ] Final synthesis message appears

### Rate Limiting
- [ ] Guest limited to 5 req/min
- [ ] User limited to 20 req/min
- [ ] Rate limit message shows
- [ ] Limit resets after 1 minute

### Error Handling
- [ ] Timeout shows friendly message
- [ ] Circuit open shows retry suggestion
- [ ] Unknown error doesn't crash

## Success Criteria

1. Rate limits enforced by tier
2. Error messages are user-friendly
3. /help shows tier-appropriate commands
4. /status shows tier, mode, rate usage
5. Edge cases handled gracefully
6. All integration tests pass

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Rate limit bypass | Low | Medium | Server-side enforcement |
| In-memory rate limit lost | Medium | Low | Conservative limits |
| Help text outdated | Medium | Low | Generate dynamically |
| Blocking legitimate users | Low | High | Conservative limits, /status visibility |

## Security Considerations

1. **Rate limits server-side** - Can't be bypassed by client
2. **Input sanitization** - All args validated
3. **Error masking** - Don't expose internals
4. **Blocklist support** - Can block abusive users
5. **Audit logging** - Log admin actions

## Deployment Checklist

- [ ] Add Groq credentials to Modal secrets
- [ ] Deploy with `modal deploy`
- [ ] Test all commands manually
- [ ] Monitor circuit breaker status
- [ ] Watch for rate limit effectiveness
- [ ] Review error logs

## Future Improvements

1. **Persistent rate limiting** - Use Redis/Firebase instead of in-memory
2. **Usage analytics** - Track command usage per tier
3. **Dynamic rate limits** - Adjust based on load
4. **Blocklist management** - Admin commands for blocking
5. **Usage quotas** - Monthly limits per tier
