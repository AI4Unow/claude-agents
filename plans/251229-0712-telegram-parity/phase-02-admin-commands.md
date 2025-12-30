# Phase 2: Admin Commands

**Status:** pending
**Effort:** 1-2 days
**Depends on:** Phase 1 (Auth System)

## Context

- [plan.md](plan.md) - Overview
- [phase-01-auth-system.md](phase-01-auth-system.md) - Auth prereq

## Overview

Expose monitoring endpoints via Telegram commands with tier-based access control. Developers can view traces/circuits; admins can reset circuits.

## Key Insights

1. Reuse existing API endpoints logic (`/api/traces`, `/api/circuits`)
2. Telegram output formatting differs from JSON API
3. Rate limit admin commands to prevent abuse
4. Use `require_tier` decorator from Phase 1

## Requirements

- [ ] `/traces [limit]` - List recent traces (developer+)
- [ ] `/trace <id>` - Get trace details (developer+)
- [ ] `/circuits` - Circuit breaker status (developer+)
- [ ] `/admin reset <circuit>` - Reset specific circuit (admin)
- [ ] `/task <id>` - Local task status (user+)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ADMIN COMMAND FLOW                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TELEGRAM COMMAND                                                        │
│        │                                                                 │
│        ▼                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │ TIER CHECK   │────▶│ HANDLER      │────▶│ FORMATTER    │             │
│  │ require_tier │     │ get_traces() │     │ format_for_  │             │
│  │ ("developer")│     │ get_circuits │     │ _telegram()  │             │
│  └──────────────┘     └──────────────┘     └──────────────┘             │
│        │                                          │                      │
│        │ DENIED                                   │                      │
│        ▼                                          ▼                      │
│  "Access denied"                           Formatted HTML                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| File | Purpose | Changes |
|------|---------|---------|
| `agents/main.py:596-778` | `handle_command()` | Add admin commands |
| `agents/src/core/trace.py` | Trace retrieval | Reuse `list_traces`, `get_trace` |
| `agents/src/core/resilience.py` | Circuit breakers | Reuse `get_circuit_stats`, `reset_circuit` |
| `agents/src/services/firebase.py` | Task queue | Reuse `get_task_result` |

## Implementation Steps

### Step 1: Telegram Formatters (services/telegram.py)

Add formatters for admin data:

```python
# agents/src/services/telegram.py

def format_traces_list(traces: list) -> str:
    """Format traces list for Telegram."""
    if not traces:
        return "No traces found."

    lines = ["<b>Recent Traces:</b>\n"]
    for t in traces[:10]:
        status_emoji = {
            "success": "✅",
            "error": "❌",
            "timeout": "⏱️",
            "running": "🔄"
        }.get(t.status, "❓")

        lines.append(
            f"{status_emoji} <code>{t.trace_id}</code> | "
            f"{t.skill or 'chat'} | {t.iterations}it | {t.status}"
        )

    return "\n".join(lines)


def format_trace_detail(trace) -> str:
    """Format single trace for Telegram."""
    lines = [
        f"<b>Trace: {trace.trace_id}</b>\n",
        f"Status: {trace.status}",
        f"Skill: {trace.skill or 'N/A'}",
        f"User: {trace.user_id or 'N/A'}",
        f"Iterations: {trace.iterations}",
        f"Started: {trace.started_at[:19]}",
    ]

    if trace.tool_traces:
        lines.append(f"\n<b>Tools ({len(trace.tool_traces)}):</b>")
        for tt in trace.tool_traces[:5]:
            emoji = "❌" if tt.is_error else "✅"
            lines.append(f"  {emoji} {tt.name} ({tt.duration_ms}ms)")

    if trace.final_output:
        output = trace.final_output[:200]
        lines.append(f"\n<b>Output:</b>\n<pre>{escape_html(output)}...</pre>")

    return "\n".join(lines)


def format_circuits_status(circuits: dict) -> str:
    """Format circuit breaker status for Telegram."""
    lines = ["<b>Circuit Breakers:</b>\n"]

    for name, stats in circuits.items():
        state = stats.get("state", "unknown")
        emoji = {
            "closed": "🟢",
            "open": "🔴",
            "half_open": "🟡"
        }.get(state, "⚪")

        failures = stats.get("failure_count", 0)
        lines.append(f"{emoji} <b>{name}</b>: {state} ({failures} failures)")

    return "\n".join(lines)


def format_task_status(task: dict) -> str:
    """Format local task status for Telegram."""
    status = task.get("status", "unknown")
    emoji = {
        "pending": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "failed": "❌"
    }.get(status, "❓")

    lines = [
        f"{emoji} <b>Task {task.get('id', '')[:8]}...</b>",
        f"Skill: {task.get('skill', 'N/A')}",
        f"Status: {status}",
    ]

    if status == "completed" and task.get("result"):
        result = task.get("result", "")[:300]
        lines.append(f"\n<b>Result:</b>\n<pre>{escape_html(result)}</pre>")

    if status == "failed" and task.get("error"):
        lines.append(f"\n<b>Error:</b> {escape_html(task.get('error', '')[:100])}")

    return "\n".join(lines)
```

### Step 2: Command Handlers (main.py)

Add admin commands to `handle_command()`:

```python
# agents/main.py - add to handle_command()

elif cmd == "/traces":
    # Developer+ only
    tier = await state.get_user_tier_cached(user.get("id"))
    if not has_permission(tier, "developer"):
        return "Access denied. Requires: developer tier."

    limit = 10
    if args:
        try:
            limit = min(int(args), 20)
        except ValueError:
            pass

    from src.core.trace import list_traces
    traces = await list_traces(limit=limit)

    from src.services.telegram import format_traces_list
    return format_traces_list(traces)


elif cmd == "/trace":
    # Developer+ only
    tier = await state.get_user_tier_cached(user.get("id"))
    if not has_permission(tier, "developer"):
        return "Access denied. Requires: developer tier."

    if not args:
        return "Usage: /trace <id>"

    trace_id = args.strip()[:36]  # Sanitize

    from src.core.trace import get_trace
    trace = await get_trace(trace_id)

    if not trace:
        return f"Trace not found: {trace_id}"

    from src.services.telegram import format_trace_detail
    return format_trace_detail(trace)


elif cmd == "/circuits":
    # Developer+ only
    tier = await state.get_user_tier_cached(user.get("id"))
    if not has_permission(tier, "developer"):
        return "Access denied. Requires: developer tier."

    from src.core.resilience import get_circuit_stats
    circuits = get_circuit_stats()

    from src.services.telegram import format_circuits_status
    return format_circuits_status(circuits)


elif cmd == "/admin":
    # Admin only
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != str(admin_id):
        return "Admin only command."

    if not args:
        return (
            "<b>Admin Commands:</b>\n"
            "/admin reset <circuit> - Reset circuit breaker\n"
            "/admin stats - System statistics"
        )

    parts = args.split(maxsplit=1)
    subcommand = parts[0].lower()

    if subcommand == "reset":
        if len(parts) < 2:
            from src.core.resilience import get_circuit_stats
            circuits = get_circuit_stats()
            names = ", ".join(circuits.keys())
            return f"Usage: /admin reset <circuit>\nAvailable: {names}"

        circuit_name = parts[1].strip()

        from src.core.resilience import reset_circuit
        success = reset_circuit(circuit_name)

        if success:
            return f"✅ Circuit <b>{escape_html(circuit_name)}</b> reset."
        else:
            return f"❌ Circuit not found: {escape_html(circuit_name)}"

    elif subcommand == "stats":
        from src.core.resilience import get_circuit_stats
        from src.core.state import get_state_manager

        circuits = get_circuit_stats()
        state = get_state_manager()

        lines = [
            "<b>System Statistics:</b>\n",
            f"L1 Cache Size: {len(state._l1_cache)}",
            f"Circuits Open: {sum(1 for c in circuits.values() if c.get('state') == 'open')}",
        ]

        return "\n".join(lines)

    return "Unknown admin command. Use /admin for help."


elif cmd == "/task":
    # User+ only
    tier = await state.get_user_tier_cached(user.get("id"))
    if not has_permission(tier, "user"):
        return "Access denied. Requires: user tier."

    if not args:
        return "Usage: /task <id>"

    task_id = args.strip()[:50]  # Sanitize

    from src.services.firebase import get_task_result
    task = await get_task_result(task_id)

    if not task:
        return f"Task not found: {task_id[:8]}..."

    from src.services.telegram import format_task_status
    return format_task_status(task)
```

### Step 3: Circuit Reset Function (resilience.py)

Add single circuit reset:

```python
# agents/src/core/resilience.py

def reset_circuit(name: str) -> bool:
    """Reset a specific circuit breaker by name.

    Args:
        name: Circuit name (e.g., 'firebase', 'claude')

    Returns:
        True if reset, False if not found
    """
    circuits = {
        "exa": exa_circuit,
        "tavily": tavily_circuit,
        "firebase": firebase_circuit,
        "qdrant": qdrant_circuit,
        "claude": claude_circuit,
        "telegram": telegram_circuit,
    }

    circuit = circuits.get(name.lower())
    if circuit:
        circuit.reset()
        logger.info("circuit_reset", name=name)
        return True
    return False
```

## Todo List

- [ ] Add Telegram formatters for traces, circuits, tasks
- [ ] Add `/traces [limit]` command with tier check
- [ ] Add `/trace <id>` command
- [ ] Add `/circuits` command
- [ ] Add `/admin reset <circuit>` command
- [ ] Add `/admin stats` command
- [ ] Add `/task <id>` command
- [ ] Add `reset_circuit()` to resilience.py
- [ ] Update `/help` with new commands
- [ ] Test all commands with different tiers

## Success Criteria

1. Developer can view traces via `/traces`
2. Developer can get trace detail via `/trace <id>`
3. Developer can see circuit status via `/circuits`
4. Admin can reset circuits via `/admin reset <name>`
5. User can check task status via `/task <id>`
6. Guest users get "Access denied" messages

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Trace data exposure | Low | Medium | Only show sanitized summaries |
| Circuit reset abuse | Low | Medium | Admin-only restriction |
| Firebase query cost | Medium | Low | Limit results, cache where possible |

## Security Considerations

1. **Tier validation** - Every command checks user tier
2. **Input sanitization** - Trace IDs truncated/validated
3. **Admin verification** - ADMIN_TELEGRAM_ID for sensitive ops
4. **Output sanitization** - HTML escape all user data
5. **Rate limiting** - Existing Telegram webhook rate limit applies

## Next Steps

After completing this phase:
1. Proceed to [Phase 3: Complexity Detector](phase-03-complexity-detector.md)
2. Admin commands provide visibility for debugging orchestration
