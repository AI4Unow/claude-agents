# Phase 3: Macros & NLU

**Duration:** 2-3 days
**Dependencies:** Phase 1, Phase 2
**Output:** Macro CRUD, NLU detection, macro execution, /macro commands

## Objectives

1. Implement macro CRUD in Firebase
2. Build NLU-based macro detection (exact match + semantic)
3. Implement macro executor for different action types
4. Add `/macro` Telegram commands
5. Integrate macro detection into message flow

## Files to Create/Modify

### 1. `src/services/user_macros.py`

Macro CRUD and NLU detection.

```python
"""User macros service - CRUD and NLU detection."""
from datetime import datetime, timezone
from typing import Optional, List, Dict
import uuid

from src.models.personalization import Macro, MacroActionType
from src.services.firebase import get_db, firestore
from src.services.embeddings import get_embedding
from src.utils.logging import get_logger

logger = get_logger()

# Semantic similarity threshold
SIMILARITY_THRESHOLD = 0.85
MAX_MACROS_PER_USER = 20


async def get_macros(user_id: int) -> List[Macro]:
    """Get all macros for user."""
    try:
        db = get_db()
        docs = db.collection("user_macros").document(str(user_id)) \
            .collection("macros").limit(MAX_MACROS_PER_USER).get()

        return [Macro.from_dict({**doc.to_dict(), "macro_id": doc.id})
                for doc in docs]
    except Exception as e:
        logger.error("get_macros_error", user_id=user_id, error=str(e)[:50])
        return []


async def get_macro(user_id: int, macro_id: str) -> Optional[Macro]:
    """Get specific macro by ID."""
    try:
        db = get_db()
        doc = db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).get()

        if doc.exists:
            return Macro.from_dict({**doc.to_dict(), "macro_id": doc.id})
        return None
    except Exception as e:
        logger.error("get_macro_error", error=str(e)[:50])
        return None


async def create_macro(
    user_id: int,
    trigger_phrases: List[str],
    action_type: MacroActionType,
    action: str,
    description: Optional[str] = None
) -> Optional[Macro]:
    """Create a new macro.

    Args:
        user_id: Telegram user ID
        trigger_phrases: List of phrases that trigger this macro
        action_type: command, skill, or sequence
        action: The action to execute
        description: Optional description

    Returns:
        Created Macro or None if limit reached
    """
    # Check limit
    existing = await get_macros(user_id)
    if len(existing) >= MAX_MACROS_PER_USER:
        logger.warning("macro_limit_reached", user_id=user_id)
        return None

    # Check for duplicate triggers
    existing_triggers = set()
    for m in existing:
        existing_triggers.update(t.lower() for t in m.trigger_phrases)

    for phrase in trigger_phrases:
        if phrase.lower() in existing_triggers:
            logger.warning("duplicate_trigger", user_id=user_id, phrase=phrase)
            return None

    macro_id = str(uuid.uuid4())[:8]
    macro = Macro(
        macro_id=macro_id,
        user_id=user_id,
        trigger_phrases=[t.strip().lower() for t in trigger_phrases],
        action_type=action_type,
        action=action,
        description=description,
        created_at=datetime.now(timezone.utc),
        use_count=0
    )

    try:
        db = get_db()
        db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).set(macro.to_dict())

        logger.info("macro_created", user_id=user_id, macro_id=macro_id)
        return macro
    except Exception as e:
        logger.error("create_macro_error", error=str(e)[:50])
        return None


async def delete_macro(user_id: int, macro_id: str) -> bool:
    """Delete a macro."""
    try:
        db = get_db()
        db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).delete()

        logger.info("macro_deleted", user_id=user_id, macro_id=macro_id)
        return True
    except Exception as e:
        logger.error("delete_macro_error", error=str(e)[:50])
        return False


async def increment_use_count(user_id: int, macro_id: str) -> None:
    """Increment macro use count."""
    try:
        db = get_db()
        db.collection("user_macros").document(str(user_id)) \
            .collection("macros").document(macro_id).update({
                "use_count": firestore.Increment(1)
            })
    except Exception as e:
        logger.error("increment_use_count_error", error=str(e)[:50])


async def detect_macro(user_id: int, message: str) -> Optional[Macro]:
    """Detect if message triggers a personal macro.

    Uses two-phase matching:
    1. Exact match (fast)
    2. Semantic similarity (if no exact match)

    Args:
        user_id: Telegram user ID
        message: User's message text

    Returns:
        Matched Macro or None
    """
    macros = await get_macros(user_id)
    if not macros:
        return None

    message_lower = message.lower().strip()

    # Phase 1: Exact match
    for macro in macros:
        for trigger in macro.trigger_phrases:
            if message_lower == trigger.lower():
                logger.info("macro_exact_match", user_id=user_id, trigger=trigger)
                return macro

    # Phase 2: Semantic similarity (only for short messages)
    if len(message_lower.split()) <= 5:
        return await _semantic_match(message_lower, macros)

    return None


async def _semantic_match(message: str, macros: List[Macro]) -> Optional[Macro]:
    """Find macro via semantic similarity."""
    try:
        message_embedding = get_embedding(message)

        best_match = None
        best_score = 0.0

        for macro in macros:
            for trigger in macro.trigger_phrases:
                trigger_embedding = get_embedding(trigger)
                score = _cosine_similarity(message_embedding, trigger_embedding)

                if score > best_score:
                    best_score = score
                    best_match = macro

        if best_score >= SIMILARITY_THRESHOLD:
            logger.info("macro_semantic_match", score=best_score, trigger=best_match.trigger_phrases[0])
            return best_match

        return None

    except Exception as e:
        logger.error("semantic_match_error", error=str(e)[:50])
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def format_macro_display(macro: Macro) -> str:
    """Format macro for Telegram display."""
    triggers = ", ".join(f'"{t}"' for t in macro.trigger_phrases)
    return f"""<b>Macro:</b> {macro.macro_id}
<b>Triggers:</b> {triggers}
<b>Type:</b> {macro.action_type}
<b>Action:</b> <code>{macro.action}</code>
<b>Uses:</b> {macro.use_count}"""


def format_macros_list(macros: List[Macro]) -> str:
    """Format macro list for Telegram display."""
    if not macros:
        return "<i>No macros defined. Use /macro add to create one.</i>"

    lines = ["<b>Your Macros</b>\n"]

    for m in macros:
        triggers = ", ".join(f'"{t}"' for t in m.trigger_phrases[:2])
        if len(m.trigger_phrases) > 2:
            triggers += f" (+{len(m.trigger_phrases) - 2})"
        lines.append(f"• <code>{m.macro_id}</code>: {triggers} → {m.action_type}")

    lines.append(f"\n<i>Use /macro show <id> for details</i>")
    return "\n".join(lines)
```

### 2. `src/core/macro_executor.py`

Execute different macro types.

```python
"""Macro executor - Execute macros of different types."""
from typing import Dict, Any
import json

from src.models.personalization import Macro
from src.services.user_macros import increment_use_count
from src.utils.logging import get_logger

logger = get_logger()


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
    # Increment use count
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
    dangerous = ["rm ", "sudo", "mkfs", "dd if=", ":(){", "fork"]
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
```

### 3. Update `main.py` - Add /macro Commands

Add /macro command handlers.

```python
# Add to handle_command() after existing commands:

    if cmd == "/macro":
        return await handle_macro_command(args, user, chat_id)


# Add new command handler:

async def handle_macro_command(args: str, user: dict, chat_id: int) -> str:
    """Handle /macro commands."""
    from src.services.user_macros import (
        get_macros, get_macro, create_macro, delete_macro,
        format_macros_list, format_macro_display
    )

    user_id = user.get("id")
    parts = args.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    subargs = parts[1] if len(parts) > 1 else ""

    # /macro (list all)
    if not subcmd or subcmd == "list":
        macros = await get_macros(user_id)
        return format_macros_list(macros)

    # /macro show <id>
    if subcmd == "show":
        if not subargs:
            return "Usage: /macro show <macro_id>"
        macro = await get_macro(user_id, subargs)
        if not macro:
            return f"Macro not found: {subargs}"
        return format_macro_display(macro)

    # /macro add "trigger" -> action
    if subcmd == "add":
        return await _handle_macro_add(user_id, subargs)

    # /macro remove <id>
    if subcmd in ["remove", "delete", "rm"]:
        if not subargs:
            return "Usage: /macro remove <macro_id>"
        success = await delete_macro(user_id, subargs)
        if success:
            return f"Macro deleted: {subargs}"
        return f"Failed to delete macro: {subargs}"

    # /macro help
    if subcmd == "help":
        return """<b>Macro Commands</b>

/macro - List all macros
/macro show <id> - Show macro details
/macro add "trigger" -> action - Create macro
/macro remove <id> - Delete macro

<b>Examples:</b>
<code>/macro add "deploy" -> modal deploy agents/main.py</code>
<code>/macro add "test" -> skill:research test frameworks</code>
<code>/macro add "ship it", "deploy now" -> modal deploy</code>

<b>Action Types:</b>
• command - Shell command (shown, not executed)
• skill - Invoke a skill (use <code>skill:name params</code>)
• sequence - JSON array of steps"""

    return f"Unknown subcommand: {subcmd}. Use /macro help"


async def _handle_macro_add(user_id: int, args: str) -> str:
    """Parse and create macro from add command."""
    from src.services.user_macros import create_macro

    # Parse: "trigger1", "trigger2" -> action
    if "->" not in args:
        return """Invalid format. Use:
<code>/macro add "trigger" -> action</code>

Examples:
<code>/macro add "deploy" -> modal deploy agents/main.py</code>
<code>/macro add "test" -> skill:research test frameworks</code>"""

    trigger_part, action = args.split("->", 1)
    action = action.strip()

    # Parse triggers (quoted strings or comma-separated)
    import re
    triggers = re.findall(r'"([^"]+)"', trigger_part)
    if not triggers:
        # Try comma-separated without quotes
        triggers = [t.strip() for t in trigger_part.split(",") if t.strip()]

    if not triggers:
        return "No triggers found. Use quotes: <code>\"trigger phrase\"</code>"

    # Determine action type
    if action.startswith("skill:"):
        action_type = "skill"
        action = action[6:].strip()
    elif action.startswith("["):
        action_type = "sequence"
    else:
        action_type = "command"

    macro = await create_macro(
        user_id=user_id,
        trigger_phrases=triggers,
        action_type=action_type,
        action=action
    )

    if not macro:
        return "Failed to create macro. Check if trigger already exists or limit reached (max 20)."

    return f"""✅ <b>Macro Created</b>

<b>ID:</b> {macro.macro_id}
<b>Triggers:</b> {', '.join(f'"{t}"' for t in macro.trigger_phrases)}
<b>Type:</b> {macro.action_type}
<b>Action:</b> <code>{macro.action}</code>

Say any trigger phrase to execute!"""
```

### 4. Update `main.py:process_message()` - Integrate Macro Detection

Add macro detection before normal processing.

```python
# Modify process_message() - add after loading personal context:

async def process_message(...) -> str:
    # ... existing setup code ...

    # Load personalization context
    personal_ctx = await load_personal_context(user_id)

    # CHECK MACRO TRIGGER FIRST (before any other routing)
    from src.services.user_macros import detect_macro
    from src.core.macro_executor import execute_macro

    macro = await detect_macro(user_id, text)
    if macro:
        logger.info("macro_triggered", macro_id=macro.macro_id)

        # React with macro emoji
        if message_id:
            await set_message_reaction(chat_id, message_id, "⚡")

        result = await execute_macro(macro, user, chat_id)
        return result

    # ... rest of existing process_message code ...
```

## Tasks

- [ ] Create `src/services/user_macros.py`
- [ ] Create `src/core/macro_executor.py`
- [ ] Add `/macro` command handler to main.py
- [ ] Add `_handle_macro_add` parser
- [ ] Integrate macro detection in process_message()
- [ ] Add ⚡ reaction for macro triggers
- [ ] Add unit tests for macro CRUD
- [ ] Add unit tests for NLU detection
- [ ] Test semantic matching with embeddings
- [ ] Test sequence execution

## Validation Criteria

1. `/macro add "deploy" -> modal deploy` creates macro
2. `/macro list` shows all user macros
3. `/macro remove <id>` deletes macro
4. Saying "deploy" triggers the macro
5. Saying "deploy now" triggers via semantic match (similarity > 0.85)
6. Skill macros execute correctly (`skill:research topic`)
7. Sequence macros execute steps in order
8. Dangerous commands are blocked

## Security Considerations

1. **Command macros** - NOT executed server-side, only displayed
2. **Dangerous patterns** - Blocked: rm, sudo, mkfs, dd, fork bombs
3. **Rate limiting** - Macros count toward user rate limit
4. **Sequence timeout** - Max 10s wait per step
5. **Macro limit** - Max 20 macros per user

## Notes

- Semantic matching only for short messages (≤5 words) to save embedding cost
- Cosine similarity threshold 0.85 balances precision vs recall
- Future enhancement: Admin-approved command execution via local executor
- Future enhancement: Template macros (share between users)
