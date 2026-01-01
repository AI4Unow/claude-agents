"""Live API integration tests.

These tests hit production endpoints and are skipped in CI by default.

Run with:
    pytest agents/tests/live/ -v

Skip with:
    pytest -m "not live"

Environment variables required:
    - ANTHROPIC_API_KEY: Claude API key
    - ANTHROPIC_BASE_URL: api.ai4u.now proxy URL
    - EXA_API_KEY: Exa search API key
    - GEMINI_API_KEY or GOOGLE_APPLICATION_CREDENTIALS_JSON: Gemini credentials
"""
