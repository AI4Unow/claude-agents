# Phase 1: Security Fixes

## Context

- [Comprehensive Analysis](../reports/codebase-review-251230-1119-comprehensive-analysis.md)
- [main.py Review - H8](../reports/code-reviewer-251230-1121-main-py-review.md#h8-missing-webhook-signature-verification-for-github)
- [firebase.py Review - #5](../reports/code-reviewer-251230-1121-firebase-service-review.md#5-global-state-race-condition)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P1 - Critical |
| Status | pending |
| Effort | 8 hours |
| Risk | LOW (isolated changes) |

## Key Insights

1. **GitHub webhook accepts unverified payloads** - anyone can trigger unauthorized actions
2. **No input validation on user data** - skill names, FAQ patterns, user inputs not sanitized
3. **Global Firebase state not thread-safe** - double initialization crashes possible
4. **Admin ID fetched 10+ times without centralization** - security misconfiguration risk

## Requirements

- [ ] GitHub webhook signature verification using HMAC-SHA256
- [ ] InputValidator class for skill names, text inputs, FAQ patterns
- [ ] Thread-safe Firebase initialization with lock or lru_cache
- [ ] Centralized admin ID validation with caching

## Architecture Decisions

1. **GitHub Webhook**: Use same pattern as Telegram webhook (HMAC verification)
2. **Input Validation**: Create validators module with InputValidator class
3. **Firebase Init**: Use `@lru_cache(maxsize=1)` for singleton pattern
4. **Admin Check**: Create `config/env.py` with cached `is_admin()` function

## Related Code Files

| File | Lines | Issue |
|------|-------|-------|
| `agents/main.py` | 286-313 | GitHub webhook no verification |
| `agents/main.py` | 743-1109 | Admin ID repeated 10+ times |
| `agents/main.py` | 832, 1162, 1346 | User input used without validation |
| `agents/src/services/firebase.py` | 39-40 | Global state race condition |
| `agents/src/core/state.py` | 420-447 | Rate limiting race condition |

## Implementation Steps

### 1. Add GitHub Webhook Secret (1h)

```bash
modal secret create github-credentials GITHUB_WEBHOOK_SECRET=your-secret-here
```

Create `agents/api/dependencies.py`:

```python
async def verify_github_webhook(request: Request) -> dict:
    """Verify GitHub webhook signature (HMAC-SHA256)."""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(500, "Webhook secret not configured")

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        raise HTTPException(401, "Invalid signature format")

    body = await request.body()
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, signature_header[7:]):
        raise HTTPException(401, "Invalid signature")

    return json.loads(body)
```

Update `main.py` GitHub webhook endpoint to use `Depends(verify_github_webhook)`.

### 2. Create InputValidator (2h)

Create `agents/validators/input.py`:

```python
class InputValidator:
    VALID_SKILL_NAME = re.compile(r'^[a-z0-9-]{1,50}$')

    @staticmethod
    def skill_name(name: str) -> ValidationResult:
        if not name or len(name) > 50:
            return ValidationResult(False, error="Skill name must be 1-50 chars")
        if not InputValidator.VALID_SKILL_NAME.match(name):
            return ValidationResult(False, error="Lowercase alphanumeric with hyphens only")
        return ValidationResult(True, value=name)

    @staticmethod
    def text_input(text: str, max_length: int = 4000) -> ValidationResult:
        if not text or len(text) > max_length:
            return ValidationResult(False, error=f"Text must be 1-{max_length} chars")
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        return ValidationResult(True, value=cleaned)

    @staticmethod
    def faq_pattern(pattern: str) -> ValidationResult:
        if len(pattern) > 200:
            return ValidationResult(False, error="Pattern too long (max 200)")
        if not pattern.strip():
            return ValidationResult(False, error="Pattern cannot be empty")
        return ValidationResult(True, value=pattern.strip())
```

### 3. Fix Firebase Race Condition (1h)

Update `agents/src/services/firebase.py`:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def _init_firebase_once():
    """Initialize Firebase once (thread-safe via lru_cache)."""
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not cred_json:
        raise ValueError("FIREBASE_CREDENTIALS_JSON not set")
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    app = firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("firebase_initialized", project=cred_dict.get("project_id"))
    return db

def get_db():
    """Get Firestore client (singleton)."""
    return _init_firebase_once()
```

### 4. Centralize Admin Validation (2h)

Create `agents/config/env.py`:

```python
from functools import lru_cache

class ConfigurationError(Exception):
    pass

@lru_cache(maxsize=1)
def get_admin_telegram_id() -> int:
    admin_str = os.environ.get("ADMIN_TELEGRAM_ID")
    if not admin_str:
        raise ConfigurationError("ADMIN_TELEGRAM_ID not set")
    try:
        return int(admin_str)
    except ValueError:
        raise ConfigurationError(f"Invalid ADMIN_TELEGRAM_ID: {admin_str}")

def is_admin(user_id: int) -> bool:
    try:
        return user_id == get_admin_telegram_id()
    except ConfigurationError:
        return False

def require_admin(user_id: int) -> None:
    if not is_admin(user_id):
        raise PermissionError("Admin access required")
```

Replace all admin checks in `main.py` with `is_admin()` or `require_admin()`.

### 5. Fix Rate Limit Race Condition (1h)

Update `agents/src/core/state.py`:

```python
import threading

_rate_limit_lock = threading.Lock()

def check_rate_limit(self, user_id: int, tier: str) -> tuple:
    with _rate_limit_lock:
        # Clean old entries
        self._rate_counters[user_id] = [
            ts for ts in self._rate_counters[user_id]
            if ts > window_start
        ]
        current_count = len(self._rate_counters[user_id])

        if current_count >= limit:
            oldest = min(self._rate_counters[user_id]) if self._rate_counters[user_id] else now
            reset_in = int(oldest + 60 - now)
            return False, max(1, reset_in)

        self._rate_counters[user_id].append(now)
        return True, 0
```

### 6. Testing and Validation (1h)

- Test GitHub webhook with valid/invalid signatures
- Test InputValidator with edge cases
- Verify Firebase initializes correctly under concurrent load
- Test admin commands with centralized validation
- Verify rate limiting works under concurrent requests

## Todo List

- [ ] Create Modal secret for GITHUB_WEBHOOK_SECRET
- [ ] Create `agents/api/dependencies.py` with webhook verification
- [ ] Update GitHub webhook endpoint to use dependency
- [ ] Create `agents/validators/input.py` with InputValidator
- [ ] Integrate InputValidator in skill execution paths
- [ ] Update Firebase init with lru_cache singleton
- [ ] Create `agents/config/env.py` with admin helpers
- [ ] Replace 10+ admin checks in main.py
- [ ] Add rate limit lock to state.py
- [ ] Write unit tests for all security changes
- [ ] Deploy and verify in staging

## Success Criteria

- [ ] GitHub webhook rejects requests without valid signature
- [ ] Invalid skill names return user-friendly error
- [ ] Firebase never double-initializes under concurrent requests
- [ ] Admin commands use single is_admin() function
- [ ] Rate limiting works correctly under concurrent load
- [ ] All existing tests pass

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Webhook breaks integrations | HIGH | LOW | Test in staging first |
| Input validation too strict | MEDIUM | LOW | Start lenient, tighten later |
| Firebase init change affects startup | MEDIUM | LOW | Test cold start scenarios |

## Security Considerations

- GitHub webhook secret must be stored securely in Modal secrets
- Never log webhook secrets or signatures
- Use timing-safe comparison for signature verification
- Validate env vars at startup, fail fast if missing
- Admin ID validation should default to "deny" on error

## Next Steps

After Phase 1 completion:
1. Verify all security tests pass
2. Deploy to staging for integration testing
3. Begin [Phase 2: Extract Routes](./phase-02-extract-routes.md)
