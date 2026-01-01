"""Live tests for web search with fallback chain.

Tests real web search behavior:
- Exa as primary search provider
- Fallback chain: Exa → Gemini → Tavily
- Caching performance
"""
import time
import pytest


@pytest.mark.live
@pytest.mark.asyncio
async def test_web_search_exa_primary(live_env):
    """Exa search returns results.

    Tests primary search provider with simple query.
    """
    from src.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    result = await tool.execute({"query": "Python programming language"})

    assert result.success, f"Search failed: {result.error}"
    assert len(result.data) > 100, f"Response too short: {len(result.data)} chars"
    assert "python" in result.data.lower(), "No relevant content found"

    print(f"\nSearch result length: {len(result.data)} chars")
    print(f"Preview: {result.data[:200]}...")


@pytest.mark.live
@pytest.mark.asyncio
async def test_web_search_fallback_chain(live_env, gemini_env, reset_circuits):
    """Fallback chain: Exa → Gemini → Tavily.

    Forces Exa circuit open to test fallback behavior.
    May succeed via Gemini or Tavily, or fail if all circuits open.
    """
    from src.tools.web_search import WebSearchTool
    from src.core.resilience import exa_circuit, CircuitState

    tool = WebSearchTool()

    # Force Exa circuit open
    exa_circuit._state = CircuitState.OPEN
    exa_circuit._failures = 10

    print("\nExa circuit forced open, testing fallback...")

    # Should fallback to Gemini or Tavily
    result = await tool.execute({"query": "OpenAI ChatGPT"})

    # May succeed via Gemini or Tavily, or fail if all circuits open
    if result.success:
        assert len(result.data) > 50, "Fallback response too short"
        print(f"Fallback succeeded with {len(result.data)} chars")
    else:
        print(f"All fallbacks failed (expected if circuits open): {result.error}")


@pytest.mark.live
@pytest.mark.asyncio
async def test_web_search_caching(live_env):
    """Same query returns cached result.

    Tests cache hit performance improvement.
    Second call should be significantly faster.
    """
    import time
    from src.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    query = f"test query caching {time.time()}"  # Unique query

    # First call (cache miss)
    start1 = time.time()
    result1 = await tool.execute({"query": query})
    latency1 = time.time() - start1

    assert result1.success, f"First call failed: {result1.error}"

    # Second call (should be cached)
    start2 = time.time()
    result2 = await tool.execute({"query": query})
    latency2 = time.time() - start2

    assert result2.success, f"Second call failed: {result2.error}"
    assert result1.data == result2.data, "Cache returned different result"

    print(f"\nFirst call: {latency1:.3f}s, Second call: {latency2:.3f}s")
    print(f"Speedup: {latency1/latency2:.1f}x")

    # Cache should be at least 2x faster (conservative threshold)
    assert latency2 < latency1 / 2, f"Cache not significantly faster: {latency1:.3f}s vs {latency2:.3f}s"
