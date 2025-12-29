"""Complexity detection for intelligent message routing.

Classifies messages as SIMPLE or COMPLEX to route to appropriate handler:
- SIMPLE: Direct LLM response (fast)
- COMPLEX: Orchestrator with multi-skill execution
"""
import re
from typing import Literal

from src.utils.logging import get_logger

logger = get_logger()

ComplexityType = Literal["simple", "complex"]

# Keywords that indicate complex tasks (bypass classifier)
COMPLEX_KEYWORDS = {
    "plan", "build", "create", "implement", "design", "architect",
    "develop", "write code", "make a", "set up", "configure",
    "analyze", "review", "debug", "fix", "optimize", "refactor",
    "research", "compare", "evaluate", "summarize document"
}

# Patterns that indicate simple queries
SIMPLE_PATTERNS = [
    r"^(hi|hello|hey|thanks|thank you|ok|okay)[\s!?.]*$",
    r"^what (is|are|was|were) ",
    r"^(who|where|when|why|how) (is|are|was|were|do|does|did|can|could|would|should) ",
    r"^(translate|convert|define|explain) ",
    r"^(yes|no|sure|nope)[\s!?.]*$",
]

COMPLEXITY_PROMPT = """Classify this message as SIMPLE or COMPLEX.

SIMPLE: greeting, quick question, simple info lookup, single action, translation, casual chat
COMPLEX: multi-step task, planning needed, code/analysis required, multiple skills needed, building something

Message: {message}

Reply with only one word: SIMPLE or COMPLEX"""


def fast_keyword_check(message: str) -> ComplexityType | None:
    """Fast keyword-based complexity check (no LLM needed).

    Returns:
        "simple" or "complex" if determined, None if needs LLM classification
    """
    msg_lower = message.lower()

    # Check simple patterns first
    for pattern in SIMPLE_PATTERNS:
        if re.match(pattern, msg_lower, re.IGNORECASE):
            return "simple"

    # Check complex keywords
    for keyword in COMPLEX_KEYWORDS:
        if keyword in msg_lower:
            return "complex"

    # Check message length (short = likely simple)
    if len(message) < 50 and "?" in message:
        return "simple"

    return None  # Needs LLM classification


def classify_complexity_sync(message: str) -> ComplexityType:
    """Classify message complexity using Claude Haiku (sync).

    Args:
        message: User message to classify

    Returns:
        "simple" or "complex"
    """
    # Fast path: keyword check
    fast_result = fast_keyword_check(message)
    if fast_result:
        logger.debug("complexity_fast_path", result=fast_result)
        return fast_result

    # LLM classification using Claude Haiku via existing client
    from src.services.llm import get_llm_client
    from src.core.resilience import claude_circuit, CircuitState

    # Skip LLM if circuit is open
    if claude_circuit.state == CircuitState.OPEN:
        logger.warning("complexity_circuit_open_defaulting_simple")
        return "simple"

    try:
        client = get_llm_client()
        prompt = COMPLEXITY_PROMPT.format(message=message[:500])

        # Use Haiku for fast classification (sync call)
        response = client.client.messages.create(
            model="claude-4-5-haiku-latest",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        if response.content:
            result = response.content[0].text.upper().strip()
            if "COMPLEX" in result:
                logger.debug("complexity_llm", result="complex")
                return "complex"

        logger.debug("complexity_llm", result="simple")
        return "simple"

    except Exception as e:
        logger.error("classify_complexity_error", error=str(e)[:100])
        return "simple"  # Default to simple on error


async def classify_complexity(message: str) -> ComplexityType:
    """Async wrapper for complexity classification."""
    import asyncio
    return await asyncio.to_thread(classify_complexity_sync, message)
