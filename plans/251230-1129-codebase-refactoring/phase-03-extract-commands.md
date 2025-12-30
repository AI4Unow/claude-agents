# Phase 3: Extract Command Handlers

## Context

- [main.py Review - H2](../reports/code-reviewer-251230-1121-main-py-review.md#h2-srp-violation---handle_command-is-800-line-command-router)
- [Comprehensive Analysis - Phase 3](../reports/codebase-review-251230-1119-comprehensive-analysis.md#phase-3-extract-commands-week-2-3---16-hrs)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P1 - High |
| Status | pending |
| Effort | 16 hours |
| Risk | MEDIUM (functional change) |
| Depends On | Phase 2 |

## Key Insights

1. **handle_command() is 800 lines with 30+ if/elif branches** - lines 649-1440
2. **Permission checks scattered** - admin_id fetched 6 times inside function
3. **Business logic mixed with routing** - untestable individual commands
4. **No command documentation** - help text hardcoded separately

## Requirements

- [ ] Create CommandRouter with decorator pattern
- [ ] Split commands by category (user, admin, skills, personalization, developer)
- [ ] Centralize permission checks with tier validation
- [ ] Auto-generate help text from command decorators
- [ ] Unit testable individual command handlers

## Architecture Decisions

1. **Router Pattern**: Decorator-based registration like Flask/FastAPI
2. **Permission Model**: Use tier system (guest, user, developer, admin)
3. **Command Signature**: `async def cmd(args: str, user: dict, chat_id: int) -> str`
4. **Help Generation**: Collect docstrings from registered commands

## Target Structure

```
agents/
├── commands/
│   ├── __init__.py
│   ├── base.py (CommandRouter, decorators)
│   ├── router.py (global router instance)
│   ├── user.py (/start, /help, /status, /tier, /forget)
│   ├── skills.py (/skills, /skill, /mode, /suggest)
│   ├── admin.py (/grant, /revoke, /admin, /faq)
│   ├── personalization.py (/profile, /context, /macro, /macros)
│   ├── developer.py (/traces, /circuits, /improve)
│   └── reminders.py (/remind, /reminders)
```

## Related Code Files

| File | Lines | Commands |
|------|-------|----------|
| `agents/main.py` | 649-760 | /start, /help, /status |
| `agents/main.py` | 761-830 | /tier, /skills, /skill |
| `agents/main.py` | 831-930 | /mode, /grant, /revoke |
| `agents/main.py` | 931-1050 | /admin, /faq |
| `agents/main.py` | 1051-1200 | /profile, /context, /macro |
| `agents/main.py` | 1201-1350 | /remind, /reminders |
| `agents/main.py` | 1351-1440 | /traces, /circuits, /improve |

## Implementation Steps

### 1. Create CommandRouter Base (2h)

Create `agents/commands/base.py`:

```python
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Dict, List, Optional
import structlog

logger = structlog.get_logger()

CommandHandler = Callable[[str, dict, int], Awaitable[str]]

@dataclass
class CommandDefinition:
    handler: CommandHandler
    name: str
    description: str
    usage: str
    permission_level: str = "guest"  # guest, user, developer, admin
    category: str = "general"

class CommandRouter:
    """Route commands to handlers with permission checking."""

    def __init__(self):
        self._commands: Dict[str, CommandDefinition] = {}
        self._categories: Dict[str, List[str]] = {}

    def command(
        self,
        name: str,
        description: str = "",
        usage: str = "",
        permission: str = "guest",
        category: str = "general"
    ):
        """Decorator to register command handler."""
        def decorator(func: CommandHandler):
            cmd_name = name if name.startswith("/") else f"/{name}"
            self._commands[cmd_name] = CommandDefinition(
                handler=func,
                name=cmd_name,
                description=description or func.__doc__ or "",
                usage=usage,
                permission_level=permission,
                category=category
            )
            # Track by category
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(cmd_name)
            return func
        return decorator

    async def handle(self, command: str, user: dict, chat_id: int) -> str:
        """Route command to handler with permission check."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd_def = self._commands.get(cmd)
        if not cmd_def:
            return self._unknown_command(cmd)

        # Permission check
        if not await self._check_permission(user.get("id"), cmd_def.permission_level):
            return f"Access denied. Requires {cmd_def.permission_level} tier."

        try:
            return await cmd_def.handler(args, user, chat_id)
        except Exception as e:
            logger.error("command_error", command=cmd, error=str(e))
            return f"Error: {str(e)[:100]}"

    async def _check_permission(self, user_id: int, required: str) -> bool:
        """Check if user has required permission level."""
        from src.core.state import get_state_manager
        from config.env import is_admin

        if required == "guest":
            return True

        if required == "admin":
            return is_admin(user_id)

        state = get_state_manager()
        tier = await state.get_user_tier_cached(user_id)

        tier_levels = {"guest": 0, "user": 1, "developer": 2, "admin": 3}
        return tier_levels.get(tier, 0) >= tier_levels.get(required, 0)

    def _unknown_command(self, cmd: str) -> str:
        """Return helpful message for unknown command."""
        similar = [c for c in self._commands.keys() if cmd[:3] in c]
        if similar:
            return f"Unknown command: {cmd}\nDid you mean: {', '.join(similar[:3])}?"
        return f"Unknown command: {cmd}\nUse /help to see available commands."

    def get_help_text(self, tier: str = "guest") -> str:
        """Generate help text based on user tier."""
        lines = ["Available commands:\n"]
        tier_levels = {"guest": 0, "user": 1, "developer": 2, "admin": 3}
        user_level = tier_levels.get(tier, 0)

        for category, commands in sorted(self._categories.items()):
            category_cmds = []
            for cmd_name in commands:
                cmd_def = self._commands[cmd_name]
                if tier_levels.get(cmd_def.permission_level, 0) <= user_level:
                    category_cmds.append(f"{cmd_name} - {cmd_def.description}")

            if category_cmds:
                lines.append(f"\n<b>{category.title()}</b>")
                lines.extend(category_cmds)

        return "\n".join(lines)
```

### 2. Create Global Router Instance (0.5h)

Create `agents/commands/router.py`:

```python
from commands.base import CommandRouter

# Global command router instance
command_router = CommandRouter()
```

### 3. Extract User Commands (2h)

Create `agents/commands/user.py`:

```python
from commands.router import command_router

@command_router.command(
    name="/start",
    description="Welcome message",
    permission="guest",
    category="general"
)
async def start_command(args: str, user: dict, chat_id: int) -> str:
    """Welcome message for new users."""
    name = user.get("first_name", "there")
    return f"""Hello {name}!

I'm <b>AI4U.now Bot</b> - your unified AI assistant.

Quick start:
- Just send any message to chat with AI
- Use /help to see all commands
- Use /skills to browse available skills

Enjoy!"""

@command_router.command(
    name="/help",
    description="Show available commands",
    permission="guest",
    category="general"
)
async def help_command(args: str, user: dict, chat_id: int) -> str:
    """Show help text based on user tier."""
    from src.core.state import get_state_manager
    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))
    return command_router.get_help_text(tier)

@command_router.command(
    name="/status",
    description="Show bot status and your tier",
    permission="guest",
    category="general"
)
async def status_command(args: str, user: dict, chat_id: int) -> str:
    """Show current status."""
    from src.core.state import get_state_manager
    from src.core.resilience import get_circuit_status

    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))
    session = await state.get_session(user.get("id"))
    mode = session.get("mode", "auto") if session else "auto"

    circuits = get_circuit_status()
    circuit_summary = ", ".join(f"{k}:{v}" for k, v in circuits.items())

    return f"""<b>Status</b>

User: {user.get("first_name")}
Tier: {tier}
Mode: {mode}
Circuits: {circuit_summary}"""

@command_router.command(
    name="/tier",
    description="Check your current tier",
    permission="guest",
    category="general"
)
async def tier_command(args: str, user: dict, chat_id: int) -> str:
    """Show user's current tier."""
    from src.core.state import get_state_manager
    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))

    tier_info = {
        "guest": "Basic access, rate limited",
        "user": "Standard access, more requests",
        "developer": "Full access, traces, circuits",
        "admin": "Admin access, all features"
    }

    return f"Your tier: <b>{tier}</b>\n{tier_info.get(tier, '')}"

@command_router.command(
    name="/forget",
    description="Delete your data",
    permission="user",
    category="general"
)
async def forget_command(args: str, user: dict, chat_id: int) -> str:
    """Delete user's conversation history and profile."""
    from src.core.state import get_state_manager
    from src.services.personalization import PersonalizationService

    state = get_state_manager()
    user_id = user.get("id")

    # Clear conversation
    await state.clear_conversation(user_id)

    # Clear profile (if service exists)
    try:
        ps = PersonalizationService()
        await ps.delete_profile(user_id)
    except Exception:
        pass

    return "Your data has been deleted."
```

### 4. Extract Skills Commands (2h)

Create `agents/commands/skills.py`:

```python
from commands.router import command_router
from src.skills.registry import get_registry

@command_router.command(
    name="/skills",
    description="List available skills",
    usage="/skills [category]",
    permission="guest",
    category="skills"
)
async def skills_command(args: str, user: dict, chat_id: int) -> str:
    """List skills, optionally filtered by category."""
    registry = get_registry()
    skills = registry.discover()

    if args:
        skills = [s for s in skills if s.category == args.strip()]
        if not skills:
            return f"No skills found in category: {args}"

    # Group by category
    by_category = {}
    for skill in skills:
        cat = skill.category or "other"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(skill.name)

    lines = ["<b>Available Skills</b>\n"]
    for cat, names in sorted(by_category.items()):
        lines.append(f"\n<b>{cat.title()}</b>")
        lines.append(", ".join(names[:10]))
        if len(names) > 10:
            lines.append(f"...and {len(names) - 10} more")

    return "\n".join(lines)

@command_router.command(
    name="/skill",
    description="Get skill info or execute",
    usage="/skill <name> [task]",
    permission="user",
    category="skills"
)
async def skill_command(args: str, user: dict, chat_id: int) -> str:
    """Get skill info or execute skill with task."""
    if not args:
        return "Usage: /skill <name> [task]"

    parts = args.split(maxsplit=1)
    skill_name = parts[0].lower()
    task = parts[1] if len(parts) > 1 else None

    from validators.input import InputValidator
    val = InputValidator.skill_name(skill_name)
    if not val.valid:
        return val.error

    registry = get_registry()
    skill = registry.get_full(skill_name)

    if not skill:
        suggestions = registry.suggest_similar(skill_name)
        if suggestions:
            return f"Skill '{skill_name}' not found. Did you mean: {', '.join(suggestions[:3])}?"
        return f"Skill '{skill_name}' not found. Use /skills to browse."

    if not task:
        # Return skill info
        return f"""<b>{skill.name}</b>
{skill.description}

Category: {skill.category}
Deployment: {skill.deployment}

Usage: /skill {skill.name} <your task>"""

    # Execute skill
    from execution.skill_executor import execute_skill_simple
    result = await execute_skill_simple(skill_name, task, {"user": user})
    return result

@command_router.command(
    name="/mode",
    description="Set execution mode",
    usage="/mode <simple|routed|auto>",
    permission="user",
    category="skills"
)
async def mode_command(args: str, user: dict, chat_id: int) -> str:
    """Set execution mode."""
    valid_modes = ["simple", "routed", "auto"]
    mode = args.strip().lower() if args else None

    if not mode:
        from src.core.state import get_state_manager
        state = get_state_manager()
        session = await state.get_session(user.get("id"))
        current = session.get("mode", "auto") if session else "auto"
        return f"Current mode: {current}\n\nAvailable: {', '.join(valid_modes)}"

    if mode not in valid_modes:
        return f"Invalid mode. Choose from: {', '.join(valid_modes)}"

    from src.core.state import get_state_manager
    state = get_state_manager()
    await state.set_session(user.get("id"), {"mode": mode})

    return f"Mode set to: {mode}"
```

### 5. Extract Admin Commands (2h)

Create `agents/commands/admin.py`:

```python
from commands.router import command_router
from config.env import require_admin

@command_router.command(
    name="/grant",
    description="Grant tier to user",
    usage="/grant <user_id> <tier>",
    permission="admin",
    category="admin"
)
async def grant_command(args: str, user: dict, chat_id: int) -> str:
    """Grant tier to a user."""
    parts = args.split()
    if len(parts) != 2:
        return "Usage: /grant <user_id> <tier>"

    target_id, tier = parts
    try:
        target_id = int(target_id)
    except ValueError:
        return "Invalid user ID"

    valid_tiers = ["user", "developer", "admin"]
    if tier not in valid_tiers:
        return f"Invalid tier. Choose from: {', '.join(valid_tiers)}"

    from src.services.firebase import set_user_tier
    success = await set_user_tier(target_id, tier)

    if success:
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.invalidate_user_tier(target_id)
        return f"Granted {tier} tier to user {target_id}"

    return "Failed to grant tier"

@command_router.command(
    name="/revoke",
    description="Revoke user tier (reset to guest)",
    usage="/revoke <user_id>",
    permission="admin",
    category="admin"
)
async def revoke_command(args: str, user: dict, chat_id: int) -> str:
    """Revoke user's tier."""
    if not args:
        return "Usage: /revoke <user_id>"

    try:
        target_id = int(args.strip())
    except ValueError:
        return "Invalid user ID"

    from src.services.firebase import set_user_tier
    success = await set_user_tier(target_id, "guest")

    if success:
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.invalidate_user_tier(target_id)
        return f"Revoked tier from user {target_id}"

    return "Failed to revoke tier"

@command_router.command(
    name="/faq",
    description="Manage FAQ entries",
    usage="/faq <add|edit|delete|list> [args]",
    permission="admin",
    category="admin"
)
async def faq_command(args: str, user: dict, chat_id: int) -> str:
    """Manage FAQ entries."""
    if not args:
        return "Usage: /faq <add|edit|delete|list> [args]"

    parts = args.split(maxsplit=1)
    action = parts[0].lower()
    content = parts[1] if len(parts) > 1 else ""

    from src.services.firebase import create_faq_entry, update_faq_entry, delete_faq_entry, list_faq_entries

    if action == "list":
        entries = await list_faq_entries()
        if not entries:
            return "No FAQ entries found"
        lines = ["<b>FAQ Entries</b>\n"]
        for entry in entries[:10]:
            lines.append(f"- {entry.id}: {entry.patterns[0][:30]}...")
        return "\n".join(lines)

    elif action == "add":
        if "|" not in content:
            return "Usage: /faq add <pattern> | <answer>"
        pattern, answer = content.split("|", 1)
        entry_id = await create_faq_entry(pattern.strip(), answer.strip())
        return f"FAQ entry created: {entry_id}"

    elif action == "delete":
        if not content:
            return "Usage: /faq delete <id>"
        success = await delete_faq_entry(content.strip())
        return "FAQ deleted" if success else "FAQ not found"

    return f"Unknown action: {action}"
```

### 6. Extract Developer/Personalization Commands (3h)

Create `agents/commands/developer.py` and `agents/commands/personalization.py` following same pattern.

### 7. Register All Commands (1h)

Update `agents/commands/__init__.py`:

```python
from commands.router import command_router

# Import all command modules to register them
from commands import user
from commands import skills
from commands import admin
from commands import personalization
from commands import developer
from commands import reminders

__all__ = ["command_router"]
```

### 8. Update Telegram Route (1.5h)

Update `agents/api/routes/telegram.py` to use command router:

```python
from commands import command_router

@router.post("/telegram")
async def telegram_webhook(...):
    if text.startswith("/"):
        response = await command_router.handle(text, user, chat_id)
    else:
        response = await process_message(text, user, chat_id, message_id)
```

## Todo List

- [ ] Create commands/base.py with CommandRouter
- [ ] Create commands/router.py with global instance
- [ ] Create commands/user.py (5 commands)
- [ ] Create commands/skills.py (4 commands)
- [ ] Create commands/admin.py (4 commands)
- [ ] Create commands/personalization.py (4 commands)
- [ ] Create commands/developer.py (3 commands)
- [ ] Create commands/reminders.py (2 commands)
- [ ] Create commands/__init__.py to register all
- [ ] Update telegram route to use router
- [ ] Write unit tests for each command
- [ ] Test permission checks work correctly

## Success Criteria

- [ ] All 30+ commands registered and working
- [ ] Permission checks enforced per command
- [ ] /help generates dynamic help text by tier
- [ ] Each command independently unit testable
- [ ] No regression in command behavior
- [ ] handle_command() removed from main.py

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Command behavior changes | HIGH | LOW | Compare output before/after |
| Permission model breaks | HIGH | MEDIUM | Test all tier levels |
| Help text incomplete | LOW | LOW | Auto-generate from decorators |
| Import cycles | MEDIUM | MEDIUM | Lazy imports in handlers |

## Security Considerations

- Permission checks must happen before command execution
- Admin commands require is_admin() check
- User input must be validated before use
- Error messages should not leak internal details

## Next Steps

After Phase 3 completion:
1. Verify all commands work correctly via Telegram
2. Run command unit tests
3. Begin [Phase 4: Refactor Services](./phase-04-refactor-services.md)
