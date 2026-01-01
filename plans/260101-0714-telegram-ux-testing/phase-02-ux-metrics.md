# Phase 2: UX Metrics Collection

## Context Links

- Main plan: [plan.md](./plan.md)
- Brainstorm: `plans/reports/brainstorm-260101-0714-telegram-ux-testing.md`
- Firebase modules: `agents/src/services/firebase/`

## Overview

Implement UX metrics collection service in Firestore to track latency, command success rates, and circuit breaker statistics. Instrument LLM client and command router with automatic metric recording.

## Key Insights

1. **No metrics collection exists** - Current system has tracing but no aggregated UX metrics
2. **Firestore natural fit** - Already using Firebase, add `ux_metrics` collection
3. **Minimal overhead** - Async writes, batch where possible (< 50ms target)
4. **30-day TTL** - Prevent unbounded storage growth

## Requirements

### Functional
- Record LLM response latency per request
- Record command execution success/failure
- Record circuit breaker trips and recoveries
- Provide SLA report (P50, P95, P99 latencies, success rates)
- Support time-range queries (1h, 24h, 7d)

### Non-Functional
- Metrics write overhead < 50ms
- 30-day automatic cleanup (TTL)
- Non-blocking (fire-and-forget writes)
- Circuit breaker protection for metrics themselves

## Architecture

```
+------------------+     +------------------+
|   LLM Client     |---->|                  |
|   (llm.py)       |     |                  |
+------------------+     |                  |
                         |  UXMetricsService |
+------------------+     |  (ux_metrics.py) |
| Command Router   |---->|                  |
| (commands/*.py)  |     |                  |
+------------------+     +--------+---------+
                                  |
                                  v
                         +------------------+
                         |    Firestore     |
                         |   ux_metrics     |
                         +------------------+
```

### Firestore Schema

```javascript
ux_metrics/{metricId}
  +-- type: "latency" | "command" | "circuit"
  +-- operation: string  // "llm_chat", "skill_execute", etc.
  +-- value_ms: number   // For latency metrics
  +-- success: boolean
  +-- error_type: string | null
  +-- context: {
  |     user_tier: string,
  |     command: string,
  |     skill: string,
  |     model: string
  |   }
  +-- timestamp: timestamp
  +-- expires_at: timestamp  // 30 days from creation
```

## Related Code Files

| File | Purpose |
|------|---------|
| `src/services/firebase/_circuit.py` | Circuit decorator pattern |
| `src/services/firebase/__init__.py` | Module exports |
| `src/services/llm.py` | LLMClient to instrument |
| `commands/router.py` | Command router to instrument |
| `commands/developer.py` | Add /sla command |
| `src/core/resilience.py` | Circuit breaker stats |

## Implementation Steps

### Step 1: Create src/services/firebase/ux_metrics.py

```python
"""UX metrics collection and storage.

Tracks latency, command success, and circuit breaker events.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any
import asyncio

from src.services.firebase._client import get_db
from src.services.firebase._circuit import with_firebase_circuit
from src.utils.logging import get_logger

logger = get_logger()

# TTL for metrics (30 days)
METRICS_TTL_DAYS = 30


class UXMetricsService:
    """Collect and analyze UX metrics."""

    def __init__(self):
        self._write_queue: List[Dict] = []
        self._flush_task: Optional[asyncio.Task] = None

    async def record_latency(
        self,
        operation: str,
        latency_ms: int,
        success: bool,
        context: Optional[Dict] = None
    ) -> None:
        """Record operation latency.

        Args:
            operation: "llm_chat", "skill_execute", "web_search", etc.
            latency_ms: Duration in milliseconds
            success: Whether operation succeeded
            context: Additional context (user_tier, model, etc.)
        """
        now = datetime.now(timezone.utc)
        metric = {
            "type": "latency",
            "operation": operation,
            "value_ms": latency_ms,
            "success": success,
            "context": context or {},
            "timestamp": now,
            "expires_at": now + timedelta(days=METRICS_TTL_DAYS)
        }
        await self._queue_write(metric)

    async def record_command(
        self,
        command: str,
        user_tier: str,
        success: bool,
        error_type: Optional[str] = None,
        latency_ms: Optional[int] = None
    ) -> None:
        """Record command execution.

        Args:
            command: Command name (e.g., "/start", "/skills")
            user_tier: User tier (guest, user, developer, admin)
            success: Whether command succeeded
            error_type: Error classification if failed
            latency_ms: Command execution time
        """
        now = datetime.now(timezone.utc)
        metric = {
            "type": "command",
            "operation": command,
            "success": success,
            "error_type": error_type,
            "context": {
                "user_tier": user_tier,
                "latency_ms": latency_ms
            },
            "timestamp": now,
            "expires_at": now + timedelta(days=METRICS_TTL_DAYS)
        }
        await self._queue_write(metric)

    async def record_circuit_event(
        self,
        circuit_name: str,
        event: str,  # "opened", "closed", "half_open"
        failure_count: int = 0
    ) -> None:
        """Record circuit breaker state change.

        Args:
            circuit_name: Circuit identifier
            event: State transition
            failure_count: Failures before opening
        """
        now = datetime.now(timezone.utc)
        metric = {
            "type": "circuit",
            "operation": circuit_name,
            "success": event == "closed",
            "context": {
                "event": event,
                "failure_count": failure_count
            },
            "timestamp": now,
            "expires_at": now + timedelta(days=METRICS_TTL_DAYS)
        }
        await self._queue_write(metric)

    async def _queue_write(self, metric: Dict) -> None:
        """Queue metric for batch write."""
        self._write_queue.append(metric)

        # Flush immediately for now (batch later if needed)
        await self._flush()

    @with_firebase_circuit(open_return=None)
    async def _flush(self) -> None:
        """Write queued metrics to Firestore."""
        if not self._write_queue:
            return

        db = get_db()
        batch = db.batch()
        metrics_ref = db.collection("ux_metrics")

        for metric in self._write_queue[:50]:  # Max 50 per batch
            doc_ref = metrics_ref.document()
            batch.set(doc_ref, metric)

        await asyncio.to_thread(batch.commit)
        self._write_queue = self._write_queue[50:]

        logger.debug("ux_metrics_flushed", count=min(50, len(self._write_queue) + 50))

    @with_firebase_circuit(open_return={})
    async def get_sla_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get SLA metrics for dashboard.

        Args:
            hours: Time window (1, 24, 168 for week)

        Returns:
            SLA report with P50/P95/P99 latencies, success rates
        """
        db = get_db()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Query latency metrics
        latency_query = (
            db.collection("ux_metrics")
            .where("type", "==", "latency")
            .where("timestamp", ">=", cutoff)
        )

        # Query command metrics
        command_query = (
            db.collection("ux_metrics")
            .where("type", "==", "command")
            .where("timestamp", ">=", cutoff)
        )

        # Query circuit events
        circuit_query = (
            db.collection("ux_metrics")
            .where("type", "==", "circuit")
            .where("timestamp", ">=", cutoff)
        )

        # Execute queries
        latency_docs = await asyncio.to_thread(lambda: list(latency_query.stream()))
        command_docs = await asyncio.to_thread(lambda: list(command_query.stream()))
        circuit_docs = await asyncio.to_thread(lambda: list(circuit_query.stream()))

        # Process latency metrics
        llm_latencies = []
        search_latencies = []
        for doc in latency_docs:
            data = doc.to_dict()
            latency = data.get("value_ms", 0)
            op = data.get("operation", "")
            if op == "llm_chat":
                llm_latencies.append(latency)
            elif op == "web_search":
                search_latencies.append(latency)

        # Calculate percentiles
        def percentile(data: List[int], p: int) -> int:
            if not data:
                return 0
            data_sorted = sorted(data)
            idx = int(len(data_sorted) * p / 100)
            return data_sorted[min(idx, len(data_sorted) - 1)]

        # Process command metrics
        command_total = len(command_docs)
        command_success = sum(1 for d in command_docs if d.to_dict().get("success"))

        # Process circuit events
        circuit_opens = sum(
            1 for d in circuit_docs
            if d.to_dict().get("context", {}).get("event") == "opened"
        )

        return {
            "hours": hours,
            "llm_p50": percentile(llm_latencies, 50),
            "llm_p95": percentile(llm_latencies, 95),
            "llm_p99": percentile(llm_latencies, 99),
            "llm_success_rate": (
                sum(1 for d in latency_docs if d.to_dict().get("operation") == "llm_chat" and d.to_dict().get("success"))
                / max(len(llm_latencies), 1) * 100
            ),
            "search_p50": percentile(search_latencies, 50),
            "search_p95": percentile(search_latencies, 95),
            "search_success_rate": (
                sum(1 for d in latency_docs if d.to_dict().get("operation") == "web_search" and d.to_dict().get("success"))
                / max(len(search_latencies), 1) * 100
            ),
            "command_count": command_total,
            "command_success_rate": command_success / max(command_total, 1) * 100,
            "circuits_open": circuit_opens,
            "circuit_trips": circuit_opens,
        }


# Singleton
_service: Optional[UXMetricsService] = None


def get_ux_metrics_service() -> UXMetricsService:
    """Get or create UXMetricsService singleton."""
    global _service
    if _service is None:
        _service = UXMetricsService()
    return _service
```

### Step 2: Update src/services/firebase/__init__.py

Add export for new module:

```python
# Add to exports
from src.services.firebase.ux_metrics import (
    UXMetricsService,
    get_ux_metrics_service,
)
```

### Step 3: Instrument LLM Client (src/services/llm.py)

Add latency recording to `chat()` method:

```python
# At top of file
from src.services.firebase.ux_metrics import get_ux_metrics_service
import time

# In chat() method, wrap the try block:
async def chat(self, ...):
    start_time = time.time()
    success = False

    try:
        # ... existing code ...
        success = True
        return response
    finally:
        # Record metrics (fire-and-forget)
        latency_ms = int((time.time() - start_time) * 1000)
        try:
            import asyncio
            asyncio.create_task(
                get_ux_metrics_service().record_latency(
                    operation="llm_chat",
                    latency_ms=latency_ms,
                    success=success,
                    context={"model": effective_model}
                )
            )
        except Exception:
            pass  # Don't fail on metrics
```

### Step 4: Instrument Command Router

Add command metrics to `commands/base.py`:

```python
# In CommandRouter.execute() or command handler wrapper
async def _execute_with_metrics(self, handler, args, user, chat_id):
    start_time = time.time()
    success = False
    error_type = None

    try:
        result = await handler(args, user, chat_id)
        success = True
        return result
    except Exception as e:
        error_type = type(e).__name__
        raise
    finally:
        latency_ms = int((time.time() - start_time) * 1000)
        try:
            import asyncio
            from src.services.firebase.ux_metrics import get_ux_metrics_service
            asyncio.create_task(
                get_ux_metrics_service().record_command(
                    command=handler.__name__,
                    user_tier=user.get("tier", "guest"),
                    success=success,
                    error_type=error_type,
                    latency_ms=latency_ms
                )
            )
        except Exception:
            pass
```

### Step 5: Add /sla Command to commands/developer.py

```python
@command_router.command(
    name="/sla",
    description="Show SLA metrics for last 24h (P50/P95/P99 latencies, success rates)",
    usage="/sla [hours]",
    permission="developer",
    category="developer"
)
async def sla_command(args: str, user: dict, chat_id: int) -> str:
    """Show SLA metrics."""
    from src.services.firebase.ux_metrics import get_ux_metrics_service
    from src.core.resilience import get_circuit_status

    hours = int(args) if args and args.isdigit() else 24
    hours = min(hours, 168)  # Max 7 days

    metrics = await get_ux_metrics_service().get_sla_report(hours=hours)
    circuits = get_circuit_status()

    # Count open circuits
    open_count = sum(1 for v in circuits.values() if v != "closed")

    return f"""**SLA Report ({hours}h)**

**LLM (api.ai4u.now)**
- P50: {metrics['llm_p50']}ms
- P95: {metrics['llm_p95']}ms
- P99: {metrics['llm_p99']}ms
- Success: {metrics['llm_success_rate']:.1f}%

**Web Search**
- P50: {metrics['search_p50']}ms
- P95: {metrics['search_p95']}ms
- Success: {metrics['search_success_rate']:.1f}%

**Commands**
- Total: {metrics['command_count']}
- Success: {metrics['command_success_rate']:.1f}%

**Circuits**
- Open: {open_count}/8
- Trips: {metrics['circuit_trips']}"""
```

### Step 6: Create Firestore TTL Index

Add to `firestore.indexes.json`:

```json
{
  "fieldOverrides": [
    {
      "collectionGroup": "ux_metrics",
      "fieldPath": "expires_at",
      "ttl": true
    }
  ]
}
```

Deploy with:
```bash
firebase deploy --only firestore:indexes
```

## Todo List

- [ ] Create `src/services/firebase/ux_metrics.py`
- [ ] Update `src/services/firebase/__init__.py` with export
- [ ] Instrument `src/services/llm.py` with latency recording
- [ ] Instrument command router with success/failure tracking
- [ ] Add `/sla` command to `commands/developer.py`
- [ ] Add TTL index to `firestore.indexes.json`
- [ ] Deploy Firestore indexes
- [ ] Test metrics collection manually
- [ ] Verify 30-day TTL cleanup works

## Success Criteria

- [ ] `/sla` command returns valid metrics
- [ ] LLM latencies recorded automatically
- [ ] Command success/failure tracked
- [ ] Metrics write overhead < 50ms
- [ ] Old metrics auto-deleted after 30 days
- [ ] No impact on normal bot operation

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Metrics write failures | Low | Low | Fire-and-forget, circuit breaker |
| Storage costs | Low | Low | 30-day TTL, small doc size |
| Query performance | Medium | Low | Limit time range, use indexes |
| Cold start overhead | Low | Low | Lazy service initialization |
