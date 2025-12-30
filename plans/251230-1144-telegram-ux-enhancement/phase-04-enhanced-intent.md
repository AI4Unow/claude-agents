# Phase 04: Enhanced Intent Detection

**Priority:** P1 (Intelligence Layer)
**Effort:** Medium
**Impact:** High - Smarter skill routing without commands

---

## Objective

Upgrade intent detection to extract skill + parameters in one shot, using hybrid approach (semantic first, LLM for ambiguous).

## Current State

```python
# src/core/intent.py
def fast_intent_check(message) -> Optional[IntentType]:
    """Keyword-based, returns chat/skill/orchestrate"""

async def classify_intent(message) -> IntentType:
    """LLM-based when keywords fail"""
```

**Limitations:**
- Only returns intent type, not specific skill
- No parameter extraction
- Skill routing is separate step

## Target State

```python
# Single call returns:
IntentResult(
    intent="skill",
    skill="gemini-deep-research",
    params={"topic": "AI trends", "depth": "comprehensive"},
    confidence=0.85
)
```

## Implementation

### Task 1: Add IntentResult dataclass

**File:** `agents/src/core/intent.py`

```python
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class IntentResult:
    """Result from intent detection."""
    intent: IntentType  # "chat", "skill", "orchestrate"
    skill: Optional[str] = None  # Matched skill name
    params: Dict[str, str] = field(default_factory=dict)  # Extracted parameters
    confidence: float = 1.0  # 0.0-1.0 confidence score
    reasoning: str = ""  # Brief explanation (for debugging)

    @property
    def is_skill(self) -> bool:
        return self.intent == "skill" and self.skill is not None

    @property
    def needs_llm_fallback(self) -> bool:
        return self.confidence < 0.7
```

### Task 2: Add semantic skill matching

**File:** `agents/src/core/intent.py`

```python
async def semantic_skill_match(message: str, threshold: float = 0.7) -> Optional[IntentResult]:
    """Match message to skill using Qdrant semantic search.

    Args:
        message: User message
        threshold: Minimum similarity score

    Returns:
        IntentResult if high-confidence match found
    """
    from src.core.router import SkillRouter

    router = SkillRouter(min_score=threshold)
    matches = await router.route(message, limit=1)

    if not matches:
        return None

    best = matches[0]
    if best.score >= threshold:
        # Extract basic params from message
        params = extract_params_simple(message, best.skill_name)

        return IntentResult(
            intent="skill",
            skill=best.skill_name,
            params=params,
            confidence=best.score,
            reasoning=f"Semantic match: {best.description[:50]}"
        )

    return None


def extract_params_simple(message: str, skill_name: str) -> Dict[str, str]:
    """Simple parameter extraction based on skill type.

    For complex extraction, use LLM fallback.
    """
    params = {}

    # Common patterns
    if "research" in skill_name:
        # Extract topic after common prefixes
        prefixes = ["research", "find out about", "investigate", "learn about"]
        for prefix in prefixes:
            if prefix in message.lower():
                idx = message.lower().find(prefix) + len(prefix)
                topic = message[idx:].strip()
                if topic:
                    params["topic"] = topic
                break

    elif "code" in skill_name:
        # Check for language mentions
        languages = ["python", "javascript", "typescript", "go", "rust", "java"]
        for lang in languages:
            if lang in message.lower():
                params["language"] = lang
                break

    return params
```

### Task 3: Add LLM-based intent + params extraction

**File:** `agents/src/core/intent.py`

```python
INTENT_WITH_PARAMS_PROMPT = """Analyze this user message and extract intent, skill, and parameters.

User message: {message}

Available skills (pick one if applicable):
{skill_list}

Return JSON:
{{
  "intent": "chat|skill|orchestrate",
  "skill": "skill-name or null",
  "params": {{"key": "value"}} or {{}},
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Rules:
- "chat" = greeting, simple question, casual conversation
- "skill" = user wants specific capability (research, code, design, etc.)
- "orchestrate" = complex multi-step task
- Extract meaningful parameters (topic, language, style, etc.)
- Confidence reflects certainty of classification

JSON only, no markdown:"""


async def llm_classify_with_params(message: str) -> IntentResult:
    """Use LLM for intent classification with parameter extraction.

    Fallback when semantic matching has low confidence.
    """
    import json
    from src.services.llm import get_llm_client
    from src.core.resilience import claude_circuit, CircuitState
    from src.skills.registry import get_registry

    # Skip if circuit open
    if claude_circuit.state == CircuitState.OPEN:
        logger.warning("intent_llm_circuit_open")
        return IntentResult(intent="chat", confidence=0.5)

    # Get skill list for context
    registry = get_registry()
    skill_summaries = registry.discover()
    skill_list = "\n".join([
        f"- {s.name}: {s.description[:60]}"
        for s in skill_summaries[:30]  # Limit to reduce tokens
    ])

    prompt = INTENT_WITH_PARAMS_PROMPT.format(
        message=message[:500],
        skill_list=skill_list
    )

    try:
        client = get_llm_client()
        response = client.client.messages.create(
            model="kiro-claude-opus-4-5-agentic",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        if response.content:
            text = response.content[0].text.strip()
            # Clean up potential markdown
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            data = json.loads(text)
            return IntentResult(
                intent=data.get("intent", "chat"),
                skill=data.get("skill"),
                params=data.get("params", {}),
                confidence=data.get("confidence", 0.7),
                reasoning=data.get("reasoning", "")
            )

    except json.JSONDecodeError as e:
        logger.error("intent_json_parse_error", error=str(e)[:50])
    except Exception as e:
        logger.error("intent_llm_error", error=str(e)[:100])

    # Default to chat on error
    return IntentResult(intent="chat", confidence=0.5)
```

### Task 4: Add unified detection function

**File:** `agents/src/core/intent.py`

```python
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
        # Definitely chat (greeting, simple question)
        return IntentResult(intent="chat", confidence=0.95)

    if fast_result == "orchestrate":
        # Complex task detected
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

    # Step 3: LLM fallback for ambiguous
    if fast_result == "skill" or (semantic_result and semantic_result.confidence >= 0.5):
        # Likely skill but need LLM to confirm/extract params
        llm_result = await llm_classify_with_params(message)
        logger.debug(
            "intent_llm_fallback",
            intent=llm_result.intent,
            skill=llm_result.skill,
            confidence=llm_result.confidence
        )
        return llm_result

    # Step 4: Default to chat
    return IntentResult(intent="chat", confidence=0.6)
```

### Task 5: Update process_message to use new detection

**File:** `agents/main.py`

```python
# Replace existing intent detection in auto mode (around line 692)

if mode == "auto":
    from src.core.intent import detect_intent_with_params
    from src.core.router import parse_explicit_skill

    # Check explicit skill invocation first (/skill or @skill)
    explicit = parse_explicit_skill(text, get_registry())
    if explicit:
        skill_name, remaining_text = explicit
        await status_updater.update(f"⚡ Running {skill_name}...")
        result = await execute_skill_simple(skill_name, remaining_text, {"user": user})
        await status_updater.complete()
        return format_skill_result(skill_name, result, duration_ms)

    # Unified intent detection
    intent_result = await detect_intent_with_params(text)
    logger.info(
        "intent_detected",
        intent=intent_result.intent,
        skill=intent_result.skill,
        confidence=intent_result.confidence
    )

    if intent_result.is_skill:
        await status_updater.update(f"⚡ Running {intent_result.skill}...")
        result = await execute_skill_simple(
            intent_result.skill,
            text,  # Full message as task
            {"user": user, "params": intent_result.params}
        )
        await status_updater.complete()
        return format_skill_result(intent_result.skill, result, duration_ms)

    elif intent_result.intent == "orchestrate":
        await status_updater.update("🧠 Planning approach...")
        result = await execute_orchestrated(text, user, chat_id, progress_callback)
        await status_updater.complete()
        return result

    # Default: chat (agentic loop)
    await status_updater.update("💭 Thinking...")
    # ... existing agentic loop code ...
```

## Testing

```python
# tests/test_intent_enhanced.py
import pytest
from src.core.intent import (
    IntentResult,
    detect_intent_with_params,
    semantic_skill_match,
    extract_params_simple,
)

@pytest.mark.asyncio
async def test_greeting_is_chat():
    result = await detect_intent_with_params("Hello!")
    assert result.intent == "chat"
    assert result.confidence >= 0.9

@pytest.mark.asyncio
async def test_research_detects_skill():
    result = await detect_intent_with_params("Research AI trends for 2025")
    assert result.intent == "skill"
    assert "research" in result.skill
    assert result.params.get("topic")

@pytest.mark.asyncio
async def test_complex_task_orchestrate():
    result = await detect_intent_with_params(
        "Build a complete authentication system with OAuth and JWT"
    )
    assert result.intent == "orchestrate"

def test_extract_params_research():
    params = extract_params_simple("Research quantum computing", "gemini-deep-research")
    assert params.get("topic") == "quantum computing"

def test_extract_params_code():
    params = extract_params_simple("Write a Python function", "code-review")
    assert params.get("language") == "python"

def test_intent_result_properties():
    result = IntentResult(intent="skill", skill="test", confidence=0.6)
    assert result.is_skill
    assert result.needs_llm_fallback  # 0.6 < 0.7
```

## Acceptance Criteria

- [ ] Greetings/simple questions route to chat
- [ ] Research requests detect skill + extract topic
- [ ] Code requests detect skill + extract language
- [ ] Complex tasks route to orchestrator
- [ ] Low confidence triggers LLM fallback
- [ ] Parameters extracted and passed to skill
- [ ] Confidence score logged for monitoring

## Performance Considerations

- Semantic match: ~50-100ms (Qdrant)
- LLM fallback: ~500-1000ms (Claude)
- Fast path (keywords): <5ms

Target: 90% of requests handled without LLM fallback.

## Rollback

Revert to `classify_intent()` in process_message. Keep new functions (no harm if unused).
