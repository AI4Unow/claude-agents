"""LLM client mocks for testing."""
from typing import List, Dict, Optional, Any
from unittest.mock import MagicMock


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self):
        self.responses: List[str] = []
        self.call_count = 0
        self.client = MagicMock()

    def set_responses(self, responses: List[str]):
        """Queue responses for sequential calls."""
        self.responses = list(responses)

    def chat(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 1024
    ) -> str:
        """Return queued response or default."""
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return "Mock LLM response"

    def chat_with_image(
        self,
        image_base64: str,
        prompt: str,
        max_tokens: int = 1024
    ) -> str:
        """Return mock image analysis."""
        self.call_count += 1
        return "Mock image analysis response"


class MockComplexityClassifier:
    """Mock complexity classifier."""

    def __init__(self, default: str = "simple"):
        self.default = default
        self.overrides: Dict[str, str] = {}

    def classify(self, message: str) -> str:
        """Return complexity for message."""
        for keyword, complexity in self.overrides.items():
            if keyword.lower() in message.lower():
                return complexity
        return self.default

    def set_override(self, keyword: str, complexity: str):
        """Set keyword override."""
        self.overrides[keyword] = complexity
