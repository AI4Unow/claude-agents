# Phase 03: Integration & API

## Objective

Integrate tracing into agentic loop, add tool trace capture to registry, and expose traces via API endpoint.

## Update `src/services/agentic.py`

Wrap agentic loop with TraceContext:

```python
"""Agentic loop service for tool execution with conversation persistence."""
import time
from typing import List, Dict, Optional
from src.services.llm import get_llm_client
from src.tools import get_registry, init_default_tools
from src.core.state import get_state_manager
from src.core.trace import TraceContext, ToolTrace, get_current_trace

from src.utils.logging import get_logger

logger = get_logger()

MAX_ITERATIONS = 5


async def run_agentic_loop(
    user_message: str,
    system: Optional[str] = None,
    user_id: Optional[int] = None,
    skill: Optional[str] = None,  # NEW: for trace metadata
) -> str:
    """Run agentic loop with tool execution, conversation persistence, and tracing.

    Args:
        user_message: User's input
        system: System prompt
        user_id: Telegram user ID for conversation persistence
        skill: Skill name for trace metadata

    Returns:
        Final text response
    """
    # Wrap entire execution in trace context
    async with TraceContext(user_id=user_id, skill=skill) as trace_ctx:
        try:
            result = await _execute_loop(
                user_message=user_message,
                system=system,
                user_id=user_id,
                trace_ctx=trace_ctx,
            )
            trace_ctx.set_output(result)
            return result

        except Exception as e:
            trace_ctx.set_status("error")
            trace_ctx.metadata["error"] = str(e)[:200]
            raise


async def _execute_loop(
    user_message: str,
    system: Optional[str],
    user_id: Optional[int],
    trace_ctx: TraceContext,
) -> str:
    """Internal loop execution with trace capture."""
    # Initialize tools
    init_default_tools()
    registry = get_registry()
    tools = registry.get_definitions()

    # Load conversation history from StateManager
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
        trace_ctx.increment_iteration()
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
            # Append assistant response to history
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Execute tools and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", name=block.name, input=str(block.input)[:50])

                    # Execute with timing for trace
                    start_time = time.monotonic()
                    result = await registry.execute(block.name, block.input)
                    duration_ms = int((time.monotonic() - start_time) * 1000)

                    # Determine if error
                    is_error = (
                        result.startswith("Search failed") or
                        result.startswith("Error") or
                        result.startswith("Tool error")
                    )

                    # Add to trace
                    tool_trace = ToolTrace.create(
                        name=block.name,
                        input_params=block.input if isinstance(block.input, dict) else {"input": str(block.input)},
                        output=result,
                        duration_ms=duration_ms,
                        is_error=is_error,
                    )
                    trace_ctx.add_tool_trace(tool_trace)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error,
                    })

            # Append tool results as user message
            messages.append({
                "role": "user",
                "content": tool_results
            })

    if iterations >= MAX_ITERATIONS:
        logger.warning("agentic_max_iterations", max=MAX_ITERATIONS)
        accumulated_text.append("\n\n[Note: Reached maximum iterations limit]")
        trace_ctx.set_status("timeout")

    # Save final response to conversation
    final_response = "\n".join(accumulated_text)
    messages.append({"role": "assistant", "content": final_response})

    if user_id:
        await state.save_conversation(user_id, messages)
        logger.info("conversation_saved", user_id=user_id, count=len(messages))

    return final_response
```

## Update `main.py`

Add traces API endpoint:

```python
# Add imports at top
from src.core.trace import get_trace, list_traces
from src.core.resilience import get_circuit_stats, reset_all_circuits

# Add new endpoints after existing API endpoints

@web_app.get("/api/traces")
async def list_traces_endpoint(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20
):
    """List execution traces for debugging.

    Query params:
        user_id: Filter by user
        status: Filter by status (success, error, timeout)
        limit: Max results (default 20)
    """
    try:
        traces = await list_traces(user_id=user_id, status=status, limit=limit)
        return {
            "traces": [t.to_dict() for t in traces],
            "count": len(traces),
        }
    except Exception as e:
        return {"error": str(e)}, 500


@web_app.get("/api/traces/{trace_id}")
async def get_trace_endpoint(trace_id: str):
    """Get single trace by ID."""
    trace = await get_trace(trace_id)
    if trace:
        return trace.to_dict()
    return {"error": "Trace not found"}, 404


@web_app.get("/api/circuits")
async def get_circuits_endpoint():
    """Get circuit breaker status for all services."""
    return get_circuit_stats()


@web_app.post("/api/circuits/reset")
async def reset_circuits_endpoint():
    """Reset all circuit breakers (admin only)."""
    reset_all_circuits()
    return {"message": "All circuits reset"}
```

## Update `/health` endpoint

Add circuit status to health check:

```python
@web_app.get("/health")
async def health():
    """Health check with circuit status."""
    from src.core.resilience import get_circuit_stats

    circuits = get_circuit_stats()

    # Check if any circuit is open
    any_open = any(c["state"] == "open" for c in circuits.values())

    return {
        "status": "degraded" if any_open else "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "circuits": circuits,
    }
```

## Update calls to `run_agentic_loop`

Pass skill name where available:

```python
# In handle_agentic_mode or similar:
response = await run_agentic_loop(
    user_message=text,
    system=system_prompt,
    user_id=user_id,
    skill=pending_skill,  # NEW: pass skill name
)
```

## Firebase Index (optional)

For efficient trace queries, add composite index in Firebase Console:

```
Collection: execution_traces
Fields:
  - user_id (Ascending)
  - started_at (Descending)

Collection: execution_traces
Fields:
  - status (Ascending)
  - started_at (Descending)
```

## Verification

```bash
# Test traces endpoint
curl -X GET "https://<modal-url>/api/traces?limit=5"

# Test single trace
curl -X GET "https://<modal-url>/api/traces/abc123"

# Test circuits
curl -X GET "https://<modal-url>/api/circuits"

# Check health with circuit status
curl -X GET "https://<modal-url>/health"
```

## Acceptance Criteria

- [ ] Agentic loop wrapped in TraceContext
- [ ] All tool calls captured with timing
- [ ] /api/traces returns list of traces
- [ ] /api/traces/{id} returns single trace
- [ ] /api/circuits returns circuit status
- [ ] /health shows circuit status
- [ ] Traces filtered by user_id and status
- [ ] Error traces saved 100%, success sampled 10%
