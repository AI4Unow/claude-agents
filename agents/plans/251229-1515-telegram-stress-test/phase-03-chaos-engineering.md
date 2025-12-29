# Phase 3: Chaos Engineering

## Context
- Parent: [plan.md](plan.md)
- Depends on: [Phase 2](phase-02-locust-scenarios.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P2 |
| Effort | 2h |
| Implementation | pending |
| Review | pending |

Implement chaos engineering tests to verify system resilience under adverse conditions.

## Key Insights

1. Webhook must handle malformed input gracefully
2. Rate limiting should kick in under burst load
3. Circuit breakers should trip and recover
4. Auth escalation attempts must be blocked

## Requirements

- [ ] Invalid payload tests (malformed JSON, missing fields)
- [ ] Overload tests (huge payloads, rapid fire)
- [ ] Security tests (auth escalation, invalid IDs)
- [ ] Circuit breaker tests (force trips, verify recovery)

## Architecture

```
ChaosTest
├── InvalidPayloadTests
│   ├── malformed_json()
│   ├── missing_required_fields()
│   ├── invalid_field_types()
│   └── empty_payload()
├── OverloadTests
│   ├── huge_payload()      # 10MB+
│   ├── rapid_fire()        # 1000 req/sec
│   └── concurrent_burst()
├── SecurityTests
│   ├── guest_admin_escalation()
│   ├── invalid_user_id()
│   └── negative_user_id()
└── CircuitBreakerTests
    ├── force_api_errors()
    └── verify_recovery()
```

## Related Code Files

| File | Purpose |
|------|---------|
| main.py:1625-1725 | handle_webhook() error handling |
| src/core/resilience.py | Circuit breaker implementation |
| src/services/firebase.py:71-85 | Rate limit functions |

## Implementation Steps

### 1. Create chaos.py
```python
# tests/stress/chaos.py
"""Chaos engineering tests for resilience verification."""

import httpx
import asyncio
from typing import List, Dict, Any
from .config import StressConfig

class ChaosRunner:
    """Executes chaos test scenarios."""

    def __init__(self, config: StressConfig = None):
        self.config = config or StressConfig()
        self.client = httpx.AsyncClient(timeout=self.config.request_timeout)

    async def run_all(self) -> Dict[str, Any]:
        """Run all chaos tests and return results."""

class InvalidPayloadTests:
    """Test handling of malformed inputs."""

    async def malformed_json(self) -> bool:
        """Send invalid JSON, expect 400."""
        payload = "not valid json {"
        response = await self.client.post(url, content=payload)
        return response.status_code in (400, 422)

    async def missing_message_field(self) -> bool:
        """Send update without message, expect graceful handling."""
        payload = {"update_id": 12345}  # No message
        ...

    async def empty_payload(self) -> bool:
        """Send empty body."""
        ...

    async def invalid_user_id_type(self) -> bool:
        """Send string user_id instead of int."""
        ...

class OverloadTests:
    """Test behavior under extreme load."""

    async def huge_payload(self, size_mb: int = 10) -> bool:
        """Send 10MB+ payload, expect rejection or timeout."""
        huge_text = "x" * (size_mb * 1024 * 1024)
        ...

    async def rapid_fire(self, rps: int = 1000, duration: int = 5) -> Dict:
        """Send 1000 requests/second for 5 seconds."""
        ...

    async def concurrent_burst(self, count: int = 500) -> Dict:
        """Send 500 simultaneous requests."""
        tasks = [self.send_request() for _ in range(count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        ...

class SecurityTests:
    """Test auth and permission boundaries."""

    async def guest_tries_admin_command(self) -> bool:
        """Guest user attempts /grant command."""
        guest_id = 1_000_001
        payload = text_message(guest_id, "/grant 123 developer")
        response = await self.send(payload)
        return "denied" in response.text.lower()

    async def invalid_user_id(self) -> bool:
        """Send negative or zero user ID."""
        ...

    async def user_id_overflow(self) -> bool:
        """Send extremely large user ID."""
        ...

class CircuitBreakerTests:
    """Test circuit breaker behavior."""

    async def verify_circuit_status(self) -> Dict:
        """Check /circuits endpoint for current status."""
        ...

    async def stress_until_trip(self, target_circuit: str) -> bool:
        """Send requests until circuit trips."""
        ...

    async def verify_recovery(self, circuit: str, wait_time: int = 60) -> bool:
        """Wait for cooldown and verify circuit closes."""
        ...
```

### 2. Integration with Locust
```python
# Add chaos tasks to locustfile.py

class ChaosUser(HttpUser):
    """Special user that injects chaos."""
    weight = 1  # 1% of load is chaos
    wait_time = between(10, 30)

    @task
    def send_malformed(self):
        """Inject malformed payload."""

    @task
    def burst_requests(self):
        """Send rapid burst."""
```

## Todo List

- [ ] Create chaos.py module
- [ ] Implement InvalidPayloadTests (4 tests)
- [ ] Implement OverloadTests (3 tests)
- [ ] Implement SecurityTests (3 tests)
- [ ] Implement CircuitBreakerTests (3 tests)
- [ ] Add ChaosUser to locustfile.py
- [ ] Test chaos scenarios individually

## Success Criteria

1. Invalid payloads return 4xx, not 5xx
2. Huge payloads rejected or timeout gracefully
3. Auth escalation blocked with clear error
4. Circuits trip under sustained errors
5. Circuits recover after cooldown

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Chaos tests crash production | High | Rate limit chaos injection |
| Circuit stuck open | Medium | Manual reset via /admin |
| False positives | Medium | Clear expected behavior docs |

## Security Considerations

- Chaos tests may trigger security alerts
- Document test IP ranges if possible
- Never test auth bypass with real credentials

## Next Steps

After Phase 3:
- Run chaos tests in isolation first
- Verify no cascading failures
- Proceed to Phase 4: Metrics & Runner
