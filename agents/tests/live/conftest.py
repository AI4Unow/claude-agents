"""Live API test configuration.

These tests hit production endpoints and are skipped in CI by default.
Run with: pytest agents/tests/live/ -v
Skip with: pytest -m "not live"
"""
import os
import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring live API (skipped in CI)"
    )


@pytest.fixture(scope="session")
def live_env():
    """Validate environment for live LLM tests.

    Required environment variables:
    - ANTHROPIC_API_KEY: Claude API key
    - ANTHROPIC_BASE_URL: api.ai4u.now proxy URL
    - EXA_API_KEY: Exa search API key

    Raises:
        pytest.skip: If any required env var is missing
    """
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
    """Validate Gemini environment.

    Requires either:
    - GEMINI_API_KEY: Gemini API key
    - GOOGLE_APPLICATION_CREDENTIALS_JSON: Vertex AI credentials

    Raises:
        pytest.skip: If no Gemini credentials available
    """
    has_api_key = bool(os.environ.get("GEMINI_API_KEY"))
    has_vertex = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    if not has_api_key and not has_vertex:
        pytest.skip("No Gemini credentials available")
    return True


@pytest.fixture
def reset_circuits():
    """Reset all circuits before and after test.

    Ensures each test starts with clean circuit breaker state.
    """
    from src.core.resilience import reset_all_circuits
    reset_all_circuits()
    yield
    reset_all_circuits()
