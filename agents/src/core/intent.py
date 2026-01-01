"""Intent detection for semantic message routing.

Classifies messages into three intent types for routing:
- CHAT: Direct LLM response (greeting, simple question)
- SKILL: Route to specific skill via SkillRouter
- ORCHESTRATE: Multi-skill orchestrator execution
"""
import re
from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

from src.config import FAST_MODEL
from src.utils.logging import get_logger

logger = get_logger()

IntentType = Literal["chat", "skill", "orchestrate"]


@dataclass
class IntentResult:
    """Result from enhanced intent detection."""
    intent: IntentType
    skill: Optional[str] = None
    params: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    reasoning: str = ""

    @property
    def is_skill(self) -> bool:
        return self.intent == "skill" and self.skill is not None

    @property
    def needs_llm_fallback(self) -> bool:
        return self.confidence < 0.7

# Keywords indicating user wants a specific skill capability
SKILL_KEYWORDS = {
    # Research (deep research, not web search)
    "research", "investigate", "deep dive", "find out about", "look up",
    "analyze", "study", "explore",
    # Design/Creative
    "design", "create image", "generate image", "draw", "poster", "logo",
    "mockup", "wireframe", "ui design", "ux design", "banner",
    # Code
    "code", "write code", "function", "script", "program", "debug",
    "fix code", "refactor", "implement", "algorithm",
    # Content
    "summarize", "translate", "rewrite", "convert", "paraphrase",
    "proofread", "edit text", "format", "outline",
    # Media
    "download video", "enhance image", "compress", "resize",
    "extract audio", "convert video",
    # Data
    "analyze data", "chart", "graph", "statistics", "parse",
}

# Keywords that should use CHAT intent (require tool access via agentic loop)
CHAT_WITH_TOOLS_KEYWORDS = {
    "search the web", "web search", "search online", "look up online",
    "find on the web", "google", "search for", "current news",
    "latest news", "today's news", "weather", "stock price",
    "current price", "what's happening", "recent events",
}

# Keywords indicating complex multi-step task
ORCHESTRATE_KEYWORDS = {
    "build", "develop", "implement", "architect", "create system",
    "plan", "design system", "set up", "configure",
    "refactor", "migrate", "integrate",
    "deploy", "automate", "pipeline", "workflow",
    "full stack", "end to end", "complete solution",
}

# Patterns for simple chat (bypass LLM) - compiled for performance
_CHAT_PATTERNS_RAW = [
    r"^(hi|hello|hey|thanks|thank you|ok|okay|bye|goodbye|gm|gn|gg)[\s!?.]*$",
    r"^what (is|are|was|were) ",
    r"^(who|where|when|why|how) (is|are|was|were|do|does|did|can|could|would|should) ",
    r"^(yes|no|sure|nope|yep|yeah|nah)[\s!?.]*$",
    r"^(define|explain|describe|tell me about) \w+",
    r"^(can you|could you|would you|please) (help|tell|explain|show)",
    r"^(what|how) (do|does|can|should) (i|you|we|they)",
    r"^(is|are|was|were|do|does|did|can|will|would|should) ",
]
CHAT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _CHAT_PATTERNS_RAW]

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

    # Check CHAT_WITH_TOOLS first (web search, weather, etc.)
    # These need CHAT intent to get tool access via agentic loop
    for keyword in CHAT_WITH_TOOLS_KEYWORDS:
        if keyword in msg_lower:
            logger.debug("intent_needs_tools", keyword=keyword)
            return "chat"

    # Check chat patterns (most common) - uses pre-compiled regex
    for pattern in CHAT_PATTERNS:
        if pattern.match(msg_lower):
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

        # Use fast model for classification
        response = client.client.messages.create(
            model=FAST_MODEL,
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


def extract_params_simple(message: str, skill_name: str) -> Dict[str, str]:
    """Simple parameter extraction based on skill type.

    Args:
        message: User message
        skill_name: Detected skill name

    Returns:
        Extracted parameters dict
    """
    params = {}
    msg_lower = message.lower()

    # Research skills - extract topic
    if "research" in skill_name.lower():
        prefixes = ["research", "find out about", "investigate", "learn about"]
        for prefix in prefixes:
            if prefix in msg_lower:
                idx = msg_lower.find(prefix) + len(prefix)
                topic = message[idx:].strip()
                if topic:
                    params["topic"] = topic[:200]
                break

    # Code skills - detect language
    elif "code" in skill_name.lower():
        languages = ["python", "javascript", "typescript", "go", "rust", "java"]
        for lang in languages:
            if lang in msg_lower:
                params["language"] = lang
                break

    return params


async def semantic_skill_match(message: str, threshold: float = 0.7) -> Optional[IntentResult]:
    """Match message to skill using Qdrant semantic search.

    Args:
        message: User message
        threshold: Minimum similarity score

    Returns:
        IntentResult if high-confidence match found
    """
    from src.core.router import SkillRouter

    try:
        router = SkillRouter(min_score=threshold)
        matches = await router.route(message, limit=1)

        if not matches:
            return None

        best = matches[0]
        if best.score >= threshold:
            params = extract_params_simple(message, best.skill_name)
            return IntentResult(
                intent="skill",
                skill=best.skill_name,
                params=params,
                confidence=best.score,
                reasoning=f"Semantic match: {best.description[:50]}"
            )
    except Exception as e:
        logger.error("semantic_skill_match_error", error=str(e)[:50])

    return None


async def detect_intent_with_params(
    message: str,
    semantic_threshold: float = 0.7,
    llm_fallback_threshold: float = 0.7
) -> IntentResult:
    """Unified intent detection with skill and parameter extraction.

    Strategy:
    1. Fast keyword check for obvious intents
    2. Semantic skill matching (Qdrant)
    3. LLM fallback for ambiguous cases

    Args:
        message: User message
        semantic_threshold: Min score for semantic match
        llm_fallback_threshold: Trigger LLM if below this

    Returns:
        IntentResult with intent, skill, params, confidence
    """
    # Step 1: Fast keyword check
    fast_result = fast_intent_check(message)
    if fast_result == "chat":
        return IntentResult(intent="chat", confidence=0.95)

    if fast_result == "orchestrate":
        return IntentResult(
            intent="orchestrate",
            confidence=0.85,
            reasoning="Complex task keywords detected"
        )

    # Step 2: Semantic skill matching
    semantic_result = await semantic_skill_match(message, semantic_threshold)

    if semantic_result and semantic_result.confidence >= llm_fallback_threshold:
        logger.debug(
            "intent_semantic_match",
            skill=semantic_result.skill,
            confidence=semantic_result.confidence
        )
        return semantic_result

    # Step 3: If skill keywords detected but no semantic match
    if fast_result == "skill":
        # Try lower threshold
        lower_match = await semantic_skill_match(message, threshold=0.5)
        if lower_match:
            return lower_match

        # Default skill intent without specific skill
        return IntentResult(
            intent="skill",
            confidence=0.6,
            reasoning="Skill keywords detected"
        )

    # Step 4: Default to chat
    return IntentResult(intent="chat", confidence=0.6)

