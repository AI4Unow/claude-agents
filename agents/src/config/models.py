"""Model configuration constants for the Agents system.

Centralizes all LLM model identifiers with fallback logic.
Primary: gemini-claude-* models
Fallback: gemini-claude-* models (same as primary)
"""
import os

# =============================================================================
# Primary Models (gemini-claude family)
# =============================================================================
MODEL_COMPLEX = "gemini-3-flash-preview"           # Complex/agentic tasks
MODEL_SIMPLE = "gemini-2.5-flash-lite"             # Simple/fast tasks

# =============================================================================
# Fallback Models (same as primary - gemini-claude family)
# =============================================================================
FALLBACK_COMPLEX = "gemini-3-flash-preview"
FALLBACK_SIMPLE = "gemini-2.5-flash-lite"

# =============================================================================
# Environment Variable Overrides
# =============================================================================
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "") or MODEL_COMPLEX
FAST_MODEL = os.environ.get("ANTHROPIC_MODEL_FAST", "") or MODEL_SIMPLE

# Vision model (native Anthropic, not proxied)
VISION_MODEL = "claude-sonnet-4-20250514"


def get_model_with_fallback(primary: str, fallback: str) -> str:
    """Get model with fallback if primary fails.

    Use this for runtime model selection with graceful degradation.
    """
    # Could add validation logic here in future
    return primary
