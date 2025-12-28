---
title: Code Review - Telegram Skills Terminal
date: 2025-12-27
reviewer: code-reviewer (afdad1f)
scope: Telegram bot skill integration (main.py, telegram.py)
---

# Code Review: Telegram Skills Terminal

## Scope

- **Files reviewed**: main.py, src/services/telegram.py
- **Lines analyzed**: ~750 LOC
- **Focus**: Recent changes for skill terminal implementation
- **Plan**: /Users/nad/Library/CloudStorage/OneDrive-Personal/Agents/plans/251227-2251-telegram-skills-terminal/plan.md

## Overall Assessment

**Quality**: Good implementation with solid foundation. Code is well-structured and follows async patterns correctly.

**Critical Issues**: 2 found (error handling, type safety)
**High Priority**: 3 found (security, performance)
**Medium Priority**: 4 found (edge cases)
**Low Priority**: 2 found (code quality)

## Critical Issues

### 1. Missing Error Handling in Firebase Session Functions

**Location**: main.py:695-752 (session state functions)

**Issue**: All Firebase operations lack try-catch blocks. Firebase exceptions (network errors, permission denied, quota exceeded) will crash webhook handler.

**Impact**: User requests fail silently, pending skills persist indefinitely causing wrong skill execution on next message.

**Fix**:
```python
async def get_pending_skill(user_id: int) -> str:
    """Get user's pending skill selection."""
    from src.services.firebase import init_firebase
    import structlog

    logger = structlog.get_logger()

    try:
        db = init_firebase()
        doc = db.collection("telegram_sessions").document(str(user_id)).get()

        if doc.exists:
            data = doc.to_dict()
            return data.get("pending_skill")
        return None
    except Exception as e:
        logger.error("firebase_get_pending_skill_failed", user_id=user_id, error=str(e))
        return None  # Fail gracefully
```

Apply same pattern to: `store_pending_skill`, `clear_pending_skill`, `store_user_mode`, `get_user_mode`.

### 2. User ID Type Mismatch Risk

**Location**: main.py:695-752, line 74 `user.get("id")`

**Issue**: Functions expect `user_id: int`, but Telegram API returns `user["id"]` which could be None if malformed update. Type annotation says `int` but no validation.

**Impact**: Runtime TypeError if user dict malformed, Firebase document creation with key "None".

**Fix**:
```python
# In handle_callback, handle_command, process_message
user_id = user.get("id")
if not user_id:
    logger.warning("missing_user_id", user=user)
    return "Invalid request"

# Safe to use user_id now
pending_skill = await get_pending_skill(user_id)
```

## High Priority Findings

### 3. HTML Injection in Skill Names/Descriptions

**Location**: main.py:683-690 (handle_skill_select), 541 (send_skills_menu)

**Issue**: Skill name and description inserted directly into HTML without escaping:
```python
message = (
    f"<b>{skill_name}</b>\n"  # ← UNESCAPED
    f"{desc}\n\n"              # ← UNESCAPED
)
```

If skill name contains `<script>` or malicious HTML entities, Telegram parsing may fail or behave unexpectedly.

**Impact**: Message send fails, user sees error. Potential for UI manipulation if Telegram client renders unexpected HTML.

**Fix**:
```python
from src.services.telegram import escape_html

desc = skill.description[:100] if hasattr(skill, 'description') else ""
message = (
    f"<b>{escape_html(skill_name)}</b>\n"
    f"{escape_html(desc)}\n\n"
    "Send your task now (or /cancel to exit):"
)
```

Apply to all HTML-formatted strings: help text (line 318-328), category names (line 654), mode messages.

### 4. Callback Data Length Not Validated

**Location**: main.py:568, 585, 589 (build_skills_keyboard)

**Issue**: Telegram callback_data limited to 64 bytes. No check on skill/category name length:
```python
"callback_data": f"skill:{s.name}"  # No length check
```

If skill name is "mobile-development-react-native-ios-specific" (40+ chars), combined with prefix exceeds limit, button fails silently.

**Impact**: Buttons for long-named skills don't work, no feedback to user.

**Fix**:
```python
def build_skills_keyboard(category: str = None) -> list:
    MAX_CALLBACK_LEN = 64

    # For skill buttons
    for s in skills_in_cat:
        callback_data = f"skill:{s.name}"
        if len(callback_data) > MAX_CALLBACK_LEN:
            # Use index-based reference or truncated name
            logger.warning("skill_name_too_long", skill=s.name)
            callback_data = f"skill:{s.name[:MAX_CALLBACK_LEN-7]}"  # Leave room for prefix

        keyboard.append([{
            "text": s.name,
            "callback_data": callback_data
        }])
```

Better: Use skill index or hash as callback data, store mapping in Redis/Firebase.

### 5. No Rate Limiting on Skill Execution

**Location**: main.py:369-371 (execute_skill_simple in /skill command)

**Issue**: User can spam `/skill expensive_task ...` repeatedly, each triggers full LLM execution. No rate limiting or queue.

**Impact**: Cost explosion, Modal timeout if many concurrent requests, potential DoS.

**Fix**:
```python
from datetime import datetime, timedelta
import structlog

# In-memory rate limit (better: use Redis for distributed)
_user_last_exec = {}
RATE_LIMIT_SECONDS = 10

async def execute_skill_simple(skill_name: str, task: str, context: dict) -> str:
    user_id = context.get("user", {}).get("id")

    if user_id:
        last_exec = _user_last_exec.get(user_id)
        if last_exec and (datetime.now() - last_exec).total_seconds() < RATE_LIMIT_SECONDS:
            return "⏳ Please wait a few seconds before running another skill."
        _user_last_exec[user_id] = datetime.now()

    # ... rest of execution
```

## Medium Priority Improvements

### 6. Chunking May Break HTML Tags

**Location**: src/services/telegram.py:60-105 (chunk_message)

**Issue**: Hard split at `max_length - 10` can break mid-tag:
```python
# Line 94-95
chunks.append(sentence[i:i + max_length - 10])
```

If sentence contains `<code>very long code block here...</code>`, split may occur inside tag, causing parse errors.

**Impact**: Subsequent message chunks fail HTML parsing, sent as plain text.

**Recommendation**:
```python
# After hard split, check for unclosed tags
def safe_hard_split(text, max_len):
    chunk = text[:max_len]
    # Count opening/closing tags
    open_tags = re.findall(r'<(b|i|code|pre)>', chunk)
    close_tags = re.findall(r'</(b|i|code|pre)>', chunk)

    # If unbalanced, close tags at end
    for tag in reversed(open_tags):
        if tag not in close_tags:
            chunk += f"</{tag}>"

    return chunk
```

### 7. No Timeout on Skill Execution

**Location**: main.py:369-371, 430-432

**Issue**: `execute_skill_simple` has no timeout. If skill hangs (infinite loop in LLM, external API timeout), Telegram webhook times out (60s), user sees no response.

**Impact**: Poor UX, Modal function may run until global timeout (120s).

**Fix**:
```python
import asyncio

async def execute_skill_simple(skill_name: str, task: str, context: dict) -> str:
    try:
        return await asyncio.wait_for(
            _execute_skill_simple_impl(skill_name, task, context),
            timeout=45.0  # Leave margin for response send
        )
    except asyncio.TimeoutError:
        return "⏱ Skill execution timed out. Please try a simpler task or contact admin."
```

### 8. Skill Not Found - Suggestions Logic Incomplete

**Location**: main.py:356-363

**Issue**: Suggestion logic uses prefix match OR substring:
```python
suggestions = [n for n in names if n.startswith(skill_name[:3]) or skill_name in n]
```

For input "plan", suggests "planning" ✓ but also "deployment-plan", "floor-plan", etc. Too broad.

**Better**: Use Levenshtein distance or trigram similarity.

**Low priority** since feature is nice-to-have, not critical.

### 9. Missing Logging for Callback Handling

**Location**: main.py:594-626 (handle_callback)

**Issue**: No logging for callback execution result. If skill execution fails silently, no trace.

**Fix**:
```python
elif action == "skill":
    # Skill selected - prompt for task
    logger.info("skill_button_pressed", skill=value, user_id=user.get("id"))
    await handle_skill_select(chat_id, value, user)
    logger.info("skill_prompt_sent", skill=value)
```

## Low Priority Suggestions

### 10. Redundant HTML Escaping Check

**Location**: src/services/telegram.py:13-18 (escape_html)

**Issue**: Function is correct but could be optimized using `html.escape`:
```python
import html

def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(text, quote=False)
```

**Benefit**: Standard library, handles more entities (`"` as `&quot;`).

### 11. Code Duplication in Keyboard Building

**Location**: main.py:563-575 (category keyboard building)

**Issue**: Manual row building logic duplicated:
```python
row = []
for cat, count in sorted(categories.items()):
    row.append({...})
    if len(row) == 2:
        keyboard.append(row)
        row = []
if row:
    keyboard.append(row)
```

**Refactor**:
```python
def build_button_rows(items, cols=2):
    """Build keyboard rows with N columns."""
    return [items[i:i+cols] for i in range(0, len(items), cols)]

# Usage
buttons = [{"text": f"{cat.title()} ({count})", "callback_data": f"cat:{cat}"}
           for cat, count in sorted(categories.items())]
keyboard = build_button_rows(buttons, cols=2)
```

## Positive Observations

✓ Async/await used correctly throughout
✓ Proper use of `split(maxsplit=1)` for command parsing
✓ Fallback mechanism for HTML parsing failures (line 489-494)
✓ Proper callback answer to dismiss loading state (line 611)
✓ Sensible defaults (`get_user_mode` returns "simple" if not set)
✓ Clean separation: telegram.py for utilities, main.py for handlers
✓ Good use of f-strings for formatting
✓ Chunking respects paragraph/sentence boundaries (not naive split)

## Recommended Actions

### Immediate (Before Deploy)

1. **Add try-catch to all Firebase functions** (Critical #1)
2. **Validate user_id before use** (Critical #2)
3. **Escape HTML in all message formatting** (High #3)

### High Priority (Next Sprint)

4. **Validate callback_data length** (High #4)
5. **Add rate limiting** (High #5)
6. **Add skill execution timeout** (Medium #7)

### Nice to Have

7. Fix HTML tag splitting in chunking (Medium #6)
8. Improve skill suggestions with fuzzy matching (Medium #8)
9. Add callback execution logging (Medium #9)
10. Refactor keyboard building (Low #11)

## Metrics

- **Syntax**: ✓ Valid (Python AST parse clean)
- **Type Coverage**: ~60% (type hints present but no runtime validation)
- **Error Handling**: 40% (many paths lack try-catch)
- **Security**: Medium risk (HTML injection, no rate limiting)
- **Test Coverage**: 0% (no tests found)

## Plan Update

Updated plan file: /Users/nad/Library/CloudStorage/OneDrive-Personal/Agents/plans/251227-2251-telegram-skills-terminal/plan.md

**Status**: INCOMPLETE - Critical issues must be resolved before production

**Action Items Added to Plan**:
- [ ] Add error handling to Firebase session functions
- [ ] Validate user_id before Firebase operations
- [ ] Escape HTML in all message formatting
- [ ] Validate callback_data length (64 byte limit)
- [ ] Implement rate limiting for skill execution
- [ ] Add execution timeout for skills

---

## Unresolved Questions

1. **Session state cleanup**: When should pending_skill expire? Currently persists forever if user never sends message.
2. **Concurrent execution**: If user clicks skill button multiple times quickly, does Firebase handle race condition?
3. **Skill registry caching**: Registry uses in-memory cache, but Modal may spawn multiple containers. Could users see stale skill list?
4. **Modal Volume sync**: If skill info.md updated externally, when does registry see changes? Need force_refresh trigger?
5. **Error messages i18n**: Currently all English. Should detect user language from Telegram `language_code`?
