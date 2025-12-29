# Brainstorm: Telegram Bot Comprehensive Stress Test

**Date:** 2025-12-29
**Goal:** Test all bot capabilities at 1000+ concurrent load via direct webhook testing

## Problem Statement

Need comprehensive stress test covering:
1. **Load Testing** - 1000+ concurrent requests
2. **Feature Coverage** - All 22 commands + media handlers
3. **Chaos/Resilience** - Circuit breakers, error recovery, edge cases

## Constraints Identified

| Constraint | Impact |
|------------|--------|
| Can't spoof real Telegram users | Use synthetic user IDs via direct webhook |
| Telegram rate limits (30 msg/sec) | Test our rate limiting, not Telegram's |
| Production bot testing | Need graceful handling of test traffic |

## Bot Capabilities to Test

### Commands (22 total)
| Tier | Commands |
|------|----------|
| Guest | `/start`, `/help`, `/status`, `/skills`, `/mode`, `/cancel`, `/clear` |
| User | `/skill`, `/translate`, `/summarize`, `/rewrite`, `/remind`, `/reminders`, `/task` |
| Developer | `/traces`, `/trace`, `/circuits`, `/tier` |
| Admin | `/grant`, `/revoke`, `/admin` |

### Message Types
- Text messages (simple/complex routing)
- Voice messages (transcription)
- Images (vision analysis)
- Documents (PDF, DOCX, etc.)

### Callbacks
- Category selection
- Skill selection
- Improvement approve/reject

## Proposed Solution: Locust-Based Stress Test

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   STRESS TEST HARNESS                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ Load Runner  │   │ Chaos Engine │   │ Metrics      │ │
│  │ (Locust)     │   │              │   │ Collector    │ │
│  │              │   │ • Timeouts   │   │              │ │
│  │ • 1000 users │   │ • Errors     │   │ • Latency    │ │
│  │ • Ramp up    │   │ • Bad data   │   │ • Errors     │ │
│  │ • Scenarios  │   │ • Overload   │   │ • Throughput │ │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘ │
│         │                  │                  │          │
│         └────────────┬─────┴──────────────────┘          │
│                      ▼                                   │
│         ┌────────────────────────┐                       │
│         │   Webhook Simulator    │                       │
│         │                        │                       │
│         │ • Craft Telegram JSON  │                       │
│         │ • Synthetic user IDs   │                       │
│         │ • All message types    │                       │
│         └───────────┬────────────┘                       │
│                     │                                    │
└─────────────────────┼────────────────────────────────────┘
                      ▼
         ┌────────────────────────┐
         │  Production Webhook    │
         │  /webhook/telegram     │
         └────────────────────────┘
```

### Test Scenarios

#### 1. Load Test Scenarios

| Scenario | Users | Duration | Pattern |
|----------|-------|----------|---------|
| Ramp Up | 0→1000 | 5 min | Linear increase |
| Sustained | 1000 | 10 min | Constant load |
| Spike | 500→2000→500 | 3 min | Burst traffic |
| Soak | 200 | 1 hour | Long-running stability |

#### 2. User Journey Scenarios

```python
class TelegramUserBehavior:
    """Simulates realistic user behavior patterns."""

    @task(10)  # Most common
    def send_simple_message(self):
        """Quick questions, greetings."""

    @task(5)
    def send_complex_task(self):
        """Multi-skill orchestration."""

    @task(3)
    def use_command(self):
        """Random command from user's tier."""

    @task(1)
    def send_media(self):
        """Voice, image, or document."""
```

#### 3. Chaos Scenarios

| Scenario | Purpose | Implementation |
|----------|---------|----------------|
| Invalid JSON | Test error handling | Malformed payloads |
| Missing fields | Robustness | Partial message data |
| Huge payloads | Memory limits | 10MB+ message bodies |
| Rapid fire | Rate limiting | 1000 req/sec bursts |
| Slow clients | Timeout handling | Delayed connections |
| Auth attacks | Security | Invalid user IDs, escalation attempts |

### Implementation Components

#### 1. Webhook Payload Generator

```python
def generate_telegram_update(
    user_id: int,
    message_type: str = "text",
    content: str = "Hello",
    chat_id: int = None,
) -> dict:
    """Generate valid Telegram webhook payload."""
    return {
        "update_id": random.randint(100000, 999999),
        "message": {
            "message_id": random.randint(1, 99999),
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": f"User{user_id}",
            },
            "chat": {"id": chat_id or user_id, "type": "private"},
            "date": int(time.time()),
            "text": content,
        }
    }
```

#### 2. Tier-Based User Pool

```python
USER_POOLS = {
    "guest": range(1000000, 1001000),      # 1000 guests
    "user": range(2000000, 2000100),       # 100 users
    "developer": range(3000000, 3000010),  # 10 developers
    "admin": [999999999],                  # 1 admin
}
```

#### 3. Metrics Collection

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| p50 latency | <500ms | >1s |
| p99 latency | <2s | >5s |
| Error rate | <1% | >5% |
| Throughput | >100 rps | <50 rps |
| Circuit trips | 0 | >3 |

### File Structure

```
tests/
├── stress/
│   ├── __init__.py
│   ├── locustfile.py          # Main load test definitions
│   ├── payloads.py            # Telegram payload generators
│   ├── scenarios.py           # User behavior patterns
│   ├── chaos.py               # Chaos engineering tests
│   ├── metrics.py             # Custom metrics collection
│   └── config.py              # Test configuration
├── run_stress.py              # CLI runner with reports
└── requirements-stress.txt    # locust, httpx, etc.
```

### Running Tests

```bash
# Basic load test
locust -f tests/stress/locustfile.py --host=https://your-modal-url.modal.run

# Headless with params
locust -f tests/stress/locustfile.py \
  --headless \
  --users 1000 \
  --spawn-rate 50 \
  --run-time 10m \
  --html report.html

# Chaos tests
python tests/run_stress.py --mode chaos --duration 5m

# Full stress suite
python tests/run_stress.py --mode full --users 1000 --duration 30m
```

## Alternatives Considered

### Option A: Custom HTTP Client (Not Recommended)
- Pros: Full control, no dependencies
- Cons: Reinventing wheel, less features

### Option B: k6 Load Testing
- Pros: Fast, good for pure HTTP load
- Cons: JavaScript-based, less Python integration

### Option C: Locust (Recommended)
- Pros: Python-native, great UI, realistic user simulation
- Cons: Slightly higher overhead than k6

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Production impact | Rate limit test traffic, use test user ID ranges |
| API costs | Set max concurrent to limit Claude API calls |
| False positives | Distinguish test errors from real bugs |
| Resource exhaustion | Monitor Modal container metrics |

## Success Criteria

1. **Load**: Handle 1000 concurrent without errors
2. **Latency**: p99 < 5s under full load
3. **Recovery**: Circuits trip and recover correctly
4. **Coverage**: All 22 commands tested
5. **Stability**: No memory leaks in 1-hour soak test

## Implementation Effort

| Component | Estimate |
|-----------|----------|
| Payload generators | 1-2 hours |
| Locust scenarios | 2-3 hours |
| Chaos tests | 2-3 hours |
| Metrics/reporting | 1-2 hours |
| Documentation | 1 hour |
| **Total** | **7-11 hours** |

## Next Steps

1. Create `tests/stress/` directory structure
2. Implement payload generators for all message types
3. Build Locust scenarios matching user journeys
4. Add chaos engineering tests
5. Create CLI runner with HTML reports
6. Run initial baseline test
7. Document findings and optimize

## Unresolved Questions

1. Should we exclude synthetic test users from Firebase tier storage?
2. Need webhook secret bypass for direct testing?
3. How to handle outbound Telegram API calls (mock or allow)?
