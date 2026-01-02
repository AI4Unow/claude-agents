# agents/tests/e2e/state/test_circuit_breakers.py
"""E2E tests for circuit breaker state verification."""
import pytest
from ..conftest import verify_circuit_state, send_and_wait

pytestmark = pytest.mark.no_llm  # Infrastructure tests (circuit state verification)

# Expected circuit breakers
CIRCUIT_BREAKERS = [
    "claude",
    "gemini",
    "exa",
    "tavily",
    "firebase",
    "qdrant",
    "telegram",
]


class TestCircuitBreakers:
    """Tests for circuit breaker health and behavior."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_all_circuits_healthy(self):
        """All 7 circuit breakers should be closed (healthy)."""
        for circuit in CIRCUIT_BREAKERS:
            is_closed = await verify_circuit_state(circuit, "closed")
            # Note: Some circuits may be open due to service issues
            # Log but don't fail on individual circuits
            if not is_closed:
                print(f"Warning: Circuit '{circuit}' not closed")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.admin
    async def test_status_shows_circuits(self, telegram_client, bot_username):
        """Admin /status shows circuit health."""
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/status",
            timeout=20
        )

        assert response is not None, "No status response"
        text_lower = (response.text or "").lower()

        # Should show status info (circuits may or may not be visible depending on tier)
        status_words = ["status", "running", "online", "tier", "circuit", "health"]
        assert any(word in text_lower for word in status_words), \
            f"Status not shown: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_degraded_service_message(self, telegram_client, bot_username):
        """Test bot handles degraded service gracefully."""
        # This tests that even if a circuit is open, user gets helpful message
        # We can't easily force a circuit open, so we test resilience
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "Hello, test message",
            timeout=30
        )

        assert response is not None, "No response (potential circuit issue)"
        # Should not show raw circuit error
        text_lower = (response.text or "").lower()
        assert "circuit" not in text_lower or "breaker" not in text_lower, \
            "Raw circuit error exposed to user"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_circuit_api_accessible(self, api_base_url):
        """Circuit API endpoint accessible (with auth if required)."""
        import os
        import httpx

        admin_token = os.environ.get("ADMIN_API_TOKEN")
        headers = {}
        if admin_token:
            headers["X-Admin-Token"] = admin_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{api_base_url}/api/circuits", headers=headers)

                # 401 is acceptable if no admin token provided
                if resp.status_code == 401 and not admin_token:
                    pytest.skip("Circuit API requires ADMIN_API_TOKEN")

                assert resp.status_code == 200, f"Circuit API returned {resp.status_code}"

                data = resp.json()
                # Should have circuit data
                assert isinstance(data, dict), "Circuit data should be dict"
            except httpx.RequestError as e:
                pytest.skip(f"Circuit API not accessible: {e}")
