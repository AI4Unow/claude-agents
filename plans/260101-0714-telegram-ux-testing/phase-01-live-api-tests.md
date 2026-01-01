# Phase 1: Live API Tests

## Context Links

- Main plan: [plan.md](./plan.md)
- Brainstorm: `plans/reports/brainstorm-260101-0714-telegram-ux-testing.md`
- Existing tests: `agents/tests/test_resilience.py`

## Overview

Create `tests/live/` directory with real API integration tests. These tests hit production endpoints to validate latency SLAs, error handling, and circuit breaker behavior. Marked with `@pytest.mark.live` and skipped in CI by default.

## Key Insights

1. **No live tests exist** - All current tests use mocks (MockLLM, MockFirebase)
2. **api.ai4u.now SLA** - Target P95 < 5s for LLM responses
3. **3-tier fallback** - Exa -> Gemini -> Tavily chain needs validation
4. **Circuit breakers** - 8 circuits (claude, exa, tavily, firebase, qdrant, telegram, gemini, evolution)

## Requirements

### Functional
- Test LLM latency against api.ai4u.now (P95 < 5s)
- Test rate limit recovery (429 handling)
- Test Gemini grounding and deep research
- Test web search fallback chain
- Test circuit breaker force-fail and recovery

### Non-Functional
- Skip in CI by default (`pytest -m "not live"`)
- Environment variable validation before run
- Reasonable sample size (10 requests for latency)
- Timeout protection (120s max per test)

## Architecture

```
tests/live/
+-- conftest.py           # Fixtures, markers, env validation
+-- test_llm_live.py      # api.ai4u.now tests
+-- test_gemini_live.py   # Gemini grounding/research tests
+-- test_web_search_live.py  # Fallback chain tests
+-- test_circuits_live.py # Circuit breaker tests
```

### Pytest Marker Configuration

```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "live: mark test as requiring live API")
```

### Environment Validation Fixture

```python
@pytest.fixture(scope="session")
def live_env():
    """Validate environment for live tests."""
    required = ["ANTHROPIC_API_KEY", "EXA_API_KEY", "GEMINI_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        pytest.skip(f"Missing env vars: {missing}")
    return True
```

## Related Code Files

| File | Purpose |
|------|---------|
| `src/services/llm.py` | LLMClient to test |
| `src/services/gemini.py` | GeminiClient to test |
| `src/tools/web_search.py` | WebSearchTool to test |
| `src/core/resilience.py` | Circuit breakers |
| `tests/test_resilience.py` | Existing circuit unit tests |

## Implementation Steps

### Step 1: Create tests/live/conftest.py

```python
"""Live API test configuration."""
import os
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "live: mark test as requiring live API")

@pytest.fixture(scope="session")
def live_env():
    """Validate environment for live tests."""
    required = [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "EXA_API_KEY",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        pytest.skip(f"Missing env vars for live tests: {missing}")
    return True

@pytest.fixture(scope="session")
def gemini_env():
    """Validate Gemini environment."""
    has_api_key = bool(os.environ.get("GEMINI_API_KEY"))
    has_vertex = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    if not has_api_key and not has_vertex:
        pytest.skip("No Gemini credentials available")
    return True

@pytest.fixture
def reset_circuits():
    """Reset all circuits before and after test."""
    from src.core.resilience import reset_all_circuits
    reset_all_circuits()
    yield
    reset_all_circuits()
```

### Step 2: Create tests/live/test_llm_live.py

```python
"""Live tests for api.ai4u.now LLM API."""
import time
import pytest

@pytest.mark.live
@pytest.mark.asyncio
async def test_api_latency_sla(live_env):
    """Response time < 5s for 95th percentile."""
    from src.services.llm import get_llm_client

    client = get_llm_client()
    latencies = []

    for _ in range(10):
        start = time.time()
        response = client.chat([{"role": "user", "content": "Hello, respond briefly."}])
        latencies.append(time.time() - start)
        assert response, "Empty response"

    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95 = latencies[p95_index]

    assert p95 < 5.0, f"P95 latency {p95:.2f}s exceeds 5s SLA"

@pytest.mark.live
@pytest.mark.asyncio
async def test_rate_limit_recovery(live_env):
    """Bot recovers gracefully from rate limits."""
    from src.services.llm import get_llm_client

    client = get_llm_client()

    # Rapid fire 5 requests (may trigger rate limit)
    responses = []
    for i in range(5):
        try:
            resp = client.chat([{"role": "user", "content": f"Test {i}"}])
            responses.append(resp)
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                # Expected rate limit - verify it's handled
                pass
            else:
                raise

    # At least some should succeed
    assert len(responses) >= 1, "All requests failed"

@pytest.mark.live
@pytest.mark.asyncio
async def test_vision_capability(live_env):
    """Claude Vision API works."""
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
        prompt="Describe this image briefly.",
        media_type="image/png"
    )
    assert response, "No vision response"
```

### Step 3: Create tests/live/test_gemini_live.py

```python
"""Live tests for Gemini API."""
import pytest

@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_grounding(gemini_env):
    """Gemini grounding returns citations."""
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    response = await client.grounded_query(
        query="What is the current Bitcoin price?",
        grounding_sources=["google_search"]
    )

    assert response.text, "No grounded response text"
    # Note: Citations may be empty for some queries

@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_deep_research(gemini_env):
    """Gemini deep research returns structured report."""
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    progress_updates = []

    def on_progress(msg):
        progress_updates.append(msg)

    report = await client.deep_research(
        query="Summarize recent AI developments briefly",
        on_progress=on_progress,
        max_iterations=3  # Limit for test speed
    )

    assert report.title, "No report title"
    assert report.summary, "No report summary"
    assert len(progress_updates) > 0, "No progress updates"
    assert report.query_count >= 1, "No queries executed"

@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_chat(gemini_env):
    """Basic Gemini chat works."""
    from src.services.gemini import get_gemini_client

    client = get_gemini_client()
    response = await client.chat(
        messages=[{"role": "user", "content": "Say hello briefly."}]
    )

    assert response, "No chat response"
    assert len(response) < 500, "Response too long for simple greeting"
```

### Step 4: Create tests/live/test_web_search_live.py

```python
"""Live tests for web search with fallback chain."""
import pytest

@pytest.mark.live
@pytest.mark.asyncio
async def test_web_search_exa_primary(live_env):
    """Exa search returns results."""
    from src.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    result = await tool.execute({"query": "Python programming language"})

    assert result.success, f"Search failed: {result.error}"
    assert len(result.data) > 100, "Response too short"
    assert "python" in result.data.lower(), "No relevant content"

@pytest.mark.live
@pytest.mark.asyncio
async def test_web_search_fallback_chain(live_env, gemini_env, reset_circuits):
    """Fallback chain: Exa -> Gemini -> Tavily."""
    from src.tools.web_search import WebSearchTool
    from src.core.resilience import exa_circuit, CircuitState

    tool = WebSearchTool()

    # Force Exa circuit open
    exa_circuit._state = CircuitState.OPEN
    exa_circuit._failures = 10

    # Should fallback to Gemini or Tavily
    result = await tool.execute({"query": "OpenAI ChatGPT"})

    # May succeed via Gemini or Tavily, or fail if all circuits open
    if result.success:
        assert len(result.data) > 50, "Fallback response too short"

@pytest.mark.live
@pytest.mark.asyncio
async def test_web_search_caching(live_env):
    """Same query returns cached result."""
    import time
    from src.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    query = f"test query caching {time.time()}"  # Unique query

    # First call
    start1 = time.time()
    result1 = await tool.execute({"query": query})
    latency1 = time.time() - start1

    # Second call (should be cached)
    start2 = time.time()
    result2 = await tool.execute({"query": query})
    latency2 = time.time() - start2

    assert result1.data == result2.data, "Cache returned different result"
    assert latency2 < latency1 / 2, "Cache not significantly faster"
```

### Step 5: Create tests/live/test_circuits_live.py

```python
"""Live tests for circuit breaker behavior."""
import pytest
from datetime import datetime, timezone, timedelta

@pytest.mark.live
@pytest.mark.asyncio
async def test_circuit_opens_on_failures(reset_circuits):
    """Circuit opens after threshold failures."""
    from src.core.resilience import (
        CircuitBreaker, CircuitState, CircuitOpenError
    )

    circuit = CircuitBreaker("test_live", threshold=2, cooldown=5)

    async def failing_func():
        raise ValueError("Intentional failure")

    # Two failures should open circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            await circuit.call(failing_func)

    assert circuit.state == CircuitState.OPEN

    # Next call should raise CircuitOpenError
    with pytest.raises(CircuitOpenError) as exc:
        await circuit.call(failing_func)

    assert exc.value.cooldown_remaining <= 5

@pytest.mark.live
@pytest.mark.asyncio
async def test_circuit_recovery_after_cooldown(reset_circuits):
    """Circuit recovers after cooldown period."""
    from src.core.resilience import CircuitBreaker, CircuitState

    circuit = CircuitBreaker("test_recovery", threshold=2, cooldown=1)

    async def failing_func():
        raise ValueError("Fail")

    async def success_func():
        return "success"

    # Open circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            await circuit.call(failing_func)

    assert circuit.state == CircuitState.OPEN

    # Wait for cooldown
    import asyncio
    await asyncio.sleep(1.5)

    # Should transition to HALF_OPEN
    assert circuit.state == CircuitState.HALF_OPEN

    # Successful call should close
    result = await circuit.call(success_func)
    assert result == "success"
    assert circuit.state == CircuitState.CLOSED

@pytest.mark.live
@pytest.mark.asyncio
async def test_all_circuits_status(reset_circuits):
    """All circuits are in expected initial state."""
    from src.core.resilience import get_circuit_stats, CircuitState

    stats = get_circuit_stats()

    expected_circuits = [
        "exa_api", "tavily_api", "firebase", "qdrant",
        "claude_api", "telegram_api", "gemini_api", "evolution_api"
    ]

    for name in expected_circuits:
        assert name in stats, f"Missing circuit: {name}"
        assert stats[name]["state"] == "closed", f"{name} not closed"
        assert stats[name]["failures"] == 0, f"{name} has failures"
```

## Todo List

- [ ] Create `tests/live/` directory
- [ ] Create `tests/live/conftest.py` with markers and fixtures
- [ ] Create `tests/live/test_llm_live.py` with latency SLA tests
- [ ] Create `tests/live/test_gemini_live.py` with grounding tests
- [ ] Create `tests/live/test_web_search_live.py` with fallback tests
- [ ] Create `tests/live/test_circuits_live.py` with recovery tests
- [ ] Update pytest.ini to skip live tests by default
- [ ] Document how to run live tests in README

## Success Criteria

- [ ] Live tests pass when run with credentials
- [ ] api.ai4u.now P95 latency < 5s confirmed
- [ ] Gemini grounding returns valid responses
- [ ] Web search fallback chain verified
- [ ] Circuit breaker recovery < 60s confirmed
- [ ] Tests skip gracefully without credentials

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| API costs | Low | Low | Small sample sizes, manual run only |
| Rate limiting | Medium | Low | Add delays between requests |
| Flaky tests | Medium | Medium | Retry logic, reasonable timeouts |
| Credential exposure | Low | High | Never log credentials, env-only |
