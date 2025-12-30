"""Macro executor - Execute macros of different types."""
import time
from typing import Dict, Any
import json

from src.models.personalization import Macro
from src.services.user_macros import increment_use_count
from src.utils.logging import get_logger

logger = get_logger()

# Rate limiting: per-macro cooldown (seconds)
MACRO_COOLDOWN_SECONDS = 5
_last_execution: Dict[str, float] = {}  # macro_id -> timestamp


def _check_rate_limit(macro_id: str) -> tuple[bool, int]:
    """Check if macro can be executed (rate limiting).

    Returns:
        (is_allowed, seconds_until_reset)
    """
    now = time.time()
    last = _last_execution.get(macro_id, 0)
    elapsed = now - last

    if elapsed < MACRO_COOLDOWN_SECONDS:
        return False, int(MACRO_COOLDOWN_SECONDS - elapsed)

    return True, 0


def _record_execution(macro_id: str):
    """Record macro execution time."""
    _last_execution[macro_id] = time.time()

    # Cleanup old entries (keep last 100)
    if len(_last_execution) > 100:
        oldest = sorted(_last_execution.items(), key=lambda x: x[1])[:50]
        for k, _ in oldest:
            del _last_execution[k]


async def execute_macro(
    macro: Macro,
    user: Dict,
    chat_id: int
) -> str:
    """Execute a macro and return result.

    Args:
        macro: Macro to execute
        user: Telegram user dict
        chat_id: Telegram chat ID

    Returns:
        Execution result message
    """
    # Rate limit check
    allowed, reset_in = _check_rate_limit(macro.macro_id)
    if not allowed:
        return f"⏳ Macro cooldown. Try again in {reset_in}s."

    # Record execution and increment use count
    _record_execution(macro.macro_id)
    await increment_use_count(macro.user_id, macro.macro_id)

    if macro.action_type == "command":
        return await _execute_command(macro, user, chat_id)
    elif macro.action_type == "skill":
        return await _execute_skill(macro, user, chat_id)
    elif macro.action_type == "sequence":
        return await _execute_sequence(macro, user, chat_id)
    else:
        return f"Unknown macro type: {macro.action_type}"


async def _execute_command(macro: Macro, user: Dict, chat_id: int) -> str:
    """Execute command-type macro.

    For security, command macros are NOT executed directly on the server.
    Instead, they're formatted as a suggestion for the user to execute locally.
    """
    command = macro.action

    # Security: Don't execute dangerous commands
    dangerous = ["rm ", "sudo", "mkfs", "dd if=", ":()", "fork"]
    for d in dangerous:
        if d in command.lower():
            logger.warning("dangerous_command_blocked", command=command[:50])
            return f"⚠️ Command contains dangerous pattern and was blocked.\n\n<code>{command}</code>"

    # For now, just suggest the command
    # Future: Integration with local executor for trusted commands
    return f"""🔧 <b>Macro Triggered:</b> {macro.description or macro.trigger_phrases[0]}

<b>Command:</b>
<code>{command}</code>

<i>Copy and execute locally, or use a local skill for automated execution.</i>"""


async def _execute_skill(macro: Macro, user: Dict, chat_id: int) -> str:
    """Execute skill-type macro."""
    from main import execute_skill_simple

    # Parse skill and optional params
    parts = macro.action.split(" ", 1)
    skill_name = parts[0]
    task = parts[1] if len(parts) > 1 else ""

    try:
        result = await execute_skill_simple(skill_name, task, {"user": user})
        return f"""🎯 <b>Macro Triggered:</b> {macro.description or skill_name}

{result}"""
    except Exception as e:
        logger.error("macro_skill_error", skill=skill_name, error=str(e)[:50])
        return f"❌ Skill execution failed: {str(e)[:100]}"


async def _execute_sequence(macro: Macro, user: Dict, chat_id: int) -> str:
    """Execute sequence-type macro (multiple actions)."""
    try:
        # Parse sequence JSON
        sequence = json.loads(macro.action)

        if not isinstance(sequence, list):
            return "❌ Invalid sequence format. Expected array of actions."

        results = []

        for i, step in enumerate(sequence, 1):
            step_type = step.get("type", "command")
            step_action = step.get("action", "")

            if step_type == "skill":
                # Create temp macro for skill execution
                temp = Macro(
                    macro_id="temp",
                    user_id=macro.user_id,
                    trigger_phrases=[],
                    action_type="skill",
                    action=step_action
                )
                result = await _execute_skill(temp, user, chat_id)
                results.append(f"Step {i}: {result[:100]}...")

            elif step_type == "command":
                results.append(f"Step {i}: <code>{step_action}</code>")

            elif step_type == "wait":
                import asyncio
                seconds = min(step.get("seconds", 1), 10)  # Max 10 seconds
                await asyncio.sleep(seconds)
                results.append(f"Step {i}: Waited {seconds}s")

        return f"""🔗 <b>Sequence Executed:</b> {macro.description or 'Macro Sequence'}

{chr(10).join(results)}"""

    except json.JSONDecodeError:
        return "❌ Invalid sequence JSON format."
    except Exception as e:
        logger.error("macro_sequence_error", error=str(e)[:50])
        return f"❌ Sequence execution failed: {str(e)[:100]}"
