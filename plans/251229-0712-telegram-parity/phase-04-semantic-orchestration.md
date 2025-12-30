# Phase 4: Semantic Orchestration

**Status:** pending
**Effort:** 3-5 days
**Depends on:** Phase 3 (Complexity Detector)

## Context

- [plan.md](plan.md) - Overview
- [phase-03-complexity-detector.md](phase-03-complexity-detector.md) - Previous phase
- [orchestrator.py](../../agents/src/core/orchestrator.py) - Existing orchestrator

## Overview

Modify the orchestrator to emit progress messages via Telegram. Each skill execution shows "Using: {skill}..." followed by results. Sequential visibility for complex multi-step tasks.

## Key Insights

1. Telegram has rate limits (30 msg/sec per chat) - batch small updates
2. Edit existing progress message vs. send new messages
3. Progress callback pattern already exists in agentic loop
4. Synthesis step should show final summary

## Requirements

- [ ] `progress_callback` parameter in Orchestrator.execute()
- [ ] Emit "Using: {skill}..." before each worker
- [ ] Emit "Result: ..." after each worker
- [ ] Show synthesis progress
- [ ] Handle Telegram rate limits gracefully
- [ ] Format progress for Telegram HTML

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION PROGRESS FLOW                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ORCHESTRATOR.EXECUTE()                                                  │
│       │                                                                  │
│       ▼                                                                  │
│  ┌──────────────────┐                                                    │
│  │ DECOMPOSE        │──▶ callback("📋 Planning 3 subtasks...")          │
│  └────────┬─────────┘                                                    │
│           │                                                              │
│  ┌────────▼─────────┐                                                    │
│  │ SUBTASK 1        │                                                    │
│  │ skill: planning  │                                                    │
│  └────────┬─────────┘                                                    │
│           │                                                              │
│  callback("🔧 Using: planning...")                                       │
│           │                                                              │
│  [Execute skill]                                                         │
│           │                                                              │
│  callback("📝 planning: [preview]...")                                   │
│           │                                                              │
│  ┌────────▼─────────┐                                                    │
│  │ SUBTASK 2        │                                                    │
│  │ skill: backend   │                                                    │
│  └────────┬─────────┘                                                    │
│           │                                                              │
│  callback("🔧 Using: backend-development...")                            │
│           │                                                              │
│  [Execute skill]                                                         │
│           │                                                              │
│  callback("📝 backend-development: [preview]...")                        │
│           │                                                              │
│  ┌────────▼─────────┐                                                    │
│  │ SYNTHESIZE       │──▶ callback("✨ Synthesizing results...")          │
│  └────────┬─────────┘                                                    │
│           │                                                              │
│           ▼                                                              │
│  FINAL RESPONSE                                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| File | Purpose | Changes |
|------|---------|---------|
| `agents/src/core/orchestrator.py` | Task orchestration | Add progress_callback |
| `agents/main.py:_run_orchestrated` | Telegram integration | Create callback function |
| `agents/src/services/telegram.py` | Formatters | Add progress formatters |

## Implementation Steps

### Step 1: Update Orchestrator (core/orchestrator.py)

Add progress callback support:

```python
# agents/src/core/orchestrator.py

from typing import Callable, Awaitable

# Type alias for progress callback
ProgressCallback = Callable[[str], Awaitable[None]]


class Orchestrator:
    """Decompose tasks, delegate to skill workers, synthesize results.

    Usage:
        async def progress(msg):
            print(msg)

        orch = Orchestrator()
        result = await orch.execute(
            "Build a login system",
            context={"project": "my-app"},
            progress_callback=progress
        )
    """

    def __init__(
        self,
        router: Optional[SkillRouter] = None,
        max_parallel: int = 5,
        llm_client: Optional[Any] = None
    ):
        self.router = router or SkillRouter()
        self.max_parallel = max_parallel
        self.logger = logger.bind(component="Orchestrator")

        if llm_client is None:
            from src.services.llm import get_llm_client
            llm_client = get_llm_client()
        self.llm = llm_client

    async def execute(
        self,
        task: str,
        context: Optional[Dict] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """Execute a complex task through orchestration.

        Args:
            task: Task description
            context: Additional context
            progress_callback: Async function to report progress

        Returns:
            Synthesized final response
        """
        self.logger.info("orchestration_start", task=task[:100])

        async def report(msg: str):
            if progress_callback:
                try:
                    await progress_callback(msg)
                except Exception as e:
                    self.logger.warning("progress_callback_error", error=str(e)[:50])

        # Step 1: Decompose
        await report("📋 <i>Analyzing task...</i>")
        subtasks = await self.decompose(task, context)
        self.logger.info("decomposed", subtasks=len(subtasks))

        await report(f"📋 <i>Planned {len(subtasks)} subtasks</i>")

        # Step 2: Validate dependencies
        dependencies = {str(i): st.depends_on for i, st in enumerate(subtasks)}
        validated_deps = self._validate_dependencies(
            [str(i) for i in range(len(subtasks))],
            dependencies
        )

        for i, subtask in enumerate(subtasks):
            subtask.depends_on = validated_deps.get(str(i), [])

        # Step 3: Validate DAG
        if not self._validate_dag(
            [str(i) for i in range(len(subtasks))],
            {str(i): st.depends_on for i, st in enumerate(subtasks)}
        ):
            return "Error: Circular dependency detected."

        # Step 4: Route subtasks to skills
        for i, subtask in enumerate(subtasks):
            if not subtask.skill_name:
                matches = await self.router.route(subtask.description, limit=1)
                if matches:
                    subtask.skill_name = matches[0].skill_name

        # Step 5: Execute workers with progress
        results = await self._execute_with_dependencies(subtasks, report)

        # Step 6: Synthesize
        await report("✨ <i>Synthesizing results...</i>")
        final = await self.synthesize(task, results, context)

        # Final stats
        total_time = sum(r.duration_ms for r in results)
        success_count = sum(1 for r in results if r.success)
        await report(f"✅ <i>Complete ({success_count}/{len(results)} skills, {total_time}ms)</i>")

        self.logger.info("orchestration_complete", workers=len(results))
        return final

    async def _execute_with_dependencies(
        self,
        subtasks: List[SubTask],
        report: Callable[[str], Awaitable[None]]
    ) -> List[WorkerResult]:
        """Execute subtasks respecting dependencies with progress."""
        results: List[WorkerResult] = []
        completed = set()

        while len(completed) < len(subtasks):
            ready = []
            for i, subtask in enumerate(subtasks):
                if i not in completed:
                    if all(d in completed for d in subtask.depends_on):
                        ready.append((i, subtask))

            if not ready:
                self.logger.error("dependency_deadlock")
                break

            batch = ready[:self.max_parallel]

            # Report starting skills
            skill_names = [st.skill_name or "general" for _, st in batch]
            if len(skill_names) == 1:
                await report(f"🔧 <i>Using: {skill_names[0]}</i>")
            else:
                await report(f"🔧 <i>Using: {', '.join(skill_names)}</i>")

            # Execute batch
            batch_results = await asyncio.gather(*[
                self._execute_worker(
                    subtask,
                    {str(d): results[d].output for d in subtask.depends_on if d < len(results)}
                )
                for i, subtask in batch
            ])

            # Report results
            for (i, subtask), result in zip(batch, batch_results):
                results.append(result)
                subtasks[i].result = result.output
                completed.add(i)

                # Preview of result (first 100 chars)
                preview = result.output[:100].replace('\n', ' ')
                if len(result.output) > 100:
                    preview += "..."

                emoji = "📝" if result.success else "❌"
                await report(f"{emoji} <i>{result.skill_name}: {preview}</i>")

        return results

    # ... rest of methods unchanged ...
```

### Step 2: Update Telegram Formatters (services/telegram.py)

Add orchestration progress formatters:

```python
# agents/src/services/telegram.py

def format_orchestration_progress(
    skill_name: str,
    status: str,
    preview: str = None
) -> str:
    """Format orchestration progress for Telegram.

    Args:
        skill_name: Name of skill being executed
        status: 'start', 'complete', 'error'
        preview: Optional result preview

    Returns:
        Formatted HTML string
    """
    if status == "start":
        return f"🔧 <i>Using: {escape_html(skill_name)}...</i>"
    elif status == "complete":
        if preview:
            preview_clean = escape_html(preview[:100])
            return f"📝 <i>{escape_html(skill_name)}: {preview_clean}</i>"
        return f"📝 <i>{escape_html(skill_name)}: Done</i>"
    elif status == "error":
        return f"❌ <i>{escape_html(skill_name)}: Failed</i>"
    return ""


def format_orchestration_summary(
    subtask_count: int,
    success_count: int,
    total_duration_ms: int
) -> str:
    """Format final orchestration summary."""
    return (
        f"✅ <b>Complete</b>\n"
        f"Skills: {success_count}/{subtask_count} successful\n"
        f"Duration: {total_duration_ms}ms"
    )
```

### Step 3: Update _run_orchestrated (main.py)

Create comprehensive progress callback:

```python
# agents/main.py

async def _run_orchestrated(
    text: str,
    user: dict,
    chat_id: int,
    progress_msg_id: int
) -> str:
    """Run orchestrated multi-skill execution with Telegram progress."""
    from src.core.orchestrator import Orchestrator
    import structlog

    logger = structlog.get_logger()

    # Track progress messages to avoid rate limiting
    last_update_time = [0.0]  # Use list for mutable closure
    min_update_interval = 1.0  # 1 second between updates

    async def progress_callback(status: str):
        """Throttled progress callback."""
        import time
        current_time = time.time()

        # Throttle updates
        if current_time - last_update_time[0] < min_update_interval:
            return

        last_update_time[0] = current_time

        try:
            await edit_progress_message(chat_id, progress_msg_id, status)
        except Exception as e:
            logger.warning("progress_update_failed", error=str(e)[:50])

    orchestrator = Orchestrator()

    result = await orchestrator.execute(
        task=text,
        context={"user": user, "user_id": user.get("id")},
        progress_callback=progress_callback
    )

    return result
```

### Step 4: Add Sequential Message Option (main.py)

For verbose mode, send separate messages per skill:

```python
# agents/main.py

async def _run_orchestrated_verbose(
    text: str,
    user: dict,
    chat_id: int,
    progress_msg_id: int
) -> str:
    """Orchestration with separate messages per skill (verbose mode)."""
    from src.core.orchestrator import Orchestrator

    # Send new message for each skill instead of editing
    async def progress_callback(status: str):
        # Skip intermediate status updates
        if status.startswith("📝") or status.startswith("✅"):
            await send_telegram_message(chat_id, status)

    orchestrator = Orchestrator()

    # Delete initial progress message
    await edit_progress_message(chat_id, progress_msg_id, "🔧 <i>Starting orchestration...</i>")

    result = await orchestrator.execute(
        task=text,
        context={"user": user},
        progress_callback=progress_callback
    )

    return result
```

## Todo List

- [ ] Add `ProgressCallback` type to orchestrator.py
- [ ] Add `progress_callback` parameter to `execute()`
- [ ] Update `_execute_with_dependencies()` to call callback
- [ ] Add progress calls for decompose/synthesize steps
- [ ] Add throttling to prevent rate limits
- [ ] Update `_run_orchestrated()` with callback
- [ ] Add formatters to telegram.py
- [ ] Test with multi-skill task
- [ ] Test rate limit handling

## Success Criteria

1. "Using: planning..." shows before skill execution
2. "planning: [preview]..." shows after execution
3. "Synthesizing results..." shows during synthesis
4. Final message shows "Complete (3/3 skills, 2500ms)"
5. Updates throttled to prevent rate limits
6. Errors shown with appropriate emoji

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Telegram rate limit | Medium | Low | Throttle to 1s intervals |
| Message edit fails | Low | Low | Silent failure, continue |
| Long execution timeout | Medium | Medium | Keep progress updated |
| Progress message too long | Low | Low | Truncate previews |

## Security Considerations

1. **Output sanitization** - Escape HTML in all skill outputs
2. **Preview truncation** - Limit preview to 100 chars
3. **Error masking** - Don't expose internal errors to user
4. **Rate limiting** - Throttle updates to prevent abuse

## Next Steps

After completing this phase:
1. Proceed to [Phase 5: Polish](phase-05-polish.md)
2. Full end-to-end testing of orchestration
