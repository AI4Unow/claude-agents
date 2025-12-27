"""LLM client wrapper with multi-provider support.

Supports:
- Z.AI GLM-4.7 (OpenAI-compatible API) - Primary
- Anthropic-compatible API (ai4u.now) - Fallback
"""
import os
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger()


class LLMClient:
    """Multi-provider LLM client with automatic fallback."""

    def __init__(self):
        # Primary: Z.AI
        self.zai_api_key = os.environ.get("ZAI_API_KEY", "")
        self.zai_base_url = os.environ.get("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
        self.zai_model = os.environ.get("ZAI_MODEL", "glm-4.7")

        # Fallback: Anthropic-compatible
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.anthropic_base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.ai4u.now/v1")
        self.anthropic_model = os.environ.get("ANTHROPIC_MODEL", "kiro-claude-opus-4-5-agentic")

        # Initialize clients lazily
        self._zai_client = None
        self._anthropic_client = None

    @property
    def zai_client(self):
        """Lazy-load Z.AI client."""
        if self._zai_client is None and self.zai_api_key:
            from openai import OpenAI
            self._zai_client = OpenAI(
                api_key=self.zai_api_key,
                base_url=self.zai_base_url,
            )
        return self._zai_client

    @property
    def anthropic_client(self):
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None and self.anthropic_api_key:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(
                api_key=self.anthropic_api_key,
                base_url=self.anthropic_base_url,
            )
        return self._anthropic_client

    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send chat completion with automatic fallback.

        Tries Anthropic (ai4u.now) first, falls back to Z.AI on failure.
        """
        errors = []

        # Try Anthropic-compatible (ai4u.now) first - Primary
        if self.anthropic_client:
            try:
                return self._call_anthropic(messages, system, max_tokens, temperature)
            except Exception as e:
                logger.warning("anthropic_failed_fallback", error=str(e))
                errors.append(f"Anthropic: {e}")

        # Fallback to Z.AI (OpenAI-compatible)
        if self.zai_client:
            try:
                return self._call_zai(messages, system, max_tokens, temperature)
            except Exception as e:
                logger.warning("zai_failed", error=str(e))
                errors.append(f"Z.AI: {e}")

        raise RuntimeError(f"All LLM providers failed: {errors}")

    def _call_zai(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call Z.AI OpenAI-compatible API."""
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = self.zai_client.chat.completions.create(
            model=self.zai_model,
            messages=all_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        logger.info("llm_success", provider="zai", model=self.zai_model)
        return response.choices[0].message.content

    def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call Anthropic-compatible API."""
        response = self.anthropic_client.messages.create(
            model=self.anthropic_model,
            max_tokens=max_tokens,
            system=system or "You are a helpful assistant.",
            messages=messages,
        )
        logger.info("llm_success", provider="anthropic", model=self.anthropic_model)
        return response.content[0].text


# Global client instance
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
