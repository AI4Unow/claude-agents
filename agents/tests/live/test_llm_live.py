"""Live tests for api.ai4u.now LLM API.

Tests real API behavior including:
- Latency SLA (P95 < 5s)
- Rate limit recovery (429 handling)
- Vision capability
"""
import time
import pytest


@pytest.mark.live
@pytest.mark.asyncio
async def test_api_latency_sla(live_env):
    """Response time < 5s for 95th percentile.

    Validates api.ai4u.now proxy meets SLA requirements.
    Sample size: 10 requests for statistical significance.
    """
    from src.services.llm import get_llm_client

    client = get_llm_client()
    latencies = []

    for i in range(10):
        start = time.time()
        response = client.chat([{
            "role": "user",
            "content": f"Hello {i}, respond with just 'Hi'."
        }])
        latencies.append(time.time() - start)
        assert response, f"Empty response on request {i}"

    # Calculate P95
    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95 = latencies[p95_index]

    # Report stats
    avg = sum(latencies) / len(latencies)
    print(f"\nLatency stats: avg={avg:.2f}s, p95={p95:.2f}s, max={max(latencies):.2f}s")

    assert p95 < 5.0, f"P95 latency {p95:.2f}s exceeds 5s SLA"


@pytest.mark.live
@pytest.mark.asyncio
async def test_rate_limit_recovery(live_env):
    """Bot recovers gracefully from rate limits.

    Sends rapid requests to potentially trigger rate limiting.
    Verifies at least some succeed and errors are handled properly.
    """
    from src.services.llm import get_llm_client

    client = get_llm_client()

    # Rapid fire 5 requests (may trigger rate limit)
    responses = []
    errors = []

    for i in range(5):
        try:
            resp = client.chat([{
                "role": "user",
                "content": f"Test {i}"
            }])
            responses.append(resp)
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                # Expected rate limit - verify it's handled
                errors.append(("rate_limit", str(e)))
            else:
                # Unexpected error
                errors.append(("other", str(e)))
                raise

    # At least some should succeed
    print(f"\nSuccesses: {len(responses)}, Rate limits: {len(errors)}")
    assert len(responses) >= 1, f"All requests failed: {errors}"


@pytest.mark.live
@pytest.mark.asyncio
async def test_vision_capability(live_env):
    """Gemini Vision API works.

    Tests vision using Gemini (ai4u.now proxy doesn't support image content blocks).
    Downloads a real image from the web to test.
    """
    from src.services.gemini import get_gemini_client
    import httpx
    import base64

    client = get_gemini_client()

    # Fetch a small test image from httpbin (returns 100x100 PNG)
    async with httpx.AsyncClient() as http:
        resp = await http.get("https://httpbin.org/image/png", timeout=10.0)
        image_bytes = resp.content

    image_b64 = base64.b64encode(image_bytes).decode()

    response = await client.analyze_image(
        image_base64=image_b64,
        prompt="Describe what you see in this image briefly.",
        media_type="image/png"
    )

    assert response, "No vision response"
    assert len(response) > 0, "Empty vision response"
    print(f"\nVision response: {response[:100]}...")
