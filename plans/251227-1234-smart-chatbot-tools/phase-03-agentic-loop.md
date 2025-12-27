# Phase 3: Agentic Loop Implementation

## Context

- [Plan Overview](./plan.md)
- [Anthropic Tool Use Research](./research/researcher-01-anthropic-tool-use.md)
- [Phase 1: Tool System](./phase-01-tool-system.md)
- [Phase 2: Web Search](./phase-02-web-search.md)

## Overview

Implement agentic loop that iteratively processes tool calls until Claude returns final response.

## Requirements

1. Loop until `stop_reason == "end_turn"`
2. Max 5 iterations to prevent infinite loops
3. Handle parallel tool calls in single response
4. Preserve conversation history correctly
5. Return accumulated text response

## Architecture

```
User Message
     ↓
┌─────────────────────────────────┐
│ While iterations < MAX_ITERATIONS│
│   ↓                             │
│   LLM.create(messages, tools)   │
│   ↓                             │
│   stop_reason == "end_turn"? ──→ Break, return text
│   ↓ No                          │
│   Extract tool_use blocks       │
│   Execute each tool             │
│   Append assistant + results    │
│   iterations++                  │
└─────────────────────────────────┘
```

## Implementation Steps

### 3.1 Create Agentic Service

**File:** `agents/src/services/agentic.py`

```python
from typing import List, Dict, Optional
from src.services.llm import get_llm_client
from src.tools import get_registry, init_default_tools
import structlog

logger = structlog.get_logger()

MAX_ITERATIONS = 5

async def run_agentic_loop(
    user_message: str,
    system: Optional[str] = None,
    context: Optional[List[Dict]] = None,
) -> str:
    """Run agentic loop with tool execution.

    Args:
        user_message: User's input
        system: System prompt
        context: Previous conversation messages

    Returns:
        Final text response
    """
    # Initialize tools
    init_default_tools()
    registry = get_registry()
    tools = registry.get_definitions()

    # Build initial messages
    messages = []
    if context:
        messages.extend(context[-5:])  # Last 5 for context
    messages.append({"role": "user", "content": user_message})

    llm = get_llm_client()
    iterations = 0
    accumulated_text = []

    while iterations < MAX_ITERATIONS:
        iterations += 1
        logger.info("agentic_iteration", iteration=iterations)

        # Call LLM with tools
        response = llm.chat(
            messages=messages,
            system=system,
            max_tokens=4096,
            tools=tools if tools else None,
        )

        # Collect text content
        for block in response.content:
            if block.type == "text":
                accumulated_text.append(block.text)

        # Check if done
        if response.stop_reason == "end_turn":
            logger.info("agentic_complete", iterations=iterations)
            break

        # Process tool calls
        if response.stop_reason == "tool_use":
            # Append assistant response
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Execute tools and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", name=block.name)
                    result = await registry.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Append tool results
            messages.append({
                "role": "user",
                "content": tool_results
            })

    if iterations >= MAX_ITERATIONS:
        logger.warning("agentic_max_iterations", max=MAX_ITERATIONS)
        accumulated_text.append(
            "\n\n[Note: Reached maximum iterations limit]"
        )

    return "\n".join(accumulated_text)
```

### 3.2 Update process_message in main.py

**File:** `agents/main.py` - Replace process_message

```python
async def process_message(text: str, user: dict, chat_id: int) -> str:
    """Process a regular message with agentic loop."""
    from src.services.agentic import run_agentic_loop
    from pathlib import Path

    # Read instructions from skills volume
    info_path = Path("/skills/telegram-chat/info.md")
    system_prompt = "You are a helpful AI assistant with web search capability."
    if info_path.exists():
        system_prompt = info_path.read_text()

    try:
        response = await run_agentic_loop(
            user_message=text,
            system=system_prompt,
        )
        return response
    except Exception as e:
        logger.error("agentic_error", error=str(e))
        return f"Sorry, I encountered an error: {e}"
```

### 3.3 Handle Tool Errors Gracefully

In `run_agentic_loop`, tool errors already return as strings via registry. Add explicit is_error flag:

```python
# In tool_results construction
tool_results.append({
    "type": "tool_result",
    "tool_use_id": block.id,
    "content": result,
    "is_error": result.startswith("Error")
})
```

### 3.4 Add Caching (Optional)

Simple in-memory cache for repeated queries:

```python
from functools import lru_cache
from datetime import datetime, timedelta

# In WebSearchTool
_cache = {}
CACHE_TTL = timedelta(minutes=15)

def _get_cached(self, query: str) -> Optional[str]:
    key = query.lower().strip()
    if key in _cache:
        result, timestamp = _cache[key]
        if datetime.now() - timestamp < CACHE_TTL:
            return result
    return None

def _set_cache(self, query: str, result: str):
    key = query.lower().strip()
    _cache[key] = (result, datetime.now())
```

## Todo

- [ ] Create `src/services/agentic.py`
- [ ] Implement `run_agentic_loop` function
- [ ] Update `main.py` process_message to use agentic loop
- [ ] Add is_error flag to tool results
- [ ] Test with "what's the weather in Hanoi?"
- [ ] (Optional) Add caching to WebSearchTool

## Success Criteria

1. Bot handles "What's the latest AI news?" with web search
2. Multi-step queries complete (max 5 iterations)
3. Tool errors don't crash the bot
4. Existing /start, /help commands still work
5. Response includes data from web search
