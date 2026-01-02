"""Test webhook health fixture functionality."""
import pytest
import asyncio
from .webhook_health import WebhookHealthChecker


@pytest.mark.asyncio
async def test_webhook_health_check():
    """Test basic health check functionality."""
    checker = WebhookHealthChecker()
    status = await checker.check()

    assert status is not None
    assert isinstance(status.ok, bool)
    assert status.status in ["healthy", "degraded", "error", "unknown"]
    assert isinstance(status.degraded_circuits, list)
    assert isinstance(status.pending_updates, int)


@pytest.mark.asyncio
async def test_clear_pending_updates():
    """Test clearing pending updates."""
    checker = WebhookHealthChecker()
    cleared = await checker.clear_pending()

    # Should return 0 or positive count
    assert cleared >= 0


@pytest.mark.asyncio
async def test_webhook_checker_setup():
    """Test WebhookHealthChecker can be instantiated and configured."""
    checker = WebhookHealthChecker()

    assert checker.api_base_url is not None
    assert "modal.run" in checker.api_base_url

    # Test health check and verify return type
    status = await checker.check()
    assert hasattr(status, 'ok')
    assert hasattr(status, 'status')
    assert hasattr(status, 'degraded_circuits')


if __name__ == "__main__":
    # Quick manual test
    async def main():
        checker = WebhookHealthChecker()
        status = await checker.check()
        print(f"\nHealth Status:")
        print(f"  OK: {status.ok}")
        print(f"  Status: {status.status}")
        print(f"  Degraded circuits: {status.degraded_circuits}")
        print(f"  Pending updates: {status.pending_updates}")
        print(f"  Timestamp: {status.timestamp}")

    asyncio.run(main())
