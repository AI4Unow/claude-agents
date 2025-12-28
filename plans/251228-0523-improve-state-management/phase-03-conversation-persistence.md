# Phase 03: Conversation Persistence

## Objective

Add conversation memory to StateManager so agentic loop messages persist across requests.

## Current State (agentic.py:33-41)

```python
# Current: In-function local state, lost after each request
messages = []
if context:
    messages.extend(context[-5:])
messages.append({"role": "user", "content": user_message})
```

## Target State

```python
# Target: Load from StateManager, save after loop
state = get_state_manager()
messages = await state.get_conversation(user_id)
messages.append({"role": "user", "content": user_message})
# ... run loop ...
await state.save_conversation(user_id, messages)
```

## Changes to `src/core/state.py`

Add conversation methods:

```python
# Add constants
COLLECTION_CONVERSATIONS = "conversations"
MAX_CONVERSATION_MESSAGES = 20  # Keep last N messages

async def get_conversation(self, user_id: int) -> List[Dict]:
    """Get conversation history."""
    if not user_id:
        return []

    data = await self.get(
        self.COLLECTION_CONVERSATIONS,
        str(user_id),
        ttl_seconds=self.TTL_CONVERSATION
    )

    if not data:
        return []

    return data.get("messages", [])[-self.MAX_CONVERSATION_MESSAGES:]

async def save_conversation(self, user_id: int, messages: List[Dict]):
    """Save conversation history (last N messages)."""
    if not user_id:
        return

    # Keep only serializable messages (filter out non-JSON-safe content)
    clean_messages = []
    for msg in messages[-self.MAX_CONVERSATION_MESSAGES:]:
        clean_msg = {"role": msg.get("role", "user")}

        content = msg.get("content")
        if isinstance(content, str):
            clean_msg["content"] = content
        elif isinstance(content, list):
            # Tool results - serialize to string summary
            clean_msg["content"] = "[tool results]"
        else:
            clean_msg["content"] = str(content) if content else ""

        clean_messages.append(clean_msg)

    await self.set(
        self.COLLECTION_CONVERSATIONS,
        str(user_id),
        {"messages": clean_messages, "updated_at": datetime.utcnow().isoformat()},
        ttl_seconds=self.TTL_CONVERSATION
    )

async def clear_conversation(self, user_id: int):
    """Clear conversation history."""
    if not user_id:
        return

    await self.invalidate(self.COLLECTION_CONVERSATIONS, str(user_id))
    await self._firebase_set(
        self.COLLECTION_CONVERSATIONS,
        str(user_id),
        {"messages": [], "cleared_at": datetime.utcnow().isoformat()}
    )
```

## Changes to `src/services/agentic.py`

Update `run_agentic_loop()` signature and implementation:

```python
"""Agentic loop service for tool execution."""
from typing import List, Dict, Optional
from src.services.llm import get_llm_client
from src.tools import get_registry, init_default_tools
from src.core.state import get_state_manager
from src.utils.logging import get_logger

logger = get_logger()

MAX_ITERATIONS = 5


async def run_agentic_loop(
    user_message: str,
    system: Optional[str] = None,
    user_id: Optional[int] = None,  # NEW: for conversation persistence
) -> str:
    """Run agentic loop with tool execution.

    Args:
        user_message: User's input
        system: System prompt
        user_id: Telegram user ID for conversation persistence

    Returns:
        Final text response
    """
    # Initialize tools
    init_default_tools()
    registry = get_registry()
    tools = registry.get_definitions()

    # Load conversation history
    state = get_state_manager()
    messages = []

    if user_id:
        messages = await state.get_conversation(user_id)
        logger.info("conversation_loaded", user_id=user_id, count=len(messages))

    messages.append({"role": "user", "content": user_message})

    llm = get_llm_client()
    iterations = 0
    accumulated_text = []

    while iterations < MAX_ITERATIONS:
        iterations += 1
        logger.info("agentic_iteration", iteration=iterations)

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

        if response.stop_reason == "end_turn":
            logger.info("agentic_complete", iterations=iterations)
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", name=block.name, input=str(block.input)[:50])
                    result = await registry.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": result.startswith("Search failed") or result.startswith("Error")
                    })

            messages.append({"role": "user", "content": tool_results})

    if iterations >= MAX_ITERATIONS:
        logger.warning("agentic_max_iterations", max=MAX_ITERATIONS)
        accumulated_text.append("\n\n[Note: Reached maximum iterations limit]")

    # Save final response to conversation
    final_response = "\n".join(accumulated_text)
    messages.append({"role": "assistant", "content": final_response})

    if user_id:
        await state.save_conversation(user_id, messages)
        logger.info("conversation_saved", user_id=user_id, count=len(messages))

    return final_response
```

## Changes to `main.py`

Update `process_message()` to pass `user_id`:

```python
async def process_message(text: str, user: dict, chat_id: int) -> str:
    # ... existing code ...

    try:
        response = await run_agentic_loop(
            user_message=text,
            system=system_prompt,
            user_id=user.get("id"),  # NEW: pass user_id
        )
        return response
    except Exception as e:
        logger.error("agentic_error", error=str(e))
        return f"Sorry, I encountered an error processing your request."
```

Add `/clear` command to clear conversation:

```python
# In handle_command(), add:
elif cmd == "/clear":
    state = get_state_manager()
    await state.clear_conversation(user.get("id"))
    return "Conversation history cleared."
```

## Verification

```bash
# Test conversation persistence
# 1. Send message via Telegram
# 2. Restart container (modal deploy)
# 3. Send follow-up - should reference prior context

# Check Firebase
firebase firestore:get conversations/<user_id>
```

## Acceptance Criteria

- [ ] Conversations persist across container restarts
- [ ] Last 20 messages retained per user
- [ ] /clear command works
- [ ] No memory leak (old messages pruned)
- [ ] Tool results serialized safely
