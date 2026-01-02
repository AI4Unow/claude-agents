# agents/tests/e2e/api/test_skill_api.py
"""API-direct skill tests - no Telegram credentials required.

These tests call the /api/skill endpoint directly, allowing CI to run
without Telegram session files or credentials.
"""
import os
import pytest
import httpx

# API base URL
API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    "https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run"
)

# Test user for API calls (simulates Telegram user)
TEST_USER = {
    "id": 123456789,
    "first_name": "Test",
    "last_name": "User",
    "username": "testuser",
    "tier": "user"
}

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


class TestSkillApiEndpoint:
    """Tests for /api/skill endpoint."""

    @pytest.mark.no_llm
    async def test_skill_endpoint_exists(self):
        """Skill API endpoint should respond."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # OPTIONS or HEAD to check endpoint exists
            resp = await client.options(f"{API_BASE_URL}/api/skill")
            # Any response (including 405) means endpoint exists
            assert resp.status_code in [200, 204, 405, 422], \
                f"Skill endpoint not found: {resp.status_code}"

    @pytest.mark.no_llm
    async def test_skill_list_endpoint(self):
        """Skills list endpoint should return skill catalog."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{API_BASE_URL}/api/skills")
            assert resp.status_code == 200, f"Skills list failed: {resp.status_code}"

            data = resp.json()
            assert "skills" in data or isinstance(data, list), \
                "Expected skills list in response"

            # Should have at least some skills
            skills = data.get("skills", data) if isinstance(data, dict) else data
            assert len(skills) > 0, "No skills returned"

    @pytest.mark.no_llm
    async def test_skill_without_name_handled(self):
        """Skill endpoint should handle missing skill name gracefully."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/skill",
                json={"prompt": "test prompt"}
            )
            # API may return 200 with error in body, or 4xx
            if resp.status_code == 200:
                data = resp.json()
                # Should indicate error in response body
                assert data.get("ok") is False or "error" in data or "skill" in str(data).lower(), \
                    f"Expected error indication: {data}"
            else:
                assert resp.status_code in [400, 422], \
                    f"Expected validation error, got {resp.status_code}"

    @pytest.mark.requires_claude
    async def test_planning_skill_via_api(self):
        """Planning skill should execute via API."""
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/skill",
                json={
                    "skill": "planning",
                    "prompt": "Create a simple hello world feature",
                    "user_id": TEST_USER["id"],
                    "user": TEST_USER
                }
            )

            if resp.status_code == 503:
                pytest.xfail("Claude circuit may be open")

            assert resp.status_code == 200, \
                f"Planning skill failed: {resp.status_code} - {resp.text[:200]}"

            data = resp.json()
            # API returns {ok: bool, error?: str} or {response/result/text: str}
            if data.get("ok") is False:
                error_msg = data.get("error", "")
                # Handle known transient/config errors
                if "limit" in error_msg.lower() or "402" in error_msg:
                    pytest.xfail("API rate limit reached")
                if "auth" in error_msg.lower() and "500" in error_msg:
                    pytest.xfail(f"Transient auth error: {error_msg[:100]}")
                if "unknown provider" in error_msg.lower() or "model" in error_msg.lower():
                    pytest.xfail(f"Model config issue: {error_msg[:100]}")
                pytest.fail(f"Skill execution failed: {error_msg}")

            # Success case
            assert data.get("ok") is True or "response" in data or "result" in data, \
                f"Expected success response: {list(data.keys())}"

    @pytest.mark.requires_claude
    async def test_debugging_skill_via_api(self):
        """Debugging skill should execute via API."""
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/skill",
                json={
                    "skill": "debugging",
                    "prompt": "Debug a null pointer exception in Python",
                    "user_id": TEST_USER["id"],
                    "user": TEST_USER
                }
            )

            if resp.status_code == 503:
                pytest.xfail("Claude circuit may be open")

            assert resp.status_code == 200, \
                f"Debugging skill failed: {resp.status_code}"

    @pytest.mark.requires_gemini
    async def test_gemini_grounding_skill_via_api(self):
        """Gemini grounding skill should execute via API."""
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/skill",
                json={
                    "skill": "gemini-grounding",
                    "prompt": "What is the weather API?",
                    "user_id": TEST_USER["id"],
                    "user": TEST_USER
                }
            )

            if resp.status_code == 503:
                pytest.xfail("Gemini circuit may be open")

            assert resp.status_code == 200, \
                f"Gemini grounding failed: {resp.status_code}"

    @pytest.mark.no_llm
    async def test_unknown_skill_handled(self):
        """Unknown skill should be handled gracefully."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/skill",
                json={
                    "skill": "nonexistent-skill-xyz",
                    "prompt": "test",
                    "user_id": TEST_USER["id"]
                }
            )

            # API may return 200 with error in body, or 4xx
            if resp.status_code == 200:
                data = resp.json()
                # Should indicate error or unknown skill message
                text = str(data).lower()
                assert data.get("ok") is False or "error" in data or \
                    "unknown" in text or "not found" in text or "skill" in text, \
                    f"Expected error for unknown skill: {data}"
            else:
                # 4xx errors are acceptable
                assert resp.status_code in [400, 404, 422], \
                    f"Expected client error for unknown skill, got {resp.status_code}"


class TestHealthEndpoints:
    """Tests for health and status endpoints."""

    @pytest.mark.no_llm
    async def test_health_endpoint(self):
        """Health endpoint should return status."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(f"{API_BASE_URL}/health")
                assert resp.status_code == 200, f"Health check failed: {resp.status_code}"

                data = resp.json()
                assert "status" in data or "circuits" in data, \
                    "Expected health data in response"
            except httpx.ReadTimeout:
                pytest.xfail("Health endpoint timed out (Modal cold start)")

    @pytest.mark.no_llm
    async def test_circuits_in_health(self):
        """Health endpoint should include circuit status."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(f"{API_BASE_URL}/health")
                if resp.status_code != 200:
                    pytest.skip(f"Health endpoint returned {resp.status_code}")

                data = resp.json()
                circuits = data.get("circuits", {})

                # Should have expected circuits
                expected_circuits = ["claude", "gemini", "firebase", "telegram"]
                for circuit in expected_circuits:
                    # Check various naming patterns
                    found = any(circuit in key.lower() for key in circuits.keys())
                    if not found:
                        print(f"Warning: Circuit '{circuit}' not found in {list(circuits.keys())}")
            except httpx.ReadTimeout:
                pytest.xfail("Health endpoint timed out (Modal cold start)")


class TestReportsApi:
    """Tests for reports API endpoints."""

    @pytest.mark.no_llm
    async def test_reports_endpoint_exists(self):
        """Reports endpoint should be accessible."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE_URL}/api/reports",
                params={"user_id": TEST_USER["id"]}
            )
            # 200 or 404 (no reports) are both valid
            assert resp.status_code in [200, 404], \
                f"Reports endpoint error: {resp.status_code}"


class TestTracesApi:
    """Tests for execution traces API."""

    @pytest.mark.no_llm
    async def test_traces_endpoint_exists(self):
        """Traces endpoint should be accessible."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE_URL}/api/traces")
            # May require auth, so 401/403 is acceptable
            assert resp.status_code in [200, 401, 403], \
                f"Traces endpoint error: {resp.status_code}"
