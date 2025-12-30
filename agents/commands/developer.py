"""Developer commands: traces, circuits, and improvements."""
from commands.router import command_router


@command_router.command(
    name="/traces",
    description="List recent execution traces",
    usage="/traces [limit]",
    permission="developer",
    category="developer"
)
async def traces_command(args: str, user: dict, chat_id: int) -> str:
    """List recent execution traces."""
    from src.core.trace import list_traces
    from src.services.telegram import format_traces_list

    limit = int(args) if args and args.isdigit() else 10
    limit = min(limit, 20)  # Max 20

    traces = await list_traces(limit=limit)
    return format_traces_list(traces)


@command_router.command(
    name="/trace",
    description="Get detailed trace information",
    usage="/trace <trace_id>",
    permission="developer",
    category="developer"
)
async def trace_command(args: str, user: dict, chat_id: int) -> str:
    """Get trace detail by ID."""
    from src.core.trace import get_trace
    from src.services.telegram import format_trace_detail

    if not args:
        return "Usage: /trace <trace_id>\n\nGet trace ID from /traces list."

    trace = await get_trace(args.strip())
    if not trace:
        return f"❌ Trace not found: {args}"

    return format_trace_detail(trace)


@command_router.command(
    name="/circuits",
    description="Show circuit breaker status and statistics",
    permission="developer",
    category="developer"
)
async def circuits_command(args: str, user: dict, chat_id: int) -> str:
    """Show circuit breaker status."""
    from src.core.resilience import get_circuit_stats
    from src.services.telegram import format_circuits_status

    circuits = get_circuit_stats()
    return format_circuits_status(circuits)


@command_router.command(
    name="/improve",
    description="Submit improvement suggestion for current skill",
    usage="/improve <suggestion>",
    permission="developer",
    category="developer"
)
async def improve_command(args: str, user: dict, chat_id: int) -> str:
    """Submit skill improvement suggestion."""
    if not args:
        return (
            "Usage: /improve <suggestion>\n\n"
            "Submit suggestions for improving the bot or skills.\n"
            "Admins will review and approve improvements."
        )

    from src.services.firebase import create_improvement_proposal

    proposal_id = await create_improvement_proposal(
        user_id=user.get("id"),
        suggestion=args.strip(),
        context={"chat_id": chat_id}
    )

    if proposal_id:
        return f"✓ Improvement proposal submitted: <code>{proposal_id[:8]}</code>\n\nAdmins will review soon."

    return "❌ Failed to submit improvement. Try again later."
