"""LLM client wrapper using Anthropic-compatible API (ai4u.now)."""
import os
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger()


class LLMClient:
    """LLM client using Anthropic-compatible API."""

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.ai4u.now")
        self.model = os.environ.get("ANTHROPIC_MODEL", "kiro-claude-opus-4-5-agentic")
        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send chat completion request."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a helpful assistant.",
            messages=messages,
        )
        logger.info("llm_success", model=self.model)
        return response.content[0].text


# Global client instance
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
