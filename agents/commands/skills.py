"""Skills commands: browse, execute, and configure skill execution."""
from commands.router import command_router


@command_router.command(
    name="/skills",
    description="List all available skills, optionally filter by category",
    usage="/skills [category]",
    permission="guest",
    category="skills"
)
async def skills_command(args: str, user: dict, chat_id: int) -> str:
    """List skills, optionally filtered by category."""
    from src.skills.registry import get_registry

    registry = get_registry()
    skills = registry.discover()

    if args:
        category_filter = args.strip().lower()
        skills = [s for s in skills if s.category and s.category.lower() == category_filter]
        if not skills:
            return f"❓ No skills found in category: {args}"

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
        lines.append(", ".join(sorted(names[:10])))
        if len(names) > 10:
            lines.append(f"...and {len(names) - 10} more")

    lines.append(f"\n<i>Total: {len(skills)} skills</i>")
    return "\n".join(lines)


@command_router.command(
    name="/skill",
    description="Get skill info or execute skill with task",
    usage="/skill <name> [task]",
    permission="user",
    category="skills"
)
async def skill_command(args: str, user: dict, chat_id: int) -> str:
    """Get skill info or execute skill with task."""
    if not args:
        return "Usage: /skill <name> [task]\n\nExample:\n/skill planning Create deployment plan"

    parts = args.split(maxsplit=1)
    skill_name = parts[0].lower()
    task = parts[1] if len(parts) > 1 else None

    from src.skills.registry import get_registry

    registry = get_registry()
    skill = registry.get_full(skill_name)

    if not skill:
        # Suggest similar skills
        summaries = registry.discover()
        names = [s.name for s in summaries]
        suggestions = [n for n in names if n.startswith(skill_name[:3]) or skill_name in n]

        if suggestions:
            return f"❓ Skill '{skill_name}' not found.\nDid you mean: {', '.join(suggestions[:3])}?"
        return f"❓ Skill '{skill_name}' not found.\nUse /skills to see available skills."

    if not task:
        # Return skill info
        deployment = skill.deployment or "unknown"
        return f"""<b>{skill.name}</b>

{skill.description}

<b>Category:</b> {skill.category}
<b>Deployment:</b> {deployment}

<b>Usage:</b> /skill {skill.name} <your task>"""

    # Execute skill (with local/remote routing)
    import sys
    import time
    main_module = sys.modules.get("main")
    if not main_module:
        import main as main_module
    execute_or_queue_skill = main_module.execute_or_queue_skill

    start = time.time()
    result = await execute_or_queue_skill(
        skill_name,
        task,
        user.get("id"),
        user,
        chat_id,
        None  # No progress message for command
    )
    # result is already formatted by execute_or_queue_skill
    return result


@command_router.command(
    name="/mode",
    description="Set or view execution mode (simple, routed, auto)",
    usage="/mode [simple|routed|auto]",
    permission="user",
    category="skills"
)
async def mode_command(args: str, user: dict, chat_id: int) -> str:
    """Set or view execution mode."""
    from src.core.state import get_state_manager

    valid_modes = ["simple", "routed", "auto"]
    state = get_state_manager()

    if not args or args.strip().lower() not in valid_modes:
        current = await state.get_user_mode(user.get("id"))
        return (
            f"Current mode: <b>{current}</b>\n\n"
            "<b>Modes:</b>\n"
            "• <b>simple</b> - Direct LLM response\n"
            "• <b>routed</b> - Route to best skill\n"
            "• <b>auto</b> - Smart detection (recommended)\n\n"
            f"Usage: /mode <{'|'.join(valid_modes)}>"
        )

    mode = args.strip().lower()
    await state.set_user_mode(user.get("id"), mode)
    return f"✓ Execution mode set to: <b>{mode}</b>"


@command_router.command(
    name="/suggest",
    description="Get AI-powered suggestions based on your context",
    permission="user",
    category="skills"
)
async def suggest_command(args: str, user: dict, chat_id: int) -> str:
    """Get personalized suggestions."""
    from src.core.suggestions import get_suggestions_list, format_suggestions_display

    suggestions = await get_suggestions_list(user.get("id"))
    return format_suggestions_display(suggestions)


@command_router.command(
    name="/task",
    description="Check status of queued local task",
    usage="/task <task_id>",
    permission="user",
    category="skills"
)
async def task_command(args: str, user: dict, chat_id: int) -> str:
    """Check local task status."""
    from src.services.firebase import get_task_result
    from src.services.telegram import format_task_status

    if not args:
        return "Usage: /task <task_id>\n\nGet task ID from queued local skill execution."

    task = await get_task_result(args.strip())
    return format_task_status(task)
