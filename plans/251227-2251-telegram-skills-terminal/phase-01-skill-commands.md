---
phase: 1
title: "Skill Commands"
status: pending
effort: 1.5h
---

# Phase 1: Skill Commands

## Objective

Add `/skill <name> <task>` and `/skills` commands to Telegram bot.

## Implementation Steps

### 1. Update handle_command() in main.py

**Location**: main.py:302-340

Add new command handlers:

```python
elif cmd == "/skill":
    if not args:
        return "Usage: /skill <name> <task>\nExample: /skill planning Create auth system"

    parts = args.split(maxsplit=1)
    skill_name = parts[0]
    task = parts[1] if len(parts) > 1 else ""

    if not task:
        return f"Please provide a task for skill '{skill_name}'.\nUsage: /skill {skill_name} <task>"

    result = await execute_skill_simple(skill_name, task, {"user": user})
    return result

elif cmd == "/skills":
    from src.skills.registry import get_registry
    registry = get_registry()
    summaries = registry.discover()

    if not summaries:
        return "No skills available."

    lines = ["Available skills:\n"]
    for s in summaries:
        lines.append(f"- {s.name}: {s.description[:50]}...")
    lines.append("\nUsage: /skill <name> <task>")
    return "\n".join(lines)

elif cmd == "/mode":
    # Store user mode preference (Firebase or in-memory)
    valid_modes = ["simple", "routed", "evaluated"]
    if args not in valid_modes:
        return f"Invalid mode. Available: {', '.join(valid_modes)}"
    # TODO: Store in Firebase user prefs
    return f"Mode set to: {args}"
```

### 2. Add skill name validation

**Before** `execute_skill_simple()` call:

```python
# Validate skill exists
from src.skills.registry import get_registry
registry = get_registry()
skill = registry.get_full(skill_name)

if not skill:
    # Suggest similar skills
    names = registry.get_names()
    suggestions = [n for n in names if n.startswith(skill_name[:3])]

    if suggestions:
        return f"Skill '{skill_name}' not found. Did you mean: {', '.join(suggestions[:3])}?"
    return f"Skill '{skill_name}' not found. Use /skills to see available skills."
```

### 3. Update /help command

Add new commands to help text:

```python
elif cmd == "/help":
    return (
        "Available commands:\n"
        "/start - Welcome\n"
        "/help - This message\n"
        "/status - Check agent status\n"
        "/skills - List all available skills\n"
        "/skill <name> <task> - Execute a skill\n"
        "/mode <simple|routed|evaluated> - Set execution mode\n"
        "/translate <text> - Translate to English\n"
        "/summarize <text> - Summarize text\n"
        "/rewrite <text> - Improve text"
    )
```

## Code Changes Summary

| File | Section | Change |
|------|---------|--------|
| main.py | handle_command() | Add /skill, /skills, /mode handlers |
| main.py | /help text | Update with new commands |

## Testing

1. `/skills` - Should list all 24+ skills
2. `/skill planning Create a login flow` - Should execute planning skill
3. `/skill unknown task` - Should show "not found" with suggestions
4. `/skill planning` - Should show usage error

## Success Criteria

- [ ] `/skills` lists all discovered skills with descriptions
- [ ] `/skill <name> <task>` executes skill and returns result
- [ ] Invalid skill name shows suggestions
- [ ] Missing task shows usage instructions

## Risks

| Risk | Mitigation |
|------|------------|
| Long skill list overwhelming | Truncate descriptions, add pagination in Phase 2 |
| Skill execution timeout | Modal 60s timeout sufficient for most skills |

## Next Phase

Phase 2 adds inline keyboards for interactive skill selection.
