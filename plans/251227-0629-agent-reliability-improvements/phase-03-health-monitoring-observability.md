# Phase 3: Health Monitoring & Observability

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 2](./phase-02-circuit-breakers-guardrails.md)
- Research: [modal-reliability.md](./research/researcher-02-modal-reliability.md)

## Overview

**Priority:** P1 - Visibility
**Status:** Pending
**Effort:** 2h

Implement health endpoints, structured logging with metrics, and Firebase-based alerting for agent observability.

## Key Insights

1. Health endpoints enable external monitoring
2. Structured logging with structlog enables querying
3. Firebase can serve as lightweight alerting backend
4. Key metrics: success rate, latency, error rate, token usage

## Requirements

### Functional
- `/health` endpoint for each web agent
- Structured logs with context (agent, task, user)
- Metrics collection (success/failure counts, latency)
- Firebase alert collection for critical issues

### Non-Functional
- Health check response <100ms
- Logging overhead <5ms per log line
- Metrics queryable via Firebase console

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AGENTS                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│  │ Telegram │ │ GitHub   │ │ Data     │                         │
│  │ /health  │ │          │ │          │                         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                         │
│       │            │            │                                │
│       └────────────┴────────────┘                                │
│                    │                                             │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              STRUCTURED LOGGING (structlog)               │   │
│  │  {agent: "telegram", action: "message", latency_ms: 234} │   │
│  └──────────────────────────────────────────────────────────┘   │
│                    │                                             │
│         ┌─────────┴─────────┐                                   │
│         ▼                   ▼                                   │
│  ┌─────────────┐    ┌─────────────┐                             │
│  │ Modal Logs  │    │  Firebase   │                             │
│  │ (stdout)    │    │  (metrics)  │                             │
│  └─────────────┘    └─────────────┘                             │
│                            │                                     │
│                            ▼                                     │
│                     ┌─────────────┐                              │
│                     │   Alerts    │                              │
│                     │(Telegram/   │                              │
│                     │Slack/Email) │                              │
│                     └─────────────┘                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| Path | Action | Description |
|------|--------|-------------|
| `agents/main.py` | Modify | Add health endpoint |
| `agents/src/utils/logging.py` | Modify | Enhance structured logging |
| `agents/src/utils/metrics.py` | Create | Metrics collector |
| `agents/src/services/firebase.py` | Modify | Add metrics storage |

## Implementation Steps

### 1. Create Health Endpoint

```python
# In main.py, add to web_app

from datetime import datetime

@web_app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "telegram-chat",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }

@web_app.get("/health/detailed")
async def health_detailed():
    """Detailed health with dependency checks."""
    checks = {
        "firebase": await check_firebase(),
        "qdrant": await check_qdrant(),
        "anthropic": await check_anthropic(),
        "volume": check_volume(),
    }

    all_healthy = all(c["status"] == "ok" for c in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }

async def check_firebase() -> dict:
    try:
        db.collection("health").document("ping").get()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def check_qdrant() -> dict:
    try:
        qdrant.get_collections()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def check_anthropic() -> dict:
    # Just check auth, don't make real call
    try:
        # Verify API key exists
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return {"status": "error", "message": "API key missing"}
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_volume() -> dict:
    if Path("/skills").exists():
        return {"status": "ok"}
    return {"status": "error", "message": "Volume not mounted"}
```

### 2. Enhanced Structured Logging (`src/utils/logging.py`)

```python
import structlog
import time
from functools import wraps
from contextlib import contextmanager

def setup_logging():
    """Configure structlog for production."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

def get_logger(agent_id: str = None):
    """Get logger with agent context."""
    logger = structlog.get_logger()
    if agent_id:
        logger = logger.bind(agent=agent_id)
    return logger

@contextmanager
def log_duration(logger, action: str, **extra):
    """Context manager to log action duration."""
    start = time.perf_counter()
    try:
        yield
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"{action}_completed",
            duration_ms=round(duration_ms, 2),
            **extra
        )
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(f"{action}_failed",
            duration_ms=round(duration_ms, 2),
            error=str(e),
            **extra
        )
        raise

def log_execution(action: str):
    """Decorator to log function execution."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = structlog.get_logger()
            with log_duration(logger, action):
                return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 3. Metrics Collector (`src/utils/metrics.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
import structlog

logger = structlog.get_logger()

@dataclass
class AgentMetrics:
    """Metrics for a single agent."""
    agent_id: str
    success_count: int = 0
    failure_count: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    latencies_ms: List[float] = field(default_factory=list)
    last_run: datetime = None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0

    def record_success(self, latency_ms: float, tokens: int, cost: float):
        self.success_count += 1
        self.latencies_ms.append(latency_ms)
        self.total_tokens += tokens
        self.total_cost_usd += cost
        self.last_run = datetime.utcnow()
        # Keep last 100 latencies
        if len(self.latencies_ms) > 100:
            self.latencies_ms = self.latencies_ms[-100:]

    def record_failure(self, latency_ms: float):
        self.failure_count += 1
        self.latencies_ms.append(latency_ms)
        self.last_run = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }

# Global metrics store (per-container)
_metrics: Dict[str, AgentMetrics] = {}

def get_metrics(agent_id: str) -> AgentMetrics:
    if agent_id not in _metrics:
        _metrics[agent_id] = AgentMetrics(agent_id=agent_id)
    return _metrics[agent_id]
```

### 4. Store Metrics in Firebase

```python
# In src/services/firebase.py

async def store_metrics(agent_id: str, metrics: dict):
    """Store agent metrics snapshot."""
    db.collection("metrics").document(agent_id).set({
        **metrics,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }, merge=True)

async def store_metric_datapoint(agent_id: str, metric_name: str, value: float):
    """Store time-series metric datapoint."""
    db.collection("metrics_timeseries").add({
        "agent_id": agent_id,
        "metric": metric_name,
        "value": value,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })
```

### 5. Integrate into BaseAgent

```python
from src.utils.metrics import get_metrics
from src.utils.logging import log_duration, get_logger

class BaseAgent:
    def __init__(self, agent_id: str):
        ...
        self.logger = get_logger(agent_id)
        self.metrics = get_metrics(agent_id)

    async def process(self, task: dict) -> dict:
        start = time.perf_counter()
        try:
            result = await self._process_impl(task)
            latency = (time.perf_counter() - start) * 1000
            self.metrics.record_success(latency, tokens, cost)
            return result
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self.metrics.record_failure(latency)
            raise
```

## Todo List

- [ ] Add `/health` endpoint to Telegram agent
- [ ] Add `/health/detailed` with dependency checks
- [ ] Enhance logging config
- [ ] Create metrics collector
- [ ] Integrate metrics into BaseAgent
- [ ] Store metrics snapshots in Firebase
- [ ] Write tests for health endpoint

## Success Criteria

- [ ] `/health` returns in <100ms
- [ ] Logs include agent, action, latency
- [ ] Metrics visible in Firebase console
- [ ] Alerts trigger on failures

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Metrics storage costs | Firebase bills | Aggregate, don't store every call |
| Health check fails | False alarms | Add retries to dep checks |

## Security Considerations

- Don't expose internal state in health
- Rate limit health endpoints
- Sanitize error messages in logs

## Next Steps

→ Phase 4: Self-Healing & Recovery
