"""Task Extraction - Extract actionable tasks from natural conversation.

Uses pattern matching + LLM validation to identify tasks in conversational text.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from src.utils.logging import get_logger

logger = get_logger()


@dataclass
class ExtractedTask:
    """Task extracted from conversation."""
    content: str
    confidence: float  # 0.0-1.0
    source_text: str
    trigger_words: List[str]


class TaskExtractor:
    """Extract actionable tasks from natural conversation."""

    TRIGGER_PATTERNS = [
        r"(?:I |we )?(?:need to|have to|should|must|gotta) (.+)",
        r"(?:don't forget to|remember to) (.+)",
        r"(?:remind me to|remind me about) (.+)",
        r"(?:I'll|i'll|I will) (.+) (?:later|tomorrow|next|soon)",
        r"(?:todo|to do|to-do):?\s*(.+)",
        r"(?:make sure to|be sure to) (.+)",
        r"(?:don't let me forget|can't forget) (.+)",
    ]

    EXCLUSION_PATTERNS = [
        r"(?:I think|maybe|perhaps|possibly|might)",
        r"(?:would be nice|could be|should we)",
        r"\?$",  # Questions not tasks
        r"(?:if |when )",  # Conditional statements
    ]

    # High-signal action verbs
    ACTION_VERBS = {
        "call", "email", "send", "write", "review", "finish", "complete",
        "schedule", "book", "buy", "order", "pay", "submit", "deploy",
        "meet", "discuss", "check", "update", "create", "delete", "fix"
    }

    def __init__(self):
        self.compiled_triggers = [re.compile(p, re.IGNORECASE) for p in self.TRIGGER_PATTERNS]
        self.compiled_exclusions = [re.compile(p, re.IGNORECASE) for p in self.EXCLUSION_PATTERNS]

    async def extract_from_message(
        self,
        message: str,
        current_time: Optional[datetime] = None
    ) -> List[ExtractedTask]:
        """Extract potential tasks from conversational message.

        Args:
            message: User message text
            current_time: Current timestamp for context

        Returns:
            List of ExtractedTask with confidence scores
        """
        if not message or len(message) < 5:
            return []

        current_time = current_time or datetime.now()

        # Quick pattern match first
        pattern_matches = self._pattern_extract(message)

        # If patterns found, validate with LLM
        if pattern_matches:
            validated = await self._llm_validate(pattern_matches, message)
            return [t for t in validated if t.confidence >= 0.7]

        # No patterns but might be implicit task
        if self._might_be_task(message):
            llm_extract = await self._llm_extract(message, current_time)
            return [t for t in llm_extract if t.confidence >= 0.8]

        return []

    def _pattern_extract(self, message: str) -> List[dict]:
        """Fast regex extraction of potential tasks.

        Args:
            message: Message text

        Returns:
            List of candidate dicts with 'content' and 'trigger'
        """
        matches = []

        for pattern in self.compiled_triggers:
            for match in pattern.finditer(message):
                candidate = match.group(1).strip()

                if not self._should_exclude(candidate):
                    matches.append({
                        "content": candidate,
                        "trigger": match.group(0),
                        "source": message
                    })

        logger.debug("pattern_extraction", count=len(matches))
        return matches

    def _should_exclude(self, text: str) -> bool:
        """Check exclusion patterns.

        Args:
            text: Text to check

        Returns:
            True if should be excluded
        """
        for pattern in self.compiled_exclusions:
            if pattern.search(text):
                return True
        return False

    def _might_be_task(self, message: str) -> bool:
        """Heuristic check if message might contain implicit task.

        Args:
            message: Message text

        Returns:
            True if worth LLM extraction attempt
        """
        # Check for action verbs
        words = message.lower().split()
        has_action_verb = any(verb in words for verb in self.ACTION_VERBS)

        # Check for imperative mood (starts with verb)
        starts_with_verb = len(words) > 0 and words[0].lower() in self.ACTION_VERBS

        # Check length (very short unlikely to be task)
        long_enough = len(message) > 10

        return (has_action_verb or starts_with_verb) and long_enough

    async def _llm_validate(
        self,
        candidates: List[dict],
        context: str
    ) -> List[ExtractedTask]:
        """LLM validates and scores extracted candidates.

        Args:
            candidates: List of candidate dicts
            context: Full message context

        Returns:
            List of validated ExtractedTask
        """
        from src.services.llm import generate_with_cache

        prompt = f"""Validate these potential tasks extracted from conversation:
Context: "{context}"

Candidates:
{chr(10).join(f"- {c['content']}" for c in candidates)}

For each candidate, return JSON array:
[
  {{
    "is_actionable": true/false,
    "confidence": 0.0-1.0,
    "cleaned_task": "refined task description",
    "reason": "why this is/isn't a task"
  }}
]

Rules:
- is_actionable: true only if clear action to take
- confidence: high (0.9+) if explicit, medium (0.7-0.8) if implied
- cleaned_task: concise, actionable phrasing
"""

        try:
            response = await generate_with_cache(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.2
            )

            # Parse JSON response
            import json
            result_text = response.get("content", "[]")

            # Extract JSON from markdown if needed
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            results = json.loads(result_text.strip())

            validated = []
            for i, result in enumerate(results):
                if i >= len(candidates):
                    break

                if result.get("is_actionable"):
                    validated.append(ExtractedTask(
                        content=result.get("cleaned_task", candidates[i]["content"]),
                        confidence=result.get("confidence", 0.7),
                        source_text=candidates[i]["source"],
                        trigger_words=[candidates[i]["trigger"]]
                    ))

            logger.info("llm_validation_complete", validated=len(validated), total=len(candidates))
            return validated

        except Exception as e:
            logger.error("llm_validation_error", error=str(e)[:100])
            # Fallback: return candidates with medium confidence
            return [
                ExtractedTask(
                    content=c["content"],
                    confidence=0.7,
                    source_text=c["source"],
                    trigger_words=[c["trigger"]]
                )
                for c in candidates
            ]

    async def _llm_extract(
        self,
        message: str,
        current_time: datetime
    ) -> List[ExtractedTask]:
        """LLM extraction for implicit tasks without clear patterns.

        Args:
            message: Message text
            current_time: Current timestamp

        Returns:
            List of ExtractedTask
        """
        from src.services.llm import generate_with_cache

        prompt = f"""Extract actionable tasks from this message. Current time: {current_time.isoformat()}

Message: "{message}"

Return JSON array of tasks found (or empty array if none):
[
  {{
    "task": "actionable task description",
    "confidence": 0.0-1.0,
    "reasoning": "why this is a task"
  }}
]

Only extract if confidence >= 0.8. Look for:
- Explicit intentions ("I need to...", "I'll...")
- Implicit commitments ("Let me...", "Going to...")
- Action items in context

Do NOT extract:
- Questions
- Hypotheticals
- Past actions
- General statements
"""

        try:
            response = await generate_with_cache(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2
            )

            # Parse JSON response
            import json
            result_text = response.get("content", "[]")

            # Extract JSON from markdown
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            results = json.loads(result_text.strip())

            extracted = [
                ExtractedTask(
                    content=r["task"],
                    confidence=r.get("confidence", 0.8),
                    source_text=message,
                    trigger_words=["implicit"]
                )
                for r in results
                if r.get("confidence", 0) >= 0.8
            ]

            logger.info("llm_extraction_complete", extracted=len(extracted))
            return extracted

        except Exception as e:
            logger.error("llm_extraction_error", error=str(e)[:100])
            return []
