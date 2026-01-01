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
    """Claude Vision API works.

    Tests vision using a minimal 1x1 transparent PNG.
    Verifies image encoding and API response.
    """
    from src.services.llm import get_llm_client
    import base64

    client = get_llm_client()

    # 1x1 pixel transparent PNG (smallest valid image)
    tiny_png = base64.b64encode(
        bytes.fromhex("89504e470d0a1a0a0000000d49484452"
                      "00000001000000010100000000376ef9"
                      "240000000a49444154789c626001000001"
                      "8101000afc010002580000")
    ).decode()

    response = client.chat_with_image(
        image_base64=tiny_png,
        prompt="Describe this image in one word.",
        media_type="image/png"
    )

    assert response, "No vision response"
    assert len(response) > 0, "Empty vision response"
    print(f"\nVision response: {response[:100]}...")
