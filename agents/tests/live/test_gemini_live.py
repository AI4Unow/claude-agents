"""Live tests for Gemini API.

Tests real Gemini API capabilities:
- Grounding (Google Search integration)
- Deep Research (multi-query research reports)
- Basic chat
"""
import pytest


@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_grounding(gemini_env):
    """Gemini grounding returns citations.

    Uses Google Search grounding to get current information.
    Note: Citations may be empty for some queries.
    """
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    response = await client.grounded_query(
        query="What is the current Bitcoin price?",
        grounding_sources=["google_search"]
    )

    assert response.text, "No grounded response text"
    assert len(response.text) > 20, "Response too short"
    print(f"\nGrounded response: {response.text[:200]}...")

    # Citations may be empty, just log them
    if hasattr(response, 'citations') and response.citations:
        print(f"Citations: {len(response.citations)}")


@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_deep_research(gemini_env):
    """Gemini deep research returns structured report.

    Tests multi-iteration research with progress tracking.
    Limited to 3 iterations for test speed.
    """
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    progress_updates = []

    def on_progress(msg):
        progress_updates.append(msg)
        print(f"\nProgress: {msg}")

    report = await client.deep_research(
        query="Summarize recent AI developments briefly",
        on_progress=on_progress,
        max_iterations=3  # Limit for test speed
    )

    assert report.title, "No report title"
    assert report.summary, "No report summary"
    assert len(progress_updates) > 0, "No progress updates"
    assert report.query_count >= 1, "No queries executed"

    print(f"\nReport title: {report.title}")
    print(f"Summary length: {len(report.summary)} chars")
    print(f"Query count: {report.query_count}")


@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_chat(gemini_env):
    """Basic Gemini chat works.

    Tests simple chat interaction without special features.
    """
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    response = await client.chat(
        messages=[{"role": "user", "content": "Say hello briefly."}]
    )

    assert response, "No chat response"
    assert len(response) > 0, "Empty chat response"
    assert len(response) < 500, f"Response too long ({len(response)} chars) for simple greeting"

    print(f"\nChat response: {response}")
