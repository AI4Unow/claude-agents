"""Intent detection for semantic message routing.

Classifies messages into three intent types for routing:
- CHAT: Direct LLM response (greeting, simple question)
- SKILL: Route to specific skill via SkillRouter
- ORCHESTRATE: Multi-skill orchestrator execution
"""
import re
from typing import Literal, Optional

from src.utils.logging import get_logger

logger = get_logger()

IntentType = Literal["chat", "skill", "orchestrate"]

# Keywords indicating user wants a specific skill capability
SKILL_KEYWORDS = {
    # Research
    "research", "investigate", "deep dive", "find out about",
    # Design/Creative
    "design", "create image", "generate image", "draw", "poster", "logo",
    # Code
    "code", "write code", "function", "script",
    # Content
    "summarize", "translate", "rewrite", "convert",
    # Media
    "download video", "enhance image",
}

# Keywords indicating complex multi-step task
ORCHESTRATE_KEYWORDS = {
    "build", "develop", "implement", "architect", "create system",
    "plan", "design system", "set up", "configure",
    "refactor", "migrate", "integrate",
}

# Patterns for simple chat (bypass LLM)
CHAT_PATTERNS = [
    r"^(hi|hello|hey|thanks|thank you|ok|okay|bye|goodbye)[\s!?.]*$",
    r"^what (is|are|was|were) ",
    r"^(who|where|when|why|how) (is|are|was|were|do|does|did|can|could|would|should) ",
    r"^(yes|no|sure|nope|yep|yeah)[\s!?.]*$",
    r"^(define|explain|describe) \w+$",
]

INTENT_PROMPT = """Classify this message into ONE category:

CHAT: greeting, simple question, casual conversation, quick lookup, definition
SKILL: user wants specific capability (research, design, code, summarize, translate, image)
ORCHESTRATE: complex multi-step task, building something, planning, system development

Message: {message}

Reply with only one word: CHAT, SKILL, or ORCHESTRATE"""


def fast_intent_check(message: str) -> Optional[IntentType]:
    """Fast keyword-based intent detection (no LLM needed).

    Args:
        message: User message to classify

    Returns:
        Intent type if determined, None if needs LLM classification
    """
    msg_lower = message.lower()

    # Check chat patterns first (most common)
    for pattern in CHAT_PATTERNS:
        if re.match(pattern, msg_lower, re.IGNORECASE):
            return "chat"

    # Check orchestrate keywords (most specific)
    for keyword in ORCHESTRATE_KEYWORDS:
        if keyword in msg_lower:
            return "orchestrate"

    # Check skill keywords
    for keyword in SKILL_KEYWORDS:
        if keyword in msg_lower:
            return "skill"

    # Short questions are likely chat
    if len(message) < 60 and "?" in message:
        return "chat"

    return None  # Needs LLM classification


def classify_intent_sync(message: str) -> IntentType:
    """Classify message intent using Claude Haiku (sync).

    Args:
        message: User message to classify

    Returns:
        "chat", "skill", or "orchestrate"
    """
    # Fast path: keyword/pattern check
    fast_result = fast_intent_check(message)
    if fast_result:
        logger.debug("intent_fast_path", result=fast_result)
        return fast_result

    # LLM classification using Claude Haiku
    from src.services.llm import get_llm_client
    from src.core.resilience import claude_circuit, CircuitState

    # Skip LLM if circuit is open
    if claude_circuit.state == CircuitState.OPEN:
        logger.warning("intent_circuit_open_defaulting_chat")
        return "chat"

    try:
        client = get_llm_client()
        prompt = INTENT_PROMPT.format(message=message[:500])

        # Use Haiku for fast classification
        response = client.client.messages.create(
            model="kiro-claude-opus-4-5-agentic",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        if response.content:
            result = response.content[0].text.upper().strip()
            if "ORCHESTRATE" in result:
                logger.debug("intent_llm", result="orchestrate")
                return "orchestrate"
            if "SKILL" in result:
                logger.debug("intent_llm", result="skill")
                return "skill"

        logger.debug("intent_llm", result="chat")
        return "chat"

    except Exception as e:
        logger.error("classify_intent_error", error=str(e)[:100])
        return "chat"  # Default to chat on error


async def classify_intent(message: str) -> IntentType:
    """Async wrapper for intent classification.

    Args:
        message: User message to classify

    Returns:
        "chat", "skill", or "orchestrate"
    """
    import asyncio
    return await asyncio.to_thread(classify_intent_sync, message)
