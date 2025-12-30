# Phase 5: Testing and Documentation

## Context

- [Comprehensive Analysis - Phase 5](../reports/codebase-review-251230-1119-comprehensive-analysis.md#phase-5-testing--documentation-week-4-5---16-hrs)
- [main.py Review - Metrics](../reports/code-reviewer-251230-1121-main-py-review.md#metrics-summary)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P2 - Medium |
| Status | pending |
| Effort | 16 hours |
| Risk | LOW (additive changes) |
| Depends On | Phases 1-4 |

## Key Insights

1. **Test coverage for new modules is ~0%** - refactored code untested
2. **22 existing test files** - good foundation to build upon
3. **Missing Firestore index documentation** - complex queries may fail
4. **Architecture docs outdated** - don't reflect new module structure
5. **No command-level unit tests** - commands only tested via integration

## Requirements

- [ ] Unit tests for all new commands (80%+ coverage)
- [ ] Integration tests for all API routes
- [ ] Document Firestore indexes required
- [ ] Update architecture docs with new structure
- [ ] Add inline documentation for complex functions

## Architecture Decisions

1. **Test Framework**: pytest with pytest-asyncio for async tests
2. **Mocking**: Use unittest.mock for Firebase, httpx for Telegram
3. **Test Organization**: Mirror source structure in tests/
4. **Coverage Tool**: pytest-cov with 80% minimum threshold

## Target Structure

```
tests/
├── conftest.py (shared fixtures)
├── mocks/
│   ├── __init__.py
│   ├── firebase.py (Firebase mock client)
│   ├── telegram.py (Telegram API mock)
│   └── state.py (StateManager mock)
├── unit/
│   ├── commands/
│   │   ├── test_user.py
│   │   ├── test_skills.py
│   │   ├── test_admin.py
│   │   └── test_router.py
│   ├── services/
│   │   ├── test_users.py
│   │   ├── test_tiers.py
│   │   ├── test_reports.py
│   │   └── test_circuit.py
│   └── validators/
│       └── test_input.py
├── integration/
│   ├── test_telegram_webhook.py
│   ├── test_skill_api.py
│   └── test_health.py
└── e2e/
    └── test_telegram_flow.py
```

## Related Code Files

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Shared test fixtures |
| `agents/commands/*.py` | Commands to test |
| `agents/api/routes/*.py` | Routes to test |
| `agents/src/services/firebase/*.py` | Services to test |
| `agents/validators/input.py` | Validators to test |

## Implementation Steps

### 1. Create Test Fixtures (2h)

Create `tests/conftest.py`:

```python
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_user():
    """Sample Telegram user dict."""
    return {
        "id": 123456789,
        "first_name": "Test",
        "last_name": "User",
        "username": "testuser"
    }

@pytest.fixture
def mock_admin_user():
    """Sample admin user dict."""
    return {
        "id": 999999999,  # Matches ADMIN_TELEGRAM_ID
        "first_name": "Admin",
        "username": "admin"
    }

@pytest.fixture
def mock_state_manager():
    """Mock StateManager for tests."""
    mock = MagicMock()
    mock.get_user_tier_cached = AsyncMock(return_value="user")
    mock.get_session = AsyncMock(return_value={"mode": "auto"})
    mock.set_session = AsyncMock()
    return mock

@pytest.fixture
def mock_firebase_db():
    """Mock Firestore client."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"tier": "user"}
    mock_collection.document.return_value.get.return_value = mock_doc
    mock_db.collection.return_value = mock_collection
    return mock_db

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "999999999")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
```

### 2. Create Mock Modules (2h)

Create `tests/mocks/firebase.py`:

```python
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, Optional

class MockFirestoreDoc:
    def __init__(self, data: Optional[Dict] = None):
        self.exists = data is not None
        self._data = data or {}

    def to_dict(self) -> Dict:
        return self._data

class MockFirestoreClient:
    def __init__(self):
        self._collections: Dict[str, Dict[str, Dict]] = {}

    def collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = {}
        return MockCollection(self._collections[name])

class MockCollection:
    def __init__(self, data: Dict):
        self._data = data

    def document(self, doc_id: str):
        return MockDocument(self._data, doc_id)

    def where(self, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n: int):
        return self

    def stream(self):
        for doc_id, data in self._data.items():
            yield MockFirestoreDoc({"id": doc_id, **data})

class MockDocument:
    def __init__(self, collection_data: Dict, doc_id: str):
        self._collection = collection_data
        self._id = doc_id

    def get(self):
        data = self._collection.get(self._id)
        return MockFirestoreDoc(data)

    def set(self, data: Dict, merge: bool = False):
        if merge and self._id in self._collection:
            self._collection[self._id].update(data)
        else:
            self._collection[self._id] = data

    def delete(self):
        self._collection.pop(self._id, None)
```

### 3. Command Unit Tests (4h)

Create `tests/unit/commands/test_user.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock

from commands.user import start_command, help_command, status_command

@pytest.mark.asyncio
async def test_start_command(mock_user):
    """Test /start returns welcome message."""
    result = await start_command("", mock_user, 12345)

    assert "Hello Test" in result
    assert "AI4U.now Bot" in result
    assert "/help" in result

@pytest.mark.asyncio
async def test_help_command_guest(mock_user, mock_state_manager):
    """Test /help for guest tier."""
    mock_state_manager.get_user_tier_cached.return_value = "guest"

    with patch("commands.user.get_state_manager", return_value=mock_state_manager):
        result = await help_command("", mock_user, 12345)

    assert "Available commands" in result
    assert "/start" in result
    assert "/admin" not in result  # Admin commands hidden

@pytest.mark.asyncio
async def test_help_command_admin(mock_admin_user, mock_state_manager):
    """Test /help for admin tier shows all commands."""
    mock_state_manager.get_user_tier_cached.return_value = "admin"

    with patch("commands.user.get_state_manager", return_value=mock_state_manager):
        result = await help_command("", mock_admin_user, 12345)

    assert "/grant" in result
    assert "/revoke" in result

@pytest.mark.asyncio
async def test_status_command(mock_user, mock_state_manager):
    """Test /status shows current status."""
    with patch("commands.user.get_state_manager", return_value=mock_state_manager):
        with patch("commands.user.get_circuit_status", return_value={"claude": "closed"}):
            result = await status_command("", mock_user, 12345)

    assert "Status" in result
    assert "user" in result  # tier
    assert "auto" in result  # mode
```

Create `tests/unit/commands/test_admin.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock

from commands.admin import grant_command, revoke_command

@pytest.mark.asyncio
async def test_grant_command_success(mock_admin_user):
    """Test /grant successfully grants tier."""
    with patch("commands.admin.set_user_tier", new=AsyncMock(return_value=True)):
        with patch("commands.admin.get_state_manager") as mock_state:
            mock_state.return_value.invalidate_user_tier = AsyncMock()

            result = await grant_command("123456 developer", mock_admin_user, 12345)

    assert "Granted developer tier" in result

@pytest.mark.asyncio
async def test_grant_command_invalid_tier(mock_admin_user):
    """Test /grant with invalid tier."""
    result = await grant_command("123456 superadmin", mock_admin_user, 12345)

    assert "Invalid tier" in result

@pytest.mark.asyncio
async def test_grant_command_invalid_user_id(mock_admin_user):
    """Test /grant with non-numeric user ID."""
    result = await grant_command("notanumber developer", mock_admin_user, 12345)

    assert "Invalid user ID" in result
```

### 4. Validator Unit Tests (1h)

Create `tests/unit/validators/test_input.py`:

```python
import pytest
from validators.input import InputValidator

def test_skill_name_valid():
    """Valid skill names pass validation."""
    result = InputValidator.skill_name("planning")
    assert result.valid
    assert result.value == "planning"

def test_skill_name_with_hyphens():
    """Skill names with hyphens are valid."""
    result = InputValidator.skill_name("ui-ux-pro-max")
    assert result.valid

def test_skill_name_too_long():
    """Skill names over 50 chars fail."""
    long_name = "a" * 51
    result = InputValidator.skill_name(long_name)
    assert not result.valid
    assert "1-50 chars" in result.error

def test_skill_name_invalid_chars():
    """Skill names with uppercase/special chars fail."""
    result = InputValidator.skill_name("Planning!")
    assert not result.valid
    assert "lowercase" in result.error

def test_text_input_valid():
    """Normal text passes validation."""
    result = InputValidator.text_input("Hello, how are you?")
    assert result.valid

def test_text_input_strips_control_chars():
    """Control characters are stripped."""
    result = InputValidator.text_input("Hello\x00World")
    assert result.valid
    assert result.value == "HelloWorld"

def test_text_input_too_long():
    """Text over max_length fails."""
    long_text = "a" * 5000
    result = InputValidator.text_input(long_text, max_length=4000)
    assert not result.valid

def test_faq_pattern_valid():
    """Valid FAQ patterns pass."""
    result = InputValidator.faq_pattern("how to deploy")
    assert result.valid
    assert result.value == "how to deploy"

def test_faq_pattern_empty():
    """Empty patterns fail."""
    result = InputValidator.faq_pattern("   ")
    assert not result.valid
```

### 5. Service Unit Tests (3h)

Create `tests/unit/services/test_circuit.py`:

```python
import pytest
from unittest.mock import patch, MagicMock

from src.services.firebase._circuit import with_firebase_circuit, CIRCUIT_OPEN

@pytest.mark.asyncio
async def test_circuit_open_returns_default():
    """When circuit open, return open_return value."""
    @with_firebase_circuit(open_return=None)
    async def test_func():
        return "success"

    with patch("src.services.firebase._circuit.firebase_circuit") as mock_circuit:
        mock_circuit.state = "OPEN"

        result = await test_func()

    assert result is None

@pytest.mark.asyncio
async def test_circuit_open_raises():
    """When circuit open with raise_on_open, raise error."""
    @with_firebase_circuit(raise_on_open=True)
    async def test_func():
        return "success"

    with patch("src.services.firebase._circuit.firebase_circuit") as mock_circuit:
        mock_circuit.state = "OPEN"

        with pytest.raises(Exception):  # CircuitOpenError
            await test_func()

@pytest.mark.asyncio
async def test_circuit_closed_executes():
    """When circuit closed, execute function normally."""
    @with_firebase_circuit(open_return=None)
    async def test_func():
        return "success"

    with patch("src.services.firebase._circuit.firebase_circuit") as mock_circuit:
        mock_circuit.state = "CLOSED"
        mock_circuit.record_success = MagicMock()

        result = await test_func()

    assert result == "success"
    mock_circuit.record_success.assert_called_once()
```

### 6. Integration Tests (2h)

Create `tests/integration/test_telegram_webhook.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from api.app import web_app

client = TestClient(web_app)

def test_health_check():
    """Health endpoint returns OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_telegram_webhook_message(mock_user):
    """Telegram webhook processes message."""
    update = {
        "update_id": 123,
        "message": {
            "message_id": 1,
            "from": mock_user,
            "chat": {"id": 12345},
            "text": "/start"
        }
    }

    with patch("api.routes.telegram.command_router") as mock_router:
        mock_router.handle = AsyncMock(return_value="Welcome!")

        response = client.post("/webhook/telegram", json=update)

    assert response.status_code == 200
    assert response.json()["ok"] is True

def test_telegram_webhook_rate_limited():
    """Rate limiting works on webhook."""
    update = {"update_id": 123, "message": {"text": "test"}}

    # Make many requests
    responses = []
    for _ in range(35):
        responses.append(client.post("/webhook/telegram", json=update))

    # Some should be rate limited
    rate_limited = [r for r in responses if r.status_code == 429]
    assert len(rate_limited) > 0
```

### 7. Document Firestore Indexes (1h)

Create `docs/firestore-indexes.md`:

```markdown
# Firestore Indexes

Required composite indexes for complex queries.

## task_queue

| Fields | Order | Purpose |
|--------|-------|---------|
| status ASC, created_at ASC | COLLECTION | Get pending tasks in order |
| user_id ASC, status ASC, created_at DESC | COLLECTION | User's tasks by status |

## reports

| Fields | Order | Purpose |
|--------|-------|---------|
| user_id ASC, createdAt DESC | COLLECTION | User's reports newest first |

## entities

| Fields | Order | Purpose |
|--------|-------|---------|
| type ASC, key ASC, valid_from DESC | COLLECTION | Temporal entity lookup |
| type ASC, key ASC, valid_until ASC | COLLECTION | Current entity lookup |

## reminders

| Fields | Order | Purpose |
|--------|-------|---------|
| user_id ASC, due_at ASC | COLLECTION | User's upcoming reminders |
| due_at ASC, status ASC | COLLECTION | Due reminders to process |

## tasks

| Fields | Order | Purpose |
|--------|-------|---------|
| type ASC, status ASC, priority DESC, createdAt ASC | COLLECTION | Prioritized task queue |

## Deploy Indexes

```bash
firebase deploy --only firestore:indexes
```

Or create via Firebase Console: Database > Indexes > Add Index
```

### 8. Update Architecture Docs (1h)

Update `docs/system-architecture.md` with new module structure:

```markdown
## Module Structure (Post-Refactor)

### API Layer
- `api/app.py` - FastAPI app factory
- `api/dependencies.py` - Auth, rate limiting
- `api/routes/` - Endpoint handlers

### Command Layer
- `commands/base.py` - CommandRouter pattern
- `commands/router.py` - Global router instance
- `commands/*.py` - Domain-specific commands

### Service Layer
- `src/services/firebase/` - Domain services
  - `_client.py` - Shared initialization
  - `_circuit.py` - Circuit breaker decorator
  - `users.py`, `tiers.py`, etc.

### Core Layer
- `src/core/cache.py` - CacheManager
- `src/core/session_state.py` - Session management
- `src/core/resilience.py` - Circuit breakers
```

## Todo List

- [ ] Create tests/conftest.py with fixtures
- [ ] Create tests/mocks/ with Firebase/Telegram mocks
- [ ] Write tests/unit/commands/test_user.py
- [ ] Write tests/unit/commands/test_skills.py
- [ ] Write tests/unit/commands/test_admin.py
- [ ] Write tests/unit/commands/test_router.py
- [ ] Write tests/unit/validators/test_input.py
- [ ] Write tests/unit/services/test_circuit.py
- [ ] Write tests/unit/services/test_tiers.py
- [ ] Write tests/integration/test_telegram_webhook.py
- [ ] Write tests/integration/test_skill_api.py
- [ ] Create docs/firestore-indexes.md
- [ ] Update docs/system-architecture.md
- [ ] Run coverage report, verify 80%+
- [ ] Fix any coverage gaps

## Success Criteria

- [ ] 80%+ test coverage on new modules
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Firestore indexes documented
- [ ] Architecture docs reflect new structure
- [ ] CI/CD runs tests on PR

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Flaky async tests | MEDIUM | MEDIUM | Use proper fixtures |
| Mock doesn't match real | HIGH | MEDIUM | Integration tests catch |
| Missing edge cases | MEDIUM | MEDIUM | Property-based testing |

## Security Considerations

- Tests should not use real credentials
- Mock data should not contain PII
- CI/CD should not expose secrets in logs

## Next Steps

After Phase 5 completion:
1. Verify all tests pass in CI
2. Generate coverage report
3. Plan ongoing maintenance testing
4. Consider property-based testing for validators
