"""Pytest configuration and shared fixtures."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


@pytest.fixture
def mock_state_manager():
    """Mock StateManager to avoid Firebase calls."""
    with patch("src.core.state.get_state_manager") as mock:
        manager = AsyncMock()
        manager.set = AsyncMock()
        manager.get = AsyncMock(return_value=None)
        manager.get_user_tier_cached = AsyncMock(return_value="user")
        manager.get_user_mode = AsyncMock(return_value="auto")
        manager.clear_conversation = AsyncMock()
        manager.clear_pending_skill = AsyncMock()
        manager.invalidate_user_tier = AsyncMock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_logger():
    """Mock logger to suppress output during tests."""
    with patch("src.core.trace.logger") as mock:
        mock.bind.return_value = mock
        mock.info = MagicMock()
        mock.debug = MagicMock()
        mock.warning = MagicMock()
        mock.error = MagicMock()
        yield mock


@pytest.fixture
def circuit():
    """Fresh circuit breaker for each test."""
    from src.core.resilience import CircuitBreaker
    return CircuitBreaker("test", threshold=3, cooldown=1)


@pytest.fixture
def frozen_time():
    """Provide frozen datetime for consistent testing."""
    return datetime(2025, 12, 28, 12, 0, 0, tzinfo=timezone.utc)


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
        "id": 999999999,
        "first_name": "Admin",
        "username": "admin"
    }


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "999999999")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
