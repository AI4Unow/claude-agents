"""LLM client wrapper using Anthropic-compatible API (ai4u.now)."""
import os
from typing import List, Dict, Optional

from src.utils.logging import get_logger
from src.core.resilience import claude_circuit, CircuitOpenError, CircuitState

logger = get_logger()


class LLMClient:
    """LLM client using Anthropic-compatible API."""

    def __init__(self):
        # Use `or` to handle empty strings from env vars
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "") or ""
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "") or "https://api.ai4u.now"
        self.model = os.environ.get("ANTHROPIC_MODEL", "") or "kiro-claude-opus-4-5-agentic"
        self._client = None

        # Log initialization for cold start debugging
        logger.info("llm_client_init", model=self.model, base_url=self.base_url[:30] if self.base_url else "none")

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers={"x-api-key": self.api_key},
            )
        return self._client

    def chat(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        tools: Optional[List[dict]] = None,
        timeout: float = 60.0,
        model: Optional[str] = None,
    ):
        """Send chat completion request.

        Args:
            messages: Conversation messages
            system: System prompt
            max_tokens: Max response tokens
            temperature: Sampling temperature
            tools: Optional list of tool definitions for tool_use
            timeout: Request timeout in seconds
            model: Optional model override (default: uses self.model)

        Returns:
            Full Message object if tools provided, else text string

        Raises:
            CircuitOpenError: If Claude API circuit is open
        """
        # Check circuit state before calling
        if claude_circuit.state == CircuitState.OPEN:
            cooldown = claude_circuit._cooldown_remaining()
            logger.warning("claude_circuit_open", cooldown_remaining=cooldown)
            raise CircuitOpenError("claude_api", cooldown)

        # Use provided model or default
        effective_model = model or self.model

        kwargs = {
            "model": effective_model,
            "max_tokens": max_tokens,
            "system": system or "Your name is AI4U.now Bot. You were created by the AI4U.now team. You are a unified AI assistant.",
            "messages": messages,
            "timeout": timeout,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.messages.create(**kwargs)
            claude_circuit._record_success()
            logger.info("llm_success", model=effective_model)

            # Return full response if tools (for tool_use inspection), else just text
            if tools:
                return response
            return response.content[0].text

        except Exception as e:
            claude_circuit._record_failure(e)
            logger.error("llm_error", error=str(e)[:100])
            raise

    def chat_with_image(
        self,
        image_base64: str,
        prompt: str,
        media_type: str = "image/jpeg",
        max_tokens: int = 1024
    ) -> str:
        """Send image to Claude Vision for analysis.

        Args:
            image_base64: Base64 encoded image
            prompt: User prompt about the image
            media_type: Image MIME type (default: image/jpeg)
            max_tokens: Max response tokens

        Returns:
            Text response from Claude Vision
        """
        # Check circuit state before calling
        if claude_circuit.state == CircuitState.OPEN:
            cooldown = claude_circuit._cooldown_remaining()
            logger.warning("claude_circuit_open", cooldown_remaining=cooldown)
            raise CircuitOpenError("claude_api", cooldown)

        try:
            response = self.client.messages.create(
                model="kiro-claude-opus-4-5-agentic",  # Use Opus for vision
                max_tokens=max_tokens,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )
            claude_circuit._record_success()
            logger.info("vision_success", model="kiro-claude-opus-4-5-agentic")
            return response.content[0].text

        except Exception as e:
            claude_circuit._record_failure(e)
            logger.error("vision_error", error=str(e)[:100])
            raise


# Global client instance
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
