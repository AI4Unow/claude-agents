# Phase 1: Core Infrastructure

## Context
- Parent: [plan.md](plan.md)
- Brainstorm: [brainstorm-251229-1515-telegram-stress-test.md](../reports/brainstorm-251229-1515-telegram-stress-test.md)
- Existing mocks: tests/mocks/mock_telegram.py

## Overview
| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P1 |
| Effort | 2h |
| Implementation | pending |
| Review | pending |

Create foundational stress test infrastructure: configuration, payload generators, and user pool management.

## Key Insights

1. Existing `tests/mocks/mock_telegram.py` has `create_update()` and `create_callback_query()` - reuse patterns
2. Need synthetic user ID ranges to avoid conflicts with real users
3. Webhook URL configurable for local dev vs production testing

## Requirements

- [x] Create tests/stress/ directory structure
- [ ] Implement config.py with all test parameters
- [ ] Implement payloads.py for all message types
- [ ] Implement users.py for tier-based user pools
- [ ] Add requirements-stress.txt

## Architecture

```python
# User pool ranges (non-overlapping with real users)
USER_POOLS = {
    "guest": range(1_000_000, 1_001_000),      # 1000 guests
    "user": range(2_000_000, 2_000_100),       # 100 users
    "developer": range(3_000_000, 3_000_010),  # 10 developers
    "admin": [999999999],                       # 1 admin (matches ADMIN_TELEGRAM_ID)
}
```

## Related Code Files

| File | Purpose |
|------|---------|
| tests/mocks/mock_telegram.py | Existing payload patterns |
| main.py | Webhook handler to test |
| src/services/firebase.py | Rate limit values (5/20/50/1000) |

## Implementation Steps

### 1. Create config.py
```python
# tests/stress/config.py
from dataclasses import dataclass

@dataclass
class StressConfig:
    webhook_url: str = "https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/webhook/telegram"
    webhook_secret: str = ""  # Empty for testing

    # User pools
    guest_range: range = range(1_000_000, 1_001_000)
    user_range: range = range(2_000_000, 2_000_100)
    developer_range: range = range(3_000_000, 3_000_010)
    admin_id: int = 999999999

    # Thresholds
    p50_target_ms: int = 500
    p99_target_ms: int = 5000
    error_rate_threshold: float = 0.05

    # Timeouts
    request_timeout: float = 30.0
    connect_timeout: float = 5.0
```

### 2. Create payloads.py
```python
# tests/stress/payloads.py
import random
import time
from typing import Dict, Any, Optional

def text_message(user_id: int, text: str, chat_id: int = None) -> Dict[str, Any]:
    """Generate text message payload."""

def voice_message(user_id: int, duration: int = 10) -> Dict[str, Any]:
    """Generate voice message payload with file_id."""

def image_message(user_id: int, caption: str = None) -> Dict[str, Any]:
    """Generate photo message payload."""

def document_message(user_id: int, filename: str, mime_type: str) -> Dict[str, Any]:
    """Generate document message payload."""

def callback_query(user_id: int, data: str, chat_id: int = None) -> Dict[str, Any]:
    """Generate callback query payload."""
```

### 3. Create users.py
```python
# tests/stress/users.py
import random
from typing import Literal

Tier = Literal["guest", "user", "developer", "admin"]

class UserPool:
    """Manages synthetic user allocation by tier."""

    def get_user(self, tier: Tier) -> int:
        """Get random user ID from tier pool."""

    def get_weighted_user(self) -> tuple[int, Tier]:
        """Get user with realistic tier distribution."""
        # 80% guest, 15% user, 4% developer, 1% admin
```

### 4. Create requirements-stress.txt
```
locust>=2.20.0
httpx>=0.25.0
rich>=13.0.0
```

## Todo List

- [ ] Create tests/stress/__init__.py
- [ ] Implement config.py with dataclass
- [ ] Implement payloads.py with 5 generators
- [ ] Implement users.py with UserPool class
- [ ] Create requirements-stress.txt
- [ ] Test imports work correctly

## Success Criteria

1. All payload generators produce valid Telegram JSON
2. User pool returns IDs within correct ranges
3. Config loads without errors
4. No import errors when running `python -c "from tests.stress import *"`

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Payload format changes | Medium | Match current main.py expectations |
| Admin ID conflict | High | Use env var ADMIN_TELEGRAM_ID |

## Security Considerations

- Never log full payloads (may contain test data)
- Admin operations use actual admin ID - be careful in production tests

## Next Steps

After Phase 1:
- Proceed to Phase 2: Locust Scenarios
- Verify payloads work with local webhook test
