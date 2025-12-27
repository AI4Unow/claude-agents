# Phase 7: Testing & Deployment

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 6 - Data & Content Agents](./phase-06-data-content-agents.md)

## Overview

**Priority:** P1 - Critical
**Status:** Pending
**Effort:** 3h

Complete testing suite, monitoring setup, and production deployment.

## Requirements

### Testing
- Unit tests for all services
- Integration tests for agent flows
- End-to-end tests for Telegram → Agent → Telegram flow
- Load testing for concurrent requests

### Deployment
- Production Modal deployment
- Monitoring and alerting
- Cost tracking
- Rollback procedures

---

## Part A: Testing

### Test Structure

```
agents/tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── unit/
│   ├── test_firebase.py
│   ├── test_qdrant.py
│   ├── test_embeddings.py
│   └── test_anthropic.py
├── integration/
│   ├── test_telegram_agent.py
│   ├── test_github_agent.py
│   ├── test_data_agent.py
│   └── test_content_agent.py
└── e2e/
    └── test_full_flow.py
```

### Create tests/conftest.py

```python
import pytest
import os
from unittest.mock import MagicMock, AsyncMock

# Set test environment
os.environ["TESTING"] = "true"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["FIREBASE_CREDENTIALS"] = '{"type":"service_account","project_id":"test"}'
os.environ["OPENAI_API_KEY"] = "test-key"

@pytest.fixture
def mock_firebase():
    """Mock Firebase client."""
    mock = MagicMock()
    mock.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {}
    mock.collection.return_value.document.return_value.set = MagicMock()
    mock.collection.return_value.add = MagicMock(return_value=(None, MagicMock(id="test-id")))
    return mock

@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client."""
    mock = MagicMock()
    mock.search.return_value = []
    mock.upsert = MagicMock()
    return mock

@pytest.fixture
def mock_claude():
    """Mock Claude API."""
    async def mock_response(*args, **kwargs):
        return "This is a test response from Claude."
    return mock_response

@pytest.fixture
def sample_telegram_update():
    """Sample Telegram webhook update."""
    return {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {"id": 123, "first_name": "Test"},
            "chat": {"id": 123, "type": "private"},
            "text": "Hello, AI assistant!"
        }
    }

@pytest.fixture
def sample_github_task():
    """Sample GitHub task."""
    return {
        "id": "task123",
        "type": "github",
        "payload": {
            "action": "repo_stats",
            "repo": "owner/repo",
            "user_id": "user123"
        }
    }
```

### Create tests/unit/test_firebase.py

```python
import pytest
from unittest.mock import patch, MagicMock

class TestFirebaseService:
    @patch('src.services.firebase.get_db')
    def test_create_task(self, mock_get_db):
        from src.services.firebase import create_task
        import asyncio

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.collection.return_value.add.return_value = (None, MagicMock(id="new-task-id"))

        task_id = asyncio.run(create_task(
            task_type="github",
            payload={"action": "test"},
            created_by="test-agent"
        ))

        assert task_id == "new-task-id"
        mock_db.collection.assert_called_with("tasks")

    @patch('src.services.firebase.get_db')
    def test_get_user(self, mock_get_db):
        from src.services.firebase import get_user
        import asyncio

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"tier": "free"}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        user = asyncio.run(get_user("user123"))

        assert user["tier"] == "free"

    @patch('src.services.firebase.get_db')
    def test_get_user_not_found(self, mock_get_db):
        from src.services.firebase import get_user
        import asyncio

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        user = asyncio.run(get_user("nonexistent"))

        assert user is None
```

### Create tests/integration/test_telegram_agent.py

```python
import pytest
from unittest.mock import patch, AsyncMock

class TestTelegramChatAgent:
    @pytest.mark.asyncio
    @patch('src.services.firebase.create_or_update_user', new_callable=AsyncMock)
    @patch('src.agents.telegram_chat.TelegramChatAgent.send_message', new_callable=AsyncMock)
    async def test_handle_start_command(self, mock_send, mock_create_user):
        from src.agents.telegram_chat import handle_telegram_update

        update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "text": "/start"
            }
        }

        result = await handle_telegram_update(update)

        assert result["status"] == "welcomed"
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.services.qdrant.search_conversations', new_callable=AsyncMock)
    @patch('src.services.embeddings.get_embedding')
    @patch('src.services.anthropic.get_claude_response', new_callable=AsyncMock)
    @patch('src.agents.telegram_chat.TelegramChatAgent.send_message', new_callable=AsyncMock)
    async def test_handle_text_message(
        self, mock_send, mock_claude, mock_embed, mock_search
    ):
        from src.agents.telegram_chat import handle_telegram_update

        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = []
        mock_claude.return_value = "Hello! How can I help?"

        update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "text": "Hello"
            }
        }

        result = await handle_telegram_update(update)

        assert result["status"] == "responded"
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_github_task(self):
        from src.agents.telegram_chat import TelegramChatAgent

        agent = TelegramChatAgent()

        assert agent.detect_task_type("Check my GitHub repo") == "github"
        assert agent.detect_task_type("Create a PR review") == "github"
        assert agent.detect_task_type("Write me an article") == "content"
        assert agent.detect_task_type("Generate a report") == "data"
        assert agent.detect_task_type("What's the weather?") is None
```

### Create tests/e2e/test_full_flow.py

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

class TestEndToEndFlow:
    """End-to-end tests for complete agent flows."""

    @pytest.mark.asyncio
    @patch('src.services.firebase.create_task', new_callable=AsyncMock)
    @patch('src.agents.telegram_chat.TelegramChatAgent.send_message', new_callable=AsyncMock)
    async def test_telegram_to_github_flow(self, mock_send, mock_create_task):
        """Test: User requests GitHub stats via Telegram."""
        from src.agents.telegram_chat import handle_telegram_update
        from src.agents.github_automation import process_github_task

        mock_create_task.return_value = "task-123"

        # Step 1: User sends message to Telegram
        telegram_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "text": "Show me GitHub stats for owner/repo"
            }
        }

        with patch('src.services.embeddings.get_embedding', return_value=[0.1] * 1536):
            with patch('src.services.qdrant.search_conversations', new_callable=AsyncMock, return_value=[]):
                result = await handle_telegram_update(telegram_update)

        assert result["status"] == "delegated"
        assert result["task_id"] == "task-123"

        # Step 2: GitHub agent processes task
        github_task = {
            "id": "task-123",
            "type": "github",
            "payload": {
                "action": "repo_stats",
                "repo": "owner/repo",
                "user_id": "user123"
            }
        }

        with patch('src.agents.github_automation.GitHubAgent.github') as mock_github:
            mock_repo = MagicMock()
            mock_repo.stargazers_count = 100
            mock_repo.forks_count = 50
            mock_repo.open_issues_count = 10
            mock_repo.watchers_count = 75
            mock_repo.language = "Python"
            mock_repo.get_commits.return_value = []
            mock_github.get_repo.return_value = mock_repo

            with patch('src.services.firebase.complete_task', new_callable=AsyncMock):
                with patch('src.agents.github_automation.GitHubAgent.notify_user', new_callable=AsyncMock):
                    result = await process_github_task(github_task)

        assert result["status"] == "success"
        assert result["stats"]["stars"] == 100
```

### Add pytest to requirements.txt

```
pytest>=7.4.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
pytest-cov>=4.1.0
```

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_firebase.py -v

# Run e2e tests only
pytest tests/e2e/ -v
```

---

## Part B: Deployment

### Production Deployment Checklist

```bash
# 1. Verify all secrets are configured
modal secret list

# 2. Deploy to production
modal deploy main.py

# 3. Verify deployment
modal app list
modal app logs claude-agents

# 4. Test health endpoint
curl https://<app-name>--telegram-chat-agent.modal.run/health
```

### Add Monitoring to main.py

```python
# Add to main.py
import structlog
from datetime import datetime

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Health check with metrics
@web_app.get("/health")
async def health():
    from src.services.firebase import get_db
    from src.services.qdrant import get_client

    checks = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "ok",
        "services": {}
    }

    # Check Firebase
    try:
        get_db()
        checks["services"]["firebase"] = "ok"
    except Exception as e:
        checks["services"]["firebase"] = str(e)
        checks["status"] = "degraded"

    # Check Qdrant
    try:
        client = get_client()
        client.get_collections()
        checks["services"]["qdrant"] = "ok"
    except Exception as e:
        checks["services"]["qdrant"] = str(e)
        checks["status"] = "degraded"

    return checks

# Metrics endpoint
@web_app.get("/metrics")
async def metrics():
    from src.services import firebase

    db = firebase.get_db()

    # Get task stats
    tasks = list(db.collection("tasks").get())
    task_stats = {
        "total": len(tasks),
        "pending": len([t for t in tasks if t.to_dict().get("status") == "pending"]),
        "processing": len([t for t in tasks if t.to_dict().get("status") == "processing"]),
        "done": len([t for t in tasks if t.to_dict().get("status") == "done"]),
        "failed": len([t for t in tasks if t.to_dict().get("status") == "failed"]),
    }

    # Get agent stats
    agents = list(db.collection("agents").get())
    agent_stats = {
        a.id: a.to_dict().get("status", "unknown")
        for a in agents
    }

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "tasks": task_stats,
        "agents": agent_stats
    }
```

### Create Deployment Script

```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Deploying Claude Agents to Modal..."

# Run tests first
echo "📋 Running tests..."
pytest tests/ -v --tb=short

if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Aborting deployment."
    exit 1
fi

# Deploy to Modal
echo "📦 Deploying to Modal..."
modal deploy main.py

# Verify deployment
echo "✅ Verifying deployment..."
HEALTH_URL=$(modal app logs claude-agents 2>&1 | grep -o 'https://[^"]*health' | head -1)

if [ -n "$HEALTH_URL" ]; then
    curl -s "$HEALTH_URL" | jq .
fi

echo "🎉 Deployment complete!"
```

### Rollback Procedure

```bash
# List previous deployments
modal app history claude-agents

# Rollback to previous version
modal app rollback claude-agents --version <version-id>
```

---

## Cost Monitoring

### Add Cost Tracking

```python
# src/utils/cost_tracker.py
from datetime import datetime
from src.services import firebase

PRICING = {
    "claude-sonnet": 0.003,  # per 1K input tokens
    "claude-sonnet-output": 0.015,  # per 1K output tokens
    "openai-embedding": 0.0001,  # per 1K tokens
    "modal-cpu-second": 0.000018,
    "modal-memory-gb-second": 0.000005,
}

async def track_api_cost(
    service: str,
    operation: str,
    tokens: int = 0,
    seconds: float = 0
):
    """Track API costs in Firebase."""
    cost = 0

    if service == "anthropic":
        cost = (tokens / 1000) * PRICING.get(operation, 0)
    elif service == "openai":
        cost = (tokens / 1000) * PRICING["openai-embedding"]
    elif service == "modal":
        cost = seconds * PRICING["modal-cpu-second"]

    db = firebase.get_db()
    db.collection("costs").add({
        "service": service,
        "operation": operation,
        "tokens": tokens,
        "seconds": seconds,
        "cost": cost,
        "timestamp": datetime.utcnow()
    })

    return cost
```

---

## Files to Create

| Path | Action | Description |
|------|--------|-------------|
| `agents/tests/conftest.py` | Create | Pytest fixtures |
| `agents/tests/unit/test_firebase.py` | Create | Firebase unit tests |
| `agents/tests/integration/test_telegram_agent.py` | Create | Telegram agent tests |
| `agents/tests/e2e/test_full_flow.py` | Create | E2E tests |
| `agents/deploy.sh` | Create | Deployment script |
| `agents/src/utils/cost_tracker.py` | Create | Cost tracking |

## Todo List

- [ ] Create test directory structure
- [ ] Write unit tests for all services
- [ ] Write integration tests for agents
- [ ] Write E2E tests for full flows
- [ ] Run tests, ensure all pass
- [ ] Add health/metrics endpoints
- [ ] Create deploy.sh script
- [ ] Deploy to Modal production
- [ ] Verify all endpoints work
- [ ] Set up cost monitoring

## Success Criteria

- [ ] All tests pass (>90% coverage)
- [ ] Health endpoint returns 200
- [ ] Metrics show agent status
- [ ] Deployment script works
- [ ] Rollback procedure tested
- [ ] Cost tracking active

## Deployment Checklist

```
Pre-deployment:
[ ] All tests pass
[ ] Secrets configured
[ ] Firebase security rules deployed
[ ] Telegram webhook URL updated

Deployment:
[ ] modal deploy main.py
[ ] Verify health endpoint
[ ] Test Telegram webhook
[ ] Verify cron schedules

Post-deployment:
[ ] Monitor logs for errors
[ ] Check cost dashboard
[ ] Verify all agents online
```

## Next Steps

After completing this phase:
1. System is production-ready
2. Monitor for 24-48 hours
3. Iterate based on usage patterns
