"""Context Optimization for II Framework.

Implements context engineering patterns:
1. Observation Masking - Store verbose outputs, reference in context
2. Context Compaction - Summarize at 80% capacity
3. Progressive Disclosure - Load minimal info first (in registry.py)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.utils.logging import get_logger

logger = get_logger()

# Default thresholds
OBSERVATION_THRESHOLD = 1000  # chars before masking
COMPACTION_THRESHOLD = 0.8  # 80% context usage triggers compaction
MAX_CONTEXT_TOKENS = 128000  # Claude 3.5 Sonnet context window


@dataclass
class MaskedObservation:
    """Reference to stored observation."""
    ref_id: str
    summary: str

    def __str__(self) -> str:
        return f"[Ref:{self.ref_id}] {self.summary}"


async def mask_observation(
    output: str,
    skill_id: str,
    threshold: int = OBSERVATION_THRESHOLD,
    summarizer: Optional[callable] = None
) -> str:
    """Mask verbose output by storing in Firebase and returning reference.

    Args:
        output: Raw output to potentially mask
        skill_id: Source skill for tracking
        threshold: Character threshold for masking
        summarizer: Optional async function to summarize content

    Returns:
        Original output if under threshold, or masked reference
    """
    if len(output) <= threshold:
        return output

    # Generate summary
    if summarizer:
        summary = await summarizer(output, max_tokens=50)
    else:
        summary = _simple_summarize(output, max_chars=100)

    # Store in Firebase
    from src.services.firebase import store_observation
    ref_id = await store_observation(
        content=output,
        summary=summary,
        skill_id=skill_id
    )

    logger.info(
        "observation_masked",
        skill=skill_id,
        original_len=len(output),
        ref_id=ref_id
    )

    return f"[Ref:{ref_id}] Key: {summary}"


def _simple_summarize(text: str, max_chars: int = 100) -> str:
    """Simple text summarization without LLM."""
    # Take first sentence or truncate
    sentences = text.split('.')
    if sentences:
        first = sentences[0].strip()
        if len(first) <= max_chars:
            return first + "..."
    return text[:max_chars] + "..."


async def unmask_observation(ref_id: str) -> Optional[str]:
    """Retrieve full observation from reference ID."""
    from src.services.firebase import get_observation
    obs = await get_observation(ref_id)
    return obs.get("content") if obs else None


@dataclass
class CompactionResult:
    """Result of context compaction."""
    original_tokens: int
    compacted_tokens: int
    reduction_ratio: float
    compacted_content: str


async def should_compact(
    current_tokens: int,
    max_tokens: int = MAX_CONTEXT_TOKENS,
    threshold: float = COMPACTION_THRESHOLD
) -> bool:
    """Check if context compaction is needed."""
    ratio = current_tokens / max_tokens
    return ratio > threshold


async def compact_context(
    messages: List[Dict[str, str]],
    memory_content: str,
    summarizer: callable,
    keep_recent: int = 5
) -> CompactionResult:
    """Compact context by summarizing old messages and memory.

    Args:
        messages: Conversation history
        memory_content: Current memory section content
        summarizer: Async function to summarize text
        keep_recent: Number of recent messages to keep verbatim

    Returns:
        CompactionResult with compacted content
    """
    # Estimate original tokens (rough: 4 chars = 1 token)
    original_text = "\n".join(m.get("content", "") for m in messages)
    original_text += memory_content
    original_tokens = len(original_text) // 4

    # Split messages into old and recent
    old_messages = messages[:-keep_recent] if len(messages) > keep_recent else []
    recent_messages = messages[-keep_recent:] if len(messages) > keep_recent else messages

    compacted_parts = []

    # Summarize old messages
    if old_messages:
        old_text = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in old_messages
        )
        old_summary = await summarizer(
            f"Summarize this conversation history concisely:\n{old_text}",
            max_tokens=200
        )
        compacted_parts.append(f"[Previous conversation summary]: {old_summary}")

    # Keep recent messages verbatim
    for m in recent_messages:
        compacted_parts.append(f"{m['role']}: {m['content']}")

    # Compact memory if too long
    if len(memory_content) > 500:
        memory_summary = await summarizer(
            f"Summarize these learnings concisely:\n{memory_content}",
            max_tokens=150
        )
        compacted_parts.append(f"[Memory]: {memory_summary}")
    elif memory_content:
        compacted_parts.append(f"[Memory]: {memory_content}")

    compacted_content = "\n\n".join(compacted_parts)
    compacted_tokens = len(compacted_content) // 4

    reduction = 1 - (compacted_tokens / original_tokens) if original_tokens > 0 else 0

    logger.info(
        "context_compacted",
        original_tokens=original_tokens,
        compacted_tokens=compacted_tokens,
        reduction=f"{reduction:.1%}"
    )

    return CompactionResult(
        original_tokens=original_tokens,
        compacted_tokens=compacted_tokens,
        reduction_ratio=reduction,
        compacted_content=compacted_content
    )


async def compact_memory(
    memory_content: str,
    summarizer: callable,
    max_lines: int = 20
) -> str:
    """Compact memory section by summarizing if too long.

    Args:
        memory_content: Current memory content
        summarizer: Async summarization function
        max_lines: Maximum lines before compaction

    Returns:
        Compacted memory content
    """
    lines = memory_content.strip().split('\n')

    if len(lines) <= max_lines:
        return memory_content

    # Keep most recent entries, summarize old ones
    old_lines = lines[:-max_lines // 2]
    recent_lines = lines[-max_lines // 2:]

    old_text = "\n".join(old_lines)
    summary = await summarizer(
        f"Summarize these learnings into 3-5 bullet points:\n{old_text}",
        max_tokens=100
    )

    compacted = f"<!-- Compacted {datetime.now().strftime('%Y-%m-%d')} -->\n"
    compacted += f"[Historical]: {summary}\n\n"
    compacted += "[Recent]:\n" + "\n".join(recent_lines)

    return compacted


class ContextManager:
    """Manages context optimization throughout conversation.

    Usage:
        ctx = ContextManager(skill_id="planning")

        # When processing output
        masked = await ctx.maybe_mask(verbose_output)

        # Periodically check compaction
        if await ctx.should_compact(current_tokens):
            result = await ctx.compact(messages, memory)
    """

    def __init__(
        self,
        skill_id: str,
        max_tokens: int = MAX_CONTEXT_TOKENS,
        observation_threshold: int = OBSERVATION_THRESHOLD,
        compaction_threshold: float = COMPACTION_THRESHOLD
    ):
        self.skill_id = skill_id
        self.max_tokens = max_tokens
        self.observation_threshold = observation_threshold
        self.compaction_threshold = compaction_threshold
        self.logger = logger.bind(skill=skill_id)

    async def maybe_mask(
        self,
        output: str,
        summarizer: Optional[callable] = None
    ) -> str:
        """Mask output if it exceeds threshold."""
        return await mask_observation(
            output=output,
            skill_id=self.skill_id,
            threshold=self.observation_threshold,
            summarizer=summarizer
        )

    async def should_compact(self, current_tokens: int) -> bool:
        """Check if compaction is needed."""
        return await should_compact(
            current_tokens,
            self.max_tokens,
            self.compaction_threshold
        )

    async def compact(
        self,
        messages: List[Dict[str, str]],
        memory: str,
        summarizer: callable
    ) -> CompactionResult:
        """Perform context compaction."""
        return await compact_context(messages, memory, summarizer)

    async def unmask(self, ref_id: str) -> Optional[str]:
        """Retrieve masked observation."""
        return await unmask_observation(ref_id)
