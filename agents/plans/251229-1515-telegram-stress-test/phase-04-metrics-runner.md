# Phase 4: Metrics & Runner

## Context
- Parent: [plan.md](plan.md)
- Depends on: [Phase 3](phase-03-chaos-engineering.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P2 |
| Effort | 2h |
| Implementation | pending |
| Review | pending |

Implement custom metrics collection and CLI runner for executing stress tests with reporting.

## Key Insights

1. Locust provides built-in metrics but we need custom ones for circuits
2. CLI runner should support all test modes (load, chaos, full)
3. HTML reports needed for CI/CD integration

## Requirements

- [ ] Custom metrics for latency percentiles, circuit trips
- [ ] CLI runner with mode selection
- [ ] HTML and JSON report generation
- [ ] Integration with Locust events system

## Architecture

```
run_stress.py
├── --mode load     → Run locustfile.py
├── --mode chaos    → Run chaos.py tests
├── --mode full     → Both load + chaos
├── --profile X     → ramp_up|sustained|spike|soak
├── --users N       → Concurrent users
├── --duration T    → Test duration
└── --report FILE   → Output report path

Metrics Collection:
┌─────────────────────────────────────────┐
│              MetricsCollector           │
├─────────────────────────────────────────┤
│ • request_latencies[]                   │
│ • error_counts{}                        │
│ • circuit_trips{}                       │
│ • throughput_samples[]                  │
├─────────────────────────────────────────┤
│ percentile(p) → ms                      │
│ error_rate() → float                    │
│ to_report() → Dict                      │
└─────────────────────────────────────────┘
```

## Related Code Files

| File | Purpose |
|------|---------|
| tests/stress/locustfile.py | Load test definitions |
| tests/stress/chaos.py | Chaos test runner |

## Implementation Steps

### 1. Create metrics.py
```python
# tests/stress/metrics.py
"""Custom metrics collection for stress tests."""

import time
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Any
from collections import defaultdict

@dataclass
class MetricsCollector:
    """Collects and aggregates test metrics."""

    latencies: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    circuit_trips: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start_time: float = field(default_factory=time.time)

    def record_request(self, latency_ms: float, success: bool, error_type: str = None):
        """Record a single request result."""
        self.latencies.append(latency_ms)
        if not success and error_type:
            self.errors[error_type] += 1

    def record_circuit_trip(self, circuit_name: str):
        """Record a circuit breaker trip."""
        self.circuit_trips[circuit_name] += 1

    def percentile(self, p: int) -> float:
        """Get latency percentile (p50, p95, p99)."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * p / 100)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p50(self) -> float:
        return self.percentile(50)

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    @property
    def error_rate(self) -> float:
        """Total error rate as fraction."""
        total = len(self.latencies)
        errors = sum(self.errors.values())
        return errors / total if total > 0 else 0.0

    @property
    def throughput(self) -> float:
        """Requests per second."""
        duration = time.time() - self.start_time
        return len(self.latencies) / duration if duration > 0 else 0.0

    def to_report(self) -> Dict[str, Any]:
        """Generate report dictionary."""
        return {
            "summary": {
                "total_requests": len(self.latencies),
                "duration_seconds": time.time() - self.start_time,
                "throughput_rps": round(self.throughput, 2),
                "error_rate": round(self.error_rate * 100, 2),
            },
            "latency_ms": {
                "p50": round(self.p50, 2),
                "p95": round(self.p95, 2),
                "p99": round(self.p99, 2),
                "min": round(min(self.latencies), 2) if self.latencies else 0,
                "max": round(max(self.latencies), 2) if self.latencies else 0,
            },
            "errors": dict(self.errors),
            "circuit_trips": dict(self.circuit_trips),
        }
```

### 2. Locust Event Hooks
```python
# Add to locustfile.py

from locust import events
from .metrics import MetricsCollector

collector = MetricsCollector()

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Capture every request for custom metrics."""
    success = exception is None
    error_type = type(exception).__name__ if exception else None
    collector.record_request(response_time, success, error_type)

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate report when test ends."""
    report = collector.to_report()
    print(json.dumps(report, indent=2))
```

### 3. Create run_stress.py
```python
#!/usr/bin/env python3
# tests/run_stress.py
"""CLI runner for stress tests."""

import argparse
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

def run_load_test(args):
    """Run Locust load test."""
    cmd = [
        "locust",
        "-f", "tests/stress/locustfile.py",
        "--host", args.host,
        "--headless",
        "--users", str(args.users),
        "--spawn-rate", str(args.spawn_rate),
        "--run-time", args.duration,
    ]
    if args.report:
        cmd.extend(["--html", args.report])
    return subprocess.run(cmd)

def run_chaos_test(args):
    """Run chaos engineering tests."""
    from tests.stress.chaos import ChaosRunner
    import asyncio

    runner = ChaosRunner()
    results = asyncio.run(runner.run_all())
    print(json.dumps(results, indent=2))
    return 0 if results.get("passed") else 1

def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Stress Test Runner")
    parser.add_argument("--mode", choices=["load", "chaos", "full"], default="load")
    parser.add_argument("--host", default="https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--spawn-rate", type=int, default=10)
    parser.add_argument("--duration", default="5m")
    parser.add_argument("--profile", choices=["ramp_up", "sustained", "spike", "soak"])
    parser.add_argument("--report", help="Output HTML report path")

    args = parser.parse_args()

    if args.profile:
        # Override with profile settings
        profiles = {...}  # From locustfile.py
        profile = profiles[args.profile]
        args.users = profile["users"]
        args.duration = profile["run_time"]

    if args.mode == "load":
        return run_load_test(args)
    elif args.mode == "chaos":
        return run_chaos_test(args)
    else:  # full
        run_load_test(args)
        return run_chaos_test(args)

if __name__ == "__main__":
    sys.exit(main())
```

## Todo List

- [ ] Create metrics.py with MetricsCollector
- [ ] Add Locust event hooks to locustfile.py
- [ ] Create run_stress.py CLI runner
- [ ] Implement profile selection
- [ ] Add HTML report generation
- [ ] Add JSON report output
- [ ] Test CLI with all modes

## Success Criteria

1. `python tests/run_stress.py --mode load --users 10` works
2. Metrics show accurate p50/p95/p99
3. HTML report generated with Locust
4. JSON summary printed after tests
5. Chaos mode runs all chaos tests

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Metrics memory growth | Medium | Cap latencies list size |
| Report file permissions | Low | Use writable directory |

## Security Considerations

- Reports may contain sensitive timing data
- Don't commit reports to git

## Next Steps

After Phase 4:
- Run baseline test with 100 users
- Document typical latency ranges
- Create CI/CD integration guide
