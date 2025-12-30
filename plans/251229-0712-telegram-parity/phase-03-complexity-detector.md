# Phase 3: Complexity Detector (REVISED)

**Status:** pending
**Effort:** 2-3 days
**Depends on:** Phase 1 (Auth System), Phase 2 (Admin Commands)

## Context

- [plan.md](plan.md) - Overview
- [phase-02-admin-commands.md](phase-02-admin-commands.md) - Previous phase

## Overview

Implement a fast LLM classifier that routes messages to either direct LLM response (simple) or orchestrator (complex). Use **Claude Haiku** (already integrated) for speed and simplicity.

**Validation Changes:**
- ~~Groq~~ → Claude Haiku (no new secret needed)
- Reuse existing LLM client infrastructure

## Key Insights

1. Speed is critical - Claude Haiku is fast (~200-300ms)
2. Binary classification: SIMPLE vs COMPLEX
3. Fallback to direct response if classifier fails
4. User can override with `/mode` command
5. Keywords can bypass classifier (e.g., "plan", "build", "implement")
6. **No new dependencies** - reuse existing Claude client

## Requirements

- [ ] Complexity classifier using Claude Haiku
- [ ] `/mode auto|simple|routed` command update
- [ ] Keyword-based fast-path detection
- [ ] Routing logic in `process_message()`
- [ ] ~~Groq client integration~~ (removed)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPLEXITY DETECTION FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  USER MESSAGE                                                            │
│       │                                                                  │
│       ▼                                                                  │
│  ┌──────────────┐     YES     ┌──────────────┐                          │
│  │ KEYWORD      │────────────▶│ ORCHESTRATOR │                          │
│  │ FAST PATH?   │             │ (complex)    │                          │
│  │ "plan","build"│            └──────────────┘                          │
│  └──────┬───────┘                                                        │
│         │ NO                                                             │
│         ▼                                                                │
│  ┌──────────────┐                                                        │
│  │ USER MODE?   │                                                        │
│  └──────┬───────┘                                                        │
│         │                                                                │
│    ┌────┴────┬────────────┐                                              │
│    ▼         ▼            ▼                                              │
│  SIMPLE   ROUTED        AUTO                                             │
│    │         │            │                                              │
│    ▼         ▼            ▼                                              │
│  Direct   Direct    ┌──────────────┐                                     │
│  LLM      +Skill    │ CLASSIFIER   │                                     │
│           Routing   │ (Haiku)      │                                     │
│                     └──────┬───────┘                                     │
│                            │                                             │
│                     ┌──────┴──────┐                                      │
│                     ▼             ▼                                      │
│                  SIMPLE        COMPLEX                                   │
│                     │             │                                      │
│                     ▼             ▼                                      │
│                  Direct      Orchestrator                                │
│                  LLM                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| File | Purpose | Changes |
|------|---------|---------|
| `agents/main.py:1061-1158` | `process_message()` | Add routing logic |
| `agents/main.py:670-679` | `/mode` command | Add "auto" mode |
| `agents/src/core/complexity.py` | (NEW) Classifier | Complexity detection |
| `agents/src/services/llm.py` | Existing LLM client | Use for classification |

## Implementation Steps

### Step 1: Complexity Classifier (core/complexity.py)

Create the complexity detection module using existing LLM client:

```python
# agents/src/core/complexity.py

import re
from typing import Literal
from src.utils.logging import get_logger

logger = get_logger()

ComplexityType = Literal["simple", "complex"]

# Keywords that indicate complex tasks (bypass classifier)
COMPLEX_KEYWORDS = {
    "plan", "build", "create", "implement", "design", "architect",
    "develop", "write code", "make a", "set up", "configure",
    "analyze", "review", "debug", "fix", "optimize", "refactor",
    "research", "compare", "evaluate", "summarize document"
}

# Patterns that indicate simple queries
SIMPLE_PATTERNS = [
    r"^(hi|hello|hey|thanks|thank you|ok|okay)[\s!?.]*$",
    r"^what (is|are|was|were) ",
    r"^(who|where|when|why|how) (is|are|was|were|do|does|did|can|could|would|should) ",
    r"^(translate|convert|define|explain) ",
    r"^(yes|no|sure|nope)[\s!?.]*$",
]

COMPLEXITY_PROMPT = """Classify this message as SIMPLE or COMPLEX.

SIMPLE: greeting, quick question, simple info lookup, single action, translation, casual chat
COMPLEX: multi-step task, planning needed, code/analysis required, multiple skills needed, building something

Message: {message}

Reply with only one word: SIMPLE or COMPLEX"""


def fast_keyword_check(message: str) -> ComplexityType | None:
    """Fast keyword-based complexity check (no LLM needed).

    Returns:
        "simple" or "complex" if determined, None if needs LLM classification
    """
    msg_lower = message.lower()

    # Check simple patterns first
    for pattern in SIMPLE_PATTERNS:
        if re.match(pattern, msg_lower, re.IGNORECASE):
            return "simple"

    # Check complex keywords
    for keyword in COMPLEX_KEYWORDS:
        if keyword in msg_lower:
            return "complex"

    # Check message length (short = likely simple)
    if len(message) < 50 and "?" in message:
        return "simple"

    return None  # Needs LLM classification


def classify_complexity_sync(message: str) -> ComplexityType:
    """Classify message complexity using Claude Haiku (sync).

    Args:
        message: User message to classify

    Returns:
        "simple" or "complex"
    """
    # Fast path: keyword check
    fast_result = fast_keyword_check(message)
    if fast_result:
        logger.debug("complexity_fast_path", result=fast_result)
        return fast_result

    # LLM classification using Claude Haiku via existing client
    from src.services.llm import get_llm_client
    from src.core.resilience import claude_circuit, CircuitState

    # Skip LLM if circuit is open
    if claude_circuit.state == CircuitState.OPEN:
        logger.warning("complexity_circuit_open_defaulting_simple")
        return "simple"

    try:
        client = get_llm_client()
        prompt = COMPLEXITY_PROMPT.format(message=message[:500])

        # Use Haiku for fast classification (sync call)
        response = client.client.messages.create(
            model="kiro-claude-haiku-4-5-agentic",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        if response.content:
            result = response.content[0].text.upper().strip()
            if "COMPLEX" in result:
                logger.debug("complexity_llm", result="complex")
                return "complex"

        logger.debug("complexity_llm", result="simple")
        return "simple"

    except Exception as e:
        logger.error("classify_complexity_error", error=str(e)[:100])
        return "simple"  # Default to simple on error


async def classify_complexity(message: str) -> ComplexityType:
    """Async wrapper for complexity classification."""
    import asyncio
    return await asyncio.to_thread(classify_complexity_sync, message)
```

### Step 2: Update Mode Command (main.py)

Extend `/mode` to include "auto":

```python
# agents/main.py - update /mode handler

elif cmd == "/mode":
    valid_modes = ["simple", "routed", "auto"]  # Add "auto"
    from src.core.state import get_state_manager
    state = get_state_manager()

    if args not in valid_modes:
        current = await state.get_user_mode(user.get("id"))
        return (
            f"Current mode: <b>{current}</b>\n\n"
            "<b>Modes:</b>\n"
            "• <b>simple</b> - Direct LLM response\n"
            "• <b>routed</b> - Route to best skill\n"
            "• <b>auto</b> - Smart detection (recommended)\n\n"
            f"Usage: /mode <{'|'.join(valid_modes)}>"
        )

    await state.set_user_mode(user.get("id"), args)
    return f"Mode set to: <b>{args}</b>"
```

### Step 3: Update process_message() Routing (main.py)

Add complexity-based routing:

```python
# agents/main.py - update process_message()

async def process_message(
    text: str,
    user: dict,
    chat_id: int,
    message_id: int = None
) -> str:
    """Process a regular message with intelligent routing."""
    import asyncio
    from src.core.state import get_state_manager
    from src.core.complexity import classify_complexity
    from src.core.orchestrator import Orchestrator
    import structlog
    import time

    logger = structlog.get_logger()
    state = get_state_manager()
    user_id = user.get("id")

    # React to acknowledge receipt
    if message_id:
        await set_message_reaction(chat_id, message_id, "👀")

    # Send initial progress message
    progress_msg_id = await send_progress_message(chat_id, "⏳ <i>Processing...</i>")

    # Start typing indicator
    cancel_event = asyncio.Event()
    typing_task = asyncio.create_task(typing_indicator(chat_id, cancel_event))

    try:
        # Check for pending skill (from /skills menu)
        pending_skill = await state.get_pending_skill(user_id)
        if pending_skill:
            # Execute pending skill with this message as task
            await state.clear_pending_skill(user_id)
            start = time.time()
            result = await execute_skill_simple(pending_skill, text, {"user": user})
            duration_ms = int((time.time() - start) * 1000)

            if message_id:
                await set_message_reaction(chat_id, message_id, "✅")
            await edit_progress_message(chat_id, progress_msg_id, "✅ <i>Complete</i>")

            from src.services.telegram import format_skill_result
            return format_skill_result(pending_skill, result, duration_ms)

        # Get user's mode preference
        mode = await state.get_user_mode(user_id)

        # Route based on mode
        if mode == "simple":
            # Direct LLM response
            response = await _run_simple(text, user, chat_id, progress_msg_id)

        elif mode == "routed":
            # Route to best skill
            response = await _run_routed(text, user, chat_id, progress_msg_id)

        elif mode == "auto":
            # Classify complexity and route
            await edit_progress_message(chat_id, progress_msg_id, "🧠 <i>Analyzing...</i>")

            complexity = await classify_complexity(text)
            logger.info("complexity_detected", complexity=complexity, mode=mode)

            if complexity == "complex":
                await edit_progress_message(chat_id, progress_msg_id, "🔧 <i>Orchestrating...</i>")
                response = await _run_orchestrated(text, user, chat_id, progress_msg_id)
            else:
                response = await _run_simple(text, user, chat_id, progress_msg_id)

        else:
            # Default to simple
            response = await _run_simple(text, user, chat_id, progress_msg_id)

        # Success reaction
        if message_id:
            await set_message_reaction(chat_id, message_id, "✅")
        await edit_progress_message(chat_id, progress_msg_id, "✅ <i>Complete</i>")

        return response

    except Exception as e:
        logger.error("process_message_error", error=str(e))
        if message_id:
            await set_message_reaction(chat_id, message_id, "❌")
        await edit_progress_message(chat_id, progress_msg_id, f"❌ <i>Error</i>")

        return format_error_message(str(e))

    finally:
        cancel_event.set()
        typing_task.cancel()


async def _run_simple(text: str, user: dict, chat_id: int, progress_msg_id: int) -> str:
    """Run direct LLM response (existing agentic loop)."""
    from src.services.agentic import run_agentic_loop
    from pathlib import Path
    import aiofiles

    async def update_progress(status: str):
        await edit_progress_message(chat_id, progress_msg_id, status)

    info_path = Path("/skills/telegram-chat/info.md")
    system_prompt = "You are a helpful AI assistant."

    if info_path.exists():
        async with aiofiles.open(info_path, 'r') as f:
            system_prompt = await f.read()

    return await run_agentic_loop(
        user_message=text,
        system=system_prompt,
        user_id=user.get("id"),
        progress_callback=update_progress,
    )


async def _run_routed(text: str, user: dict, chat_id: int, progress_msg_id: int) -> str:
    """Route to best skill and execute."""
    from src.core.router import SkillRouter

    await edit_progress_message(chat_id, progress_msg_id, "🔍 <i>Finding skill...</i>")

    router = SkillRouter()
    skill = await router.route_single(text)

    if not skill:
        return await _run_simple(text, user, chat_id, progress_msg_id)

    await edit_progress_message(chat_id, progress_msg_id, f"🔧 <i>Using: {skill.name}</i>")

    import time
    start = time.time()
    result = await execute_skill_simple(skill.name, text, {"user": user})
    duration_ms = int((time.time() - start) * 1000)

    from src.services.telegram import format_skill_result
    return format_skill_result(skill.name, result, duration_ms)


async def _run_orchestrated(text: str, user: dict, chat_id: int, progress_msg_id: int) -> str:
    """Run orchestrated multi-skill execution."""
    from src.core.orchestrator import Orchestrator

    async def update_progress(status: str):
        await edit_progress_message(chat_id, progress_msg_id, status)

    orchestrator = Orchestrator()

    # Execute with progress callback (Phase 4 will enhance this)
    result = await orchestrator.execute(
        task=text,
        context={"user": user}
    )

    return result
```

## Todo List

- [ ] Create `agents/src/core/complexity.py` with classifier
- [ ] Update `/mode` command with "auto" option
- [ ] Refactor `process_message()` with routing logic
- [ ] Add helper functions `_run_simple`, `_run_routed`, `_run_orchestrated`
- [ ] Test keyword fast-path detection
- [ ] Test LLM classification accuracy
- [ ] Add fallback on classifier failure

## Success Criteria

1. Greetings route to simple (fast)
2. "Build a login system" routes to complex
3. `/mode auto` enables intelligent routing
4. Haiku classifier responds in <500ms
5. Keyword bypass works without LLM call
6. Graceful fallback on classifier failure

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Haiku API latency | Low | Low | Keyword fast-path handles most cases |
| Misclassification | Medium | Low | User can override with /mode |
| Latency overhead | Low | Medium | Keyword fast-path, async call |
| API cost | Low | Low | ~$0.0001/classification with Haiku |

## Security Considerations

1. **No sensitive data to classifier** - Only send message content
2. **Timeout protection** - Rely on LLM client defaults
3. **Rate limiting** - Telegram webhook rate limit applies
4. **Fallback safe** - Defaults to simple on any error

## Next Steps

After completing this phase:
1. Proceed to [Phase 4: Semantic Orchestration](phase-04-semantic-orchestration.md)
2. Orchestrator will emit progress messages for complex tasks
