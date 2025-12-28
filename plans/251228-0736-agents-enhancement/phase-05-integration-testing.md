# Phase 5: Integration & Testing

## Context

- Plan: `./plan.md`
- Depends on: Phase 3 (ImprovementService), Phase 4 (Telegram Notifications)

## Overview

- **Priority:** P1
- **Status:** Pending
- **Effort:** 3h

Hook ImprovementService into agentic loop error detection and test full flow.

## Key Insights

- Error detection in agentic.py:116-134 (tool error check)
- Need to trigger improvement analysis after tool errors
- Non-blocking: improvement should not delay user response
- Use asyncio.create_task() for background processing

## Requirements

### Functional
- Detect tool errors in agentic loop
- Trigger improvement analysis asynchronously (non-blocking)
- Store proposal and send notification to admin
- Full end-to-end flow works

### Non-Functional
- User response not delayed by improvement processing
- Errors in improvement flow don't crash agentic loop
- Comprehensive logging for debugging

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     INTEGRATION FLOW                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  agentic.py: run_agentic_loop()                                      │
│       │                                                              │
│       ▼                                                              │
│  for block in response.content:                                      │
│       if block.type == "tool_use":                                   │
│           result = await registry.execute(block.name, block.input)   │
│           is_error = result.startswith("Error") or ...               │
│                │                                                     │
│                ▼                                                     │
│           if is_error:                                               │
│               # NEW: Trigger improvement (non-blocking)              │
│               asyncio.create_task(                                   │
│                   trigger_improvement(                               │
│                       skill_name=current_skill,                      │
│                       error=result,                                  │
│                       context={...}                                  │
│                   )                                                  │
│               )                                                      │
│                                                                      │
│  trigger_improvement() [background task]:                            │
│       │                                                              │
│       ├── ImprovementService.analyze_error()                         │
│       ├── ImprovementService.store_proposal()                        │
│       └── send_improvement_notification()                            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Related Code Files

### Modify
- `agents/src/services/agentic.py` - Add improvement trigger

### Reference
- `agents/src/core/improvement.py` - ImprovementService
- `agents/main.py` - send_improvement_notification()

## Implementation Steps

1. Create trigger_improvement() function in agentic.py
2. Modify _execute_loop() to call trigger on errors
3. Add error handling for improvement flow
4. Write test function for full flow
5. Test with intentional error
6. Test rate limiting
7. Test deduplication

## Code Changes

### agentic.py modifications

```python
# In agents/src/services/agentic.py

import asyncio
from typing import Optional

# Add at module level
_improvement_tasks: list = []


async def trigger_improvement(
    skill_name: Optional[str],
    error: str,
    context: dict
):
    """Background task to trigger improvement proposal.

    Non-blocking: runs in background, doesn't delay user response.
    """
    if not skill_name:
        skill_name = "telegram-chat"  # Default for chat agent

    try:
        from src.core.improvement import get_improvement_service

        service = get_improvement_service()

        # Analyze error and generate proposal
        proposal = await service.analyze_error(
            skill_name=skill_name,
            error=error,
            context=context
        )

        if proposal:
            # Store proposal in Firebase
            await service.store_proposal(proposal)

            # Send notification to admin
            # Import here to avoid circular dependency
            from main import send_improvement_notification
            await send_improvement_notification(proposal.to_dict())

            logger.info("improvement_triggered", skill=skill_name, proposal_id=proposal.id)
        else:
            logger.info("improvement_skipped", skill=skill_name, reason="rate_limit_or_duplicate")

    except Exception as e:
        # Never crash - improvement is non-critical
        logger.error("improvement_trigger_failed", error=str(e), skill=skill_name)


# Modify _execute_loop() - add error trigger after tool execution

async def _execute_loop(
    user_message: str,
    system: Optional[str],
    user_id: Optional[int],
    trace_ctx: TraceContext,
) -> str:
    """Internal loop execution with trace capture."""
    # ... existing code until tool execution ...

    # Process tool calls
    if response.stop_reason == "tool_use":
        # ... existing code ...

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

                # NEW: Trigger improvement for errors (non-blocking)
                if is_error:
                    context = {
                        "tool": block.name,
                        "input": str(block.input)[:200],
                        "user_id": user_id,
                        "trace_id": trace_ctx.trace_id if hasattr(trace_ctx, 'trace_id') else None,
                    }
                    # Use skill from trace_ctx or default
                    skill = getattr(trace_ctx, 'skill', None) or 'telegram-chat'

                    # Non-blocking background task
                    task = asyncio.create_task(
                        trigger_improvement(skill, result, context)
                    )
                    _improvement_tasks.append(task)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": is_error,
                })

    # ... rest of existing code ...
```

## Test Plan

### Test 1: Intentional Error

```python
# Create test function in main.py

@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=120,
)
async def test_improvement_flow():
    """Test self-improvement flow with intentional error."""
    from src.core.improvement import get_improvement_service

    service = get_improvement_service()

    # Simulate error
    proposal = await service.analyze_error(
        skill_name="telegram-chat",
        error="Test error: web_search failed with timeout",
        context={"test": True}
    )

    if proposal:
        await service.store_proposal(proposal)

        # Test notification
        from main import send_improvement_notification
        await send_improvement_notification(proposal.to_dict())

        return {
            "status": "success",
            "proposal_id": proposal.id,
            "message": "Check Telegram for notification"
        }

    return {"status": "skipped", "reason": "rate_limit_or_duplicate"}
```

### Test 2: Rate Limiting

- Trigger 5 errors in 1 hour for same skill
- Verify only 3 proposals created
- Verify 4th and 5th are rate-limited

### Test 3: Deduplication

- Trigger same error twice within 24 hours
- Verify second one is deduplicated

### Test 4: End-to-End

1. Send message that triggers web_search
2. Temporarily break web_search to cause error
3. Verify proposal created
4. Verify Telegram notification received
5. Click Approve
6. Verify info.md updated
7. Verify Volume committed

## Todo List

- [ ] Add trigger_improvement() function to agentic.py
- [ ] Modify _execute_loop() to call trigger on errors
- [ ] Add test_improvement_flow() function
- [ ] Test with simulated error
- [ ] Test rate limiting
- [ ] Test deduplication
- [ ] Test full end-to-end flow
- [ ] Verify Volume commit works
- [ ] Check logs for any issues

## Success Criteria

- Tool errors trigger improvement analysis
- User response not delayed (background task)
- Proposals stored in Firebase
- Telegram notifications sent to admin
- Approve/reject buttons work
- info.md updated on approval
- Volume commits persist changes

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Circular import | High | Lazy imports in trigger_improvement |
| Task not awaited | Low | Track tasks, cleanup on shutdown |
| Firebase rate limits | Medium | Our rate limiting prevents this |
| Volume commit fails | Medium | Error message to admin, retry option |

## Next Steps

After this phase, proceed to Phase 6: Deploy & Monitor
