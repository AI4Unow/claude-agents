# Phase 4: SLA Dashboard Enhancement

## Context Links

- Main plan: [plan.md](./plan.md)
- Phase 2: [phase-02-ux-metrics.md](./phase-02-ux-metrics.md)
- Developer commands: `agents/commands/developer.py`

## Overview

Enhance the `/sla` command added in Phase 2 with historical metrics, circuit breaker details, and optional time ranges. This is a low-priority polish phase building on Phase 2's metrics infrastructure.

## Key Insights

1. **Foundation in Phase 2** - `/sla` command already implemented with basic metrics
2. **KISS principle** - Telegram command sufficient, no external dashboard needed
3. **Developer-only** - Only developer+ tier can access
4. **Historical queries** - Support 1h, 24h, 7d time ranges

## Requirements

### Functional
- Show P50/P95/P99 latencies for LLM and web search
- Show command success rates
- Show circuit breaker current states
- Show circuit trip count for period
- Support time range parameter (1h, 24h, 7d)

### Non-Functional
- Response under 3 seconds
- Clean formatted output
- Graceful degradation if metrics unavailable

## Architecture

```
/sla [hours]
    |
    v
+------------------+     +-----------------+
| UXMetricsService |---->| Firestore       |
| get_sla_report() |     | ux_metrics      |
+------------------+     +-----------------+
    |
    v
+------------------+
| get_circuit_stats|
| (resilience.py)  |
+------------------+
    |
    v
Formatted Response
```

## Related Code Files

| File | Purpose |
|------|---------|
| `commands/developer.py` | /sla command |
| `src/services/firebase/ux_metrics.py` | Metrics service |
| `src/core/resilience.py` | Circuit stats |
| `src/services/telegram.py` | Message formatting |

## Implementation Steps

### Step 1: Enhance /sla Command (commands/developer.py)

The basic implementation is in Phase 2. This phase adds:

```python
@command_router.command(
    name="/sla",
    description="Show SLA metrics (P50/P95/P99 latencies, success rates, circuits)",
    usage="/sla [hours=24]",
    permission="developer",
    category="developer"
)
async def sla_command(args: str, user: dict, chat_id: int) -> str:
    """Show SLA metrics dashboard."""
    from src.services.firebase.ux_metrics import get_ux_metrics_service
    from src.core.resilience import get_circuit_stats

    # Parse hours argument
    hours = 24
    if args:
        arg = args.strip()
        if arg.isdigit():
            hours = int(arg)
        elif arg.endswith("h"):
            hours = int(arg[:-1])
        elif arg.endswith("d"):
            hours = int(arg[:-1]) * 24

    hours = max(1, min(hours, 168))  # 1h to 7d

    # Get metrics
    try:
        metrics = await get_ux_metrics_service().get_sla_report(hours=hours)
    except Exception as e:
        return f"Error fetching metrics: {str(e)[:50]}"

    # Get circuit states
    circuits = get_circuit_stats()
    open_circuits = [
        name for name, stats in circuits.items()
        if stats["state"] == "open"
    ]

    # Format circuit summary
    circuit_summary = "All healthy" if not open_circuits else ", ".join(open_circuits)

    # Build response
    time_label = f"{hours}h" if hours < 24 else f"{hours//24}d"

    response = f"""**SLA Dashboard ({time_label})**

**LLM Performance** (api.ai4u.now)
- P50: `{metrics.get('llm_p50', 0):,}ms`
- P95: `{metrics.get('llm_p95', 0):,}ms`
- P99: `{metrics.get('llm_p99', 0):,}ms`
- Success: `{metrics.get('llm_success_rate', 0):.1f}%`

**Web Search**
- P50: `{metrics.get('search_p50', 0):,}ms`
- P95: `{metrics.get('search_p95', 0):,}ms`
- Success: `{metrics.get('search_success_rate', 0):.1f}%`

**Commands**
- Total: `{metrics.get('command_count', 0):,}`
- Success: `{metrics.get('command_success_rate', 0):.1f}%`

**Circuits**
- Status: {circuit_summary}
- Trips: `{metrics.get('circuit_trips', 0)}`
"""

    # Add SLA warnings
    warnings = []
    if metrics.get('llm_p95', 0) > 5000:
        warnings.append("LLM P95 > 5s SLA")
    if metrics.get('command_success_rate', 100) < 99:
        warnings.append("Command success < 99%")
    if open_circuits:
        warnings.append(f"Open circuits: {len(open_circuits)}")

    if warnings:
        response += "\n**Warnings**\n" + "\n".join(f"- {w}" for w in warnings)

    return response
```

### Step 2: Add Detailed Circuit View

Add `/circuits detail` subcommand or enhance existing:

```python
# In commands/developer.py - enhance circuits_command

@command_router.command(
    name="/circuits",
    description="Show circuit breaker status and statistics",
    usage="/circuits [detail]",
    permission="developer",
    category="developer"
)
async def circuits_command(args: str, user: dict, chat_id: int) -> str:
    """Show circuit breaker status."""
    from src.core.resilience import get_circuit_stats

    circuits = get_circuit_stats()
    show_detail = args and "detail" in args.lower()

    if show_detail:
        # Detailed view
        lines = ["**Circuit Breaker Details**\n"]
        for name, stats in circuits.items():
            state_emoji = {
                "closed": "green",
                "open": "red",
                "half_open": "yellow"
            }.get(stats["state"], "white")

            lines.append(f"**{name}**")
            lines.append(f"  State: {stats['state']}")
            lines.append(f"  Failures: {stats['failures']}/{stats['threshold']}")
            lines.append(f"  Successes: {stats['successes']}")
            if stats['cooldown_remaining'] > 0:
                lines.append(f"  Cooldown: {stats['cooldown_remaining']}s")
            lines.append("")

        return "\n".join(lines)

    # Summary view (existing)
    from src.services.telegram import format_circuits_status
    return format_circuits_status(circuits)
```

### Step 3: Add Metrics Cleanup Cron (Optional)

If TTL index doesn't work, add manual cleanup:

```python
# In main.py - add cron job

@app.function(
    schedule=modal.Cron("0 3 * * *"),  # 3 AM daily
    secrets=[firebase_secret]
)
async def cleanup_old_metrics():
    """Delete UX metrics older than 30 days."""
    from datetime import datetime, timezone, timedelta
    from src.services.firebase._client import get_db

    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # Query old metrics
    old_metrics = (
        db.collection("ux_metrics")
        .where("timestamp", "<", cutoff)
        .limit(500)  # Batch size
    )

    docs = list(old_metrics.stream())
    if not docs:
        return {"deleted": 0}

    # Batch delete
    batch = db.batch()
    for doc in docs:
        batch.delete(doc.reference)
    batch.commit()

    return {"deleted": len(docs)}
```

## Todo List

- [ ] Enhance `/sla` with time range parsing (1h, 24h, 7d)
- [ ] Add SLA warning indicators
- [ ] Add `/circuits detail` subcommand
- [ ] Test metrics display formatting
- [ ] Add metrics cleanup cron (if TTL index fails)

## Success Criteria

- [ ] `/sla 24` shows last 24 hours
- [ ] `/sla 7d` shows last 7 days
- [ ] SLA warnings displayed when thresholds exceeded
- [ ] `/circuits detail` shows all circuit info
- [ ] Response time < 3s

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Slow queries | Medium | Low | Limit time range, use indexes |
| Missing data | Low | Low | Show "N/A" for missing metrics |
| Format issues | Low | Low | Test with real data |
