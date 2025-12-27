"""LLM client wrapper for Z.AI GLM-4.7 (OpenAI-compatible API)."""
import os
from typing import List, Dict, Optional
from openai import OpenAI
import structlog

logger = structlog.get_logger()


class LLMClient:
    """Client for Z.AI GLM-4.7 using OpenAI-compatible API."""

    def __init__(self):
        self.api_key = os.environ.get("ZAI_API_KEY", "")
        self.base_url = os.environ.get("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
        self.model = os.environ.get("ZAI_MODEL", "glm-4.7")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send chat completion request to LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLM response text
        """
        all_messages = []

        if system:
            all_messages.append({"role": "system", "content": system})

        all_messages.extend(messages)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=all_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("llm_error", error=str(e), model=self.model)
            raise


# Global client instance
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
