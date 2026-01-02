"""Hybrid NLP parser for task extraction.

Combines LLM intent extraction with dateparser time normalization.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Literal
import re
import json

try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False

from src.services.llm import LLMClient
from src.utils.logging import get_logger

logger = get_logger()


# Security: LLM output validation limits
MAX_CONTENT_LENGTH = 500
MAX_TIME_EXPRESSION_LENGTH = 100
VALID_PRIORITIES = {"p1", "p2", "p3", "p4"}
VALID_CONTEXTS = {"@home", "@work", "@errands"}
VALID_INTENTS = {"task", "reminder", "query"}


@dataclass
class ParsedTask:
    """Result of task parsing."""
    content: str
    intent: Literal["task", "reminder", "query"]
    due_date: Optional[datetime] = None
    due_time: Optional[time] = None
    recurrence: Optional[str] = None
    priority: Optional[str] = None
    context: Optional[str] = None
    confidence: float = 1.0
    raw_time_str: Optional[str] = None  # For debugging


async def parse_task(
    user_input: str,
    current_time: datetime,
    timezone: str = "UTC"
) -> ParsedTask:
    """Hybrid parse: LLM for intent, dateparser for time.

    Args:
        user_input: User's natural language input
        current_time: Current datetime for relative time resolution
        timezone: User's timezone (default: UTC)

    Returns:
        ParsedTask with extracted fields

    Raises:
        ValueError: If LLM extraction fails
    """
    # Step 1: LLM extraction
    llm_result = await _llm_extract(user_input, current_time, timezone)

    # Step 2: dateparser normalization (if time string found)
    if llm_result.raw_time_str and HAS_DATEPARSER:
        parsed_dt = dateparser.parse(
            llm_result.raw_time_str,
            settings={
                'RELATIVE_BASE': current_time,
                'PREFER_DATES_FROM': 'future',
                'STRICT_PARSING': True,
                'TIMEZONE': timezone,
                'RETURN_AS_TIMEZONE_AWARE': True
            }
        )

        if parsed_dt:
            llm_result.due_date = parsed_dt
            # Only set time if it's not midnight (indicates explicit time)
            if parsed_dt.time() != time(0, 0):
                llm_result.due_time = parsed_dt.time()
        else:
            logger.warning(
                "dateparser_failed",
                raw_time_str=llm_result.raw_time_str,
                user_input=user_input[:50]
            )

    # Step 3: Recurrence pattern detection
    if llm_result.raw_time_str:
        llm_result.recurrence = _detect_recurrence(llm_result.raw_time_str)

    return llm_result


async def _llm_extract(
    user_input: str,
    current_time: datetime,
    timezone: str
) -> ParsedTask:
    """Extract task fields using LLM.

    Args:
        user_input: User's message
        current_time: Current datetime
        timezone: User's timezone

    Returns:
        ParsedTask with LLM-extracted fields
    """
    prompt = f"""You are a task parser. Current time: {current_time.isoformat()} ({timezone}).

Extract from the user message:
- task_content: The action to do (clean text without time/priority/context)
- time_expression: Raw time string if mentioned (e.g., "tomorrow 3pm", "next Friday", "in 2 hours")
- priority: p1/p2/p3/p4 if mentioned (p1=urgent, p4=low)
- context: @home/@work/@errands if mentioned
- intent: "task" (actionable item), "reminder" (notification only), or "query" (asking about tasks)

User message: "{user_input}"

Respond in JSON format:
{{
  "task_content": "...",
  "time_expression": "..." or null,
  "priority": "p1/p2/p3/p4" or null,
  "context": "@home/@work/@errands" or null,
  "intent": "task/reminder/query"
}}

IMPORTANT:
- Only extract time_expression if explicitly mentioned
- Do not infer priority unless keywords like "urgent", "important", "low priority" are present
- Return clean task_content without metadata"""

    try:
        llm = LLMClient()
        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,  # Deterministic extraction
            max_tokens=200
        )

        # Parse JSON response
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning("llm_json_parse_failed", error=str(e)[:50], response=response[:100])
            raise ValueError("Invalid JSON response from LLM")

        # Security: Validate and sanitize all LLM output fields
        task_content = data.get("task_content", user_input)
        if not isinstance(task_content, str):
            task_content = str(task_content)
        task_content = task_content.strip()[:MAX_CONTENT_LENGTH]

        # Validate time expression
        time_expression = data.get("time_expression")
        if time_expression:
            if not isinstance(time_expression, str):
                time_expression = None
            else:
                time_expression = time_expression.strip()[:MAX_TIME_EXPRESSION_LENGTH]

        # Validate priority - strict whitelist
        priority = data.get("priority")
        if priority:
            priority = str(priority).lower().strip()
            if priority not in VALID_PRIORITIES:
                priority = None

        # Validate context - strict whitelist
        context = data.get("context")
        if context:
            context = str(context).lower().strip()
            if context not in VALID_CONTEXTS:
                context = None

        # Validate intent - strict whitelist with fallback
        intent = data.get("intent", "task")
        if not isinstance(intent, str) or intent.lower().strip() not in VALID_INTENTS:
            intent = "task"
        else:
            intent = intent.lower().strip()

        # Build ParsedTask with validated fields
        return ParsedTask(
            content=task_content if task_content else user_input,
            intent=intent,
            raw_time_str=time_expression,
            priority=priority,
            context=context,
            confidence=0.9  # LLM extraction confidence
        )

    except Exception as e:
        logger.error("llm_extraction_failed", error=str(e), user_input=user_input[:50])
        # Fallback: return raw input as task
        return ParsedTask(
            content=user_input,
            intent="task",
            confidence=0.5  # Low confidence fallback
        )


def _detect_recurrence(time_str: str) -> Optional[str]:
    """Detect recurrence pattern and return RRULE string.

    Args:
        time_str: Time expression (e.g., "every Monday", "daily")

    Returns:
        RRULE string or None

    Examples:
        "every Monday" -> "FREQ=WEEKLY;BYDAY=MO"
        "daily" -> "FREQ=DAILY"
        "weekly" -> "FREQ=WEEKLY"
        "every weekday" -> "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    """
    time_lower = time_str.lower()

    # Daily patterns
    if re.search(r'\b(daily|every day|each day)\b', time_lower):
        return "FREQ=DAILY"

    # Weekly patterns
    if re.search(r'\b(weekly|every week)\b', time_lower):
        return "FREQ=WEEKLY"

    # Weekday patterns
    if re.search(r'\b(every weekday|weekdays)\b', time_lower):
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"

    # Specific day patterns
    day_map = {
        'monday': 'MO', 'tuesday': 'TU', 'wednesday': 'WE',
        'thursday': 'TH', 'friday': 'FR', 'saturday': 'SA', 'sunday': 'SU'
    }

    for day_name, day_code in day_map.items():
        if re.search(rf'\bevery {day_name}\b', time_lower):
            return f"FREQ=WEEKLY;BYDAY={day_code}"

    # Monthly patterns
    if re.search(r'\b(monthly|every month)\b', time_lower):
        return "FREQ=MONTHLY"

    # Yearly patterns
    if re.search(r'\b(yearly|annually|every year)\b', time_lower):
        return "FREQ=YEARLY"

    return None


def format_task_summary(task: ParsedTask) -> str:
    """Format ParsedTask as human-readable summary.

    Args:
        task: ParsedTask instance

    Returns:
        Formatted string for user confirmation
    """
    parts = [f"📋 {task.content}"]

    if task.due_date:
        if task.due_time:
            parts.append(f"⏰ {task.due_date.strftime('%Y-%m-%d')} at {task.due_time.strftime('%H:%M')}")
        else:
            parts.append(f"📅 {task.due_date.strftime('%Y-%m-%d')}")

    if task.recurrence:
        parts.append(f"🔁 {task.recurrence}")

    if task.priority:
        priority_emoji = {"p1": "🔴", "p2": "🟡", "p3": "🟢", "p4": "⚪"}
        parts.append(f"{priority_emoji.get(task.priority, '')} {task.priority.upper()}")

    if task.context:
        parts.append(f"📍 {task.context}")

    if task.confidence < 0.8:
        parts.append(f"⚠️ Low confidence ({task.confidence:.0%})")

    return "\n".join(parts)
