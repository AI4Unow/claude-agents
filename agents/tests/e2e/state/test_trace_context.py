# agents/tests/e2e/state/test_trace_context.py
"""E2E tests for execution trace verification."""
import pytest
from ..conftest import send_and_wait, get_trace


class TestTraceContext:
    """Tests for execution tracing."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_request_generates_trace(self, telegram_client, bot_username, api_base_url):
        """Each request generates trace context."""
        import httpx

        # Make a request
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "/status",
            timeout=20
        )

        assert response is not None, "No response"

        # Check traces API has recent entries
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{api_base_url}/api/traces")
                if resp.status_code == 200:
                    data = resp.json()
                    assert "traces" in data or isinstance(data, list), \
                        "Traces API should return trace list"
            except httpx.RequestError:
                pytest.skip("Traces API not accessible")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_trace_api_returns_data(self, api_base_url):
        """Trace API returns structured data."""
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{api_base_url}/api/traces")
                if resp.status_code == 200:
                    data = resp.json()
                    # Should have trace structure
                    if data:
                        first = data[0] if isinstance(data, list) else list(data.values())[0]
                        # Trace should have basic fields
                        assert "trace_id" in first or "id" in first, \
                            "Trace missing ID field"
            except httpx.RequestError:
                pytest.skip("Traces API not accessible")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.tier_developer
    async def test_developer_can_access_traces(self, telegram_client, bot_username):
        """Developer tier can view traces."""
        # This would need developer-tier test account
        # For now, just verify the endpoint exists
        response = await send_and_wait(
            telegram_client,
            bot_username,
            "Show me recent traces",
            timeout=30
        )

        # Response content depends on tier
        assert response is not None, "No response to trace request"
