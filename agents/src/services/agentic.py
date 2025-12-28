"""Agentic loop service for tool execution with conversation persistence."""
import time
from typing import List, Dict, Optional
from src.services.llm import get_llm_client
from src.tools import get_registry, init_default_tools, ToolResult
from src.core.state import get_state_manager
from src.core.trace import TraceContext, ToolTrace

from src.utils.logging import get_logger

logger = get_logger()

MAX_ITERATIONS = 5


async def run_agentic_loop(
    user_message: str,
    system: Optional[str] = None,
    user_id: Optional[int] = None,
    skill: Optional[str] = None,
) -> str:
    """Run agentic loop with tool execution, conversation persistence, and tracing.

    Args:
        user_message: User's input
        system: System prompt
        user_id: Telegram user ID for conversation persistence
        skill: Skill name for trace metadata

    Returns:
        Final text response
    """
    # Wrap entire execution in trace context
    async with TraceContext(user_id=user_id, skill=skill) as trace_ctx:
        try:
            result = await _execute_loop(
                user_message=user_message,
                system=system,
                user_id=user_id,
                trace_ctx=trace_ctx,
            )
            trace_ctx.set_output(result)
            return result

        except Exception as e:
            trace_ctx.set_status("error")
            trace_ctx.metadata["error"] = str(e)[:200]
            raise


async def _execute_loop(
    user_message: str,
    system: Optional[str],
    user_id: Optional[int],
    trace_ctx: TraceContext,
) -> str:
    """Internal loop execution with trace capture."""
    # Initialize tools
    init_default_tools()
    registry = get_registry()
    tools = registry.get_definitions()

    # Load conversation history from StateManager
    state = get_state_manager()
    messages = []

    if user_id:
        messages = await state.get_conversation(user_id)
        logger.info("conversation_loaded", user_id=user_id, count=len(messages))

    messages.append({"role": "user", "content": user_message})

    llm = get_llm_client()
    iterations = 0
    accumulated_text = []

    while iterations < MAX_ITERATIONS:
        iterations += 1
        trace_ctx.increment_iteration()
        logger.info("agentic_iteration", iteration=iterations)

        # Call LLM with tools
        response = llm.chat(
            messages=messages,
            system=system,
            max_tokens=4096,
            tools=tools if tools else None,
        )

        # Collect text content
        for block in response.content:
            if block.type == "text":
                accumulated_text.append(block.text)

        # Check if done
        if response.stop_reason == "end_turn":
            logger.info("agentic_complete", iterations=iterations)
            break

        # Process tool calls
        if response.stop_reason == "tool_use":
            # Append assistant response to history
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Execute tools and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", name=block.name, input=str(block.input)[:50])

                    # Execute with timing for trace
                    start_time = time.monotonic()
                    result: ToolResult = await registry.execute(block.name, block.input)
                    duration_ms = int((time.monotonic() - start_time) * 1000)

                    # Add to trace
                    tool_trace = ToolTrace.create(
                        name=block.name,
                        input_params=block.input if isinstance(block.input, dict) else {"input": str(block.input)},
                        output=result.to_str(),
                        duration_ms=duration_ms,
                        is_error=not result.success,
                    )
                    trace_ctx.add_tool_trace(tool_trace)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.to_str(),
                        "is_error": not result.success,
                    })

                    # Trigger improvement proposal on errors
                    if not result.success and skill:
                        await _trigger_improvement_proposal(
                            skill_name=skill,
                            error=result.to_str(),
                            context={
                                "tool": block.name,
                                "input": str(block.input)[:200],
                                "user_id": user_id,
                            }
                        )

            # Append tool results as user message
            messages.append({
                "role": "user",
                "content": tool_results
            })

    if iterations >= MAX_ITERATIONS:
        logger.warning("agentic_max_iterations", max=MAX_ITERATIONS)
        accumulated_text.append("\n\n[Note: Reached maximum iterations limit]")
        trace_ctx.set_status("timeout")

    # Save final response to conversation
    final_response = "\n".join(accumulated_text)
    messages.append({"role": "assistant", "content": final_response})

    if user_id:
        await state.save_conversation(user_id, messages)
        logger.info("conversation_saved", user_id=user_id, count=len(messages))

    return final_response


async def _trigger_improvement_proposal(
    skill_name: str,
    error: str,
    context: dict
) -> None:
    """Trigger improvement proposal on tool error.

    Non-blocking: Logs errors but doesn't crash the main loop.
    """
    try:
        from src.core.improvement import get_improvement_service

        service = get_improvement_service()

        # Analyze error and generate proposal
        proposal = await service.analyze_error(skill_name, error, context)
        if not proposal:
            return  # Rate limited or duplicate

        # Store proposal in Firebase
        await service.store_proposal(proposal)

        # Send notification to admin
        try:
            # Import here to avoid circular imports
            import os
            admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
            if admin_id:
                # Lazy import main module's notification function
                from main import send_improvement_notification
                await send_improvement_notification(proposal.to_dict())
        except ImportError:
            # Running outside Modal context, skip notification
            logger.debug("skipping_notification_outside_modal")

        logger.info(
            "improvement_proposal_created",
            proposal_id=proposal.id,
            skill=skill_name
        )

    except Exception as e:
        logger.error("improvement_proposal_failed", error=str(e)[:100])
