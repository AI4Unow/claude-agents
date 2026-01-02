"""Webhook health checking fixture for E2E tests."""
import os
import asyncio
from typing import Optional
from dataclasses import dataclass

import httpx
import pytest


# API base URL
API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    "https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run"
)


@dataclass
class HealthStatus:
    """Health check result."""
    ok: bool
    status: str
    degraded_circuits: list[str]
    pending_updates: int
    timestamp: str


class WebhookHealthChecker:
    """Check and manage webhook health."""

    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_base_url = api_base_url
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    async def check(self) -> HealthStatus:
        """Check webhook health via /health endpoint.

        Returns:
            HealthStatus with overall health and circuit states
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.api_base_url}/health")
                if resp.status_code != 200:
                    return HealthStatus(
                        ok=False,
                        status="error",
                        degraded_circuits=[],
                        pending_updates=0,
                        timestamp=""
                    )

                data = resp.json()
                status = data.get("status", "unknown")
                circuits = data.get("circuits", {})

                # Find degraded circuits (open or half_open)
                degraded = [
                    name for name, info in circuits.items()
                    if info.get("state") in ["open", "half_open"]
                ]

                # Check pending updates if bot token available
                pending = 0
                if self.bot_token:
                    pending = await self._get_pending_updates_count()

                return HealthStatus(
                    ok=(status == "healthy"),
                    status=status,
                    degraded_circuits=degraded,
                    pending_updates=pending,
                    timestamp=data.get("timestamp", "")
                )

            except Exception as e:
                print(f"[E2E] Health check failed: {e}")
                return HealthStatus(
                    ok=False,
                    status="error",
                    degraded_circuits=[],
                    pending_updates=0,
                    timestamp=""
                )

    async def _get_pending_updates_count(self) -> int:
        """Get count of pending Telegram updates."""
        if not self.bot_token:
            return 0

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://api.telegram.org/bot{self.bot_token}/getUpdates",
                    params={"limit": 100, "timeout": 0}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return len(data.get("result", []))
                return 0
            except Exception:
                return 0

    async def clear_pending(self) -> int:
        """Clear pending Telegram updates.

        Returns:
            Number of updates cleared
        """
        if not self.bot_token:
            print("[E2E] No TELEGRAM_BOT_TOKEN, skipping clear")
            return 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Get updates to find highest offset
                resp = await client.get(
                    f"https://api.telegram.org/bot{self.bot_token}/getUpdates",
                    params={"limit": 100, "timeout": 0}
                )

                if resp.status_code != 200:
                    print(f"[E2E] Failed to get updates: {resp.status_code}")
                    return 0

                data = resp.json()
                updates = data.get("result", [])
                count = len(updates)

                if count == 0:
                    print("[E2E] No pending updates to clear")
                    return 0

                # Get highest update_id
                last_update_id = max(u["update_id"] for u in updates)

                # Confirm updates with offset = last_update_id + 1
                resp = await client.get(
                    f"https://api.telegram.org/bot{self.bot_token}/getUpdates",
                    params={"offset": last_update_id + 1, "timeout": 0}
                )

                if resp.status_code == 200:
                    print(f"[E2E] Cleared {count} pending updates")
                    return count
                else:
                    print(f"[E2E] Failed to confirm clear: {resp.status_code}")
                    return 0

            except Exception as e:
                print(f"[E2E] Error clearing updates: {e}")
                return 0

    async def setup(self, webhook_url: Optional[str] = None, secret_token: Optional[str] = None):
        """Setup webhook with Telegram.

        Args:
            webhook_url: URL to set (default: API_BASE_URL/webhook/telegram)
            secret_token: Secret token for verification (from env if not provided)
        """
        if not self.bot_token:
            print("[E2E] No TELEGRAM_BOT_TOKEN, skipping webhook setup")
            return False

        url = webhook_url or f"{self.api_base_url}/webhook/telegram"
        secret = secret_token or os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                params = {"url": url}
                if secret:
                    params["secret_token"] = secret

                resp = await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/setWebhook",
                    json=params
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        print(f"[E2E] Webhook set to {url}")
                        return True
                    else:
                        print(f"[E2E] Webhook setup failed: {data}")
                        return False
                else:
                    print(f"[E2E] Webhook setup error: {resp.status_code}")
                    return False

            except Exception as e:
                print(f"[E2E] Webhook setup exception: {e}")
                return False


@pytest.fixture(scope="module")
async def webhook_healthy():
    """Ensure webhook is healthy before running test module.

    Checks:
    1. Health endpoint returns healthy status
    2. No critical circuit breakers open
    3. Pending updates cleared if count > 5

    Yields:
        WebhookHealthChecker instance for use in tests
    """
    checker = WebhookHealthChecker()

    # Check health
    status = await checker.check()
    print(f"\n[E2E] Webhook health: {status.status}")

    if status.degraded_circuits:
        print(f"[E2E] Degraded circuits: {', '.join(status.degraded_circuits)}")

    # Clear pending updates if excessive
    if status.pending_updates > 5:
        print(f"[E2E] Clearing {status.pending_updates} pending updates...")
        cleared = await checker.clear_pending()
        await asyncio.sleep(2)  # Wait for clear to propagate

    # Verify critical circuits not open
    critical_circuits = ["telegram_api", "claude_api"]
    open_critical = [c for c in status.degraded_circuits if c in critical_circuits]

    if open_critical:
        pytest.skip(f"Critical circuits open: {', '.join(open_critical)}")

    yield checker
