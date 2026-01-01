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


@command_router.command(
    name="/sla",
    description="Show SLA metrics (P50/P95/P99 latencies, success rates, circuits)",
    usage="/sla [hours=24]",
    permission="developer",
    category="developer"
)
async def sla_command(args: str, user: dict, chat_id: int) -> str:
    """Show SLA metrics dashboard."""
    import asyncio
    import os
    import httpx
    from src.services.firebase.ux_metrics import get_ux_metrics_service
    from src.core.resilience import get_circuit_stats

    # Parse hours argument
    hours = 24
    if args:
        arg = args.strip()
        if arg.isdigit():
            hours = int(arg)
        elif arg.endswith("h"):
            hours = int(arg[:-1])
        elif arg.endswith("d"):
            hours = int(arg[:-1]) * 24

    hours = max(1, min(hours, 168))  # 1h to 7d

    # Get metrics
    try:
        metrics = await get_ux_metrics_service().get_sla_report(hours=hours)
    except Exception as e:
        return f"❌ Error fetching metrics: {str(e)[:50]}"

    # Get circuit states
    circuits = get_circuit_stats()
    open_circuits = [
        name for name, stats in circuits.items()
        if stats["state"] == "open"
    ]

    # Format circuit summary
    circuit_summary = "All healthy ✅" if not open_circuits else "⚠️ " + ", ".join(open_circuits)

    # Build response
    time_label = f"{hours}h" if hours < 24 else f"{hours//24}d"

    response = f"""<b>SLA Dashboard ({time_label})</b>

<b>LLM Performance</b> (api.ai4u.now)
• P50: <code>{metrics.get('llm_p50', 0):,}ms</code>
• P95: <code>{metrics.get('llm_p95', 0):,}ms</code>
• P99: <code>{metrics.get('llm_p99', 0):,}ms</code>
• Success: <code>{metrics.get('llm_success_rate', 0):.1f}%</code>

<b>Web Search</b>
• P50: <code>{metrics.get('search_p50', 0):,}ms</code>
• P95: <code>{metrics.get('search_p95', 0):,}ms</code>
• Success: <code>{metrics.get('search_success_rate', 0):.1f}%</code>

<b>Commands</b>
• Total: <code>{metrics.get('command_count', 0):,}</code>
• Success: <code>{metrics.get('command_success_rate', 0):.1f}%</code>

<b>Circuits</b>
• Status: {circuit_summary}
• Trips: <code>{metrics.get('circuit_trips', 0)}</code>
"""

    # Add SLA warnings
    warnings = []
    llm_p95 = metrics.get('llm_p95', 0)
    cmd_success = metrics.get('command_success_rate', 100)

    if llm_p95 > 5000:
        warnings.append("⚠️ LLM P95 > 5s SLA")
    if cmd_success < 95:
        warnings.append("⚠️ Command success < 95%")
    if open_circuits:
        warnings.append(f"⚠️ Open circuits: {len(open_circuits)}")

    if warnings:
        response += "\n<b>⚠️ Warnings</b>\n" + "\n".join(f"• {w}" for w in warnings)

        # Send alert to admin (fire-and-forget)
        try:
            admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if admin_id and bot_token:
                alert_msg = f"""<b>🚨 SLA Alert ({time_label})</b>

{chr(10).join(warnings)}

Metrics:
• LLM P95: {llm_p95:,}ms
• Commands: {cmd_success:.1f}%
• Open circuits: {len(open_circuits)}
"""
                asyncio.create_task(
                    _send_admin_alert(bot_token, admin_id, alert_msg)
                )
        except Exception:
            pass  # Non-blocking, ignore errors

    return response


async def _send_admin_alert(bot_token: str, admin_id: str, message: str) -> None:
    """Send alert to admin (helper function)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": admin_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
            )
    except Exception:
        pass  # Fire-and-forget, ignore errors
