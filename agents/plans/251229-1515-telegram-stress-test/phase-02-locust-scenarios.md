# Phase 2: Locust Scenarios

## Context
- Parent: [plan.md](plan.md)
- Depends on: [Phase 1](phase-01-core-infrastructure.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P1 |
| Effort | 3h |
| Implementation | pending |
| Review | pending |

Implement Locust user behavior classes and test scenarios covering all 22 commands with realistic weighted distributions.

## Key Insights

1. Locust uses `@task(weight)` for realistic distribution
2. Each user class simulates a tier's capabilities
3. Need 4 test profiles: ramp_up, sustained, spike, soak

## Requirements

- [ ] Create scenarios.py with message content generators
- [ ] Create locustfile.py with 4 user behavior classes
- [ ] Support all 22 commands with tier-appropriate users
- [ ] Implement 4 test profiles

## Architecture

```
GuestUser ─────┬─► /start, /help, /status, /skills, /mode, /cancel, /clear
               │   + simple text messages
               │
PowerUser ─────┼─► Guest commands + /skill, /translate, /summarize,
               │   /rewrite, /remind, /reminders, /task
               │   + complex tasks, media messages
               │
DeveloperUser ─┼─► Power commands + /traces, /trace, /circuits, /tier
               │
AdminUser ─────┴─► All commands + /grant, /revoke, /admin
```

## Related Code Files

| File | Purpose |
|------|---------|
| main.py:649-1087 | handle_command() - all 22 commands |
| main.py:1114-1250 | Media handlers |
| tests/stress/payloads.py | Payload generators (Phase 1) |

## Implementation Steps

### 1. Create scenarios.py
```python
# tests/stress/scenarios.py
"""Message content generators for realistic scenarios."""

import random

# Simple messages (greetings, questions)
SIMPLE_MESSAGES = [
    "hi", "hello", "thanks", "ok",
    "what is Python?", "who made this bot?",
    "how are you?", "help me",
]

# Complex messages (trigger orchestrator)
COMPLEX_MESSAGES = [
    "build a login system with OAuth",
    "analyze this codebase and suggest improvements",
    "create a REST API for user management",
    "review my code for security issues",
]

# Translate requests
TRANSLATE_REQUESTS = [
    "Hello world",
    "The quick brown fox",
    "Machine learning is fascinating",
]

def get_simple_message() -> str: ...
def get_complex_message() -> str: ...
def get_translate_text() -> str: ...
def get_summarize_text() -> str: ...
```

### 2. Create locustfile.py
```python
# tests/stress/locustfile.py
from locust import HttpUser, task, between, events
from .config import StressConfig
from .payloads import text_message, voice_message, callback_query
from .users import UserPool
from .scenarios import get_simple_message, get_complex_message

class GuestUser(HttpUser):
    """Simulates guest-tier behavior."""
    weight = 80  # 80% of users
    wait_time = between(1, 5)

    def on_start(self):
        self.user_id = UserPool().get_user("guest")

    @task(10)
    def send_simple_message(self):
        """Most common: greetings, questions."""

    @task(3)
    def use_help_command(self):
        """/help, /status, /skills."""

    @task(1)
    def start_command(self):
        """/start for new session."""

class PowerUser(HttpUser):
    """Simulates user-tier behavior."""
    weight = 15
    wait_time = between(2, 8)

    @task(5)
    def send_complex_task(self):
        """Orchestrated multi-skill tasks."""

    @task(3)
    def use_skill_command(self):
        """/skill <name>."""

    @task(2)
    def quick_commands(self):
        """/translate, /summarize, /rewrite."""

    @task(1)
    def send_media(self):
        """Voice, image, or document."""

class DeveloperUser(HttpUser):
    """Simulates developer-tier behavior."""
    weight = 4
    wait_time = between(5, 15)

    @task(3)
    def check_traces(self):
        """/traces, /trace <id>."""

    @task(2)
    def check_circuits(self):
        """/circuits."""

class AdminUser(HttpUser):
    """Simulates admin behavior."""
    weight = 1
    wait_time = between(10, 30)

    @task(2)
    def admin_commands(self):
        """/admin, /circuits."""

    @task(1)
    def tier_management(self):
        """/grant, /revoke (with test IDs)."""
```

### 3. Test Profiles
```python
# In locustfile.py or separate profiles.py

PROFILES = {
    "ramp_up": {
        "users": 1000,
        "spawn_rate": 10,  # 10 users/sec → 100s to full load
        "run_time": "5m",
    },
    "sustained": {
        "users": 1000,
        "spawn_rate": 50,
        "run_time": "10m",
    },
    "spike": {
        "users": 2000,
        "spawn_rate": 100,
        "run_time": "3m",
    },
    "soak": {
        "users": 200,
        "spawn_rate": 20,
        "run_time": "1h",
    },
}
```

## Todo List

- [ ] Create scenarios.py with message generators
- [ ] Implement GuestUser class
- [ ] Implement PowerUser class
- [ ] Implement DeveloperUser class
- [ ] Implement AdminUser class
- [ ] Add test profiles
- [ ] Test with `locust -f tests/stress/locustfile.py --users 10`

## Success Criteria

1. All 4 user classes instantiate without errors
2. Weighted distribution matches: 80% guest, 15% user, 4% dev, 1% admin
3. All 22 commands covered across user classes
4. Locust web UI shows correct task distribution

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wrong command/tier pairing | Medium | Map commands to tiers from main.py |
| Unrealistic message patterns | Low | Use real message examples |

## Security Considerations

- /grant and /revoke use test user IDs only
- Never grant real tiers during stress tests

## Next Steps

After Phase 2:
- Run initial load test with 10 users
- Verify all commands execute correctly
- Proceed to Phase 3: Chaos Engineering
