# Phase 2: Profile & Context

**Duration:** 2-3 days
**Dependencies:** Phase 1 (Core Infrastructure)
**Output:** Profile CRUD, onboarding flow, context auto-update, /profile & /context commands

## Objectives

1. Implement user profile CRUD operations
2. Build hybrid onboarding flow (auto-detect + manual)
3. Implement work context management with auto-update
4. Add `/profile` and `/context` Telegram commands
5. Integrate personalization into main message flow

## Files to Create/Modify

### 1. `src/services/user_profile.py`

Profile CRUD and onboarding logic.

```python
"""User profile service - CRUD and onboarding."""
from datetime import datetime, timezone
from typing import Optional, Dict, Literal
import asyncio

from src.models.personalization import UserProfile, CommunicationPrefs, ToneType
from src.core.state import get_state_manager
from src.services.firebase import get_db, firestore
from src.utils.logging import get_logger

logger = get_logger()

# Language detection keywords
LANGUAGE_INDICATORS = {
    "vi": ["xin", "chào", "tôi", "bạn", "được", "không", "có", "này"],
    "zh": ["你好", "我", "是", "的", "了", "吗"],
    "ja": ["こんにちは", "私", "です", "ます", "ありがとう"],
    "ko": ["안녕", "저", "입니다", "감사"],
}


async def get_profile(user_id: int) -> Optional[UserProfile]:
    """Get user profile."""
    state = get_state_manager()
    data = await state.get_user_profile(user_id)
    if data:
        return UserProfile.from_dict(data)
    return None


async def create_profile(user_id: int, name: Optional[str] = None) -> UserProfile:
    """Create default profile for new user."""
    profile = UserProfile(
        user_id=user_id,
        name=name,
        onboarded=False,
        updated_at=datetime.now(timezone.utc)
    )

    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())

    logger.info("profile_created", user_id=user_id)
    return profile


async def update_profile(user_id: int, updates: Dict) -> Optional[UserProfile]:
    """Update user profile fields."""
    profile = await get_profile(user_id)
    if not profile:
        profile = await create_profile(user_id)

    # Apply updates
    for key, value in updates.items():
        if hasattr(profile, key):
            setattr(profile, key, value)

    profile.updated_at = datetime.now(timezone.utc)

    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())

    logger.info("profile_updated", user_id=user_id, fields=list(updates.keys()))
    return profile


async def mark_onboarded(user_id: int) -> None:
    """Mark user as onboarded."""
    await update_profile(user_id, {
        "onboarded": True,
        "onboarded_at": datetime.now(timezone.utc)
    })


async def set_tone(user_id: int, tone: ToneType) -> None:
    """Set user's preferred tone."""
    await update_profile(user_id, {"tone": tone})


async def set_response_length(user_id: int, length: Literal["short", "medium", "long"]) -> None:
    """Set preferred response length."""
    profile = await get_profile(user_id)
    if not profile:
        profile = await create_profile(user_id)

    profile.communication.response_length = length
    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())


async def toggle_emoji(user_id: int, enabled: bool) -> None:
    """Toggle emoji usage in responses."""
    profile = await get_profile(user_id)
    if not profile:
        profile = await create_profile(user_id)

    profile.communication.use_emoji = enabled
    state = get_state_manager()
    await state.set_user_profile(user_id, profile.to_dict())


async def detect_language(text: str) -> str:
    """Detect language from text (simple heuristic)."""
    text_lower = text.lower()

    for lang, indicators in LANGUAGE_INDICATORS.items():
        if any(ind in text_lower for ind in indicators):
            return lang

    return "en"  # Default to English


async def auto_detect_preferences(user_id: int, first_message: str, user_info: Dict) -> UserProfile:
    """Auto-detect preferences from first message and user info.

    Args:
        user_id: Telegram user ID
        first_message: User's first message
        user_info: Telegram user object

    Returns:
        Created/updated profile with detected preferences
    """
    # Detect language
    language = await detect_language(first_message)

    # Extract name from Telegram user info
    name = user_info.get("first_name") or user_info.get("username")

    # Create profile with detected preferences
    profile = await create_profile(user_id, name=name)
    await update_profile(user_id, {
        "language": language,
        "name": name
    })

    logger.info("preferences_auto_detected", user_id=user_id, language=language)
    return profile


def format_profile_display(profile: UserProfile) -> str:
    """Format profile for Telegram display."""
    lines = ["<b>Your Profile</b>\n"]

    lines.append(f"👤 <b>Name:</b> {profile.name or 'Not set'}")
    lines.append(f"🌍 <b>Language:</b> {profile.language}")
    lines.append(f"🕐 <b>Timezone:</b> {profile.timezone}")
    lines.append(f"💬 <b>Tone:</b> {profile.tone}")
    lines.append(f"📏 <b>Response length:</b> {profile.communication.response_length}")
    lines.append(f"😀 <b>Emoji:</b> {'Enabled' if profile.communication.use_emoji else 'Disabled'}")

    if profile.domain:
        lines.append(f"🏢 <b>Domain:</b> {', '.join(profile.domain)}")
    if profile.tech_stack:
        lines.append(f"🛠 <b>Tech stack:</b> {', '.join(profile.tech_stack)}")

    lines.append(f"\n<i>Onboarded:</i> {'Yes' if profile.onboarded else 'No'}")

    return "\n".join(lines)


async def delete_profile(user_id: int) -> bool:
    """Delete user profile (for /forget command)."""
    try:
        db = get_db()
        db.collection("user_profiles").document(str(user_id)).delete()

        # Invalidate cache
        state = get_state_manager()
        await state.invalidate("user_profiles", str(user_id))

        logger.info("profile_deleted", user_id=user_id)
        return True
    except Exception as e:
        logger.error("profile_delete_error", user_id=user_id, error=str(e)[:50])
        return False
```

### 2. `src/services/user_context.py`

Work context management with auto-update.

```python
"""User context service - Work context management."""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from src.models.personalization import WorkContext
from src.core.state import get_state_manager
from src.services.firebase import get_db
from src.utils.logging import get_logger

logger = get_logger()

# Session timeout
SESSION_TIMEOUT_HOURS = 2

# Patterns for context extraction
PROJECT_PATTERNS = [
    r"working on (\w+[-\w]*)",
    r"project[:\s]+(\w+[-\w]*)",
    r"repo[:\s]+(\w+[-\w]*)",
]

TASK_PATTERNS = [
    r"implementing (.+?)(?:\.|$)",
    r"fixing (.+?)(?:\.|$)",
    r"building (.+?)(?:\.|$)",
    r"adding (.+?)(?:\.|$)",
]

BRANCH_PATTERNS = [
    r"branch[:\s]+(\S+)",
    r"on (\S+) branch",
]


async def get_context(user_id: int) -> Optional[WorkContext]:
    """Get user's work context."""
    state = get_state_manager()
    data = await state.get_work_context(user_id)

    if not data:
        return None

    context = WorkContext.from_dict(data)

    # Check session timeout
    if context.last_active:
        timeout = datetime.now(timezone.utc) - timedelta(hours=SESSION_TIMEOUT_HOURS)
        if context.last_active.replace(tzinfo=timezone.utc) < timeout:
            logger.info("session_expired", user_id=user_id)
            return await reset_context(user_id)

    return context


async def reset_context(user_id: int) -> WorkContext:
    """Reset context to empty state."""
    context = WorkContext(
        user_id=user_id,
        session_start=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc)
    )

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())

    return context


async def update_context(user_id: int, updates: Dict) -> WorkContext:
    """Update work context fields."""
    context = await get_context(user_id)
    if not context:
        context = WorkContext(
            user_id=user_id,
            session_start=datetime.now(timezone.utc)
        )

    # Apply updates
    for key, value in updates.items():
        if hasattr(context, key):
            setattr(context, key, value)

    context.last_active = datetime.now(timezone.utc)

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())

    return context


async def add_recent_skill(user_id: int, skill: str) -> None:
    """Add skill to recent skills list."""
    context = await get_context(user_id)
    if not context:
        context = WorkContext(user_id=user_id)

    # Add to front, remove duplicates, limit size
    skills = [skill] + [s for s in context.recent_skills if s != skill]
    context.recent_skills = skills[:WorkContext.MAX_RECENT_SKILLS]

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())


async def add_session_fact(user_id: int, fact: str) -> None:
    """Add fact to session facts."""
    context = await get_context(user_id)
    if not context:
        context = WorkContext(user_id=user_id)

    # Avoid duplicates, limit size
    if fact not in context.session_facts:
        context.session_facts.append(fact)
        context.session_facts = context.session_facts[-WorkContext.MAX_SESSION_FACTS:]

    state = get_state_manager()
    await state.set_work_context(user_id, context.to_dict())


async def extract_and_update_context(user_id: int, message: str, skill_used: Optional[str] = None) -> None:
    """Extract context from message and update.

    This is called after each message to auto-update context.

    Args:
        user_id: Telegram user ID
        message: User's message text
        skill_used: Skill that was executed (if any)
    """
    updates = {}
    message_lower = message.lower()

    # Extract project
    for pattern in PROJECT_PATTERNS:
        match = re.search(pattern, message_lower)
        if match:
            updates["current_project"] = match.group(1)
            break

    # Extract task
    for pattern in TASK_PATTERNS:
        match = re.search(pattern, message_lower)
        if match:
            updates["current_task"] = match.group(1)[:100]  # Limit length
            break

    # Extract branch
    for pattern in BRANCH_PATTERNS:
        match = re.search(pattern, message_lower)
        if match:
            updates["active_branch"] = match.group(1)
            break

    # Update context if we found anything
    if updates:
        await update_context(user_id, updates)

    # Add skill to recent
    if skill_used:
        await add_recent_skill(user_id, skill_used)

    # Update last_active
    await update_context(user_id, {"last_active": datetime.now(timezone.utc)})


def format_context_display(context: WorkContext) -> str:
    """Format work context for Telegram display."""
    lines = ["<b>Work Context</b>\n"]

    if context.current_project:
        lines.append(f"📁 <b>Project:</b> {context.current_project}")
    if context.current_task:
        lines.append(f"📋 <b>Task:</b> {context.current_task}")
    if context.active_branch:
        lines.append(f"🌿 <b>Branch:</b> {context.active_branch}")
    if context.recent_skills:
        lines.append(f"🔧 <b>Recent skills:</b> {', '.join(context.recent_skills)}")
    if context.session_facts:
        lines.append(f"📝 <b>Session facts:</b>")
        for fact in context.session_facts[-5:]:
            lines.append(f"  • {fact}")

    if context.session_start:
        lines.append(f"\n<i>Session started:</i> {context.session_start.strftime('%H:%M')}")

    if len(lines) == 1:
        lines.append("<i>No context captured yet. Keep chatting!</i>")

    return "\n".join(lines)


async def clear_context(user_id: int) -> None:
    """Clear user's work context."""
    await reset_context(user_id)
    logger.info("context_cleared", user_id=user_id)
```

### 3. Update `main.py` - Add Commands

Add /profile and /context commands.

```python
# Add to handle_command() after existing commands (around line 649):

    if cmd == "/profile":
        return await handle_profile_command(args, user)

    if cmd == "/context":
        return await handle_context_command(args, user)


# Add new command handlers:

async def handle_profile_command(args: str, user: dict) -> str:
    """Handle /profile command."""
    from src.services.user_profile import (
        get_profile, create_profile, set_tone, set_response_length,
        toggle_emoji, mark_onboarded, format_profile_display
    )

    user_id = user.get("id")
    args_lower = args.lower().strip()

    # /profile reset
    if args_lower == "reset":
        await create_profile(user_id, user.get("first_name"))
        return "Profile reset to defaults."

    # /profile tone <value>
    if args_lower.startswith("tone "):
        tone = args_lower.split(" ", 1)[1]
        if tone in ["concise", "detailed", "casual", "formal"]:
            await set_tone(user_id, tone)
            return f"Tone set to: <b>{tone}</b>"
        return "Invalid tone. Options: concise, detailed, casual, formal"

    # /profile length <value>
    if args_lower.startswith("length "):
        length = args_lower.split(" ", 1)[1]
        if length in ["short", "medium", "long"]:
            await set_response_length(user_id, length)
            return f"Response length set to: <b>{length}</b>"
        return "Invalid length. Options: short, medium, long"

    # /profile emoji on/off
    if args_lower.startswith("emoji "):
        value = args_lower.split(" ", 1)[1]
        enabled = value in ["on", "true", "yes", "1"]
        await toggle_emoji(user_id, enabled)
        return f"Emoji {'enabled' if enabled else 'disabled'}."

    # /profile (show current)
    profile = await get_profile(user_id)
    if not profile:
        profile = await create_profile(user_id, user.get("first_name"))

    return format_profile_display(profile)


async def handle_context_command(args: str, user: dict) -> str:
    """Handle /context command."""
    from src.services.user_context import (
        get_context, clear_context, format_context_display, reset_context
    )

    user_id = user.get("id")
    args_lower = args.lower().strip()

    # /context clear
    if args_lower == "clear":
        await clear_context(user_id)
        return "Work context cleared."

    # /context (show current)
    context = await get_context(user_id)
    if not context:
        context = await reset_context(user_id)

    return format_context_display(context)
```

### 4. Update `main.py:process_message()` - Integration

Integrate personalization into message flow.

```python
# Modify process_message() starting at line 1514:

async def process_message(
    text: str,
    user: dict,
    chat_id: int,
    message_id: int = None
) -> str:
    """Process a regular message with agentic loop (tools enabled)."""
    import asyncio
    from src.services.agentic import run_agentic_loop
    from src.core.state import get_state_manager
    from src.services.personalization import load_personal_context, build_personalized_prompt
    from src.services.user_context import extract_and_update_context
    from src.services.user_profile import get_profile, create_profile, auto_detect_preferences
    from pathlib import Path
    import structlog
    import time
    import aiofiles

    logger = structlog.get_logger()
    state = get_state_manager()
    user_id = user.get("id")

    # Get tier and check rate limit
    tier = await state.get_user_tier_cached(user_id)
    allowed, reset_in = state.check_rate_limit(user_id, tier)

    if not allowed:
        return f"Rate limited. Try again in {reset_in}s.\n\nUpgrade tier for higher limits."

    # Load personalization context (parallel fetch)
    personal_ctx = await load_personal_context(user_id)

    # Check if first-time user - trigger onboarding
    if not personal_ctx.is_onboarded:
        await auto_detect_preferences(user_id, text, user)
        # Refresh context after auto-detect
        personal_ctx = await load_personal_context(user_id)

    # React to acknowledge receipt
    if message_id:
        await set_message_reaction(chat_id, message_id, "👀")

    # Send initial progress message
    progress_msg_id = await send_progress_message(chat_id, "⏳ <i>Processing...</i>")

    # ... (rest of existing code)

    # At the end before return, add learning:
    try:
        # Track skill used (if any)
        skill_used = None  # Set this based on routing result

        # Update context from this interaction
        await extract_and_update_context(user_id, text, skill_used)

    except Exception as e:
        logger.warning("context_update_failed", error=str(e)[:50])

    return response
```

### 5. Onboarding Keyboard

Add inline keyboard for onboarding.

```python
# Add to main.py or a new file src/services/telegram_keyboards.py:

def build_onboarding_keyboard() -> list:
    """Build inline keyboard for tone selection."""
    return [
        [
            {"text": "📝 Concise", "callback_data": "onboard_tone:concise"},
            {"text": "📖 Detailed", "callback_data": "onboard_tone:detailed"},
        ],
        [
            {"text": "😊 Casual", "callback_data": "onboard_tone:casual"},
            {"text": "👔 Formal", "callback_data": "onboard_tone:formal"},
        ]
    ]


def build_profile_keyboard() -> list:
    """Build inline keyboard for profile editing."""
    return [
        [
            {"text": "📝 Tone", "callback_data": "profile_edit:tone"},
            {"text": "📏 Length", "callback_data": "profile_edit:length"},
        ],
        [
            {"text": "😀 Emoji", "callback_data": "profile_edit:emoji"},
            {"text": "🔄 Reset", "callback_data": "profile_edit:reset"},
        ]
    ]


# Add callback handler in handle_callback():

async def handle_onboard_callback(callback_data: str, user: dict, chat_id: int) -> str:
    """Handle onboarding callback."""
    from src.services.user_profile import set_tone, mark_onboarded

    if callback_data.startswith("onboard_tone:"):
        tone = callback_data.split(":")[1]
        await set_tone(user.get("id"), tone)
        await mark_onboarded(user.get("id"))

        return f"Perfect! I'll respond in a <b>{tone}</b> style.\n\nYou can change this anytime with /profile."

    return "Unknown action."
```

## Tasks

- [ ] Create `src/services/user_profile.py`
- [ ] Create `src/services/user_context.py`
- [ ] Add `/profile` command handler to main.py
- [ ] Add `/context` command handler to main.py
- [ ] Integrate `load_personal_context()` into process_message()
- [ ] Add onboarding keyboard and callback handler
- [ ] Add context extraction to post-message learning
- [ ] Add unit tests for profile CRUD
- [ ] Add unit tests for context management
- [ ] Test onboarding flow end-to-end

## Validation Criteria

1. New user gets onboarding keyboard on first message
2. `/profile` shows current settings with edit options
3. `/profile tone concise` updates tone preference
4. `/context` shows current work context
5. `/context clear` resets session context
6. Context auto-updates from message patterns
7. Personalized system prompt includes user preferences

## Notes

- Language detection is basic heuristic - can be enhanced later
- Context extraction uses regex patterns - LLM extraction in Phase 4
- Onboarding only asks for tone, other preferences auto-detected
- Session timeout is 2 hours of inactivity
